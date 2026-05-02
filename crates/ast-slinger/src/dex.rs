use std::sync::Arc;

use alloy::{
    network::EthereumWallet,
    primitives::{Address, B256, U256},
    providers::ProviderBuilder,
    signers::local::PrivateKeySigner,
    sol,
    transports::http::reqwest::Url,
};
use ast_core::{Chain, ExecutionOrder, LiveExecutionConfig, Venue};
use rust_decimal::Decimal;

use crate::{
    gas::GasEstimator,
    slippage::SlippageGuard,
    tx_manager::{NonceManager, PendingTx, TxMonitor},
    SlingerError,
};

type Result<T> = std::result::Result<T, SlingerError>;

// Uniswap V2-compatible router ABI (covers UniV2, SushiSwap, PancakeSwap,
// BaseSwap, Aerodrome's V2-mode router, etc.).
sol! {
    #[sol(rpc)]
    interface IUniswapV2Router02 {
        function swapExactETHForTokens(
            uint256 amountOutMin,
            address[] calldata path,
            address to,
            uint256 deadline
        ) external payable returns (uint256[] memory amounts);

        function swapExactTokensForTokens(
            uint256 amountIn,
            uint256 amountOutMin,
            address[] calldata path,
            address to,
            uint256 deadline
        ) external returns (uint256[] memory amounts);

        function getAmountsOut(
            uint256 amountIn,
            address[] calldata path
        ) external view returns (uint256[] memory amounts);
    }
}

sol! {
    #[sol(rpc)]
    interface IERC20 {
        function approve(address spender, uint256 amount) external returns (bool);
        function allowance(address owner, address spender) external view returns (uint256);
        function balanceOf(address account) external view returns (uint256);
    }
}

/// Receipt returned by a successful swap. The LiveSlinger builds an
/// `ExecutionResult` from this.
#[derive(Debug, Clone)]
pub struct DexSwapReceipt {
    pub tx_hash: B256,
    /// Tokens received (buy) or tokens sold (sell), in raw token-unit `U256`.
    pub amount_token: U256,
    /// ETH spent (buy) or ETH received (sell), in wei.
    pub amount_eth_wei: U256,
    /// Quoted slippage in bps relative to a no-impact swap. 0 means we got
    /// exactly the AMM-quoted output.
    pub observed_slippage_bps: u32,
}

/// WETH addresses per supported chain. Returns None for non-EVM chains.
pub(crate) fn weth_for_chain(chain: &Chain) -> Option<Address> {
    let raw = match chain {
        Chain::Ethereum => "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        Chain::Base => "0x4200000000000000000000000000000000000006",
        Chain::Arbitrum => "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        Chain::Solana => return None,
    };
    raw.parse().ok()
}

pub(crate) fn chain_id_for(chain: &Chain) -> Option<u64> {
    match chain {
        Chain::Ethereum => Some(1),
        Chain::Base => Some(8453),
        Chain::Arbitrum => Some(42161),
        Chain::Solana => None,
    }
}

/// Low-level Uniswap V2 swap executor. Stateless aside from optional
/// shared infrastructure (nonce manager, tx monitor, gas estimator).
///
/// The executor is "ready" only when (a) `private_key` and `rpc_url` are
/// non-empty in config, and (b) the order's chain has a known WETH and
/// chain ID. `LiveSlinger::execute` checks `is_ready_for` and returns a
/// rejected `ExecutionResult` when it isn't, so the gate stays closed
/// for unconfigured runtimes.
pub struct DexSwapExecutor {
    config: LiveExecutionConfig,
    nonce_manager: Option<Arc<NonceManager>>,
    tx_monitor: Option<Arc<TxMonitor>>,
    gas_estimator: Option<GasEstimator>,
}

impl DexSwapExecutor {
    pub fn new(config: LiveExecutionConfig) -> Self {
        Self {
            config,
            nonce_manager: None,
            tx_monitor: None,
            gas_estimator: None,
        }
    }

    pub fn with_nonce_manager(mut self, nonce_manager: Arc<NonceManager>) -> Self {
        self.nonce_manager = Some(nonce_manager);
        self
    }

    pub fn with_tx_monitor(mut self, tx_monitor: Arc<TxMonitor>) -> Self {
        self.tx_monitor = Some(tx_monitor);
        self
    }

