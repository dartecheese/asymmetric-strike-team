use alloy::{
    network::EthereumWallet,
    primitives::{Address, B256, U256},
    providers::ProviderBuilder,
    signers::local::PrivateKeySigner,
    sol,
    transports::http::reqwest::Url,
};
use ast_core::{AstError, ExecutionOrder, Result, Venue};
use async_trait::async_trait;
use rust_decimal::Decimal;

// Uniswap V2-compatible router ABI (covers UniV2, SushiSwap, PancakeSwap, etc.)
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

// Canonical WETH addresses per chain
fn weth_for_chain(chain: &str) -> Option<&'static str> {
    match chain.to_lowercase().as_str() {
        "ethereum" | "eth" | "1" => {
            Some("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
        }
        "base" | "8453" => Some("0x4200000000000000000000000000000000000006"),
        "arbitrum" | "42161" => Some("0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"),
        "optimism" | "10" => Some("0x4200000000000000000000000000000000000006"),
        "polygon" | "137" => Some("0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"),
        _ => None,
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DexQuote {
    pub expected_out: Decimal,
    pub amount_out_minimum: Decimal,
}

#[async_trait]
pub trait DexVenue: Send + Sync {
    async fn quote_swap(&self, order: &ExecutionOrder) -> Result<DexQuote>;
}

#[derive(Debug, Clone)]
pub struct DexConfig {
    pub rpc_url: String,
    /// Loaded from env — never hardcoded.
    pub private_key: String,
    pub paper_mode: bool,
    pub max_slippage_bps: u32,
    /// Seconds from now until swap deadline expires.
    pub swap_deadline_secs: u64,
    /// ETH/USD price used to convert allocation to wei.
    /// In production, replace with an oracle call (Chainlink, Uniswap V3 TWAP).
    pub eth_price_usd: Decimal,
}

impl Default for DexConfig {
    fn default() -> Self {
        Self {
            rpc_url: String::new(),
            private_key: String::new(),
            paper_mode: true,
            max_slippage_bps: 300,
            swap_deadline_secs: 60,
            eth_price_usd: Decimal::new(3000, 0),
        }
    }
}

pub struct DexSwapExecutor {
    config: DexConfig,
}

impl DexSwapExecutor {
    pub fn new(config: DexConfig) -> Self {
        Self { config }
    }

    /// Execute a buy swap for the given authorized order.
    /// Returns a transaction hash string, or "paper:simulated" in paper mode.
    pub async fn execute_buy(
        &self,
        order: &ExecutionOrder,
        router_address: &str,
    ) -> Result<String> {
        let Venue::Dex { chain, .. } = order.venue() else {
            return Err(AstError::Validation(
                "DexSwapExecutor requires a DEX venue".into(),
            ));
        };

        if self.config.paper_mode {
            return Ok("paper:simulated".to_string());
        }

        let weth_addr = weth_for_chain(chain.as_str()).ok_or_else(|| {
            AstError::Validation(format!("no WETH address known for chain '{chain}'"))
        })?;

        let signer: PrivateKeySigner = self
            .config
            .private_key
            .parse()
            .map_err(|_| AstError::Validation("invalid private key".into()))?;
        let my_address = signer.address();
        let wallet = EthereumWallet::from(signer);
        let url: Url = self
            .config
            .rpc_url
            .parse()
            .map_err(|_| AstError::Validation("invalid RPC URL".into()))?;

        let provider = ProviderBuilder::new()
            .wallet(wallet)
            .connect_http(url);

        let router: Address = router_address
            .parse()
            .map_err(|_| AstError::Validation(format!("invalid router: {router_address}")))?;
        let token_addr: Address =
            order.token().address.as_str().parse().map_err(|_| {
                AstError::Validation(format!("invalid token: {}", order.token().address))
            })?;
        let weth: Address = weth_addr.parse().expect("hardcoded WETH is valid");

        let amount_in_wei = self.usd_to_wei(order.amount_usd().value())?;
        let path = vec![weth, token_addr];
        let deadline = U256::from(
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system clock is valid")
                .as_secs()
                + self.config.swap_deadline_secs,
        );

        let router_contract = IUniswapV2Router02::new(router, &provider);

        // getAmountsOut returns (uint256[] amounts) — unwrapped to Vec<U256> by alloy
        let quote_amounts = match router_contract
            .getAmountsOut(amount_in_wei, path.clone())
            .call()
            .await
        {
            Ok(v) => v,
            Err(e) => return Err(AstError::Execution(format!("quote call failed: {e}"))),
        };
        let expected_out: U256 = quote_amounts.last().copied().ok_or_else(|| {
            AstError::Execution("empty quote response".into())
        })?;

        let amount_out_min =
            expected_out * U256::from(10_000u32 - self.config.max_slippage_bps)
                / U256::from(10_000u32);

        let pending = match router_contract
            .swapExactETHForTokens(amount_out_min, path, my_address, deadline)
            .value(amount_in_wei)
            .send()
            .await
        {
            Ok(p) => p,
            Err(e) => return Err(AstError::Execution(format!("swap send failed: {e}"))),
        };

        let tx_hash: B256 = *pending.tx_hash();
        Ok(format!("{tx_hash}"))
    }

    fn usd_to_wei(&self, usd: Decimal) -> Result<U256> {
        if self.config.eth_price_usd.is_zero() {
            return Err(AstError::Config(
                "eth_price_usd is zero — set an oracle price".into(),
            ));
        }
        let eth_amount = usd / self.config.eth_price_usd;
        let eth_scaled = eth_amount * Decimal::new(1_000_000_000_000_000_000i64, 0);
        let wei_str = eth_scaled.round().to_string();
        wei_str
            .parse::<U256>()
            .map_err(|e| AstError::Execution(format!("ETH→wei conversion: {e}")))
    }
}

#[async_trait]
impl DexVenue for DexSwapExecutor {
    async fn quote_swap(&self, order: &ExecutionOrder) -> Result<DexQuote> {
        let Venue::Dex { chain, router } = order.venue() else {
            return Err(AstError::Validation("not a DEX venue".into()));
        };

        if self.config.paper_mode {
            return Ok(DexQuote {
                expected_out: Decimal::new(1_000_000, 0),
                amount_out_minimum: Decimal::new(970_000, 0),
            });
        }

        let weth_addr = weth_for_chain(chain.as_str()).ok_or_else(|| {
            AstError::Validation(format!("no WETH for chain '{chain}'"))
        })?;

        let url: Url = self
            .config
            .rpc_url
            .parse()
            .map_err(|_| AstError::Validation("invalid RPC URL".into()))?;
        let provider = ProviderBuilder::new().connect_http(url);

        let router_addr: Address = router
            .as_str()
            .parse()
            .map_err(|_| AstError::Validation(format!("invalid router: {router}")))?;
        let token_addr: Address = order.token().address.as_str().parse().map_err(|_| {
            AstError::Validation(format!("invalid token: {}", order.token().address))
        })?;
        let weth: Address = weth_addr.parse().expect("hardcoded WETH is valid");

        let amount_in_wei = self.usd_to_wei(order.amount_usd().value())?;
        let router_contract = IUniswapV2Router02::new(router_addr, &provider);

        let amounts = match router_contract
            .getAmountsOut(amount_in_wei, vec![weth, token_addr])
            .call()
            .await
        {
            Ok(v) => v,
            Err(e) => return Err(AstError::Execution(format!("quote call failed: {e}"))),
        };

        let expected_raw: U256 = amounts.last().copied().ok_or_else(|| {
            AstError::Execution("empty quote".into())
        })?;

        let expected_dec = Decimal::from_str_exact(&expected_raw.to_string())
            .map_err(|e| AstError::Execution(format!("decimal conversion: {e}")))?;
        let slippage_factor =
            Decimal::new(10_000i64 - self.config.max_slippage_bps as i64, 4);
        let minimum = expected_dec * slippage_factor;

        Ok(DexQuote {
            expected_out: expected_dec,
            amount_out_minimum: minimum,
        })
    }
}
