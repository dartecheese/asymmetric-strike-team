use std::path::{Path, PathBuf};
use std::sync::Arc;

use async_trait::async_trait;
use reqwest::Client;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;
use tokio::sync::Mutex;

use ast_core::{
    cache_json, cached_json, prepare_request, record_failure, record_success, CloseError,
    ExecutionOrder, ExecutionResult, LiveCloseExecutor, Position, PositionState,
    ProviderFailureKind, Signal, SignedUsd, Usd,
};

#[derive(Debug, Error)]
pub enum ReaperError {
    #[error("position store is unavailable: {0}")]
    StoreUnavailable(String),
    #[error("position persistence failed: {0}")]
    Persistence(String),
    #[error("market data failed: {0}")]
    MarketData(String),
}

#[async_trait]
pub trait PositionTracker: Send + Sync {
    async fn track_fill(
        &self,
        order: &ExecutionOrder,
        signal: &Signal,
        result: &ExecutionResult,
    ) -> Result<Position, ReaperError>;

    async fn monitor_positions(&self) -> Result<Vec<Position>, ReaperError>;

    async fn positions(&self) -> Result<Vec<Position>, ReaperError>;
}

pub struct FileReaper {
    state_path: PathBuf,
    ledger_path: PathBuf,
    positions: Arc<Mutex<Vec<Position>>>,
    client: Client,
    /// When set, stop-loss triggers attempt an on-chain sell via this
    /// executor before marking the position closed. None = paper mode.
    live_close: Option<Arc<dyn LiveCloseExecutor>>,
}

impl FileReaper {
    pub async fn new(state_dir: impl AsRef<Path>, strategy_name: &str) -> Result<Self, ReaperError> {
        let positions_dir = state_dir.as_ref().join("positions");
        tokio::fs::create_dir_all(&positions_dir)
            .await
            .map_err(|error| ReaperError::Persistence(error.to_string()))?;

        let ledger_dir = state_dir.as_ref().join("ledger");
        tokio::fs::create_dir_all(&ledger_dir)
            .await
            .map_err(|error| ReaperError::Persistence(error.to_string()))?;

        let state_path = positions_dir.join(format!("{strategy_name}.json"));
        let positions = if tokio::fs::try_exists(&state_path)
            .await
            .map_err(|error| ReaperError::Persistence(error.to_string()))?
        {
            let bytes = tokio::fs::read(&state_path)
                .await
                .map_err(|error| ReaperError::Persistence(error.to_string()))?;
            serde_json::from_slice::<Vec<Position>>(&bytes)
                .map_err(|error| ReaperError::Persistence(error.to_string()))?
        } else {
            Vec::new()
        };

        Ok(Self {
            state_path,
            ledger_path: ledger_dir.join(format!("{strategy_name}.jsonl")),
            positions: Arc::new(Mutex::new(positions)),
            client: Client::builder()
                .user_agent("asymmetric-strike-team/0.1")
                .build()
                .unwrap_or_else(|_| Client::new()),
            live_close: None,
        })
    }

    /// Attach a live close executor. When present, stop-loss triggers
    /// in `monitor_positions` will submit an on-chain sell before
    /// marking the position closed. Without this, closes are paper-only.
    pub fn with_live_close(mut self, executor: Arc<dyn LiveCloseExecutor>) -> Self {
        self.live_close = Some(executor);
        self
    }

    async fn persist(&self, positions: &[Position]) -> Result<(), ReaperError> {
        let state_path = self.state_path.clone();
        let data = serde_json::to_vec_pretty(positions)
            .map_err(|error| ReaperError::Persistence(error.to_string()))?;

        tokio::task::spawn_blocking(move || persist_atomically(&state_path, &data))
            .await
            .map_err(|error| ReaperError::Persistence(error.to_string()))?
    }

    async fn append_ledger(&self, record: &LedgerRecord) -> Result<(), ReaperError> {
        let path = self.ledger_path.clone();
        let line = serde_json::to_string(record)
            .map_err(|error| ReaperError::Persistence(error.to_string()))?;
        tokio::task::spawn_blocking(move || append_line_atomically(&path, &(line + "\n")))
            .await
            .map_err(|error| ReaperError::Persistence(error.to_string()))?
    }

