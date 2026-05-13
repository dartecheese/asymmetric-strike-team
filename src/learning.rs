use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use anyhow::Result;
use ast_core::{
    ExecutionOrder, ExecutionResult, Position, PositionState, RiskAssessment, Signal,
};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use tokio::io::AsyncWriteExt;

use crate::llm::{SignalIntent, TradeReflection};

#[derive(Debug, Clone)]
pub struct EpisodeJournal {
    base_dir: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "record_type", rename_all = "snake_case")]
enum EpisodeRecord {
    Signal {
        strategy: String,
        signal_id: String,
        token_symbol: String,
        timestamp_ms: u64,
        chain: String,
        source: String,
        price_usd: Decimal,
        volume_24h_usd: Decimal,
        liquidity_usd: Decimal,
        target_notional_usd: Decimal,
        metadata: BTreeMap<String, String>,
    },
    Intent {
        strategy: String,
        signal_id: String,
        token_symbol: String,
        timestamp_ms: u64,
        intent: SignalIntent,
    },
    Risk {
        strategy: String,
        signal_id: String,
        token_symbol: String,
        timestamp_ms: u64,
        level: String,
        decision: String,
        approved_notional_usd: Decimal,
        rationale: String,
        factors: Vec<ast_core::RiskFactor>,
    },
    Safety {
        strategy: String,
        signal_id: String,
        token_symbol: String,
        timestamp_ms: u64,
        should_trade: bool,
        reason: String,
    },
    Order {
        strategy: String,
        signal_id: String,
        order_id: String,
        token_symbol: String,
        timestamp_ms: u64,
        requested_notional_usd: Decimal,
        limit_price_usd: Decimal,
        observed_liquidity_usd: Decimal,
        observed_volume_24h_usd: Decimal,
        max_slippage_bps: u16,
        venue: String,
    },
    Fill {
        strategy: String,
        signal_id: String,
        order_id: String,
        token_symbol: String,
        timestamp_ms: u64,
        status: String,
        fill_price_usd: Decimal,
        filled_amount: Decimal,
        slippage_bps: u16,
        fill_ratio_bps: u16,
        requested_notional_usd: Decimal,
        executed_notional_usd: Decimal,
        fee_usd: Decimal,
        venue: String,
    },
    Position {
        strategy: String,
        signal_id: String,
        token_symbol: String,
        position_id: String,
        timestamp_ms: u64,
        state: String,
        entry_price_usd: Decimal,
        current_price_usd: Decimal,
        quantity: Decimal,
        entry_notional_usd: Decimal,
        realized_pnl_usd: Decimal,
        unrealized_pnl_usd: Decimal,
        fees_paid_usd: Decimal,
        monitor_passes: u64,
        metadata: BTreeMap<String, String>,
    },
    Reflection {
        strategy: String,
        signal_id: String,
        token_symbol: String,
        timestamp_ms: u64,
        state: String,
        reflection: TradeReflection,
    },
    StrategyPortfolio {
        strategy: String,
        timestamp_ms: u64,
        open_positions: usize,
        closed_positions: usize,
        invested_usd: Decimal,
        market_value_usd: Decimal,
        realized_pnl_usd: Decimal,
        unrealized_pnl_usd: Decimal,
        fees_paid_usd: Decimal,
        win_rate: Decimal,
    },
    GlobalPortfolio {
        timestamp_ms: u64,
        open_positions: usize,
        closed_positions: usize,
        invested_usd: Decimal,
        market_value_usd: Decimal,
        realized_pnl_usd: Decimal,
        unrealized_pnl_usd: Decimal,
        fees_paid_usd: Decimal,
        equity_usd: Decimal,
        cash_balance_usd: Decimal,
        win_rate: Decimal,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrategyPortfolioSnapshot {
    pub strategy: String,
    pub timestamp_ms: u64,
    pub open_positions: usize,
    pub closed_positions: usize,
    pub invested_usd: Decimal,
    pub market_value_usd: Decimal,
    pub realized_pnl_usd: Decimal,
    pub unrealized_pnl_usd: Decimal,
    pub fees_paid_usd: Decimal,
    pub win_rate: Decimal,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GlobalPortfolioSnapshot {
    pub timestamp_ms: u64,
    pub open_positions: usize,
    pub closed_positions: usize,
    pub invested_usd: Decimal,
    pub market_value_usd: Decimal,
    pub realized_pnl_usd: Decimal,
    pub unrealized_pnl_usd: Decimal,
    pub fees_paid_usd: Decimal,
    pub equity_usd: Decimal,
    pub cash_balance_usd: Decimal,
    pub win_rate: Decimal,
}

impl EpisodeJournal {
    pub fn new(state_dir: impl AsRef<Path>) -> Self {
        Self {
            base_dir: state_dir.as_ref().join("learning"),
        }
    }

    pub async fn record_signal(&self, strategy: &str, signal: &Signal) -> Result<()> {
        self.append(
            strategy,
            &EpisodeRecord::Signal {
                strategy: strategy.to_owned(),
                signal_id: signal.id.clone(),
                token_symbol: signal.token.symbol.clone(),
                timestamp_ms: signal.timestamp_ms,
                chain: signal.token.chain.to_string(),
                source: signal
                    .metadata
                    .get("source")
                    .cloned()
                    .unwrap_or_else(|| "unknown".to_owned()),
                price_usd: signal.price_usd.0,
                volume_24h_usd: signal.volume_24h_usd.0,
                liquidity_usd: signal.liquidity_usd.0,
                target_notional_usd: signal.target_notional_usd.0,
                metadata: signal.metadata.clone(),
            },
        )
        .await
    }

    pub async fn record_intent(&self, strategy: &str, signal: &Signal, intent: &SignalIntent) -> Result<()> {
        self.append(
            strategy,
            &EpisodeRecord::Intent {
                strategy: strategy.to_owned(),
                signal_id: signal.id.clone(),
                token_symbol: signal.token.symbol.clone(),
                timestamp_ms: signal.timestamp_ms,
                intent: intent.clone(),
            },
        )
        .await
    }

    pub async fn record_risk(&self, strategy: &str, signal: &Signal, assessment: &RiskAssessment) -> Result<()> {
        self.append(
            strategy,
            &EpisodeRecord::Risk {
                strategy: strategy.to_owned(),
                signal_id: signal.id.clone(),
                token_symbol: signal.token.symbol.clone(),
                timestamp_ms: signal.timestamp_ms,
                level: format!("{:?}", assessment.level).to_lowercase(),
                decision: format!("{:?}", assessment.decision).to_lowercase(),
                approved_notional_usd: assessment.approved_notional_usd.0,
                rationale: assessment.rationale.clone(),
                factors: assessment.factors.clone(),
            },
        )
        .await
    }

    pub async fn record_safety(
        &self,
        strategy: &str,
        signal: &Signal,
        should_trade: bool,
        reason: &str,
    ) -> Result<()> {
        self.append(
            strategy,
            &EpisodeRecord::Safety {
                strategy: strategy.to_owned(),
                signal_id: signal.id.clone(),
                token_symbol: signal.token.symbol.clone(),
                timestamp_ms: signal.timestamp_ms,
                should_trade,
                reason: reason.to_owned(),
            },
        )
        .await
    }

    pub async fn record_order(&self, strategy: &str, signal: &Signal, order: &ExecutionOrder) -> Result<()> {
        self.append(
            strategy,
            &EpisodeRecord::Order {
                strategy: strategy.to_owned(),
                signal_id: signal.id.clone(),
                order_id: order.id.clone(),
                token_symbol: signal.token.symbol.clone(),
                timestamp_ms: signal.timestamp_ms,
                requested_notional_usd: order.notional_usd.0,
                limit_price_usd: order.limit_price_usd.0,
                observed_liquidity_usd: order.observed_liquidity_usd.0,
                observed_volume_24h_usd: order.observed_volume_24h_usd.0,
                max_slippage_bps: order.max_slippage_bps,
                venue: format!("{:?}", order.venue),
            },
        )
        .await
    }

    pub async fn record_fill(
        &self,
        strategy: &str,
        signal: &Signal,
        order: &ExecutionOrder,
        result: &ExecutionResult,
    ) -> Result<()> {
        self.append(
            strategy,
            &EpisodeRecord::Fill {
                strategy: strategy.to_owned(),
                signal_id: signal.id.clone(),
                order_id: order.id.clone(),
                token_symbol: signal.token.symbol.clone(),
                timestamp_ms: result.timestamp_ms,
                status: format!("{:?}", result.status).to_lowercase(),
                fill_price_usd: result.fill_price_usd.0,
                filled_amount: result.filled_amount.0,
                slippage_bps: result.slippage_bps,
                fill_ratio_bps: result.fill_ratio_bps,
                requested_notional_usd: result.requested_notional_usd.0,
                executed_notional_usd: result.notional_usd.0,
                fee_usd: result.fee_usd.0,
                venue: format!("{:?}", result.venue),
            },
        )
        .await
    }

    pub async fn record_position(&self, strategy: &str, signal: &Signal, position: &Position) -> Result<()> {
        self.append(
            strategy,
            &EpisodeRecord::Position {
                strategy: strategy.to_owned(),
                signal_id: signal.id.clone(),
                token_symbol: signal.token.symbol.clone(),
                position_id: position.id.clone(),
                timestamp_ms: position.updated_at_ms,
                state: format!("{:?}", position.state).to_lowercase(),
                entry_price_usd: position.entry_price_usd.0,
                current_price_usd: position.current_price_usd.0,
                quantity: position.quantity.0,
                entry_notional_usd: position.entry_notional_usd.0,
                realized_pnl_usd: position.realized_pnl_usd.0,
                unrealized_pnl_usd: position.unrealized_pnl_usd.0,
                fees_paid_usd: position.fees_paid_usd.0,
                monitor_passes: position.monitor_passes,
                metadata: position.metadata.clone(),
            },
        )
        .await
    }

    pub async fn record_reflection(
        &self,
        strategy: &str,
        signal: &Signal,
        position: &Position,
        reflection: &TradeReflection,
    ) -> Result<()> {
        self.append(
            strategy,
            &EpisodeRecord::Reflection {
                strategy: strategy.to_owned(),
                signal_id: signal.id.clone(),
                token_symbol: signal.token.symbol.clone(),
                timestamp_ms: position.updated_at_ms,
                state: format!("{:?}", position.state).to_lowercase(),
                reflection: reflection.clone(),
            },
        )
        .await
    }

    pub async fn record_strategy_portfolio(&self, strategy: &str, positions: &[Position]) -> Result<()> {
        let snapshot = compute_strategy_snapshot(strategy, positions);
        self.append(
            strategy,
            &EpisodeRecord::StrategyPortfolio {
                strategy: snapshot.strategy,
                timestamp_ms: snapshot.timestamp_ms,
                open_positions: snapshot.open_positions,
                closed_positions: snapshot.closed_positions,
                invested_usd: snapshot.invested_usd,
                market_value_usd: snapshot.market_value_usd,
                realized_pnl_usd: snapshot.realized_pnl_usd,
                unrealized_pnl_usd: snapshot.unrealized_pnl_usd,
                fees_paid_usd: snapshot.fees_paid_usd,
                win_rate: snapshot.win_rate,
            },
        )
        .await
    }

    pub async fn record_global_portfolio(&self, initial_balance_usd: Decimal) -> Result<()> {
        let snapshot = self.compute_global_snapshot(initial_balance_usd).await?;
        self.append_global(&EpisodeRecord::GlobalPortfolio {
            timestamp_ms: snapshot.timestamp_ms,
            open_positions: snapshot.open_positions,
            closed_positions: snapshot.closed_positions,
            invested_usd: snapshot.invested_usd,
            market_value_usd: snapshot.market_value_usd,
            realized_pnl_usd: snapshot.realized_pnl_usd,
            unrealized_pnl_usd: snapshot.unrealized_pnl_usd,
            fees_paid_usd: snapshot.fees_paid_usd,
            equity_usd: snapshot.equity_usd,
            cash_balance_usd: snapshot.cash_balance_usd,
            win_rate: snapshot.win_rate,
        })
        .await
    }

    pub async fn latest_intent(&self, strategy: &str, signal_id: &str) -> Result<Option<SignalIntent>> {
        let path = self.path_for(strategy);
        if !tokio::fs::try_exists(&path).await? {
            return Ok(None);
        }

        let content = tokio::fs::read_to_string(path).await?;
        for line in content.lines().rev() {
            let Ok(record) = serde_json::from_str::<EpisodeRecord>(line) else {
                continue;
            };
            if let EpisodeRecord::Intent {
                signal_id: record_signal_id,
                intent,
                ..
            } = record
            {
                if record_signal_id == signal_id {
                    return Ok(Some(intent));
                }
            }
        }

        Ok(None)
    }

    async fn compute_global_snapshot(&self, initial_balance_usd: Decimal) -> Result<GlobalPortfolioSnapshot> {
        let positions_dir = self.base_dir.parent().unwrap_or(&self.base_dir).join("positions");
        let mut positions = Vec::new();

        if tokio::fs::try_exists(&positions_dir).await? {
            let mut entries = tokio::fs::read_dir(&positions_dir).await?;
            while let Some(entry) = entries.next_entry().await? {
                let path = entry.path();
                if path.extension().and_then(|ext| ext.to_str()) != Some("json") {
                    continue;
                }
                let bytes = tokio::fs::read(path).await?;
                let mut strategy_positions = serde_json::from_slice::<Vec<Position>>(&bytes)?;
                positions.append(&mut strategy_positions);
            }
        }

        Ok(compute_global_snapshot(&positions, initial_balance_usd))
    }

    async fn append(&self, strategy: &str, record: &EpisodeRecord) -> Result<()> {
        tokio::fs::create_dir_all(&self.base_dir).await?;
        let path = self.path_for(strategy);
        append_jsonl(path, record).await
    }

    async fn append_global(&self, record: &EpisodeRecord) -> Result<()> {
        tokio::fs::create_dir_all(&self.base_dir).await?;
        append_jsonl(self.base_dir.join("portfolio.jsonl"), record).await
    }

    fn path_for(&self, strategy: &str) -> PathBuf {
        self.base_dir.join(format!("{strategy}.jsonl"))
    }
}

async fn append_jsonl(path: PathBuf, record: &EpisodeRecord) -> Result<()> {
    let mut file = tokio::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .await?;
    let line = serde_json::to_string(record)?;
    file.write_all(line.as_bytes()).await?;
    file.write_all(b"\n").await?;
    file.flush().await?;
    Ok(())
}

fn compute_strategy_snapshot(strategy: &str, positions: &[Position]) -> StrategyPortfolioSnapshot {
    let timestamp_ms = positions.iter().map(|position| position.updated_at_ms).max().unwrap_or(0);
    let open_positions = positions.iter().filter(|p| is_active_position(&p.state)).count();
    let closed_positions = positions.iter().filter(|p| matches!(p.state, PositionState::Closed)).count();
    // Financial fields use is_filled_position — Pending intent has not consumed
    // cash and has no market value until the slinger reports a fill. Counting
    // Pending here was producing snapshots like equity_usd = -$9.5k on a $10k
    // account when many Pending orders accumulated but never executed.
    let invested_usd = positions
        .iter()
        .filter(|p| is_filled_position(&p.state))
        .fold(Decimal::ZERO, |acc, position| acc + position.entry_notional_usd.0);
    let market_value_usd = positions
        .iter()
        .filter(|p| is_filled_position(&p.state))
        .fold(Decimal::ZERO, |acc, position| acc + (position.current_price_usd.0 * position.quantity.0));
    let realized_pnl_usd = positions.iter().fold(Decimal::ZERO, |acc, position| acc + position.realized_pnl_usd.0);
    let unrealized_pnl_usd = positions
        .iter()
        .filter(|p| is_filled_position(&p.state))
        .fold(Decimal::ZERO, |acc, position| acc + position.unrealized_pnl_usd.0);
    let fees_paid_usd = positions.iter().fold(Decimal::ZERO, |acc, position| acc + position.fees_paid_usd.0);
    let win_rate = compute_win_rate(positions);

    StrategyPortfolioSnapshot {
        strategy: strategy.to_owned(),
        timestamp_ms,
        open_positions,
        closed_positions,
        invested_usd,
        market_value_usd,
        realized_pnl_usd,
        unrealized_pnl_usd,
        fees_paid_usd,
        win_rate,
    }
}

fn compute_global_snapshot(positions: &[Position], initial_balance_usd: Decimal) -> GlobalPortfolioSnapshot {
    let timestamp_ms = positions.iter().map(|position| position.updated_at_ms).max().unwrap_or(0);
    let open_positions = positions.iter().filter(|p| is_active_position(&p.state)).count();
    let closed_positions = positions.iter().filter(|p| matches!(p.state, PositionState::Closed)).count();
    // See compute_strategy_snapshot for the Pending-vs-filled rationale.
    let invested_usd = positions
        .iter()
        .filter(|p| is_filled_position(&p.state))
        .fold(Decimal::ZERO, |acc, position| acc + position.entry_notional_usd.0);
    let market_value_usd = positions
        .iter()
        .filter(|p| is_filled_position(&p.state))
        .fold(Decimal::ZERO, |acc, position| acc + (position.current_price_usd.0 * position.quantity.0));
    let realized_pnl_usd = positions.iter().fold(Decimal::ZERO, |acc, position| acc + position.realized_pnl_usd.0);
    let unrealized_pnl_usd = positions
        .iter()
        .filter(|p| is_filled_position(&p.state))
        .fold(Decimal::ZERO, |acc, position| acc + position.unrealized_pnl_usd.0);
    let fees_paid_usd = positions.iter().fold(Decimal::ZERO, |acc, position| acc + position.fees_paid_usd.0);
    let cash_balance_usd = initial_balance_usd + realized_pnl_usd - invested_usd;
    let equity_usd = cash_balance_usd + market_value_usd;
    let win_rate = compute_win_rate(positions);

    GlobalPortfolioSnapshot {
        timestamp_ms,
        open_positions,
        closed_positions,
        invested_usd,
        market_value_usd,
        realized_pnl_usd,
        unrealized_pnl_usd,
        fees_paid_usd,
        equity_usd,
        cash_balance_usd,
        win_rate,
    }
}

fn is_active_position(state: &PositionState) -> bool {
    matches!(
        state,
        PositionState::Pending | PositionState::Open | PositionState::FreeRide | PositionState::Closing
    )
}

/// Filled positions — slinger has reported a fill, so cash has truly moved.
/// Pending is excluded because pending = intent, not committed capital.
/// Use this for any field that represents money (invested, market value, PnL).
fn is_filled_position(state: &PositionState) -> bool {
    matches!(
        state,
        PositionState::Open | PositionState::FreeRide | PositionState::Closing
    )
}

fn compute_win_rate(positions: &[Position]) -> Decimal {
    let closed: Vec<_> = positions
        .iter()
        .filter(|position| matches!(position.state, PositionState::Closed))
        .collect();
    if closed.is_empty() {
        return Decimal::ZERO;
    }
    let winners = closed
        .iter()
        .filter(|position| position.realized_pnl_usd.0 > Decimal::ZERO)
        .count();
    Decimal::from(winners as u64) / Decimal::from(closed.len() as u64)
}

#[cfg(test)]
mod tests {
    use super::*;
    use alloy_primitives::Address;
    use ast_core::{Chain, SignedUsd, Token, TokenAmount, Usd, Venue};
    use rust_decimal::Decimal;
    use std::collections::BTreeMap;
    use std::str::FromStr;

    fn mk_position(state: PositionState, entry_notional: &str, qty: &str, price: &str) -> Position {
        Position {
            id: "test".to_owned(),
            strategy: "test".to_owned(),
            signal_id: "test-sig".to_owned(),
            token: Token {
                address: Address::ZERO,
                chain: Chain::Base,
                symbol: "TEST".to_owned(),
                decimals: 18,
            },
            state,
            venue: Venue::Dex {
                chain: Chain::Base,
                router: Address::ZERO,
            },
            quantity: TokenAmount::new(Decimal::from_str(qty).unwrap()).unwrap(),
            entry_price_usd: Usd::new(Decimal::from_str(price).unwrap()).unwrap(),
            current_price_usd: Usd::new(Decimal::from_str(price).unwrap()).unwrap(),
            entry_notional_usd: Usd::new(Decimal::from_str(entry_notional).unwrap()).unwrap(),
            realized_pnl_usd: SignedUsd::zero(),
            unrealized_pnl_usd: SignedUsd::zero(),
            fees_paid_usd: Usd::zero(),
            stop_loss_price_usd: Usd::zero(),
            take_profit_price_usd: Usd::zero(),
            monitor_passes: 0,
            updated_at_ms: 0,
            metadata: BTreeMap::new(),
        }
    }

    #[test]
    fn pending_positions_do_not_consume_cash() {
        // Regression: portfolio.jsonl historically reported equity_usd = -$9,503 on a
        // $10k account because 10,419 Pending positions ($2.4M of intent) were counted
        // as invested cash. Pending = intent, not capital — should not move cash.
        let initial = Decimal::from(10_000);
        let pending_intent = mk_position(PositionState::Pending, "500", "1", "1");

        let snap = compute_global_snapshot(&[pending_intent], initial);

        assert_eq!(snap.invested_usd, Decimal::ZERO, "Pending must not consume cash");
        assert_eq!(snap.market_value_usd, Decimal::ZERO, "Pending must have no market value");
        assert_eq!(snap.cash_balance_usd, initial, "cash must equal initial");
        assert_eq!(snap.equity_usd, initial, "equity must equal initial");
    }

    #[test]
    fn open_positions_do_consume_cash() {
        let initial = Decimal::from(10_000);
        // Filled $500 of TOKEN at $1 each → cash drops by $500, market value = $500.
        let filled = mk_position(PositionState::Open, "500", "500", "1");

        let snap = compute_global_snapshot(&[filled], initial);

        assert_eq!(snap.invested_usd, Decimal::from(500));
        assert_eq!(snap.market_value_usd, Decimal::from(500));
        assert_eq!(snap.cash_balance_usd, Decimal::from(9_500));
        assert_eq!(snap.equity_usd, Decimal::from(10_000));
    }

    #[test]
    fn mixed_pending_and_open_only_filled_count() {
        // The scenario that broke: many Pendings + a few Opens. Equity should reflect
        // only the Opens regardless of how absurd the Pending intent total is.
        let initial = Decimal::from(10_000);
        let mut positions = Vec::new();
        for _ in 0..1_000 {
            positions.push(mk_position(PositionState::Pending, "500", "1", "1"));
        }
        positions.push(mk_position(PositionState::Open, "250", "250", "1"));

        let snap = compute_global_snapshot(&positions, initial);

        assert_eq!(snap.invested_usd, Decimal::from(250));
        assert_eq!(snap.market_value_usd, Decimal::from(250));
        assert!(snap.equity_usd >= Decimal::ZERO,
                "equity must never go negative just from accumulating Pendings");
        assert_eq!(snap.equity_usd, Decimal::from(10_000));
    }
}