    pub fn with_gas_estimator(mut self, gas_estimator: GasEstimator) -> Self {
        self.gas_estimator = Some(gas_estimator);
        self
    }

    /// Returns true when this executor can submit on-chain swaps for `chain`.
    /// Used by the LiveSlinger to decide whether to attempt execution or
    /// short-circuit with a rejected result.
    pub fn is_ready_for(&self, chain: &Chain) -> bool {
        !self.config.private_key.is_empty()
            && !self.config.rpc_url.is_empty()
            && weth_for_chain(chain).is_some()
            && chain_id_for(chain).is_some()
    }

    /// Submit an ETH → token swap. The order's `notional_usd` is converted
    /// to wei via `config.eth_price_usd`. The router on the order's venue
    /// is used as the swap target.
    pub async fn execute_buy(&self, order: &ExecutionOrder) -> Result<DexSwapReceipt> {
        let (chain, router) = require_dex_venue(order)?;
        let weth = weth_for_chain(chain)
            .ok_or_else(|| SlingerError::OrderValidation(format!("no WETH for chain {chain}")))?;
        let chain_id = chain_id_for(chain).ok_or_else(|| {
            SlingerError::OrderValidation(format!("no chain id known for chain {chain}"))
        })?;
        self.enforce_max_trade(order)?;

        let signer = self.signer()?;
        let my_address = signer.address();
        let url: Url = self
            .config
            .rpc_url
            .parse()
            .map_err(|_| SlingerError::OrderValidation("invalid rpc_url".into()))?;
        let wallet = EthereumWallet::from(signer);
        let provider = ProviderBuilder::new().wallet(wallet).on_http(url);

        let token_addr = order.token.address;
        let amount_in_wei = self.usd_to_wei(order.notional_usd.0)?;
        let path = vec![weth, token_addr];

        let router_contract = IUniswapV2Router02::new(router, &provider);
        let quote = router_contract
            .getAmountsOut(amount_in_wei, path.clone())
            .call()
            .await
            .map_err(|e| SlingerError::ExternalService {
                service: "rpc",
                message: format!("getAmountsOut failed: {e}"),
            })?;
        let expected_out: U256 = last_u256(&quote.amounts)?;
        let amount_out_min = self.minimum_out(expected_out, order.max_slippage_bps)?;
        let deadline = self.deadline();

        let mut builder = router_contract
            .swapExactETHForTokens(amount_out_min, path, my_address, deadline)
            .value(amount_in_wei);

        if let Some(estimator) = &self.gas_estimator {
            let params = estimator.estimate(&provider).await?;
            builder = builder
                .max_fee_per_gas(params.max_fee_per_gas)
                .max_priority_fee_per_gas(params.max_priority_fee_per_gas);
        }

        let nonce_used = if let Some(nm) = &self.nonce_manager {
            let n = nm.next_nonce(chain_id, my_address, &provider).await?;
            builder = builder.nonce(n);
            Some(n)
        } else {
            None
        };

        let pending = builder
            .send()
            .await
            .map_err(|e| SlingerError::Execution(format!("buy swap send failed: {e}")))?;
        let tx_hash: B256 = *pending.tx_hash();

        if let Some(monitor) = &self.tx_monitor {
            monitor
                .track(PendingTx::new(
                    tx_hash,
                    chain_id,
                    my_address,
                    nonce_used.unwrap_or(0),
                ))
                .await;
        }

        Ok(DexSwapReceipt {
            tx_hash,
            amount_token: expected_out,
            amount_eth_wei: amount_in_wei,
            observed_slippage_bps: 0,
        })
    }

