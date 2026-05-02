use std::sync::Arc;

use async_trait::async_trait;
use ast_core::{
    ExecutionOrder, ExecutionResult, ExecutionStatus, LiveExecutionConfig, RiskAssessment, Signal,
    StrategyProfile, TokenAmount, Usd, Venue,
};
use rust_decimal::Decimal;

use crate::{
    dex::DexSwapExecutor, ExecutionRouter, SlingerError, VenueResolver,
};

/// Production execution router. Wraps a `DexSwapExecutor` and implements
/// `ExecutionRouter` for live on-chain swaps.
///
/// `route()` mirrors the paper variant but additionally clamps the notional
/// to `live_config.max_trade_usd` — a hard ceiling on real-money sizing
/// that the operator sets in TOML / env.
///
/// `execute()` requires the wrapped executor to be ready for the order's
/// chain (wallet + RPC configured, EVM chain). Otherwise it returns
/// `SlingerError::Execution` so the runtime can refuse loudly rather than
/// quietly fall back to paper.
pub struct LiveSlinger<R: VenueResolver> {
    strategy: StrategyProfile,
    resolver: R,
    executor: Arc<DexSwapExecutor>,
    live_config: LiveExecutionConfig,
}

impl<R: VenueResolver> LiveSlinger<R> {
    pub fn new(
        strategy: StrategyProfile,
        resolver: R,
        executor: Arc<DexSwapExecutor>,
        live_config: LiveExecutionConfig,
    ) -> Self {
        Self {
            strategy,
            resolver,
            executor,
            live_config,
        }
    }
}

