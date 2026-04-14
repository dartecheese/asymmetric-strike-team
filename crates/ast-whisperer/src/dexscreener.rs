use std::{
    collections::{HashMap, HashSet},
    sync::Arc,
    time::{Duration, Instant},
};

use ast_core::{AstError, Result, Signal, SignalMetrics, SignalSource, Token};
use reqwest::Client;
use rust_decimal::Decimal;
use rust_decimal::prelude::ToPrimitive;
use serde::Deserialize;
use tokio::sync::Mutex;
use tracing::warn;

use crate::Whisperer;

const DEXSCREENER_BASE_URL: &str = "https://api.dexscreener.com";
const DEFAULT_TIMEOUT_MS: u64 = 5_000;
const DEFAULT_RATE_LIMIT_DELAY_MS: u64 = 250;
const DEFAULT_MIN_LIQUIDITY_USD: i64 = 10_000;
const DEFAULT_MIN_VELOCITY_SCORE: u16 = 50;

#[derive(Debug, Clone)]
pub struct DexScreenerConfig {
    pub base_url: String,
    pub request_timeout: Duration,
    pub min_request_spacing: Duration,
    pub min_liquidity_usd: Decimal,
    pub min_velocity_score: u16,
}

impl Default for DexScreenerConfig {
    fn default() -> Self {
        Self {
            base_url: DEXSCREENER_BASE_URL.to_string(),
            request_timeout: Duration::from_millis(DEFAULT_TIMEOUT_MS),
            min_request_spacing: Duration::from_millis(DEFAULT_RATE_LIMIT_DELAY_MS),
            min_liquidity_usd: Decimal::from(DEFAULT_MIN_LIQUIDITY_USD),
            min_velocity_score: DEFAULT_MIN_VELOCITY_SCORE,
        }
    }
}

#[derive(Debug)]
pub struct DexScreenerClient {
    http: Client,
    config: DexScreenerConfig,
    next_request_at: Mutex<Instant>,
}

impl DexScreenerClient {
    pub fn new(config: DexScreenerConfig) -> Result<Self> {
        let http = Client::builder()
            .timeout(config.request_timeout)
            .user_agent("AsymmetricStrikeTeam/0.1")
            .build()
            .map_err(|error| {
                AstError::Config(format!("failed to build DexScreener client: {error}"))
            })?;

        Ok(Self {
            http,
            config,
            next_request_at: Mutex::new(Instant::now()),
        })
    }

    pub async fn latest_profiles(&self) -> Result<Vec<TokenProfile>> {
        self.get_json::<Vec<TokenProfile>>("/token-profiles/latest/v1")
            .await
    }

    pub async fn top_boosts(&self) -> Result<Vec<TokenBoost>> {
        self.get_json::<Vec<TokenBoost>>("/token-boosts/top/v1")
            .await
    }

    pub async fn pairs_for_token(&self, token_address: &str) -> Result<Vec<Pair>> {
        let path = format!("/latest/dex/tokens/{token_address}");
        let response = self.get_json::<TokenPairsResponse>(&path).await?;
        Ok(response.pairs)
    }

    async fn get_json<T>(&self, path: &str) -> Result<T>
    where
        T: for<'de> Deserialize<'de>,
    {
        self.wait_for_rate_limit().await;

        let url = format!("{}{}", self.config.base_url, path);
        let response = self.http.get(&url).send().await.map_err(|error| {
            map_reqwest_error("DexScreener", self.config.request_timeout, error)
        })?;

        response
            .error_for_status()
            .map_err(|error| map_reqwest_error("DexScreener", self.config.request_timeout, error))?
            .json::<T>()
            .await
            .map_err(|error| AstError::ExternalService {
                service: "DexScreener",
                message: format!("invalid JSON response: {error}"),
            })
    }

    async fn wait_for_rate_limit(&self) {
        let mut guard = self.next_request_at.lock().await;
        let now = Instant::now();
        if *guard > now {
            tokio::time::sleep(*guard - now).await;
        }
        *guard = Instant::now() + self.config.min_request_spacing;
    }
}