    /// Submit a token → ETH swap. Performs an allowance bump first if the
    /// router's current allowance is below `amount_token_in`.
    pub async fn execute_sell(
        &self,
        order: &ExecutionOrder,
        amount_token_in: U256,
    ) -> Result<DexSwapReceipt> {
        if amount_token_in.is_zero() {
            return Err(SlingerError::OrderValidation(
                "sell amount must be positive".into(),
            ));
        }

        let (chain, router) = require_dex_venue(order)?;
        let weth = weth_for_chain(chain)
            .ok_or_else(|| SlingerError::OrderValidation(format!("no WETH for chain {chain}")))?;
        let chain_id = chain_id_for(chain).ok_or_else(|| {
            SlingerError::OrderValidation(format!("no chain id known for chain {chain}"))
        })?;

        let signer = self.signer()?;
        let my_address = signer.address();
        let url: Url = self
            .config
            .rpc_url
            .parse()
            .map_err(|_| SlingerError::OrderValidation("invalid rpc_url".into()))?;
        let wallet = EthereumWallet::from(signer);
        let provider = ProviderBuilder::new().wallet(wallet).on_http(url);

        let token_addr = order.token.address;

        // Step 1: allowance check + approve if needed.
        let token_contract = IERC20::new(token_addr, &provider);
        let allowance_resp = token_contract
            .allowance(my_address, router)
            .call()
            .await
            .map_err(|e| SlingerError::ExternalService {
                service: "rpc",
                message: format!("allowance query failed: {e}"),
            })?;
        let current_allowance: U256 = allowance_resp._0;

        if current_allowance < amount_token_in {
            let approve_pending = token_contract
                .approve(router, amount_token_in)
                .send()
                .await
                .map_err(|e| SlingerError::Execution(format!("approve send failed: {e}")))?;
            approve_pending
                .get_receipt()
                .await
                .map_err(|e| SlingerError::Execution(format!("approve receipt failed: {e}")))?;
        }

        // Step 2: quote and submit swap.
        let path = vec![token_addr, weth];
        let router_contract = IUniswapV2Router02::new(router, &provider);
        let quote = router_contract
            .getAmountsOut(amount_token_in, path.clone())
            .call()
            .await
            .map_err(|e| SlingerError::ExternalService {
                service: "rpc",
                message: format!("getAmountsOut failed: {e}"),
            })?;
        let expected_out: U256 = last_u256(&quote.amounts)?;
        let amount_out_min = self.minimum_out(expected_out, order.max_slippage_bps)?;
        let deadline = self.deadline();

        let mut builder = router_contract.swapExactTokensForTokens(
            amount_token_in,
            amount_out_min,
            path,
            my_address,
            deadline,
        );

        if let Some(estimator) = &self.gas_estimator {
            let params = estimator.estimate(&provider).await?;
            builder = builder
                .max_fee_per_gas(params.max_fee_per_gas)
                .max_priority_fee_per_gas(params.max_priority_fee_per_gas);
        }

        let nonce_used = if let Some(nm) = &self.nonce_manager {
            let n = nm.next_nonce(chain_id, my_address, &provider).await?;
            builder = builder.nonce(n);
            Some(n)
        } else {
            None
        };

        let pending = builder
            .send()
            .await
            .map_err(|e| SlingerError::Execution(format!("sell swap send failed: {e}")))?;
        let tx_hash: B256 = *pending.tx_hash();

        if let Some(monitor) = &self.tx_monitor {
            monitor
                .track(PendingTx::new(
                    tx_hash,
                    chain_id,
                    my_address,
                    nonce_used.unwrap_or(0),
                ))
                .await;
        }

        Ok(DexSwapReceipt {
            tx_hash,
            amount_token: amount_token_in,
            amount_eth_wei: expected_out,
            observed_slippage_bps: 0,
        })
    }

    fn signer(&self) -> Result<PrivateKeySigner> {
        if self.config.private_key.is_empty() {
            return Err(SlingerError::Execution(
                "private key not configured — refusing to build wallet".into(),
            ));
        }
        self.config
            .private_key
            .parse::<PrivateKeySigner>()
            .map_err(|_| SlingerError::OrderValidation("invalid private key".into()))
    }

    fn enforce_max_trade(&self, order: &ExecutionOrder) -> Result<()> {
        if self.config.max_trade_usd > Decimal::ZERO
            && order.notional_usd.0 > self.config.max_trade_usd
        {
            return Err(SlingerError::OrderValidation(format!(
                "order notional ${} exceeds live max_trade_usd ${}",
                order.notional_usd.0, self.config.max_trade_usd
            )));
        }
        Ok(())
    }

    fn usd_to_wei(&self, usd: Decimal) -> Result<U256> {
        if self.config.eth_price_usd.is_zero() {
            return Err(SlingerError::OrderValidation(
                "eth_price_usd is zero — set an oracle price".into(),
            ));
        }
        let eth = usd / self.config.eth_price_usd;
        let wei_dec = eth * Decimal::new(1_000_000_000_000_000_000i64, 0);
        wei_dec
            .round()
            .to_string()
            .parse::<U256>()
            .map_err(|e| SlingerError::Execution(format!("ETH→wei conversion: {e}")))
    }

