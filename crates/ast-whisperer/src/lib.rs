use std::collections::BTreeMap;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use alloy_primitives::Address;
use async_trait::async_trait;
use reqwest::Client;
use rust_decimal::Decimal;
use serde::Deserialize;
use thiserror::Error;
use tokio::sync::Mutex;
use tracing::warn;

use ast_core::{Chain, Signal, StrategyProfile, Token, Usd, Venue};

#[derive(Debug, Error)]
pub enum WhispererError {
    #[error("request failed: {0}")]
    Request(String),
    #[error("response parsing failed: {0}")]
    Parse(String),
    #[error("signal build failed: {0}")]
    SignalBuild(String),
}

#[async_trait]
pub trait SignalScanner: Send + Sync {
    async fn scan(&self) -> Result<Vec<Signal>, WhispererError>;
}

#[derive(Debug, Clone)]
pub struct DexScreenerWhisperer {
    strategy: StrategyProfile,
    client: Client,
    paper_mode: bool,
    min_spacing: Duration,
    last_scan: Arc<Mutex<Option<std::time::Instant>>>,
}

impl DexScreenerWhisperer {
    pub fn new(strategy: StrategyProfile, paper_mode: bool) -> Self {
        Self {
            strategy,
            client: Client::new(),
            paper_mode,
            min_spacing: Duration::from_millis(500),
            last_scan: Arc::new(Mutex::new(None)),
        }
    }

    async fn rate_limit(&self) {
        let mut guard = self.last_scan.lock().await;
        if let Some(last_scan) = *guard {
            let elapsed = last_scan.elapsed();
            if elapsed < self.min_spacing {
                tokio::time::sleep(self.min_spacing - elapsed).await;
            }
        }
        *guard = Some(std::time::Instant::now());
    }

    async fn fetch_live_signals(&self) -> Result<Vec<Signal>, WhispererError> {
        let query = self.discovery_query();
        let url = format!("https://api.dexscreener.com/latest/dex/search/?q={query}");
        let response = self
            .client
            .get(url)
            .send()
            .await
            .map_err(|error| WhispererError::Request(error.to_string()))?;
        let status = response.status();
        if !status.is_success() {
            return Err(WhispererError::Request(format!(
                "dexscreener returned status {status}"
            )));
        }

        let payload = response
            .json::<DexScreenerResponse>()
            .await
            .map_err(|error| WhispererError::Parse(error.to_string()))?;

        let mut signals = Vec::new();
        for pair in payload.pairs.into_iter().take(3) {
            signals.push(self.pair_to_signal(pair)?);
        }

        if signals.is_empty() {
            return Err(WhispererError::Parse(
                "dexscreener returned no usable pairs".to_owned(),
            ));
        }

        Ok(signals)
    }

    fn discovery_query(&self) -> &'static str {
        match self.strategy.name.as_str() {
            "bridge" => "weth",
            "clarity" => "usdc",
            "nurture" => "yield",
            "insight" => "ai",
            _ => "base",
        }
    }

    fn pair_to_signal(&self, pair: DexPair) -> Result<Signal, WhispererError> {
        let chain = parse_chain(&pair.chain_id);
        let address = pair
            .base_token
            .address
            .parse::<Address>()
            .unwrap_or(Address::ZERO);
        let router = pair
            .pair_address
            .parse::<Address>()
            .unwrap_or(Address::ZERO);
        let price = parse_usd(pair.price_usd)?;
        let volume = parse_usd(pair.volume.h24.unwrap_or_default())?;
        let liquidity = parse_usd(pair.liquidity.usd.unwrap_or_default())?;
        let target_notional_usd = if self.strategy.max_position_size_usd < liquidity {
            self.strategy.max_position_size_usd.clone()
        } else {
            liquidity.clone()
        };

        let mut metadata = BTreeMap::new();
        metadata.insert("source".to_owned(), "dexscreener".to_owned());
        metadata.insert("pair_address".to_owned(), pair.pair_address);

        Ok(Signal {
            id: format!("{}-{}", self.strategy.name, timestamp_ms()),
            token: Token {
                address,
                chain: chain.clone(),
                symbol: pair.base_token.symbol,
                decimals: 18,
            },
            venue: Venue::Dex {
                chain,
                router,
            },
            price_usd: price,
            volume_24h_usd: volume,
            liquidity_usd: liquidity,
            target_notional_usd,
            timestamp_ms: timestamp_ms(),
            metadata,
        })
    }

    fn mock_signals(&self) -> Result<Vec<Signal>, WhispererError> {
        let now = timestamp_ms();
        let seed = match self.strategy.name.as_str() {
            "thrive" => ("THRV", Decimal::new(145, 2), Decimal::new(250_000, 0), Decimal::new(80_000, 0)),
            "swift" => ("SWFT", Decimal::new(92, 2), Decimal::new(120_000, 0), Decimal::new(60_000, 0)),
            "echo" => ("ECHO", Decimal::new(210, 2), Decimal::new(300_000, 0), Decimal::new(140_000, 0)),
            "bridge" => ("BRDG", Decimal::new(300, 2), Decimal::new(500_000, 0), Decimal::new(200_000, 0)),
            "flow" => ("FLOW", Decimal::new(175, 2), Decimal::new(180_000, 0), Decimal::new(90_000, 0)),
            "clarity" => ("CLAR", Decimal::new(240, 2), Decimal::new(220_000, 0), Decimal::new(150_000, 0)),
            "nurture" => ("NURT", Decimal::new(88, 2), Decimal::new(95_000, 0), Decimal::new(70_000, 0)),
            _ => ("INSG", Decimal::new(160, 2), Decimal::new(275_000, 0), Decimal::new(110_000, 0)),
        };

        let mut metadata = BTreeMap::new();
        metadata.insert("source".to_owned(), "paper_mock".to_owned());
        metadata.insert("strategy".to_owned(), self.strategy.name.clone());

        Ok(vec![Signal {
            id: format!("{}-{now}", self.strategy.name),
            token: Token {
                address: Address::ZERO,
                chain: Chain::Base,
                symbol: seed.0.to_owned(),
                decimals: 18,
            },
            venue: Venue::Dex {
                chain: Chain::Base,
                router: Address::ZERO,
            },
            price_usd: Usd::new(seed.1).map_err(|error| WhispererError::SignalBuild(error.to_string()))?,
            volume_24h_usd: Usd::new(seed.2)
                .map_err(|error| WhispererError::SignalBuild(error.to_string()))?,
            liquidity_usd: Usd::new(seed.3)
                .map_err(|error| WhispererError::SignalBuild(error.to_string()))?,
            target_notional_usd: self.strategy.max_position_size_usd.clone(),
            timestamp_ms: now,
            metadata,
        }])
    }
}