    async fn fetch_live_mark(&self, position: &Position) -> Result<Option<MarketMark>, ReaperError> {
        let Some(pair_address) = position.metadata.get("pair_address") else {
            return Ok(None);
        };

        match self.fetch_dexscreener_mark(position, pair_address).await {
            Ok(Some(mark)) => Ok(Some(mark)),
            Ok(None) | Err(_) => self.fetch_geckoterminal_mark(position, pair_address).await,
        }
    }

    async fn fetch_dexscreener_mark(
        &self,
        position: &Position,
        pair_address: &str,
    ) -> Result<Option<MarketMark>, ReaperError> {
        let chain = position.token.chain.to_string();
        let url = format!("https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}");
        let payload = self
            .get_json_with_retries("dexscreener", &url, std::time::Duration::from_secs(10), std::time::Duration::from_secs(60))
            .await?;
        let payload = serde_json::from_value::<DexPairResponse>(payload)
            .map_err(|error| ReaperError::MarketData(error.to_string()))?;
        let pair = payload.pair.or_else(|| payload.pairs.into_iter().next());
        let Some(pair) = pair else {
            return Ok(None);
        };

        let Some(price_raw) = pair.price_usd else {
            return Ok(None);
        };
        let price = parse_non_negative_decimal(&price_raw)?;
        let liquidity = parse_optional_non_negative_decimal(pair.liquidity.and_then(|value| value.usd))?
            .unwrap_or(position.entry_notional_usd.0);
        let volume = parse_optional_non_negative_decimal(pair.volume.and_then(|value| value.h24))?
            .unwrap_or(position.entry_notional_usd.0);

        Ok(Some(MarketMark {
            price_usd: Usd::new(price).map_err(|error| ReaperError::MarketData(error.to_string()))?,
            liquidity_usd: Usd::new(liquidity)
                .map_err(|error| ReaperError::MarketData(error.to_string()))?,
            volume_24h_usd: Usd::new(volume)
                .map_err(|error| ReaperError::MarketData(error.to_string()))?,
            source: "dexscreener".to_owned(),
        }))
    }

    async fn fetch_geckoterminal_mark(
        &self,
        position: &Position,
        pair_address: &str,
    ) -> Result<Option<MarketMark>, ReaperError> {
        let network = match position.token.chain {
            ast_core::Chain::Ethereum => "eth",
            ast_core::Chain::Arbitrum => "arbitrum_one",
            ast_core::Chain::Base => "base",
            ast_core::Chain::Solana => return Ok(None),
        };
        let url = format!("https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pair_address}");
        let payload = self
            .get_json_with_retries("geckoterminal", &url, std::time::Duration::from_secs(10), std::time::Duration::from_secs(60))
            .await?;
        let Some(attributes) = payload
            .get("data")
            .and_then(|value| value.get("attributes"))
            .and_then(Value::as_object)
        else {
            return Ok(None);
        };

        let Some(price_raw) = attributes
            .get("base_token_price_usd")
            .and_then(|value| value.as_str().map(ToOwned::to_owned).or_else(|| value.as_f64().map(|v| v.to_string())))
        else {
            return Ok(None);
        };
        let price = parse_non_negative_decimal(&price_raw)?;
        let liquidity = parse_optional_non_negative_decimal(
            attributes.get("reserve_in_usd").and_then(value_to_string),
        )?
        .unwrap_or(position.entry_notional_usd.0);
        let volume = parse_optional_non_negative_decimal(
            attributes
                .get("volume_usd")
                .and_then(|value| value.get("h24"))
                .and_then(value_to_string),
        )?
        .unwrap_or(position.entry_notional_usd.0);

        Ok(Some(MarketMark {
            price_usd: Usd::new(price).map_err(|error| ReaperError::MarketData(error.to_string()))?,
            liquidity_usd: Usd::new(liquidity)
                .map_err(|error| ReaperError::MarketData(error.to_string()))?,
            volume_24h_usd: Usd::new(volume)
                .map_err(|error| ReaperError::MarketData(error.to_string()))?,
            source: "geckoterminal".to_owned(),
        }))
    }