#[derive(Debug)]
pub struct DexScreenerWhisperer {
    client: Arc<DexScreenerClient>,
    seen_tokens: Mutex<HashSet<String>>,
}

impl DexScreenerWhisperer {
    pub fn new(config: DexScreenerConfig) -> Result<Self> {
        Ok(Self {
            client: Arc::new(DexScreenerClient::new(config)?),
            seen_tokens: Mutex::new(HashSet::new()),
        })
    }

    async fn build_candidates(&self) -> Result<Vec<CandidateSignal>> {
        let profiles = match self.client.latest_profiles().await {
            Ok(profiles) => profiles,
            Err(error) => {
                warn!(error = %error, "DexScreener profiles unavailable");
                return Ok(Vec::new());
            }
        };

        let boosts = match self.client.top_boosts().await {
            Ok(boosts) => boosts,
            Err(error) => {
                warn!(error = %error, "DexScreener boosts unavailable");
                Vec::new()
            }
        };

        let seen_tokens = self.seen_tokens.lock().await.clone();
        let mut candidates = HashMap::<String, CandidateSignal>::new();

        for profile in profiles {
            let Some(token) = profile.token() else {
                continue;
            };

            if seen_tokens.contains(&token.address.as_str().to_lowercase()) {
                continue;
            }

            let pair = self.best_pair(token.address.as_str()).await.ok().flatten();
            let score = compute_signal_score(pair.as_ref(), false);
            let candidate = CandidateSignal::from_profile(token, profile, pair, score);
            candidates.insert(candidate.token.address.as_str().to_lowercase(), candidate);
        }

        for boost in boosts {
            let Some(token) = boost.token() else {
                continue;
            };

            if seen_tokens.contains(&token.address.as_str().to_lowercase()) {
                continue;
            }

            if let Some(existing) = candidates.get_mut(&token.address.as_str().to_lowercase()) {
                existing.source = SignalSource::DexProfileAndBoost;
                existing.metrics.boost_score_bps = existing
                    .metrics
                    .boost_score_bps
                    .saturating_add(boost.boost_score_bps());
                existing.confidence_bps = existing
                    .confidence_bps
                    .saturating_add(boost.boost_score_bps())
                    .min(10_000);
                existing.reasoning =
                    format!("{} | matched DexScreener boost feed", existing.reasoning);
                continue;
            }

            let pair = self.best_pair(token.address.as_str()).await.ok().flatten();
            let score =
                compute_signal_score(pair.as_ref(), true).saturating_add(boost.boost_score_bps());
            let candidate = CandidateSignal::from_boost(token, boost, pair, score);
            candidates.insert(candidate.token.address.as_str().to_lowercase(), candidate);
        }

        Ok(candidates.into_values().collect())
    }

    async fn best_pair(&self, token_address: &str) -> Result<Option<Pair>> {
        let pairs = self.client.pairs_for_token(token_address).await?;
        Ok(pairs
            .into_iter()
            .filter(|pair| pair.supported_chain())
            .filter(|pair| {
                pair.liquidity_usd().unwrap_or_default() >= self.client.config.min_liquidity_usd
            })
            .max_by(|left, right| left.liquidity_usd().cmp(&right.liquidity_usd())))
    }
}

#[async_trait::async_trait]
impl Whisperer for DexScreenerWhisperer {
    async fn scan(&self) -> Result<Vec<Signal>> {
        let mut candidates = self.build_candidates().await?;
        candidates.retain(|candidate| {
            candidate.metrics.velocity_score >= self.client.config.min_velocity_score
        });
        candidates.sort_by(|left, right| right.confidence_bps.cmp(&left.confidence_bps));

        let mut seen_tokens = self.seen_tokens.lock().await;
        let mut signals = Vec::new();
        for candidate in candidates {
            seen_tokens.insert(candidate.token.address.as_str().to_lowercase());
            signals.push(candidate.into_signal());
        }

        Ok(signals)
    }
}

#[derive(Debug, Clone)]
struct CandidateSignal {
    token: Token,
    confidence_bps: u16,
    source: SignalSource,
    reasoning: String,
    metrics: SignalMetrics,
}

