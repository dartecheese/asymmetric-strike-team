use std::ffi::OsString;
use std::path::{Path, PathBuf};

use config::{Config, Environment, File, FileFormat};
use serde::{Deserialize, Serialize};

use crate::error::{AstError, Result};

const DEFAULT_CONFIG_PATH: &str = "config/default.toml";

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

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SecretConfig {
    pub rpc_url: Option<String>,
    pub exchange_api_key: Option<String>,
    pub exchange_api_secret: Option<String>,
    pub private_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct StartupConfig {
    pub app: AppConfig,
    pub secrets: SecretConfig,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CliOverrides {
    config_path: Option<PathBuf>,
    scan_interval_ms: Option<u64>,
    paper_mode: Option<bool>,
}

impl AppConfig {
    pub fn load() -> Result<Self> {
        Ok(StartupConfig::load()?.app)
    }

    pub fn load_from_sources(config_path: &Path, overrides: &CliOverrides) -> Result<Self> {
        let config_path = config_path
            .to_str()
            .ok_or_else(|| AstError::Config("config path must be valid UTF-8".into()))?;

        let builder = Config::builder()
            .add_source(File::new(config_path, FileFormat::Toml).required(true))
            .add_source(Environment::with_prefix("AST").separator("__"))
            .set_override_option(
                "scan_interval_ms",
                overrides
                    .scan_interval_ms
                    .map(i64::try_from)
                    .transpose()
                    .map_err(|_| {
                        AstError::Config("scan_interval_ms override exceeds supported range".into())
                    })?,
            )
            .map_err(config_error)?
            .set_override_option("paper_mode", overrides.paper_mode)
            .map_err(config_error)?;

        builder
            .build()
            .map_err(config_error)?
            .try_deserialize()
            .map_err(config_error)
    }
}

impl StartupConfig {
    pub fn load() -> Result<Self> {
        let overrides = CliOverrides::parse(std::env::args_os())?;
        let config_path = overrides
            .config_path
            .clone()
            .unwrap_or_else(|| PathBuf::from(DEFAULT_CONFIG_PATH));

        Ok(Self {
            app: AppConfig::load_from_sources(&config_path, &overrides)?,
            secrets: SecretConfig::from_env(),
        })
    }
}

impl SecretConfig {
    pub fn from_env() -> Self {
        Self {
            rpc_url: std::env::var("AST_RPC_URL").ok(),
            exchange_api_key: std::env::var("AST_EXCHANGE_API_KEY").ok(),
            exchange_api_secret: std::env::var("AST_EXCHANGE_API_SECRET").ok(),
            private_key: std::env::var("AST_PRIVATE_KEY").ok(),
        }
    }
}

impl CliOverrides {
    pub fn parse<I>(args: I) -> Result<Self>
    where
        I: IntoIterator<Item = OsString>,
    {
        let mut parsed = Self::default();
        let args = args
            .into_iter()
            .map(|arg| {
                arg.into_string()
                    .map_err(|_| AstError::Config("CLI arguments must be valid UTF-8".into()))
            })
            .collect::<Result<Vec<_>>>()?;

        for arg in args.into_iter().skip(1) {
            if let Some(value) = arg.strip_prefix("--config=") {
                parsed.config_path = Some(PathBuf::from(value));
                continue;
            }
            if let Some(value) = arg.strip_prefix("--scan-interval-ms=") {
                parsed.scan_interval_ms = Some(parse_u64_arg("scan-interval-ms", value)?);
                continue;
            }
            if arg == "--paper-mode" {
                parsed.paper_mode = Some(true);
                continue;
            }
            if arg == "--live-mode" {
                parsed.paper_mode = Some(false);
                continue;
            }
            if is_secret_flag(&arg) {
                return Err(AstError::Config(format!(
                    "secret CLI flag `{arg}` is not allowed; use environment variables instead"
                )));
            }
        }

        Ok(parsed)
    }
}

fn parse_u64_arg(flag: &str, value: &str) -> Result<u64> {
    value
        .parse::<u64>()
        .map_err(|_| AstError::Config(format!("`--{flag}` requires an unsigned integer value")))
}

fn is_secret_flag(flag: &str) -> bool {
    matches!(
        flag.split('=').next(),
        Some("--rpc-url" | "--exchange-api-key" | "--exchange-api-secret" | "--private-key")
    )
}

fn config_error(error: config::ConfigError) -> AstError {
    AstError::Config(error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cli_overrides_reject_secret_flags() {
        let error = CliOverrides::parse([
            OsString::from("ast"),
            OsString::from("--private-key=secret"),
        ])
        .expect_err("secrets must stay out of CLI args");

        assert!(matches!(error, AstError::Config(_)));
    }

    #[test]
    fn cli_overrides_capture_supported_flags() {
        let overrides = CliOverrides::parse([
            OsString::from("ast"),
            OsString::from("--config=/tmp/test.toml"),
            OsString::from("--scan-interval-ms=2500"),
            OsString::from("--live-mode"),
        ])
        .expect("supported flags should parse");

        assert_eq!(overrides.config_path, Some(PathBuf::from("/tmp/test.toml")));
        assert_eq!(overrides.scan_interval_ms, Some(2500));
        assert_eq!(overrides.paper_mode, Some(false));
    }
}