    async fn get_json_with_retries(
        &self,
        provider: &'static str,
        url: &str,
        fresh_ttl: std::time::Duration,
        stale_ttl: std::time::Duration,
    ) -> Result<Value, ReaperError> {
        if let Some(cached) = cached_json(url, fresh_ttl) {
            return Ok(cached);
        }

        let stale_cache = cached_json(url, stale_ttl);
        let mut last_error = None;
        for delay_ms in [0u64, 250, 750] {
            match prepare_request(provider, std::time::Duration::from_millis(400)) {
                Ok(wait_for) => {
                    let total_wait = wait_for + std::time::Duration::from_millis(delay_ms);
                    if total_wait > std::time::Duration::ZERO {
                        tokio::time::sleep(total_wait).await;
                    }
                }
                Err(_) => {
                    if let Some(cached) = stale_cache.clone() {
                        return Ok(cached);
                    }
                    last_error = Some("provider cooldown".to_owned());
                    continue;
                }
            }
            match self.client.get(url).send().await {
                Ok(response) => {
                    let status = response.status();
                    if status.is_success() {
                        let payload = response
                            .json::<Value>()
                            .await
                            .map_err(|error| ReaperError::MarketData(error.to_string()))?;
                        cache_json(url, &payload);
                        record_success(provider);
                        return Ok(payload);
                    }
                    if status.as_u16() == 429 {
                        record_failure(provider, ProviderFailureKind::RateLimited);
                    } else {
                        record_failure(provider, ProviderFailureKind::Other);
                    }
                    last_error = Some(format!("status {status}"));
                }
                Err(error) => {
                    record_failure(provider, ProviderFailureKind::Other);
                    last_error = Some(error.to_string());
                }
            }
        }

        if let Some(cached) = stale_cache {
            return Ok(cached);
        }

        Err(ReaperError::MarketData(format!(
            "request failed after retries: {}",
            last_error.unwrap_or_else(|| "unknown error".to_owned())
        )))
    }
}

#[async_trait]
impl PositionTracker for FileReaper {
    async fn track_fill(
        &self,
        order: &ExecutionOrder,
        signal: &Signal,
        result: &ExecutionResult,
    ) -> Result<Position, ReaperError> {
        let stop_loss_price = Usd::new((result.fill_price_usd.0 * Decimal::new(92, 2)).round_dp(8))
            .map_err(|error| ReaperError::StoreUnavailable(error.to_string()))?;
        let take_profit_price =
            Usd::new((result.fill_price_usd.0 * Decimal::new(115, 2)).round_dp(8))
                .map_err(|error| ReaperError::StoreUnavailable(error.to_string()))?;

        let mut metadata = signal.metadata.clone();
        metadata.insert("entry_source".to_owned(), signal.metadata.get("source").cloned().unwrap_or_else(|| "unknown".to_owned()));
        metadata.insert("last_mark_source".to_owned(), "entry_fill".to_owned());

        let position = Position {
            id: format!("{}-position", order.id),
            strategy: order.strategy.clone(),
            signal_id: signal.id.clone(),
            token: signal.token.clone(),
            state: PositionState::Open,
            venue: order.venue.clone(),
            quantity: result.filled_amount.clone(),
            entry_price_usd: result.fill_price_usd.clone(),
            current_price_usd: result.fill_price_usd.clone(),
            entry_notional_usd: result.notional_usd.clone(),
            realized_pnl_usd: SignedUsd::zero(),
            unrealized_pnl_usd: SignedUsd::new(-(result.fee_usd.0)),
            fees_paid_usd: result.fee_usd.clone(),
            stop_loss_price_usd: stop_loss_price,
            take_profit_price_usd: take_profit_price,
            monitor_passes: 0,
            updated_at_ms: result.timestamp_ms,
            metadata,
        };

        let snapshot = {
            let mut positions = self.positions.lock().await;
            positions.push(position.clone());
            positions.clone()
        };
        self.persist(&snapshot).await?;
        self
            .append_ledger(&LedgerRecord::fill_tracked(order, signal, result, &position))
            .await?;
        Ok(position)
    }