impl CandidateSignal {
    fn from_profile(
        token: Token,
        profile: TokenProfile,
        pair: Option<Pair>,
        confidence_bps: u16,
    ) -> Self {
        let metrics = pair_metrics(pair.as_ref(), false);
        Self {
            token,
            confidence_bps,
            source: SignalSource::DexProfile,
            reasoning: format!(
                "DexScreener profile candidate: {}",
                profile
                    .description
                    .unwrap_or_else(|| "profile listed without description".to_string())
            ),
            metrics,
        }
    }

    fn from_boost(
        token: Token,
        boost: TokenBoost,
        pair: Option<Pair>,
        confidence_bps: u16,
    ) -> Self {
        let mut metrics = pair_metrics(pair.as_ref(), true);
        metrics.boost_score_bps = boost.boost_score_bps();

        Self {
            token,
            confidence_bps,
            source: SignalSource::DexBoost,
            reasoning: format!(
                "DexScreener boosted candidate with total boost {}",
                boost.total_amount.unwrap_or_default()
            ),
            metrics,
        }
    }

    fn into_signal(self) -> Signal {
        Signal {
            token: self.token,
            confidence_bps: self.confidence_bps,
            source: self.source,
            reasoning: self.reasoning,
            metrics: self.metrics,
        }
    }
}

fn pair_metrics(pair: Option<&Pair>, include_boost: bool) -> SignalMetrics {
    let Some(pair) = pair else {
        return SignalMetrics {
            boost_score_bps: if include_boost { 1_500 } else { 0 },
            ..SignalMetrics::default()
        };
    };

    let price_h1_bps = percent_string_to_bps(pair.price_change.h1.as_deref());
    let price_h6_bps = percent_string_to_bps(pair.price_change.h6.as_deref());
    let liquidity = pair.liquidity_usd();
    let volume = pair.volume_24h_usd();

    SignalMetrics {
        liquidity_usd: liquidity,
        volume_24h_usd: volume,
        velocity_score: compute_signal_score(Some(pair), include_boost),
        price_change_h1_bps: price_h1_bps,
        price_change_h6_bps: price_h6_bps,
        freshness_bonus_bps: freshness_bonus_bps(pair.pair_created_at),
        boost_score_bps: if include_boost { 1_500 } else { 0 },
    }
}

fn compute_signal_score(pair: Option<&Pair>, include_boost: bool) -> u16 {
    let Some(pair) = pair else {
        return if include_boost { 1_500 } else { 500 };
    };

    let liquidity = pair.liquidity_usd().unwrap_or_default();
    let volume = pair.volume_24h_usd().unwrap_or_default();
    let velocity_component = if liquidity > Decimal::ZERO {
        ((volume / liquidity) * Decimal::from(1_000))
            .round()
            .to_u16()
            .unwrap_or(u16::MAX)
            .min(4_000)
    } else {
        0
    };

    let h1_component = percent_string_to_bps(pair.price_change.h1.as_deref())
        .unsigned_abs()
        .min(2_000) as u16;
    let h6_component = (percent_string_to_bps(pair.price_change.h6.as_deref()).unsigned_abs() / 2)
        .min(1_000) as u16;
    let freshness_component = freshness_bonus_bps(pair.pair_created_at);
    let boost_component = if include_boost { 1_500 } else { 0 };
    let liquidity_penalty = if liquidity < Decimal::from(DEFAULT_MIN_LIQUIDITY_USD) {
        5_000
    } else {
        0
    };

    velocity_component
        .saturating_add(h1_component)
        .saturating_add(h6_component)
        .saturating_add(freshness_component)
        .saturating_add(boost_component)
        .saturating_sub(liquidity_penalty)
}

fn freshness_bonus_bps(pair_created_at: Option<u64>) -> u16 {
    let Some(created_at_ms) = pair_created_at else {
        return 0;
    };

    let now_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;

    let age_hours = now_ms.saturating_sub(created_at_ms) / 3_600_000;
    match age_hours {
        0 => 2_000,
        1..=5 => 1_000,
        6..=23 => 500,
        _ => 0,
    }
}