#[async_trait]
impl<R> ExecutionRouter for LiveSlinger<R>
where
    R: VenueResolver + Send + Sync,
{
    async fn route(
        &self,
        signal: &Signal,
        risk: &RiskAssessment,
    ) -> Result<ExecutionOrder, SlingerError> {
        let venue = self.resolver.resolve(signal).await?;

        let mut approved_notional = risk
            .approved_notional_usd
            .0
            .min(self.strategy.max_position_size_usd.0);
        if self.live_config.max_trade_usd > Decimal::ZERO {
            approved_notional = approved_notional.min(self.live_config.max_trade_usd);
        }

        if approved_notional <= Decimal::ZERO {
            return Err(SlingerError::OrderValidation(
                "approved notional must be positive after live caps".to_owned(),
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
            .id(format!("{}-live-order-{}", self.strategy.name, signal.timestamp_ms))
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
        let chain = match &order.venue {
            Venue::Dex { chain, .. } => chain,
            Venue::Cex { .. } => {
                return Err(SlingerError::OrderValidation(
                    "LiveSlinger only routes DEX venues".to_owned(),
                ));
            }
        };

        if !self.executor.is_ready_for(chain) {
            return Err(SlingerError::Execution(format!(
                "live executor not ready for {chain}: configure ETH_RPC_URL and PRIVATE_KEY, and use a supported EVM chain"
            )));
        }

        let receipt = self.executor.execute_buy(order).await?;

        // Convert the U256 amounts back into Decimal-denominated fields the
        // ExecutionResult expects. Rust Decimal max ~10^28 — fine for
        // realistic trade sizes (18-decimal tokens at $5–$500 notional fit
        // comfortably).
        let token_amount_dec = decimal_from_u256(receipt.amount_token)?;
        let token_scale = decimal_pow10(order.token.decimals as u32);
        let filled_amount_dec = (token_amount_dec / token_scale).round_dp(8);
        let filled_amount = TokenAmount::new(filled_amount_dec.max(Decimal::new(1, 8)))
            .map_err(|error| SlingerError::Execution(error.to_string()))?;

        let eth_wei_dec = decimal_from_u256(receipt.amount_eth_wei)?;
        let eth_scale = decimal_pow10(18);
        let eth_amount_dec = eth_wei_dec / eth_scale;
        let executed_notional_dec =
            (eth_amount_dec * self.live_config.eth_price_usd).round_dp(8);
        let notional_usd = Usd::new(executed_notional_dec.max(Decimal::ZERO))
            .map_err(|error| SlingerError::Execution(error.to_string()))?;

        let fill_price_dec = if filled_amount_dec > Decimal::ZERO {
            (executed_notional_dec / filled_amount_dec).round_dp(8)
        } else {
            order.limit_price_usd.0
        };
        let fill_price_usd = Usd::new(fill_price_dec.max(Decimal::ZERO))
            .map_err(|error| SlingerError::Execution(error.to_string()))?;

        Ok(ExecutionResult {
            order_id: order.id.clone(),
            status: ExecutionStatus::Filled,
            fill_price_usd,
            filled_amount,
            slippage_bps: receipt.observed_slippage_bps.min(u16::MAX as u32) as u16,
            // V2 swaps either succeed for the full amount or revert — no
            // partial fills like a paper sim. Use 100% on success.
            fill_ratio_bps: 10_000,
            notional_usd,
            requested_notional_usd: order.notional_usd.clone(),
            // TODO: poll the TX receipt for actual gas_used and convert to
            // fee_usd. Reaper reconciliation slice will refine this.
            fee_usd: Usd::zero(),
            venue: order.venue.clone(),
            timestamp_ms: timestamp_ms(),
        })
    }
}

fn decimal_from_u256(value: alloy::primitives::U256) -> Result<Decimal, SlingerError> {
    Decimal::from_str_exact(&value.to_string()).map_err(|e| {
        SlingerError::Execution(format!(
            "U256 -> Decimal conversion overflowed (value={value}): {e}"
        ))
    })
}

fn decimal_pow10(exp: u32) -> Decimal {
    let mut result = Decimal::ONE;
    for _ in 0..exp {
        result *= Decimal::from(10u32);
    }
    result
}

fn timestamp_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use alloy_primitives::Address;
    use ast_core::{
        Chain, LiveExecutionConfig, RiskAssessment, RiskDecision, RiskLevel, Signal,
        StrategyProfile, Token, Usd, Venue,
    };
    use rust_decimal::Decimal;

    use super::*;
    use crate::DefaultVenueResolver;

    fn strategy(max_position: Decimal) -> StrategyProfile {
        StrategyProfile {
            name: "swift".to_owned(),
            description: "Fast entry on new pairs".to_owned(),
            max_position_size_usd: Usd::new(max_position).expect("usd"),
            max_slippage_bps: 200,
            risk_tolerance: RiskLevel::Medium,
            scan_interval_seconds: 15,
            paper_trading: false,
        }
    }

    fn signal(price: Decimal, chain: Chain) -> Signal {
        Signal {
            id: "signal-test".to_owned(),
            token: Token {
                address: Address::ZERO,
                chain: chain.clone(),
                symbol: "TEST".to_owned(),
                decimals: 18,
            },
            venue: Venue::Dex {
                chain,
                router: Address::ZERO,
            },
            price_usd: Usd::new(price).expect("price"),
            volume_24h_usd: Usd::new(Decimal::new(100_000, 0)).expect("vol"),
            liquidity_usd: Usd::new(Decimal::new(500_000, 0)).expect("liq"),
            target_notional_usd: Usd::new(Decimal::new(50, 0)).expect("target"),
            timestamp_ms: 1,
            metadata: BTreeMap::new(),
        }
    }

    fn risk(approved: Decimal) -> RiskAssessment {
        RiskAssessment {
            level: RiskLevel::Low,
            decision: RiskDecision::Accept,
            rationale: "ok".to_owned(),
            approved_notional_usd: Usd::new(approved).expect("approved"),
            factors: Vec::new(),
        }
    }

    fn unconfigured_executor() -> Arc<DexSwapExecutor> {
        Arc::new(DexSwapExecutor::new(LiveExecutionConfig::default()))
    }

    fn order(notional: Decimal, chain: Chain) -> ExecutionOrder {
        ExecutionOrder::builder()
            .id("order-test")
            .strategy("swift")
            .signal_id("signal-test")
            .token(Token {
                address: Address::ZERO,
                chain: chain.clone(),
                symbol: "TEST".to_owned(),
                decimals: 18,
            })
            .venue(Venue::Dex {
                chain,
                router: Address::ZERO,
            })
            .amount(TokenAmount::new(Decimal::new(1, 0)).expect("amount"))
            .notional_usd(Usd::new(notional).expect("notional"))
            .limit_price_usd(Usd::new(Decimal::ONE).expect("price"))
            .observed_liquidity_usd(Usd::new(Decimal::new(100_000, 0)).expect("liq"))
            .observed_volume_24h_usd(Usd::new(Decimal::new(50_000, 0)).expect("vol"))
            .max_slippage_bps(300)
            .metadata(BTreeMap::new())
            .build()
            .expect("order")
    }

    #[tokio::test]
    async fn route_clamps_to_live_max_trade_when_lower_than_strategy() {
        // strategy allows $200, risk approves $200, but live cap is $25
        let live_config = LiveExecutionConfig {
            max_trade_usd: Decimal::new(25, 0),
            ..LiveExecutionConfig::default()
        };
        let slinger = LiveSlinger::new(
            strategy(Decimal::new(200, 0)),
            DefaultVenueResolver,
            unconfigured_executor(),
            live_config,
        );
        let order = slinger
            .route(&signal(Decimal::ONE, Chain::Base), &risk(Decimal::new(200, 0)))
            .await
            .expect("route");
        assert_eq!(order.notional_usd.0, Decimal::new(25, 0));
    }

    #[tokio::test]
    async fn route_clamps_to_strategy_when_lower_than_live_cap() {
        // strategy allows $5, live cap is $25 — strategy wins
        let live_config = LiveExecutionConfig {
            max_trade_usd: Decimal::new(25, 0),
            ..LiveExecutionConfig::default()
        };
        let slinger = LiveSlinger::new(
            strategy(Decimal::new(5, 0)),
            DefaultVenueResolver,
            unconfigured_executor(),
            live_config,
        );
        let order = slinger
            .route(&signal(Decimal::ONE, Chain::Base), &risk(Decimal::new(50, 0)))
            .await
            .expect("route");
        assert_eq!(order.notional_usd.0, Decimal::new(5, 0));
    }

    #[tokio::test]
    async fn execute_rejects_loudly_when_executor_not_ready() {
        // No private_key, no rpc_url — executor reports !is_ready_for(Base)
        let slinger = LiveSlinger::new(
            strategy(Decimal::new(5, 0)),
            DefaultVenueResolver,
            unconfigured_executor(),
            LiveExecutionConfig::default(),
        );
        let err = slinger
            .execute(&order(Decimal::new(5, 0), Chain::Base))
            .await
            .expect_err("must refuse without wallet/rpc");
        assert!(matches!(err, SlingerError::Execution(msg) if msg.contains("not ready")));
    }

    #[tokio::test]
    async fn execute_rejects_solana_chain() {
        let slinger = LiveSlinger::new(
            strategy(Decimal::new(5, 0)),
            DefaultVenueResolver,
            unconfigured_executor(),
            LiveExecutionConfig::default(),
        );
        let err = slinger
            .execute(&order(Decimal::new(5, 0), Chain::Solana))
            .await
            .expect_err("solana not supported");
        assert!(matches!(err, SlingerError::Execution(_)));
    }

    #[tokio::test]
    async fn execute_rejects_cex_venue() {
        let token = Token {
            address: Address::ZERO,
            chain: Chain::Solana,
            symbol: "BONK".to_owned(),
            decimals: 9,
        };
        let cex_order = ExecutionOrder::builder()
            .id("order-cex")
            .strategy("swift")
            .signal_id("signal-cex")
            .token(token)
            .venue(Venue::Cex {
                exchange: "binance".to_owned(),
                pair: "BONK/USDT".to_owned(),
            })
            .amount(TokenAmount::new(Decimal::ONE).expect("amount"))
            .notional_usd(Usd::new(Decimal::new(5, 0)).expect("notional"))
            .limit_price_usd(Usd::new(Decimal::ONE).expect("price"))
            .observed_liquidity_usd(Usd::new(Decimal::new(100_000, 0)).expect("liq"))
            .observed_volume_24h_usd(Usd::new(Decimal::new(50_000, 0)).expect("vol"))
            .max_slippage_bps(300)
            .metadata(BTreeMap::new())
            .build()
            .expect("order");
        let slinger = LiveSlinger::new(
            strategy(Decimal::new(5, 0)),
            DefaultVenueResolver,
            unconfigured_executor(),
            LiveExecutionConfig::default(),
        );
        let err = slinger.execute(&cex_order).await.expect_err("cex denied");
        assert!(matches!(err, SlingerError::OrderValidation(_)));
    }

    #[test]
    fn decimal_pow10_returns_correct_powers() {
        assert_eq!(decimal_pow10(0), Decimal::ONE);
        assert_eq!(decimal_pow10(1), Decimal::new(10, 0));
        assert_eq!(decimal_pow10(18), Decimal::new(1_000_000_000_000_000_000i64, 0));
    }
}