    async fn monitor_positions(&self) -> Result<Vec<Position>, ReaperError> {
        let mut ledger_records = Vec::new();
        // Positions whose stop-loss tripped on this pass — we'll attempt
        // on-chain closes for them outside the lock to avoid holding the
        // mutex across awaits to the slinger.
        let mut close_candidates: Vec<usize> = Vec::new();
        let snapshot_phase1 = {
            let mut positions = self.positions.lock().await;
            for (idx, position) in positions.iter_mut().enumerate() {
                if !matches!(
                    position.state,
                    PositionState::Open | PositionState::FreeRide | PositionState::Closing
                ) {
                    continue;
                }

                position.monitor_passes += 1;
                if let Some(mark) = self.fetch_live_mark(position).await? {
                    position.current_price_usd = mark.price_usd.clone();
                    position.metadata.insert("last_mark_source".to_owned(), mark.source.clone());
                    position.metadata.insert(
                        "last_mark_liquidity_usd".to_owned(),
                        mark.liquidity_usd.0.round_dp(2).to_string(),
                    );
                    position.metadata.insert(
                        "last_mark_volume_24h_usd".to_owned(),
                        mark.volume_24h_usd.0.round_dp(2).to_string(),
                    );
                }
                position.unrealized_pnl_usd = net_pnl(position, false);
                position.updated_at_ms = timestamp_ms();

                let previous_state = position.state.clone();
                let is_open = matches!(position.state, PositionState::Open | PositionState::FreeRide);
                let stop_loss_hit =
                    is_open && position.current_price_usd.0 <= position.stop_loss_price_usd.0;
                let take_profit_hit = is_open
                    && matches!(position.state, PositionState::Open)
                    && position.current_price_usd.0 >= position.take_profit_price_usd.0;

                if stop_loss_hit {
                    if self.live_close.is_some() {
                        // Live: queue for on-chain close. Mark Closing so
                        // we don't double-sell on the next pass.
                        position.state = PositionState::Closing;
                        close_candidates.push(idx);
                    } else {
                        // Paper: file-only close.
                        position.state = PositionState::Closed;
                        position.realized_pnl_usd = net_pnl(position, true);
                        position.unrealized_pnl_usd = SignedUsd::zero();
                    }
                } else if matches!(position.state, PositionState::Closing) {
                    // Already in flight — nothing to do this pass; wait
                    // for the prior close attempt to finish or fail.
                } else if take_profit_hit {
                    position.state = PositionState::FreeRide;
                }

                ledger_records.push(LedgerRecord::position_marked(position));
                if previous_state != position.state {
                    ledger_records.push(LedgerRecord::state_changed(&previous_state, position));
                }
            }
            positions.clone()
        };

        // Phase 2: outside the mutex, submit on-chain closes for any
        // candidates we identified. On success, lock again to update the
        // position. On failure, the position stays in Closing state and
        // we'll retry on the next monitor pass.
        for idx in close_candidates {
            let position_for_close = snapshot_phase1
                .get(idx)
                .cloned()
                .ok_or_else(|| ReaperError::Persistence("position index out of bounds".into()))?;
            let executor = match &self.live_close {
                Some(exec) => exec.clone(),
                None => continue,
            };

            match executor.close_position(&position_for_close).await {
                Ok(receipt) => {
                    let mut positions = self.positions.lock().await;
                    if let Some(position) = positions.get_mut(idx) {
                        // Use the actual ETH received as realized USD,
                        // not the optimistic mark-based net_pnl.
                        let invested = position.entry_notional_usd.0;
                        let realized = receipt.eth_received_usd - receipt.fee_usd - invested;
                        position.state = PositionState::Closed;
                        position.realized_pnl_usd = SignedUsd::new(realized.round_dp(8));
                        position.unrealized_pnl_usd = SignedUsd::zero();
                        position.fees_paid_usd = Usd::new(
                            (position.fees_paid_usd.0 + receipt.fee_usd).round_dp(8),
                        )
                        .unwrap_or(Usd::zero());
                        position
                            .metadata
                            .insert("close_tx_hash".to_owned(), receipt.tx_hash.clone());
                        position.metadata.insert(
                            "close_block_number".to_owned(),
                            receipt.block_number.to_string(),
                        );
                        position.updated_at_ms = timestamp_ms();
                        ledger_records.push(LedgerRecord::state_changed(
                            &PositionState::Closing,
                            position,
                        ));
                    }
                }
                Err(error) => {
                    // Leave position in Closing state for retry next pass.
                    let mut positions = self.positions.lock().await;
                    if let Some(position) = positions.get_mut(idx) {
                        position.metadata.insert(
                            "last_close_error".to_owned(),
                            close_error_string(&error),
                        );
                        position.metadata.insert(
                            "last_close_error_ts_ms".to_owned(),
                            timestamp_ms().to_string(),
                        );
                    }
                }
            }
        }

        let snapshot = {
            let positions = self.positions.lock().await;
            positions.clone()
        };
        self.persist(&snapshot).await?;
        for record in &ledger_records {
            self.append_ledger(record).await?;
        }
        Ok(snapshot)
    }

    async fn positions(&self) -> Result<Vec<Position>, ReaperError> {
        let positions = self.positions.lock().await;
        Ok(positions.clone())
    }
}

