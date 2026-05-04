use std::sync::Arc;

use alloy::primitives::U256;
use async_trait::async_trait;
use ast_core::{
    CloseError, CloseReceipt, ExecutionOrder, ExecutionResult, ExecutionStatus,
    LiveCloseExecutor, LiveExecutionConfig, Position, RiskAssessment, Signal, StrategyProfile,
    TokenAmount, Usd, Venue,
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

        // gas_used (units) × effective_gas_price (wei/unit) = total fee in wei.
        // Convert to USD via eth_price_usd. Receipt is populated only after
        // the TX mines (DexSwapExecutor::wait_for_receipt), so this is real
        // — not estimated.
        let gas_fee_wei = (receipt.gas_used as u128)
            .saturating_mul(receipt.effective_gas_price as u128);
        let gas_fee_wei_dec = Decimal::from_str_exact(&gas_fee_wei.to_string())
            .map_err(|e| SlingerError::Execution(format!("gas wei → decimal: {e}")))?;
        let gas_fee_eth_dec = gas_fee_wei_dec / decimal_pow10(18);
        let fee_usd_dec =
            (gas_fee_eth_dec * self.live_config.eth_price_usd).round_dp(8);
        let fee_usd = Usd::new(fee_usd_dec.max(Decimal::ZERO))
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
            fee_usd,
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

/// Adapts `DexSwapExecutor::execute_sell` to the `LiveCloseExecutor`
/// trait used by the Reaper. The Reaper stores `position.quantity` as
/// a Decimal in human units; this adapter handles the
/// Decimal → raw-token-unit U256 scaling and the Position →
/// ExecutionOrder shaping the executor needs.
pub struct LiveCloseAdapter {
    executor: Arc<DexSwapExecutor>,
    config: LiveExecutionConfig,
}

impl LiveCloseAdapter {
    pub fn new(executor: Arc<DexSwapExecutor>, config: LiveExecutionConfig) -> Self {
        Self { executor, config }
    }
}

#[async_trait]
impl LiveCloseExecutor for LiveCloseAdapter {
    async fn close_position(
        &self,
        position: &Position,
        partial_amount: Option<TokenAmount>,
    ) -> Result<CloseReceipt, CloseError> {
        // Refuse to attempt a close on a venue we can't execute on.
        let chain = match &position.venue {
            Venue::Dex { chain, .. } => chain,
            Venue::Cex { .. } => {
                return Err(CloseError::Validation(
                    "LiveCloseAdapter only handles DEX venues".to_owned(),
                ));
            }
        };
        if !self.executor.is_ready_for(chain) {
            return Err(CloseError::Skipped(format!(
                "executor not ready for {chain} (no wallet/RPC or unsupported chain)"
            )));
        }

        // Decimal target quantity → raw token-unit U256. position.quantity
        // and partial_amount are both human-readable (e.g., 1234.567);
        // decimals lives on the token.
        let target_qty_dec = match partial_amount.as_ref() {
            None => position.quantity.0,
            Some(qty) => {
                if qty.0 > position.quantity.0 {
                    return Err(CloseError::Validation(format!(
                        "partial close amount {} exceeds position quantity {}",
                        qty.0, position.quantity.0
                    )));
                }
                qty.0
            }
        };
        let scale = decimal_pow10(position.token.decimals as u32);
        let raw_units_dec = (target_qty_dec * scale).round_dp(0);
        if raw_units_dec <= Decimal::ZERO {
            return Err(CloseError::Validation(format!(
                "close amount {} scales to non-positive raw units",
                target_qty_dec
            )));
        }
        let amount_token_in: U256 = raw_units_dec.to_string().parse().map_err(|e| {
            CloseError::Execution(format!("Decimal → U256 (qty {}): {e}", target_qty_dec))
        })?;

        // Synthetic ExecutionOrder for the sell. The executor only needs
        // venue (for chain + router), token (for address), and
        // max_slippage_bps. Everything else is informational and gets
        // sensible placeholders.
        let id_suffix = if partial_amount.is_some() {
            "partial-close"
        } else {
            "close"
        };
        let order_amount =
            TokenAmount::new(target_qty_dec).map_err(|e| CloseError::Validation(e.to_string()))?;
        let synthetic_order = ExecutionOrder::builder()
            .id(format!("{}-{}", id_suffix, position.id))
            .strategy(position.strategy.clone())
            .signal_id(position.signal_id.clone())
            .token(position.token.clone())
            .venue(position.venue.clone())
            .amount(order_amount)
            .notional_usd(position.entry_notional_usd.clone())
            .limit_price_usd(position.entry_price_usd.clone())
            .observed_liquidity_usd(Usd::new(Decimal::ZERO).unwrap_or(Usd::zero()))
            .observed_volume_24h_usd(Usd::new(Decimal::ZERO).unwrap_or(Usd::zero()))
            .max_slippage_bps(500) // Closes need to clear; allow more slippage than entries.
            .metadata(position.metadata.clone())
            .build()
            .map_err(|error| CloseError::Validation(error.to_string()))?;

        let receipt = self
            .executor
            .execute_sell(&synthetic_order, amount_token_in)
            .await
            .map_err(|error| match error {
                SlingerError::OrderValidation(msg) => CloseError::Validation(msg),
                _ => CloseError::Execution(error.to_string()),
            })?;

        // Compute USD received. amount_eth_wei is the WETH out (V2's
        // last quote); convert to USD via eth_price_usd.
        let eth_wei_dec = Decimal::from_str_exact(&receipt.amount_eth_wei.to_string())
            .map_err(|e| CloseError::Execution(format!("U256 → Decimal: {e}")))?;
        let eth_dec = eth_wei_dec / decimal_pow10(18);
        let eth_received_usd = (eth_dec * self.config.eth_price_usd).round_dp(8);

        // Gas fee in USD.
        let gas_fee_wei = (receipt.gas_used as u128)
            .saturating_mul(receipt.effective_gas_price as u128);
        let gas_fee_wei_dec = Decimal::from_str_exact(&gas_fee_wei.to_string())
            .map_err(|e| CloseError::Execution(format!("gas → Decimal: {e}")))?;
        let gas_fee_eth = gas_fee_wei_dec / decimal_pow10(18);
        let fee_usd = (gas_fee_eth * self.config.eth_price_usd).round_dp(8);

        Ok(CloseReceipt {
            tx_hash: format!("{}", receipt.tx_hash),
            eth_received_usd: eth_received_usd.max(Decimal::ZERO),
            fee_usd: fee_usd.max(Decimal::ZERO),
            block_number: receipt.block_number,
        })
    }
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
