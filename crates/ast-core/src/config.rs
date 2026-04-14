use config::{Config, Environment, File};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrategyProfile {
    pub name: String,
    pub enabled: bool,
    pub max_positions: u32,
    pub max_slippage_bps: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub scan_interval_ms: u64,
    pub paper_mode: bool,
    pub strategy_profiles: Vec<StrategyProfile>,
}

impl AppConfig {
    pub fn load() -> Result<Self, config::ConfigError> {
        Config::builder()
            .add_source(File::with_name("config/default.toml"))
            .add_source(Environment::with_prefix("AST").separator("__"))
            .build()?
            .try_deserialize()
    }
}