fn close_error_string(error: &CloseError) -> String {
    match error {
        CloseError::Validation(msg) => format!("validation: {msg}"),
        CloseError::Execution(msg) => format!("execution: {msg}"),
        CloseError::Skipped(msg) => format!("skipped: {msg}"),
    }
}

fn net_pnl(position: &Position, realized: bool) -> SignedUsd {
    let gross = (position.current_price_usd.0 - position.entry_price_usd.0) * position.quantity.0;
    let net = gross - position.fees_paid_usd.0;
    if realized {
        SignedUsd::new(net.round_dp(8))
    } else {
        SignedUsd::new(net.round_dp(8))
    }
}

fn persist_atomically(path: &Path, data: &[u8]) -> Result<(), ReaperError> {
    use std::fs::{self, File};
    use std::io::Write;

    let tmp_path = path.with_extension("json.tmp");
    let mut file = File::create(&tmp_path)
        .map_err(|error| ReaperError::Persistence(error.to_string()))?;
    file.write_all(data)
        .map_err(|error| ReaperError::Persistence(error.to_string()))?;
    file.sync_all()
        .map_err(|error| ReaperError::Persistence(error.to_string()))?;
    fs::rename(&tmp_path, path).map_err(|error| ReaperError::Persistence(error.to_string()))?;
    if let Some(parent) = path.parent() {
        File::open(parent)
            .and_then(|directory| directory.sync_all())
            .map_err(|error| ReaperError::Persistence(error.to_string()))?;
    }
    Ok(())
}

fn append_line_atomically(path: &Path, line: &str) -> Result<(), ReaperError> {
    use std::fs::OpenOptions;
    use std::io::Write;

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| ReaperError::Persistence(error.to_string()))?;
    file.write_all(line.as_bytes())
        .map_err(|error| ReaperError::Persistence(error.to_string()))?;
    file.sync_all()
        .map_err(|error| ReaperError::Persistence(error.to_string()))?;
    Ok(())
}

fn parse_non_negative_decimal(value: &str) -> Result<Decimal, ReaperError> {
    value
        .parse::<Decimal>()
        .map_err(|error| ReaperError::MarketData(error.to_string()))
}

fn parse_optional_non_negative_decimal(value: Option<String>) -> Result<Option<Decimal>, ReaperError> {
    match value {
        Some(value) => parse_non_negative_decimal(&value).map(Some),
        None => Ok(None),
    }
}

fn value_to_string(value: &Value) -> Option<String> {
    match value {
        Value::String(value) => Some(value.clone()),
        Value::Number(value) => Some(value.to_string()),
        _ => None,
    }
}

fn timestamp_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or_default()
}

#[derive(Debug, Serialize)]
#[serde(tag = "record_type", rename_all = "snake_case")]
enum LedgerRecord {
    FillTracked {
        timestamp_ms: u64,
        order_id: String,
        signal_id: String,
        token_symbol: String,
        strategy: String,
        requested_notional_usd: Decimal,
        executed_notional_usd: Decimal,
        fee_usd: Decimal,
        fill_ratio_bps: u16,
        slippage_bps: u16,
        position: Position,
    },
    PositionMarked {
        timestamp_ms: u64,
        position: Position,
    },
    StateChanged {
        timestamp_ms: u64,
        prior_state: String,
        next_state: String,
        position: Position,
    },
}

impl LedgerRecord {
    fn fill_tracked(order: &ExecutionOrder, signal: &Signal, result: &ExecutionResult, position: &Position) -> Self {
        Self::FillTracked {
            timestamp_ms: result.timestamp_ms,
            order_id: order.id.clone(),
            signal_id: signal.id.clone(),
            token_symbol: signal.token.symbol.clone(),
            strategy: order.strategy.clone(),
            requested_notional_usd: result.requested_notional_usd.0,
            executed_notional_usd: result.notional_usd.0,
            fee_usd: result.fee_usd.0,
            fill_ratio_bps: result.fill_ratio_bps,
            slippage_bps: result.slippage_bps,
            position: position.clone(),
        }
    }

    fn position_marked(position: &Position) -> Self {
        Self::PositionMarked {
            timestamp_ms: position.updated_at_ms,
            position: position.clone(),
        }
    }

    fn state_changed(previous_state: &PositionState, position: &Position) -> Self {
        Self::StateChanged {
            timestamp_ms: position.updated_at_ms,
            prior_state: format!("{:?}", previous_state).to_lowercase(),
            next_state: format!("{:?}", position.state).to_lowercase(),
            position: position.clone(),
        }
    }
}

