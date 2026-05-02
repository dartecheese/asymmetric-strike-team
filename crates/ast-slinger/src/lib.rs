pub mod dex;
pub mod gas;
pub mod slippage;
pub mod tx_manager;

use async_trait::async_trait;
use rust_decimal::Decimal;
use thiserror::Error;

use ast_core::{
    ExecutionOrder, ExecutionResult, ExecutionStatus, RiskAssessment, Signal, StrategyProfile,
    TokenAmount, Usd, Venue,
};

#[derive(Debug, Error)]
pub enum SlingerError {
    #[error("order validation failed: {0}")]
    OrderValidation(String),
    #[error("execution failed: {0}")]
    Execution(String),
    #[error("external service {service} failed: {message}")]
    ExternalService {
        service: &'static str,
        message: String,
    },
    #[error("slippage exceeded: observed {observed_bps} bps > max {max_bps} bps")]
    SlippageExceeded { observed_bps: u32, max_bps: u32 },
}

pub use dex::{DexSwapExecutor, DexSwapReceipt};
pub use gas::{GasConfig, GasEstimator, GasParams};
pub use slippage::{SlippageCheck, SlippageGuard};
pub use tx_manager::{NonceManager, PendingTx, TxMonitor};

#[async_trait]
pub trait VenueResolver: Send + Sync {
    async fn resolve(&self, signal: &Signal) -> Result<Venue, SlingerError>;
}

#[async_trait]
pub trait ExecutionRouter: Send + Sync {
    async fn route(
        &self,
        signal: &Signal,
        risk: &RiskAssessment,
    ) -> Result<ExecutionOrder, SlingerError>;

    async fn execute(&self, order: &ExecutionOrder) -> Result<ExecutionResult, SlingerError>;
}

#[derive(Debug, Default)]
pub struct DefaultVenueResolver;

#[async_trait]
impl VenueResolver for DefaultVenueResolver {
    async fn resolve(&self, signal: &Signal) -> Result<Venue, SlingerError> {
        Ok(signal.venue.clone())
    }
}

#[derive(Debug)]
pub struct PaperSlinger<R>
where
    R: VenueResolver,
{
    strategy: StrategyProfile,
    resolver: R,
    slippage_model: String,
}

impl<R> PaperSlinger<R>
where
    R: VenueResolver,
{
    pub fn new(strategy: StrategyProfile, resolver: R, slippage_model: impl Into<String>) -> Self {
        Self {
            strategy,
            resolver,
            slippage_model: slippage_model.into(),
        }
    }
}

#[async_trait]
impl<R> ExecutionRouter for PaperSlinger<R>
where
    R: VenueResolver + Send + Sync,
{
    async fn route(
        &self,
        signal: &Signal,
        risk: &RiskAssessment,
    ) -> Result<ExecutionOrder, SlingerError> {
        let venue = self.resolver.resolve(signal).await?;
        let approved_notional = risk.approved_notional_usd.0.min(self.strategy.max_position_size_usd.0);
        if approved_notional <= Decimal::ZERO {
            return Err(SlingerError::OrderValidation(
                "approved notional must be positive".to_owned(),
            ));
        }
        if signal.price_usd.0 <= Decimal::ZERO {
            return Err(SlingerError::OrderValidation(
                "signal price must be positive".to_owned(),
            ));
        }

        let amount = TokenAmount::new((approved_notional / signal.price_usd.0).round_dp(8))
            .map_err(|error| SlingerError::OrderValidation(error.to_string()))?;
        let limit_price = signal.price_usd.clone();
        let notional_usd = Usd::new(approved_notional)
            .map_err(|error| SlingerError::OrderValidation(error.to_string()))?;

        ExecutionOrder::builder()
            .id(format!("{}-order-{}", self.strategy.name, signal.timestamp_ms))
            .strategy(self.strategy.name.clone())
            .signal_id(signal.id.clone())
            .token(signal.token.clone())
            .venue(venue)
            .amount(amount)
            .notional_usd(notional_usd)
            .limit_price_usd(limit_price)
            .observed_liquidity_usd(signal.liquidity_usd.clone())
            .observed_volume_24h_usd(signal.volume_24h_usd.clone())
            .max_slippage_bps(self.strategy.max_slippage_bps.min(500))
            .metadata(signal.metadata.clone())
            .build()
            .map_err(|error| SlingerError::OrderValidation(error.to_string()))
    }

    async fn execute(&self, order: &ExecutionOrder) -> Result<ExecutionResult, SlingerError> {
        let simulated_bps = if self.slippage_model == "simulated" {
            simulated_slippage_bps(order)
        } else {
            0
        };

        if simulated_bps > order.max_slippage_bps {
            return Err(SlingerError::Execution(format!(
                "simulated slippage {}bps exceeds configured max {}bps",
                simulated_bps, order.max_slippage_bps
            )));
        }

        let fill_ratio_bps = simulated_fill_ratio_bps(order);
        if fill_ratio_bps < 5_000 {
            return Err(SlingerError::Execution(format!(
                "simulated fill ratio {}bps too low for execution",
                fill_ratio_bps
            )));
        }

        let multiplier = Decimal::ONE + (Decimal::from(simulated_bps) / Decimal::new(10_000, 0));
        let fill_price = Usd::new((order.limit_price_usd.0 * multiplier).round_dp(8))
            .map_err(|error| SlingerError::Execution(error.to_string()))?;
        let executed_notional = Usd::new(
            (order.notional_usd.0 * Decimal::from(fill_ratio_bps) / Decimal::new(10_000, 0)).round_dp(8),
        )
        .map_err(|error| SlingerError::Execution(error.to_string()))?;
        let fee_usd = Usd::new((executed_notional.0 * Decimal::new(30, 4)).round_dp(8))
            .map_err(|error| SlingerError::Execution(error.to_string()))?;
        let filled_amount = TokenAmount::new((executed_notional.0 / fill_price.0).round_dp(8))
            .map_err(|error| SlingerError::Execution(error.to_string()))?;

        Ok(ExecutionResult {
            order_id: order.id.clone(),
            status: ExecutionStatus::Filled,
            fill_price_usd: fill_price,
            filled_amount,
            slippage_bps: simulated_bps,
            fill_ratio_bps,
            notional_usd: executed_notional,
            requested_notional_usd: order.notional_usd.clone(),
            fee_usd,
            venue: order.venue.clone(),
            timestamp_ms: timestamp_ms(),
        })
    }
}

