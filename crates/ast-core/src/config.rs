use std::collections::BTreeMap;
use std::path::Path;

use config::{Config, Environment, File};
#[cfg(test)]
use config::FileFormat;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

use crate::{CoreError, RiskLevel, StrategyProfile, Usd};

const STRATEGY_ORDER: [&str; 8] = [
    "thrive",
    "swift",
    "echo",
    "bridge",
    "flow",
    "clarity",
    "nurture",
    "insight",
];

#[derive(Debug, Clone, Default)]
pub struct CliOverrides {
    pub log_filter: Option<String>,
    pub paper_trading_enabled: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RuntimeConfig {
    pub position_monitor_interval_seconds: u64,
    pub shutdown_grace_period_ms: u64,
    pub recent_event_capacity: usize,
    pub state_dir: String,
}

impl Default for RuntimeConfig {
    fn default() -> Self {
        Self {
            position_monitor_interval_seconds: 15,
            shutdown_grace_period_ms: 2_000,
            recent_event_capacity: 5_000,
            state_dir: "data".to_owned(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObserveConfig {
    pub log_filter: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct ApiConfig {
    pub deepseek_api_key: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LlmConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_ollama_base_url")]
    pub base_url: String,
    #[serde(default = "default_live_model")]
    pub live_model: String,
    #[serde(default = "default_critic_model")]
    pub critic_model: String,
    #[serde(default = "default_enabled_strategies")]
    pub enabled_strategies: Vec<String>,
    #[serde(default = "default_request_timeout_ms")]
    pub request_timeout_ms: u64,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            base_url: default_ollama_base_url(),
            live_model: default_live_model(),
            critic_model: default_critic_model(),
            enabled_strategies: default_enabled_strategies(),
            request_timeout_ms: default_request_timeout_ms(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PaperTradingConfig {
    pub enabled: bool,
    pub initial_balance_usd: Usd,
    pub default_slippage_model: String,
    #[serde(default = "default_true")]
    pub use_live_market_data: bool,
    #[serde(default = "default_true")]
    pub use_live_risk_checks: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AppConfig {
    pub runtime: RuntimeConfig,
    pub strategies: Vec<StrategyProfile>,
    pub paper_trading: PaperTradingConfig,
    pub observe: ObserveConfig,
    pub api: ApiConfig,
    pub llm: LlmConfig,
    pub live_execution: LiveExecutionConfig,
}

/// Configuration for real on-chain execution. Loaded but ignored while
/// `live_execution_ready` is false in main.rs — the gate stays closed until
/// the executor + reconciliation paths land.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveExecutionConfig {
    /// Default chain key (matches keys in `routers`). e.g. "base", "base_sepolia".
    #[serde(default = "default_live_chain")]
    pub default_chain: String,
    /// JSON-RPC endpoint. Loaded from `ETH_RPC_URL` env var when not in TOML.
    /// Empty string means unset.
    #[serde(default)]
    pub rpc_url: String,
    /// Hex private key (`0x…`). Loaded from `PRIVATE_KEY` env var when not in
    /// TOML. Never echoed in logs. Empty means unset.
    #[serde(default)]
    pub private_key: String,
    /// Chain → Uniswap V2-compatible router address.
    #[serde(default = "default_routers")]
    pub routers: BTreeMap<String, String>,
    /// Manual ETH/USD price used to size native-token swaps. Replace with a
    /// Chainlink/TWAP read once the executor is wired.
    #[serde(default = "default_eth_price_usd")]
    pub eth_price_usd: Decimal,
    /// Hard floor on per-trade notional in USD. The executor refuses larger
    /// orders. Defaults to a small testnet ceiling.
    #[serde(default = "default_max_trade_usd")]
    pub max_trade_usd: Decimal,
    /// Wallet balance in USD below which the executor refuses to open new
    /// positions. Acts as a kill-floor on a draining wallet.
    #[serde(default)]
    pub wallet_floor_usd: Decimal,
    /// Maximum cumulative realized loss this session, in USD (positive
    /// number). When session realized PnL drops below -this_value, the
    /// circuit breaker refuses new orders. 0 disables the check.
    #[serde(default)]
    pub daily_loss_cap_usd: Decimal,
    /// Seconds from now until a swap deadline expires.
    #[serde(default = "default_swap_deadline_secs")]
    pub swap_deadline_secs: u64,
}

impl Default for LiveExecutionConfig {
    fn default() -> Self {
        Self {
            default_chain: default_live_chain(),
            rpc_url: String::new(),
            private_key: String::new(),
            routers: default_routers(),
            eth_price_usd: default_eth_price_usd(),
            max_trade_usd: default_max_trade_usd(),
            wallet_floor_usd: Decimal::ZERO,
            daily_loss_cap_usd: Decimal::ZERO,
            swap_deadline_secs: default_swap_deadline_secs(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct FileConfig {
    #[serde(default)]
    runtime: RuntimeConfig,
    #[serde(default)]
    observe: ObserveConfigFile,
    #[serde(default)]
    llm: LlmConfig,
    #[serde(default)]
    live_execution: LiveExecutionConfig,
    paper_trading: PaperTradingConfig,
    strategies: BTreeMap<String, StrategyProfileFile>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct ObserveConfigFile {
    #[serde(default = "default_log_filter")]
    log_filter: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StrategyProfileFile {
    description: String,
    max_position_size_usd: Decimal,
    max_slippage_bps: u16,
    risk_tolerance: RiskLevel,
    scan_interval_seconds: u64,
}

fn default_log_filter() -> String {
    "info".to_owned()
}

fn default_ollama_base_url() -> String {
    "http://127.0.0.1:11434".to_owned()
}

fn default_live_model() -> String {
    "qwen2.5:3b".to_owned()
}

fn default_critic_model() -> String {
    "qwen2.5:7b".to_owned()
}

fn default_enabled_strategies() -> Vec<String> {
    vec!["bridge".to_owned()]
}

fn default_request_timeout_ms() -> u64 {
    10_000
}

fn default_true() -> bool {
    true
}

fn default_live_chain() -> String {
    "base_sepolia".to_owned()
}

fn default_eth_price_usd() -> Decimal {
    Decimal::new(3000, 0)
}

fn default_max_trade_usd() -> Decimal {
    // Conservative testnet ceiling. Override in TOML / env for real budgets.
    Decimal::new(25, 0)
}

fn default_swap_deadline_secs() -> u64 {
    60
}

fn default_routers() -> BTreeMap<String, String> {
    let mut routers = BTreeMap::new();
    // Uniswap V2 Router02 on Ethereum mainnet
    routers.insert(
        "ethereum".to_owned(),
        "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D".to_owned(),
    );
    // Uniswap V2 Router02 on Base mainnet
    routers.insert(
        "base".to_owned(),
        "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24".to_owned(),
    );
    // Uniswap V2 Router02 on Base Sepolia (testnet)
    routers.insert(
        "base_sepolia".to_owned(),
        "0x1689E7B1F10000AE47eBfE339a4f69dECd19F602".to_owned(),
    );
    routers
}

impl AppConfig {
    pub fn load(path: &Path, overrides: CliOverrides) -> Result<Self, CoreError> {
        let builder = Config::builder()
            .add_source(File::from(path))
            .add_source(Environment::with_prefix("AST").separator("__"))
            .set_override_option("observe.log_filter", overrides.log_filter)?
            .set_override_option("paper_trading.enabled", overrides.paper_trading_enabled)?;

        let raw = builder.build()?.try_deserialize::<FileConfig>()?;
        let live_env = LiveExecutionEnv {
            rpc_url: std::env::var("ETH_RPC_URL").ok(),
            private_key: std::env::var("PRIVATE_KEY").ok(),
        };
        Self::from_file_config(raw, std::env::var("DEEPSEEK_API_KEY").ok(), live_env)
    }

    fn from_file_config(
        raw: FileConfig,
        deepseek_api_key: Option<String>,
        live_env: LiveExecutionEnv,
    ) -> Result<Self, CoreError> {

        let mut strategies = Vec::with_capacity(raw.strategies.len());
        for strategy_name in STRATEGY_ORDER {
            let Some(profile) = raw.strategies.get(strategy_name) else {
                return Err(CoreError::Validation(format!(
                    "missing strategy profile: {strategy_name}"
                )));
            };

            strategies.push(StrategyProfile {
                name: strategy_name.to_owned(),
                description: profile.description.clone(),
                max_position_size_usd: Usd::new(profile.max_position_size_usd)?,
                max_slippage_bps: profile.max_slippage_bps,
                risk_tolerance: profile.risk_tolerance.clone(),
                scan_interval_seconds: profile.scan_interval_seconds,
                paper_trading: raw.paper_trading.enabled,
            });
        }

        // Env vars fill in only when the TOML field is empty. Lets operators
        // commit non-secret config (chain, routers, eth_price) and keep
        // secrets in .env.
        let mut live_execution = raw.live_execution;
        if live_execution.rpc_url.is_empty() {
            if let Some(rpc_url) = live_env.rpc_url {
                live_execution.rpc_url = rpc_url;
            }
        }
        if live_execution.private_key.is_empty() {
            if let Some(private_key) = live_env.private_key {
                live_execution.private_key = private_key;
            }
        }

        Ok(Self {
            runtime: raw.runtime,
            strategies,
            paper_trading: raw.paper_trading,
            observe: ObserveConfig {
                log_filter: raw.observe.log_filter,
            },
            api: ApiConfig { deepseek_api_key },
            llm: raw.llm,
            live_execution,
        })
    }

    #[cfg(test)]
    fn from_toml_str(document: &str, overrides: CliOverrides, api_key: &str) -> Result<Self, CoreError> {
        let builder = Config::builder()
            .add_source(File::from_str(document, FileFormat::Toml))
            .set_override_option("observe.log_filter", overrides.log_filter)?
            .set_override_option("paper_trading.enabled", overrides.paper_trading_enabled)?;

        let raw = builder.build()?.try_deserialize::<FileConfig>()?;
        let api_key = if api_key.is_empty() {
            None
        } else {
            Some(api_key.to_owned())
        };
        Self::from_file_config(raw, api_key, LiveExecutionEnv::default())
    }
}

#[derive(Debug, Default)]
struct LiveExecutionEnv {
    rpc_url: Option<String>,
    private_key: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::{AppConfig, CliOverrides};
    use crate::RiskLevel;

    const CONFIG: &str = r#"
        [runtime]
        position_monitor_interval_seconds = 30
        shutdown_grace_period_ms = 1000
        recent_event_capacity = 5000
        state_dir = "data"

        [observe]
        log_filter = "debug"

        [llm]
        enabled = true
        base_url = "http://127.0.0.1:11434"
        live_model = "qwen2.5:3b"
        critic_model = "qwen2.5:7b"
        enabled_strategies = ["bridge"]
        request_timeout_ms = 10000

        [paper_trading]
        enabled = true
        initial_balance_usd = "10000"
        default_slippage_model = "simulated"
        use_live_market_data = true
        use_live_risk_checks = true

        [strategies.thrive]
        description = "Aggressive high-growth entries"
        max_position_size_usd = 500
        max_slippage_bps = 250
        risk_tolerance = "high"
        scan_interval_seconds = 30

        [strategies.swift]
        description = "Fast entry on new pairs"
        max_position_size_usd = 200
        max_slippage_bps = 200
        risk_tolerance = "medium"
        scan_interval_seconds = 15

        [strategies.echo]
        description = "Mirrors smart wallet moves"
        max_position_size_usd = 300
        max_slippage_bps = 150
        risk_tolerance = "medium"
        scan_interval_seconds = 60

        [strategies.bridge]
        description = "Cross-venue arbitrage"
        max_position_size_usd = 400
        max_slippage_bps = 50
        risk_tolerance = "low"
        scan_interval_seconds = 10

        [strategies.flow]
        description = "Liquidity event plays"
        max_position_size_usd = 250
        max_slippage_bps = 200
        risk_tolerance = "medium"
        scan_interval_seconds = 30

        [strategies.clarity]
        description = "Oracle manipulation detection"
        max_position_size_usd = 350
        max_slippage_bps = 100
        risk_tolerance = "low"
        scan_interval_seconds = 60

        [strategies.nurture]
        description = "Yield cultivation"
        max_position_size_usd = 150
        max_slippage_bps = 100
        risk_tolerance = "low"
        scan_interval_seconds = 120

        [strategies.insight]
        description = "Contract-analysis-based opportunities"
        max_position_size_usd = 200
        max_slippage_bps = 250
        risk_tolerance = "high"
        scan_interval_seconds = 45
    "#;

    #[test]
    fn config_loads_all_strategy_profiles() {
        let config = AppConfig::from_toml_str(
            CONFIG,
            CliOverrides {
                log_filter: Some("trace".to_owned()),
                paper_trading_enabled: None,
            },
            "secret",
        )
        .expect("config should load");

        assert_eq!(config.strategies.len(), 8);
        assert_eq!(config.observe.log_filter, "trace");
        assert_eq!(config.strategies[0].name, "thrive");
        assert_eq!(config.strategies[7].risk_tolerance, RiskLevel::High);
        assert!(config.paper_trading.enabled);
        assert!(config.paper_trading.use_live_market_data);
        assert!(config.paper_trading.use_live_risk_checks);
        assert_eq!(config.api.deepseek_api_key.as_deref(), Some("secret"));
        assert!(config.llm.enabled);
        assert_eq!(config.llm.live_model, "qwen2.5:3b");
    }

    #[test]
    fn config_loads_without_deepseek_key_for_paper_mode() {
        let config = AppConfig::from_toml_str(CONFIG, CliOverrides::default(), "")
            .expect("config should load without deepseek key");

        assert_eq!(config.api.deepseek_api_key, None);
        assert!(config.paper_trading.enabled);
    }

    #[test]
    fn live_execution_defaults_when_section_missing() {
        // Existing configs without [live_execution] still load — defaults fire.
        let config = AppConfig::from_toml_str(CONFIG, CliOverrides::default(), "")
            .expect("config should load with default live_execution");

        let live = &config.live_execution;
        assert_eq!(live.default_chain, "base_sepolia");
        assert!(live.rpc_url.is_empty());
        assert!(live.private_key.is_empty());
        assert!(live.routers.contains_key("base_sepolia"));
        assert!(live.routers.contains_key("base"));
        assert!(live.routers.contains_key("ethereum"));
        assert_eq!(live.eth_price_usd, rust_decimal::Decimal::new(3000, 0));
        assert_eq!(live.max_trade_usd, rust_decimal::Decimal::new(25, 0));
        assert_eq!(live.swap_deadline_secs, 60);
    }

    #[test]
    fn live_execution_overrides_from_toml() {
        let custom = format!(
            "{CONFIG}\n[live_execution]\ndefault_chain = \"base\"\nrpc_url = \"https://example/rpc\"\nmax_trade_usd = 100\nwallet_floor_usd = 50\n"
        );
        let config = AppConfig::from_toml_str(&custom, CliOverrides::default(), "")
            .expect("config with explicit live_execution should load");

        assert_eq!(config.live_execution.default_chain, "base");
        assert_eq!(config.live_execution.rpc_url, "https://example/rpc");
        assert_eq!(
            config.live_execution.max_trade_usd,
            rust_decimal::Decimal::new(100, 0)
        );
        assert_eq!(
            config.live_execution.wallet_floor_usd,
            rust_decimal::Decimal::new(50, 0)
        );
    }
}