#[derive(Debug)]
struct MarketMark {
    price_usd: Usd,
    liquidity_usd: Usd,
    volume_24h_usd: Usd,
    source: String,
}

#[derive(Debug, Deserialize)]
struct DexPairResponse {
    #[serde(default)]
    pair: Option<DexPair>,
    #[serde(default)]
    pairs: Vec<DexPair>,
}

#[derive(Debug, Deserialize)]
struct DexPair {
    #[serde(rename = "priceUsd")]
    price_usd: Option<String>,
    #[serde(default)]
    liquidity: Option<DexLiquidity>,
    #[serde(default)]
    volume: Option<DexVolume>,
}

#[derive(Debug, Deserialize)]
struct DexLiquidity {
    #[serde(default)]
    usd: Option<String>,
}

#[derive(Debug, Deserialize)]
struct DexVolume {
    #[serde(rename = "h24", default)]
    h24: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::{timestamp_ms, FileReaper, PositionTracker};
    use ast_core::{
        Chain, ExecutionOrder, ExecutionResult, ExecutionStatus, RiskLevel, Signal,
        StrategyProfile, Token, TokenAmount, Usd, Venue,
    };
    use rust_decimal::Decimal;
    use std::collections::BTreeMap;

    #[tokio::test]
    async fn track_fill_persists_position() {
        let temp_dir = std::env::temp_dir().join(format!("ast-reaper-test-{}", timestamp_ms()));
        let reaper = FileReaper::new(&temp_dir, "swift")
            .await
            .expect("reaper should initialize");
        let strategy = StrategyProfile {
            name: "swift".to_owned(),
            description: "Fast entry on new pairs".to_owned(),
            max_position_size_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            max_slippage_bps: 200,
            risk_tolerance: RiskLevel::Medium,
            scan_interval_seconds: 15,
            paper_trading: true,
        };
        let mut metadata = BTreeMap::new();
        metadata.insert("source".to_owned(), "paper_mock".to_owned());
        let signal = Signal {
            id: "signal-1".to_owned(),
            token: Token {
                address: alloy_primitives::Address::ZERO,
                chain: Chain::Base,
                symbol: "SWFT".to_owned(),
                decimals: 18,
            },
            venue: Venue::Dex {
                chain: Chain::Base,
                router: alloy_primitives::Address::ZERO,
            },
            price_usd: Usd::new(Decimal::ONE).expect("valid usd"),
            volume_24h_usd: Usd::new(Decimal::new(100_000, 0)).expect("valid usd"),
            liquidity_usd: Usd::new(Decimal::new(500_000, 0)).expect("valid usd"),
            target_notional_usd: strategy.max_position_size_usd.clone(),
            timestamp_ms: 1,
            metadata,
        };
        let order = ExecutionOrder::builder()
            .id("order-1")
            .strategy(strategy.name)
            .signal_id(signal.id.clone())
            .token(signal.token.clone())
            .venue(signal.venue.clone())
            .amount(TokenAmount::new(Decimal::new(10, 0)).expect("valid amount"))
            .notional_usd(Usd::new(Decimal::new(200, 0)).expect("valid usd"))
            .limit_price_usd(Usd::new(Decimal::ONE).expect("valid usd"))
            .observed_liquidity_usd(Usd::new(Decimal::new(500_000, 0)).expect("valid usd"))
            .observed_volume_24h_usd(Usd::new(Decimal::new(100_000, 0)).expect("valid usd"))
            .max_slippage_bps(100)
            .metadata(BTreeMap::new())
            .build()
            .expect("order should build");
        let result = ExecutionResult {
            order_id: order.id.clone(),
            status: ExecutionStatus::Filled,
            fill_price_usd: Usd::new(Decimal::ONE).expect("valid usd"),
            filled_amount: TokenAmount::new(Decimal::new(10, 0)).expect("valid amount"),
            slippage_bps: 10,
            fill_ratio_bps: 10_000,
            notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            requested_notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            fee_usd: Usd::new(Decimal::new(6, 1)).expect("valid usd"),
            venue: order.venue.clone(),
            timestamp_ms: 1,
        };

        let position = reaper
            .track_fill(&order, &signal, &result)
            .await
            .expect("fill should be tracked");
        let positions = reaper.positions().await.expect("positions should load");

        assert_eq!(position.signal_id, "signal-1");
        assert_eq!(positions.len(), 1);
        assert!(temp_dir.join("ledger").join("swift.jsonl").exists());
    }
}