#[async_trait]
impl SignalScanner for DexScreenerWhisperer {
    async fn scan(&self) -> Result<Vec<Signal>, WhispererError> {
        self.rate_limit().await;

        match self.fetch_live_signals().await {
            Ok(signals) => Ok(signals),
            Err(error) if self.paper_mode => {
                warn!(
                    strategy = %self.strategy.name,
                    error = %error,
                    "falling back to mock whisperer data"
                );
                self.mock_signals()
            }
            Err(error) => Err(error),
        }
    }
}

#[derive(Debug, Deserialize)]
struct DexScreenerResponse {
    #[serde(default)]
    pairs: Vec<DexPair>,
}

#[derive(Debug, Deserialize)]
struct DexPair {
    #[serde(rename = "chainId")]
    chain_id: String,
    #[serde(rename = "pairAddress")]
    pair_address: String,
    #[serde(rename = "priceUsd")]
    price_usd: String,
    #[serde(rename = "baseToken")]
    base_token: DexToken,
    volume: DexVolume,
    liquidity: DexLiquidity,
}

#[derive(Debug, Deserialize)]
struct DexToken {
    address: String,
    symbol: String,
}

#[derive(Debug, Deserialize)]
struct DexVolume {
    #[serde(rename = "h24")]
    h24: Option<String>,
}

#[derive(Debug, Deserialize)]
struct DexLiquidity {
    usd: Option<String>,
}

fn parse_chain(value: &str) -> Chain {
    match value {
        "ethereum" => Chain::Ethereum,
        "arbitrum" => Chain::Arbitrum,
        "solana" => Chain::Solana,
        _ => Chain::Base,
    }
}

fn parse_usd(value: String) -> Result<Usd, WhispererError> {
    let decimal = value
        .parse::<Decimal>()
        .map_err(|error| WhispererError::Parse(error.to_string()))?;
    Usd::new(decimal).map_err(|error| WhispererError::SignalBuild(error.to_string()))
}

fn timestamp_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::DexScreenerWhisperer;
    use crate::SignalScanner;
    use ast_core::{RiskLevel, StrategyProfile, Usd};
    use rust_decimal::Decimal;

    #[tokio::test]
    async fn paper_mode_returns_mock_signal() {
        let strategy = StrategyProfile {
            name: "swift".to_owned(),
            description: "Fast entry on new pairs".to_owned(),
            max_position_size_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            max_slippage_bps: 200,
            risk_tolerance: RiskLevel::Medium,
            scan_interval_seconds: 15,
            paper_trading: true,
        };

        let whisperer = DexScreenerWhisperer::new(strategy, true);
        let signals = whisperer.scan().await.expect("scan should succeed");

        assert_eq!(signals.len(), 1);
        assert_eq!(signals[0].token.symbol, "SWFT");
    }
}