fn percent_string_to_bps(value: Option<&str>) -> i32 {
    let parsed = value
        .and_then(|value| value.parse::<f64>().ok())
        .unwrap_or_default();
    (parsed * 100.0).round() as i32
}

fn map_reqwest_error(service: &'static str, timeout: Duration, error: reqwest::Error) -> AstError {
    if error.is_timeout() {
        AstError::Timeout {
            service,
            duration_ms: timeout.as_millis() as u64,
        }
    } else {
        AstError::ExternalService {
            service,
            message: error.to_string(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct TokenProfile {
    #[serde(rename = "chainId")]
    pub chain_id: String,
    #[serde(rename = "tokenAddress")]
    pub token_address: String,
    pub symbol: Option<String>,
    pub description: Option<String>,
}

impl TokenProfile {
    fn token(&self) -> Option<Token> {
        let chain = chain_to_evm(&self.chain_id)?;
        Token::new(
            self.token_address.clone(),
            chain,
            self.symbol.clone().unwrap_or_else(|| "UNKNOWN".to_string()),
            18,
        )
        .ok()
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct TokenBoost {
    #[serde(rename = "chainId")]
    pub chain_id: String,
    #[serde(rename = "tokenAddress")]
    pub token_address: String,
    pub symbol: Option<String>,
    #[serde(rename = "totalAmount")]
    pub total_amount: Option<i64>,
}

impl TokenBoost {
    fn token(&self) -> Option<Token> {
        let chain = chain_to_evm(&self.chain_id)?;
        Token::new(
            self.token_address.clone(),
            chain,
            self.symbol.clone().unwrap_or_else(|| "UNKNOWN".to_string()),
            18,
        )
        .ok()
    }

    fn boost_score_bps(&self) -> u16 {
        let raw = self.total_amount.unwrap_or_default().max(0) as u16;
        raw.saturating_div(10).min(1_500)
    }
}

#[derive(Debug, Clone, Deserialize)]
struct TokenPairsResponse {
    #[serde(default)]
    pairs: Vec<Pair>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Pair {
    #[serde(rename = "chainId")]
    pub chain_id: String,
    pub liquidity: Liquidity,
    pub volume: Volume,
    #[serde(rename = "priceChange")]
    pub price_change: PriceChange,
    #[serde(rename = "pairCreatedAt")]
    pub pair_created_at: Option<u64>,
}

impl Pair {
    fn supported_chain(&self) -> bool {
        chain_to_evm(&self.chain_id).is_some()
    }

    fn liquidity_usd(&self) -> Option<Decimal> {
        self.liquidity.usd.as_deref().and_then(parse_decimal)
    }

    fn volume_24h_usd(&self) -> Option<Decimal> {
        self.volume.h24.as_deref().and_then(parse_decimal)
    }
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Liquidity {
    pub usd: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Volume {
    pub h24: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct PriceChange {
    pub h1: Option<String>,
    pub h6: Option<String>,
}

fn parse_decimal(value: &str) -> Option<Decimal> {
    Decimal::from_str_exact(value).ok()
}

fn chain_to_evm(chain: &str) -> Option<&'static str> {
    match chain {
        "ethereum" => Some("1"),
        "bsc" => Some("56"),
        "arbitrum" => Some("42161"),
        "base" => Some("8453"),
        "polygon" => Some("137"),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn boosted_pairs_get_additional_signal_weight() {
        let pair = Pair {
            chain_id: "base".to_string(),
            liquidity: Liquidity {
                usd: Some("30000".to_string()),
            },
            volume: Volume {
                h24: Some("90000".to_string()),
            },
            price_change: PriceChange {
                h1: Some("12.5".to_string()),
                h6: Some("40.0".to_string()),
            },
            pair_created_at: None,
        };

        let unboosted = compute_signal_score(Some(&pair), false);
        let boosted = compute_signal_score(Some(&pair), true);

        assert!(boosted > unboosted);
    }

    #[test]
    fn unsupported_chains_are_filtered_out() {
        let profile = TokenProfile {
            chain_id: "solana".to_string(),
            token_address: "token".to_string(),
            symbol: Some("SOL".to_string()),
            description: None,
        };

        assert!(profile.token().is_none());
    }
}
