use std::path::{Path, PathBuf};
use std::sync::Arc;

use async_trait::async_trait;
use rust_decimal::Decimal;
use thiserror::Error;
use tokio::sync::Mutex;

use ast_core::{ExecutionOrder, ExecutionResult, Position, PositionState, Signal, Usd};

#[derive(Debug, Error)]
pub enum ReaperError {
    #[error("position store is unavailable: {0}")]
    StoreUnavailable(String),
    #[error("position persistence failed: {0}")]
    Persistence(String),
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

#[derive(Debug)]
pub struct FileReaper {
    state_path: PathBuf,
    positions: Arc<Mutex<Vec<Position>>>,
}

impl FileReaper {
    pub async fn new(state_dir: impl AsRef<Path>, strategy_name: &str) -> Result<Self, ReaperError> {
        let positions_dir = state_dir.as_ref().join("positions");
        tokio::fs::create_dir_all(&positions_dir)
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
            positions: Arc::new(Mutex::new(positions)),
        })
    }

    async fn persist(&self, positions: &[Position]) -> Result<(), ReaperError> {
        let state_path = self.state_path.clone();
        let data = serde_json::to_vec_pretty(positions)
            .map_err(|error| ReaperError::Persistence(error.to_string()))?;

        tokio::task::spawn_blocking(move || persist_atomically(&state_path, &data))
            .await
            .map_err(|error| ReaperError::Persistence(error.to_string()))?
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
            realized_pnl_usd: Usd::zero(),
            stop_loss_price_usd: stop_loss_price,
            take_profit_price_usd: take_profit_price,
            monitor_passes: 0,
            updated_at_ms: result.timestamp_ms,
        };

        let snapshot = {
            let mut positions = self.positions.lock().await;
            positions.push(position.clone());
            positions.clone()
        };
        self.persist(&snapshot).await?;
        Ok(position)
    }

    async fn monitor_positions(&self) -> Result<Vec<Position>, ReaperError> {
        let snapshot = {
            let mut positions = self.positions.lock().await;
            for position in positions.iter_mut() {
                if !matches!(position.state, PositionState::Open | PositionState::FreeRide) {
                    continue;
                }

                position.monitor_passes += 1;
                let drift_bps = if position.monitor_passes % 3 == 0 { 1_600 } else { 400 };
                let multiplier = Decimal::ONE + (Decimal::from(drift_bps) / Decimal::new(10_000, 0));
                position.current_price_usd = Usd::new((position.entry_price_usd.0 * multiplier).round_dp(8))
                    .map_err(|error| ReaperError::StoreUnavailable(error.to_string()))?;
                position.updated_at_ms = timestamp_ms();

                if position.current_price_usd.0 <= position.stop_loss_price_usd.0 {
                    position.state = PositionState::StopLossHit;
                    position.realized_pnl_usd = pnl(position);
                    position.state = PositionState::Closed;
                } else if position.current_price_usd.0 >= position.take_profit_price_usd.0 {
                    position.state = PositionState::FreeRide;
                    position.realized_pnl_usd = pnl(position);
                }
            }
            positions.clone()
        };

        self.persist(&snapshot).await?;
        Ok(snapshot)
    }

    async fn positions(&self) -> Result<Vec<Position>, ReaperError> {
        let positions = self.positions.lock().await;
        Ok(positions.clone())
    }
}

fn pnl(position: &Position) -> Usd {
    let gross = (position.current_price_usd.0 - position.entry_price_usd.0) * position.quantity.0;
    Usd::new(gross.max(Decimal::ZERO)).unwrap_or_else(|_| Usd::zero())
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

fn timestamp_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or_default()
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
            metadata: BTreeMap::new(),
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
            .max_slippage_bps(100)
            .build()
            .expect("order should build");
        let result = ExecutionResult {
            order_id: order.id.clone(),
            status: ExecutionStatus::Filled,
            fill_price_usd: Usd::new(Decimal::ONE).expect("valid usd"),
            filled_amount: TokenAmount::new(Decimal::new(10, 0)).expect("valid amount"),
            slippage_bps: 10,
            notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
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
    }
}