fn simulated_slippage_bps(order: &ExecutionOrder) -> u16 {
    let liquidity_ratio_bps = ratio_bps(order.notional_usd.0, order.observed_liquidity_usd.0);
    let volume_ratio_bps = ratio_bps(order.notional_usd.0, order.observed_volume_24h_usd.0);
    let base_bps = 12u16;
    let impact_bps = liquidity_ratio_bps / 8 + volume_ratio_bps / 20;
    base_bps.saturating_add(impact_bps)
}

fn simulated_fill_ratio_bps(order: &ExecutionOrder) -> u16 {
    let liquidity_capacity = order.observed_liquidity_usd.0 * Decimal::new(3, 2);
    let volume_capacity = order.observed_volume_24h_usd.0 * Decimal::new(2, 2);
    let capped_notional = liquidity_capacity.min(volume_capacity).max(Decimal::ZERO);
    if capped_notional <= Decimal::ZERO || order.notional_usd.0 <= Decimal::ZERO {
        return 0;
    }

    ratio_bps(capped_notional.min(order.notional_usd.0), order.notional_usd.0).min(10_000)
}

fn ratio_bps(numerator: Decimal, denominator: Decimal) -> u16 {
    if denominator <= Decimal::ZERO {
        return u16::MAX;
    }

    ((numerator / denominator) * Decimal::new(10_000, 0))
        .round_dp(0)
        .to_string()
        .parse::<u16>()
        .unwrap_or(u16::MAX)
}

fn timestamp_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::{DefaultVenueResolver, ExecutionRouter, PaperSlinger};
    use ast_core::{Chain, RiskAssessment, RiskDecision, RiskLevel, Signal, StrategyProfile, Token, Usd, Venue};
    use rust_decimal::Decimal;
    use std::collections::BTreeMap;

    #[tokio::test]
    async fn paper_execution_generates_fill() {
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
            target_notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            timestamp_ms: 1,
            metadata: BTreeMap::new(),
        };
        let assessment = RiskAssessment {
            level: RiskLevel::Low,
            decision: RiskDecision::Accept,
            rationale: "ok".to_owned(),
            approved_notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            factors: Vec::new(),
        };

        let slinger = PaperSlinger::new(strategy, DefaultVenueResolver, "simulated");
        let order = slinger.route(&signal, &assessment).await.expect("route should succeed");
        let result = slinger.execute(&order).await.expect("execute should succeed");

        assert_eq!(result.status, ast_core::ExecutionStatus::Filled);
        assert!(result.fill_ratio_bps > 0);
        assert!(result.fee_usd.0 > Decimal::ZERO);
    }
}