    fn minimum_out(&self, expected_out: U256, max_slippage_bps: u16) -> Result<U256> {
        if expected_out.is_zero() {
            return Err(SlingerError::Execution(
                "expected output is zero — refusing to swap".into(),
            ));
        }
        let expected_dec = Decimal::from_str_exact(&expected_out.to_string())
            .map_err(|e| SlingerError::Execution(format!("decimal conversion: {e}")))?;
        let minimum_dec = SlippageGuard::minimum_output(expected_dec, max_slippage_bps as u32)?;
        minimum_dec
            .round()
            .to_string()
            .parse::<U256>()
            .map_err(|e| SlingerError::Execution(format!("U256 conversion: {e}")))
    }

    fn deadline(&self) -> U256 {
        U256::from(
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system clock is valid")
                .as_secs()
                + self.config.swap_deadline_secs,
        )
    }
}

fn require_dex_venue(order: &ExecutionOrder) -> Result<(&Chain, Address)> {
    match &order.venue {
        Venue::Dex { chain, router } => Ok((chain, *router)),
        Venue::Cex { .. } => Err(SlingerError::OrderValidation(
            "DexSwapExecutor requires a DEX venue".into(),
        )),
    }
}

fn last_u256(amounts: &[U256]) -> Result<U256> {
    amounts
        .last()
        .copied()
        .ok_or_else(|| SlingerError::Execution("AMM returned empty quote".into()))
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use alloy::primitives::Address;
    use ast_core::{
        ExecutionOrder, LiveExecutionConfig, Token, TokenAmount, Usd, Venue,
    };
    use rust_decimal::Decimal;

    use super::*;

    const ROUTER_HEX: &str = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D";
    const TEST_KEY: &str =
        "0x0000000000000000000000000000000000000000000000000000000000000001";

    fn order_for(chain: Chain, notional: Decimal) -> ExecutionOrder {
        let router: Address = ROUTER_HEX.parse().expect("router parses");
        let token = Token {
            address: Address::ZERO,
            chain: chain.clone(),
            symbol: "PEPE".to_owned(),
            decimals: 18,
        };
        ExecutionOrder::builder()
            .id("order-test")
            .strategy("swift")
            .signal_id("signal-test")
            .token(token)
            .venue(Venue::Dex { chain, router })
            .amount(TokenAmount::new(Decimal::new(1, 0)).expect("amount"))
            .notional_usd(Usd::new(notional).expect("notional"))
            .limit_price_usd(Usd::new(Decimal::new(1, 0)).expect("price"))
            .observed_liquidity_usd(Usd::new(Decimal::new(100_000, 0)).expect("liq"))
            .observed_volume_24h_usd(Usd::new(Decimal::new(50_000, 0)).expect("vol"))
            .max_slippage_bps(300)
            .metadata(BTreeMap::new())
            .build()
            .expect("order")
    }

    fn cex_order() -> ExecutionOrder {
        let token = Token {
            address: Address::ZERO,
            chain: Chain::Solana,
            symbol: "BONK".to_owned(),
            decimals: 9,
        };
        ExecutionOrder::builder()
            .id("order-cex")
            .strategy("swift")
            .signal_id("signal-cex")
            .token(token)
            .venue(Venue::Cex {
                exchange: "binance".to_owned(),
                pair: "BONK/USDT".to_owned(),
            })
            .amount(TokenAmount::new(Decimal::new(1, 0)).expect("amount"))
            .notional_usd(Usd::new(Decimal::new(50, 0)).expect("notional"))
            .limit_price_usd(Usd::new(Decimal::new(1, 0)).expect("price"))
            .observed_liquidity_usd(Usd::new(Decimal::new(100_000, 0)).expect("liq"))
            .observed_volume_24h_usd(Usd::new(Decimal::new(50_000, 0)).expect("vol"))
            .max_slippage_bps(300)
            .metadata(BTreeMap::new())
            .build()
            .expect("order")
    }

    fn config_with_secrets() -> LiveExecutionConfig {
        LiveExecutionConfig {
            private_key: TEST_KEY.to_owned(),
            rpc_url: "http://localhost:0".to_owned(),
            ..LiveExecutionConfig::default()
        }
    }

    #[test]
    fn weth_table_covers_evm_chains_only() {
        assert!(weth_for_chain(&Chain::Ethereum).is_some());
        assert!(weth_for_chain(&Chain::Base).is_some());
        assert!(weth_for_chain(&Chain::Arbitrum).is_some());
        assert!(weth_for_chain(&Chain::Solana).is_none());
    }

    #[test]
    fn chain_ids_match_well_known_evm_networks() {
        assert_eq!(chain_id_for(&Chain::Ethereum), Some(1));
        assert_eq!(chain_id_for(&Chain::Base), Some(8453));
        assert_eq!(chain_id_for(&Chain::Arbitrum), Some(42161));
        assert_eq!(chain_id_for(&Chain::Solana), None);
    }

    #[test]
    fn is_ready_for_returns_false_when_secrets_missing() {
        let executor = DexSwapExecutor::new(LiveExecutionConfig::default());
        assert!(!executor.is_ready_for(&Chain::Base));
    }

    #[test]
    fn is_ready_for_returns_false_for_solana_even_with_secrets() {
        let executor = DexSwapExecutor::new(config_with_secrets());
        assert!(!executor.is_ready_for(&Chain::Solana));
    }

    #[test]
    fn is_ready_for_returns_true_for_evm_chain_with_secrets() {
        let executor = DexSwapExecutor::new(config_with_secrets());
        assert!(executor.is_ready_for(&Chain::Base));
    }

    #[test]
    fn usd_to_wei_round_trips_at_pegged_eth_price() {
        let executor = DexSwapExecutor::new(LiveExecutionConfig::default());
        let wei = executor
            .usd_to_wei(Decimal::new(3000, 0))
            .expect("conversion");
        assert_eq!(wei, U256::from(1_000_000_000_000_000_000u128));
    }

    #[test]
    fn usd_to_wei_rejects_zero_eth_price() {
        let cfg = LiveExecutionConfig {
            eth_price_usd: Decimal::ZERO,
            ..LiveExecutionConfig::default()
        };
        let executor = DexSwapExecutor::new(cfg);
        assert!(executor.usd_to_wei(Decimal::new(50, 0)).is_err());
    }

    #[test]
    fn minimum_out_applies_slippage_budget() {
        let executor = DexSwapExecutor::new(LiveExecutionConfig::default());
        let minimum = executor
            .minimum_out(U256::from(1_000_000u64), 300)
            .expect("min");
        assert_eq!(minimum, U256::from(970_000u64));
    }

    #[tokio::test]
    async fn buy_rejects_non_dex_venue() {
        let executor = DexSwapExecutor::new(config_with_secrets());
        let order = cex_order();
        assert!(matches!(
            executor.execute_buy(&order).await,
            Err(SlingerError::OrderValidation(_))
        ));
    }

    #[tokio::test]
    async fn sell_rejects_non_dex_venue() {
        let executor = DexSwapExecutor::new(config_with_secrets());
        let order = cex_order();
        assert!(matches!(
            executor.execute_sell(&order, U256::from(1_000_000u64)).await,
            Err(SlingerError::OrderValidation(_))
        ));
    }

    #[tokio::test]
    async fn sell_rejects_zero_amount() {
        let executor = DexSwapExecutor::new(config_with_secrets());
        let order = order_for(Chain::Base, Decimal::new(5, 0));
        assert!(matches!(
            executor.execute_sell(&order, U256::ZERO).await,
            Err(SlingerError::OrderValidation(_))
        ));
    }

    #[tokio::test]
    async fn buy_rejects_solana_chain_at_weth_lookup() {
        let executor = DexSwapExecutor::new(config_with_secrets());
        let order = order_for(Chain::Solana, Decimal::new(5, 0));
        let err = executor.execute_buy(&order).await.expect_err("solana");
        assert!(matches!(err, SlingerError::OrderValidation(msg) if msg.contains("WETH")));
    }

    #[tokio::test]
    async fn buy_rejects_when_notional_exceeds_max_trade_cap() {
        let cfg = LiveExecutionConfig {
            private_key: TEST_KEY.to_owned(),
            rpc_url: "http://localhost:0".to_owned(),
            max_trade_usd: Decimal::new(5, 0),
            ..LiveExecutionConfig::default()
        };
        let executor = DexSwapExecutor::new(cfg);
        let order = order_for(Chain::Base, Decimal::new(50, 0));
        let err = executor.execute_buy(&order).await.expect_err("over cap");
        assert!(matches!(err, SlingerError::OrderValidation(msg) if msg.contains("max_trade_usd")));
    }
}
