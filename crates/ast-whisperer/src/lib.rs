use std::collections::BTreeMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use alloy_primitives::Address;
use async_trait::async_trait;
use reqwest::Client;
use rust_decimal::Decimal;
use serde::{Deserialize, Deserializer};
use serde_json::Value;
use thiserror::Error;
use tokio::sync::Mutex;
use tracing::warn;

use ast_core::{
    cache_json, cached_json, prepare_request, record_failure, record_success, Chain,
    ProviderFailureKind, Signal, StrategyProfile, Token, Usd, Venue,
};

/// Minimum 24-hour volume for a pool to be considered tradable.
/// Pools below this are "dead" — they may have locked liquidity but no swap
/// activity, so any meaningful fill blows past slippage limits.
/// A $200 position against a $1k/day pool is ~20% of daily flow — painful
/// but plausibly fillable; below that, give up at discovery time.
const MIN_VOLUME_24H_USD: i64 = 1_000;

const NOTABLE_DEXES: [NotableDex; 5] = [
    NotableDex::new("uniswap", "Uniswap", &["uniswap", "uniswap_v2", "uniswap_v3"]),
    NotableDex::new("aerodrome", "Aerodrome", &["aerodrome", "aerodrome-slipstream"]),
    NotableDex::new("pancakeswap", "PancakeSwap", &["pancakeswap", "pancakeswap_v2", "pancakeswap_v3"]),
    NotableDex::new("sushiswap", "SushiSwap", &["sushiswap", "sushi"]),
    NotableDex::new("camelot", "Camelot", &["camelot"]),
];

#[derive(Debug, Clone, Copy)]
struct NotableDex {
    key: &'static str,
    label: &'static str,
    aliases: &'static [&'static str],
}

impl NotableDex {
    const fn new(key: &'static str, label: &'static str, aliases: &'static [&'static str]) -> Self {
        Self { key, label, aliases }
    }
}

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
    live_data_enabled: bool,
    min_spacing: Duration,
    last_scan: Arc<Mutex<Option<Instant>>>,
    cached_live_signals: Arc<Mutex<Option<CachedSignalSet>>>,
}

#[derive(Debug, Clone)]
struct CachedSignalSet {
    signals: Vec<Signal>,
    provider: &'static str,
    cached_at: Instant,
}

impl DexScreenerWhisperer {
    pub fn new(strategy: StrategyProfile, paper_mode: bool, live_data_enabled: bool) -> Self {
        Self {
            strategy,
            client: Client::builder()
                .user_agent("asymmetric-strike-team/0.1")
                .build()
                .unwrap_or_else(|_| Client::new()),
            paper_mode,
            live_data_enabled,
            min_spacing: Duration::from_millis(500),
            last_scan: Arc::new(Mutex::new(None)),
            cached_live_signals: Arc::new(Mutex::new(None)),
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
        *guard = Some(Instant::now());
    }

    async fn fetch_live_signals(&self) -> Result<Vec<Signal>, WhispererError> {
        let mut failures = Vec::new();

        match self.fetch_dexscreener_signals().await {
            Ok(signals) if !signals.is_empty() => {
                self.cache_live_signals(&signals, "dexscreener").await;
                return Ok(signals);
            }
            Ok(_) => failures.push("dexscreener returned no signals".to_owned()),
            Err(error) => failures.push(format!("dexscreener: {error}")),
        }

        match self.fetch_geckoterminal_signals().await {
            Ok(signals) if !signals.is_empty() => {
                self.cache_live_signals(&signals, "geckoterminal").await;
                return Ok(signals);
            }
            Ok(_) => failures.push("geckoterminal returned no signals".to_owned()),
            Err(error) => failures.push(format!("geckoterminal: {error}")),
        }

        if let Some(cached) = self.cached_live_signals().await {
            return Ok(cached);
        }

        Err(WhispererError::Parse(format!(
            "live market providers exhausted: {}",
            failures.join(" | ")
        )))
    }

    async fn fetch_dexscreener_signals(&self) -> Result<Vec<Signal>, WhispererError> {
        for query in self.discovery_queries() {
            let encoded_query = query.replace(' ', "%20");
            let url = format!("https://api.dexscreener.com/latest/dex/search/?q={encoded_query}");
            let payload = self
                .get_json_with_retries("dexscreener", &url, Duration::from_secs(20), Duration::from_secs(120))
                .await?;
            let pairs = payload.get("pairs").and_then(Value::as_array).ok_or_else(|| {
                WhispererError::Parse("dexscreener response missing pairs array".to_owned())
            })?;

            let mut ranked_pairs = Vec::new();
            for pair in pairs.iter().take(30) {
                match serde_json::from_value::<DexPair>(pair.clone()) {
                    Ok(pair) => {
                        if !pair.is_supported_chain() {
                            continue;
                        }
                        let score = self.pair_score(&pair);
                        if score > 0 {
                            ranked_pairs.push((score, pair));
                        }
                    }
                    Err(error) => {
                        warn!(strategy = %self.strategy.name, query, error = %error, "skipping unparseable dexscreener pair");
                    }
                }
            }

            ranked_pairs.sort_by(|left, right| right.0.cmp(&left.0));
            let mut signals = Vec::new();
            for (_, pair) in ranked_pairs {
                match self.pair_to_signal(pair) {
                    Ok(signal) => {
                        signals.push(signal);
                        if signals.len() == 3 {
                            break;
                        }
                    }
                    Err(error) => {
                        warn!(strategy = %self.strategy.name, query, error = %error, "skipping unusable dexscreener pair");
                    }
                }
            }

            if !signals.is_empty() {
                return Ok(signals);
            }
        }

        Err(WhispererError::Parse(
            "dexscreener returned no usable supported-chain pairs".to_owned(),
        ))
    }

    async fn fetch_geckoterminal_signals(&self) -> Result<Vec<Signal>, WhispererError> {
        for query in self.discovery_queries() {
            let encoded_query = query.replace(' ', "%20");
            let url = format!("https://api.geckoterminal.com/api/v2/search/pools?query={encoded_query}");
            let payload = self
                .get_json_with_retries("geckoterminal", &url, Duration::from_secs(20), Duration::from_secs(120))
                .await?;
            let data = payload.get("data").and_then(Value::as_array).ok_or_else(|| {
                WhispererError::Parse("geckoterminal response missing data array".to_owned())
            })?;

            let included = payload
                .get("included")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            let mut ranked_pools = Vec::new();

            for pool in data.iter().take(30) {
                match GeckoPool::from_value(pool, &included) {
                    Ok(pool) => {
                        if !pool.is_supported_chain() {
                            continue;
                        }
                        let score = self.gecko_pool_score(&pool);
                        if score > 0 {
                            ranked_pools.push((score, pool));
                        }
                    }
                    Err(error) => warn!(strategy = %self.strategy.name, query, error = %error, "skipping unusable geckoterminal pool"),
                }
            }

            ranked_pools.sort_by(|left, right| right.0.cmp(&left.0));
            let mut signals = Vec::new();
            for (_, pool) in ranked_pools {
                match self.gecko_pool_to_signal(pool) {
                    Ok(signal) => {
                        signals.push(signal);
                        if signals.len() == 3 {
                            break;
                        }
                    }
                    Err(error) => warn!(strategy = %self.strategy.name, query, error = %error, "skipping invalid geckoterminal signal"),
                }
            }

            if !signals.is_empty() {
                return Ok(signals);
            }
        }

        Err(WhispererError::Parse(
            "geckoterminal returned no usable supported-chain pools".to_owned(),
        ))
    }

    async fn get_json_with_retries(
        &self,
        provider: &'static str,
        url: &str,
        fresh_ttl: Duration,
        stale_ttl: Duration,
    ) -> Result<Value, WhispererError> {
        if let Some(cached) = cached_json(url, fresh_ttl) {
            return Ok(cached);
        }

        let stale_cache = cached_json(url, stale_ttl);
        let mut last_error = None;
        for delay_ms in [0u64, 250, 750] {
            match prepare_request(provider, self.min_spacing) {
                Ok(wait_for) => {
                    let total_wait = wait_for + Duration::from_millis(delay_ms);
                    if total_wait > Duration::ZERO {
                        tokio::time::sleep(total_wait).await;
                    }
                }
                Err(cooldown) => {
                    if let Some(cached) = stale_cache.clone() {
                        warn!(strategy = %self.strategy.name, provider, retry_after_ms = cooldown.retry_after.as_millis() as u64, "provider cooling down; using stale cached market data");
                        return Ok(cached);
                    }
                    last_error = Some(format!("provider cooldown {}ms", cooldown.retry_after.as_millis()));
                    continue;
                }
            }

            match self.client.get(url).send().await {
                Ok(response) => {
                    let status = response.status();
                    if status.is_success() {
                        let payload = response
                            .json::<Value>()
                            .await
                            .map_err(|error| WhispererError::Parse(error.to_string()))?;
                        cache_json(url, &payload);
                        record_success(provider);
                        return Ok(payload);
                    }
                    if status.as_u16() == 429 {
                        record_failure(provider, ProviderFailureKind::RateLimited);
                    } else {
                        record_failure(provider, ProviderFailureKind::Other);
                    }
                    last_error = Some(format!("status {status}"));
                }
                Err(error) => {
                    record_failure(provider, ProviderFailureKind::Other);
                    last_error = Some(error.to_string());
                }
            }
        }

        if let Some(cached) = stale_cache {
            warn!(strategy = %self.strategy.name, provider, "live fetch retries exhausted; using stale cached market data");
            return Ok(cached);
        }

        Err(WhispererError::Request(format!(
            "request failed after retries: {}",
            last_error.unwrap_or_else(|| "unknown error".to_owned())
        )))
    }

    async fn cache_live_signals(&self, signals: &[Signal], provider: &'static str) {
        let mut cache = self.cached_live_signals.lock().await;
        *cache = Some(CachedSignalSet {
            signals: signals.to_vec(),
            provider,
            cached_at: Instant::now(),
        });
    }

    async fn cached_live_signals(&self) -> Option<Vec<Signal>> {
        let cache = self.cached_live_signals.lock().await;
        let cached = cache.as_ref()?;
        if cached.cached_at.elapsed() > Duration::from_secs(90) {
            return None;
        }

        let mut signals = cached.signals.clone();
        for signal in &mut signals {
            signal.id = format!("{}-cached-{}", self.strategy.name, timestamp_ms());
            signal.timestamp_ms = timestamp_ms();
            signal
                .metadata
                .insert("source".to_owned(), format!("{}_cached", cached.provider));
            signal
                .metadata
                .insert("cached_provider".to_owned(), cached.provider.to_owned());
        }
        Some(signals)
    }

    fn discovery_queries(&self) -> &'static [&'static str] {
        match self.strategy.name.as_str() {
            "thrive" => &["base meme", "base trending", "base"],
            "swift" => &["base new", "base trending", "base"],
            "echo" => &["smart money base", "base", "ethereum"],
            "bridge" => &["weth usdc", "arb usdc", "base weth"],
            "flow" => &["liquidity base", "base volume", "base"],
            "clarity" => &["usdc weth", "usdc base", "ethereum usdc"],
            "nurture" => &["yield base", "yield ethereum", "defi yield"],
            "insight" => &["ai base", "ai ethereum", "base"],
            _ => &["base"],
        }
    }

    fn pair_score(&self, pair: &DexPair) -> i64 {
        if pair.notable_dex().is_none() {
            return -1;
        }
        let liquidity = pair.liquidity.usd_decimal().unwrap_or_default();
        let volume = pair.volume.h24_decimal().unwrap_or_default();
        self.score_pair(
            pair.chain_id.as_str(),
            pair.price_usd.is_some(),
            liquidity,
            volume,
            pair.notable_dex(),
        )
    }

    fn gecko_pool_score(&self, pool: &GeckoPool) -> i64 {
        if pool.notable_dex().is_none() {
            return -1;
        }
        self.score_pair(
            pool.network.as_str(),
            pool.price_usd.is_some(),
            pool.reserve_usd,
            pool.volume_24h_usd,
            pool.notable_dex(),
        )
    }

    fn score_pair(
        &self,
        chain_hint: &str,
        price_present: bool,
        liquidity: Decimal,
        volume: Decimal,
        dex: Option<NotableDex>,
    ) -> i64 {
        if !price_present || liquidity <= Decimal::ZERO {
            return -1;
        }
        // Volume floor — dead pools (high TVL, no swaps) pass the liquidity
        // check trivially but blow past the slippage cap at fill time, so they
        // produce orders that never fill. The insight strategy traced 19,378
        // orders → 0 fills to this: every signal it found had liquidity in
        // the tens of thousands but 24h volume in the tens of dollars.
        if volume < Decimal::from(MIN_VOLUME_24H_USD) {
            return -1;
        }

        let mut score = 0i64;
        score += match chain_hint {
            "base" => 5_000,
            "ethereum" | "eth" => 4_000,
            "arbitrum" | "arbitrum_one" => 3_000,
            _ => 0,
        };
        score += liquidity.round_dp(0).to_string().parse::<i64>().unwrap_or(0).min(2_000_000);
        score += volume.round_dp(0).to_string().parse::<i64>().unwrap_or(0).min(1_000_000) / 2;
        if let Some(dex) = dex {
            score += 25_000;
            score += self.strategy_dex_bonus(dex);
        }
        score
    }

    fn strategy_dex_bonus(&self, dex: NotableDex) -> i64 {
        let ordered = match self.strategy.name.as_str() {
            "bridge" => ["uniswap", "aerodrome", "camelot", "sushiswap", "pancakeswap"],
            "swift" => ["aerodrome", "uniswap", "pancakeswap", "sushiswap", "camelot"],
            "thrive" => ["aerodrome", "pancakeswap", "uniswap", "sushiswap", "camelot"],
            "echo" => ["uniswap", "sushiswap", "aerodrome", "camelot", "pancakeswap"],
            "flow" => ["aerodrome", "uniswap", "camelot", "pancakeswap", "sushiswap"],
            "clarity" => ["uniswap", "camelot", "aerodrome", "sushiswap", "pancakeswap"],
            "nurture" => ["uniswap", "camelot", "sushiswap", "aerodrome", "pancakeswap"],
            "insight" => ["uniswap", "aerodrome", "sushiswap", "camelot", "pancakeswap"],
            _ => ["uniswap", "aerodrome", "pancakeswap", "sushiswap", "camelot"],
        };

        ordered
            .iter()
            .position(|key| *key == dex.key)
            .map(|rank| match rank {
                0 => 18_000,
                1 => 12_000,
                2 => 8_000,
                3 => 4_000,
                _ => 2_000,
            })
            .unwrap_or(0)
    }

    fn pair_to_signal(&self, pair: DexPair) -> Result<Signal, WhispererError> {
        let notable_dex = pair.notable_dex();
        let chain = parse_chain(&pair.chain_id);
        let address = pair.base_token.address.parse::<Address>().unwrap_or(Address::ZERO);
        let router = pair.pair_address.parse::<Address>().unwrap_or(Address::ZERO);
        let price = parse_usd(
            pair.price_usd
                .ok_or_else(|| WhispererError::Parse("missing priceUsd".to_owned()))?,
        )?;
        let volume = parse_usd(pair.volume.h24.unwrap_or_default())?;
        let liquidity = parse_usd(
            pair.liquidity
                .usd
                .ok_or_else(|| WhispererError::Parse("missing liquidity.usd".to_owned()))?,
        )?;
        self.build_signal(
            chain,
            address,
            router,
            pair.base_token.symbol,
            price,
            volume,
            liquidity,
            "dexscreener",
            vec![
                ("pair_address", pair.pair_address),
                ("query_strategy", self.strategy.name.clone()),
                ("dex_id", pair.dex_id.unwrap_or_else(|| "unknown".to_owned())),
                (
                    "dex_label",
                    notable_dex.map(|dex| dex.label.to_owned()).unwrap_or_else(|| "Unknown DEX".to_owned()),
                ),
                (
                    "strategy_dex_fit",
                    notable_dex
                        .map(|dex| self.strategy_dex_fit_label(dex).to_owned())
                        .unwrap_or_else(|| "unranked".to_owned()),
                ),
            ],
        )
    }

    fn gecko_pool_to_signal(&self, pool: GeckoPool) -> Result<Signal, WhispererError> {
        let notable_dex = pool.notable_dex();
        let chain = parse_chain(&pool.network);
        let address = pool.base_token_address.parse::<Address>().unwrap_or(Address::ZERO);
        let router = pool.pool_address.parse::<Address>().unwrap_or(Address::ZERO);
        let price = parse_usd(
            pool.price_usd
                .ok_or_else(|| WhispererError::Parse("missing base_token_price_usd".to_owned()))?,
        )?;
        let volume = Usd::new(pool.volume_24h_usd)
            .map_err(|error| WhispererError::SignalBuild(error.to_string()))?;
        let liquidity = Usd::new(pool.reserve_usd)
            .map_err(|error| WhispererError::SignalBuild(error.to_string()))?;
        self.build_signal(
            chain,
            address,
            router,
            pool.base_token_symbol,
            price,
            volume,
            liquidity,
            "geckoterminal",
            vec![
                ("pair_address", pool.pool_address),
                ("query_strategy", self.strategy.name.clone()),
                (
                    "dex_id",
                    pool.dex_id.clone().unwrap_or_else(|| "unknown".to_owned()),
                ),
                (
                    "dex_label",
                    notable_dex.map(|dex| dex.label.to_owned()).unwrap_or_else(|| "Unknown DEX".to_owned()),
                ),
                (
                    "strategy_dex_fit",
                    notable_dex
                        .map(|dex| self.strategy_dex_fit_label(dex).to_owned())
                        .unwrap_or_else(|| "unranked".to_owned()),
                ),
            ],
        )
    }

    fn strategy_dex_fit_label(&self, dex: NotableDex) -> &'static str {
        let bonus = self.strategy_dex_bonus(dex);
        match bonus {
            18_000 => "primary",
            12_000 => "strong",
            8_000 => "good",
            4_000 => "secondary",
            2_000 => "allowed",
            _ => "unranked",
        }
    }

    fn build_signal(
        &self,
        chain: Chain,
        address: Address,
        router: Address,
        symbol: String,
        price: Usd,
        volume: Usd,
        liquidity: Usd,
        source: &str,
        metadata_pairs: Vec<(&str, String)>,
    ) -> Result<Signal, WhispererError> {
        if liquidity.0 <= Decimal::ZERO {
            return Err(WhispererError::SignalBuild(
                "liquidity must be positive for live pair".to_owned(),
            ));
        }
        let target_notional_usd = if self.strategy.max_position_size_usd < liquidity {
            self.strategy.max_position_size_usd.clone()
        } else {
            liquidity.clone()
        };

        let mut metadata = BTreeMap::new();
        metadata.insert("source".to_owned(), source.to_owned());
        for (key, value) in metadata_pairs {
            metadata.insert(key.to_owned(), value);
        }

        Ok(Signal {
            id: format!("{}-{}", self.strategy.name, timestamp_ms()),
            token: Token {
                address,
                chain: chain.clone(),
                symbol,
                decimals: 18,
            },
            venue: Venue::Dex { chain, router },
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
            volume_24h_usd: Usd::new(seed.2).map_err(|error| WhispererError::SignalBuild(error.to_string()))?,
            liquidity_usd: Usd::new(seed.3).map_err(|error| WhispererError::SignalBuild(error.to_string()))?,
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

        if self.live_data_enabled {
            match self.fetch_live_signals().await {
                Ok(signals) => Ok(signals),
                Err(error) if self.paper_mode => {
                    warn!(strategy = %self.strategy.name, error = %error, "falling back to mock whisperer data");
                    self.mock_signals()
                }
                Err(error) => Err(error),
            }
        } else if self.paper_mode {
            self.mock_signals()
        } else {
            self.fetch_live_signals().await
        }
    }
}

#[derive(Debug, Deserialize)]
struct DexPair {
    #[serde(rename = "chainId")]
    chain_id: String,
    #[serde(rename = "dexId", default)]
    dex_id: Option<String>,
    #[serde(rename = "pairAddress")]
    pair_address: String,
    #[serde(rename = "priceUsd", default, deserialize_with = "de_opt_string_or_number")]
    price_usd: Option<String>,
    #[serde(rename = "baseToken")]
    base_token: DexToken,
    #[serde(default)]
    volume: DexVolume,
    #[serde(default)]
    liquidity: DexLiquidity,
}

impl DexPair {
    fn is_supported_chain(&self) -> bool {
        matches!(self.chain_id.as_str(), "base" | "ethereum" | "arbitrum")
    }

    fn notable_dex(&self) -> Option<NotableDex> {
        lookup_notable_dex(self.dex_id.as_deref())
    }
}

#[derive(Debug, Deserialize, Default)]
struct DexToken {
    #[serde(default)]
    address: String,
    #[serde(default)]
    symbol: String,
}

#[derive(Debug, Deserialize, Default)]
struct DexVolume {
    #[serde(rename = "h24", default, deserialize_with = "de_opt_string_or_number")]
    h24: Option<String>,
}

impl DexVolume {
    fn h24_decimal(&self) -> Option<Decimal> {
        self.h24.as_deref().and_then(|value| value.parse::<Decimal>().ok())
    }
}

#[derive(Debug, Deserialize, Default)]
struct DexLiquidity {
    #[serde(default, deserialize_with = "de_opt_string_or_number")]
    usd: Option<String>,
}

impl DexLiquidity {
    fn usd_decimal(&self) -> Option<Decimal> {
        self.usd.as_deref().and_then(|value| value.parse::<Decimal>().ok())
    }
}

#[derive(Debug)]
struct GeckoPool {
    network: String,
    dex_id: Option<String>,
    pool_address: String,
    base_token_address: String,
    base_token_symbol: String,
    price_usd: Option<String>,
    reserve_usd: Decimal,
    volume_24h_usd: Decimal,
}

impl GeckoPool {
    fn from_value(pool: &Value, included: &[Value]) -> Result<Self, WhispererError> {
        let attributes = pool
            .get("attributes")
            .and_then(Value::as_object)
            .ok_or_else(|| WhispererError::Parse("gecko pool missing attributes".to_owned()))?;
        let relationships = pool
            .get("relationships")
            .and_then(Value::as_object)
            .ok_or_else(|| WhispererError::Parse("gecko pool missing relationships".to_owned()))?;

        let network = pool
            .get("id")
            .and_then(Value::as_str)
            .and_then(|id| id.split('_').next())
            .unwrap_or("base")
            .to_owned();
        let pool_address = attributes
            .get("address")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_owned();
        let dex_id = attributes
            .get("dex_name")
            .and_then(Value::as_str)
            .map(|value| value.to_ascii_lowercase())
            .or_else(|| {
                pool.get("relationships")
                    .and_then(|value| value.get("dex"))
                    .and_then(|value| value.get("data"))
                    .and_then(|value| value.get("id"))
                    .and_then(Value::as_str)
                    .map(|value| value.to_ascii_lowercase())
            });
        let price_usd = attributes
            .get("base_token_price_usd")
            .and_then(|value| value.as_str().map(ToOwned::to_owned).or_else(|| value.as_f64().map(|v| v.to_string())));
        let reserve_usd = decimal_from_value(attributes.get("reserve_in_usd"))?.unwrap_or_default();
        let volume_24h_usd = attributes
            .get("volume_usd")
            .and_then(|value| value.get("h24"))
            .map(Some)
            .map(decimal_from_value)
            .transpose()?
            .flatten()
            .unwrap_or_default();

        let base_token_id = relationships
            .get("base_token")
            .and_then(|value| value.get("data"))
            .and_then(|value| value.get("id"))
            .and_then(Value::as_str)
            .unwrap_or_default();
        let mut base_token_address = String::new();
        let mut base_token_symbol = attributes
            .get("name")
            .and_then(Value::as_str)
            .and_then(|name| name.split('/').next())
            .map(|name| name.trim().to_owned())
            .unwrap_or_else(|| "UNK".to_owned());

        for item in included {
            if item.get("id").and_then(Value::as_str) != Some(base_token_id) {
                continue;
            }
            if let Some(token_attrs) = item.get("attributes").and_then(Value::as_object) {
                base_token_address = token_attrs
                    .get("address")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_owned();
                if let Some(symbol) = token_attrs.get("symbol").and_then(Value::as_str) {
                    base_token_symbol = symbol.to_owned();
                }
            }
        }

        Ok(Self {
            network,
            dex_id,
            pool_address,
            base_token_address,
            base_token_symbol,
            price_usd,
            reserve_usd,
            volume_24h_usd,
        })
    }

    fn is_supported_chain(&self) -> bool {
        matches!(self.network.as_str(), "base" | "eth" | "ethereum" | "arbitrum" | "arbitrum_one")
    }

    fn notable_dex(&self) -> Option<NotableDex> {
        lookup_notable_dex(self.dex_id.as_deref())
    }
}

fn lookup_notable_dex(raw: Option<&str>) -> Option<NotableDex> {
    let raw = raw?.trim().to_ascii_lowercase();
    NOTABLE_DEXES
        .iter()
        .copied()
        .find(|dex| dex.aliases.iter().any(|alias| *alias == raw) || dex.key == raw)
}

fn decimal_from_value(value: Option<&Value>) -> Result<Option<Decimal>, WhispererError> {
    match value {
        Some(Value::String(value)) => value
            .parse::<Decimal>()
            .map(Some)
            .map_err(|error| WhispererError::Parse(error.to_string())),
        Some(Value::Number(value)) => value
            .to_string()
            .parse::<Decimal>()
            .map(Some)
            .map_err(|error| WhispererError::Parse(error.to_string())),
        Some(Value::Null) | None => Ok(None),
        Some(other) => Err(WhispererError::Parse(format!(
            "expected decimal-compatible value, got {other}"
        ))),
    }
}

fn de_opt_string_or_number<'de, D>(deserializer: D) -> Result<Option<String>, D::Error>
where
    D: Deserializer<'de>,
{
    match Option::<Value>::deserialize(deserializer)? {
        Some(Value::String(value)) => Ok(Some(value)),
        Some(Value::Number(value)) => Ok(Some(value.to_string())),
        Some(Value::Null) | None => Ok(None),
        Some(other) => Err(serde::de::Error::custom(format!(
            "expected optional string or number, got {other}"
        ))),
    }
}

fn parse_chain(value: &str) -> Chain {
    match value {
        "ethereum" | "eth" => Chain::Ethereum,
        "arbitrum" | "arbitrum_one" => Chain::Arbitrum,
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
    use super::{lookup_notable_dex, DexPair, DexScreenerWhisperer};
    use crate::SignalScanner;
    use ast_core::{RiskLevel, StrategyProfile, Usd};
    use rust_decimal::Decimal;

    #[tokio::test]
    async fn paper_mode_returns_mock_signal_when_live_feed_disabled() {
        let strategy = StrategyProfile {
            name: "swift".to_owned(),
            description: "Fast entry on new pairs".to_owned(),
            max_position_size_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            max_slippage_bps: 200,
            risk_tolerance: RiskLevel::Medium,
            scan_interval_seconds: 15,
            paper_trading: true,
        };

        let whisperer = DexScreenerWhisperer::new(strategy, true, false);
        let signals = whisperer.scan().await.expect("scan should succeed");

        assert_eq!(signals.len(), 1);
        assert_eq!(signals[0].token.symbol, "SWFT");
        assert_eq!(signals[0].metadata.get("source").map(String::as_str), Some("paper_mock"));
    }

    #[test]
    fn dex_pair_without_liquidity_object_still_deserializes() {
        let pair: DexPair = serde_json::from_str(
            r#"{
                "chainId": "base",
                "pairAddress": "0x0000000000000000000000000000000000000000",
                "priceUsd": "1.23",
                "baseToken": {"address": "0x0000000000000000000000000000000000000000", "symbol": "TEST"},
                "volume": {"h24": 10}
            }"#,
        )
        .expect("pair should deserialize");

        assert!(pair.liquidity.usd.is_none());
        assert!(pair.is_supported_chain());
    }

    #[test]
    fn maps_known_notable_dex_aliases() {
        let dex = lookup_notable_dex(Some("uniswap_v3")).expect("should map alias");
        assert_eq!(dex.key, "uniswap");

        let dex = lookup_notable_dex(Some("aerodrome-slipstream")).expect("should map alias");
        assert_eq!(dex.key, "aerodrome");
    }

    #[test]
    fn dead_pool_with_high_tvl_but_no_volume_is_rejected() {
        // Regression for the insight strategy's 19,378-orders → 0-fills run.
        // Pools with $70k+ locked liquidity but $36/day volume passed the
        // liquidity floor, scored above 0, and produced orders that the
        // slinger then refused for slippage. The volume floor rejects them
        // at discovery instead.
        use super::{lookup_notable_dex, DexScreenerWhisperer};
        let strategy = StrategyProfile {
            name: "insight".to_owned(),
            description: "test".to_owned(),
            max_position_size_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            max_slippage_bps: 250,
            risk_tolerance: RiskLevel::High,
            scan_interval_seconds: 45,
            paper_trading: true,
        };
        let whisperer = DexScreenerWhisperer::new(strategy, true, true);
        let uniswap = lookup_notable_dex(Some("uniswap"));

        // High TVL, dead volume — matches the real sample from data/learning/insight.jsonl.
        let dead_score = whisperer.score_pair(
            "base",
            true,
            Decimal::new(7195123, 2), // $71,951.23 liquidity
            Decimal::new(3697, 2),    // $36.97 daily volume
            uniswap,
        );
        assert_eq!(dead_score, -1, "dead pool must be rejected at scoring time");

        // Same liquidity, healthy volume — must score positively.
        let live_score = whisperer.score_pair(
            "base",
            true,
            Decimal::new(7195123, 2),     // same $71,951.23 liquidity
            Decimal::new(5_000_000, 2),   // $50,000 daily volume
            uniswap,
        );
        assert!(live_score > 0, "pool with healthy volume must score positively");
    }

    #[test]
    fn bridge_prefers_uniswap_over_pancakeswap() {
        let strategy = StrategyProfile {
            name: "bridge".to_owned(),
            description: "Cross-venue arbitrage".to_owned(),
            max_position_size_usd: Usd::new(Decimal::new(400, 0)).expect("valid usd"),
            max_slippage_bps: 50,
            risk_tolerance: RiskLevel::Low,
            scan_interval_seconds: 10,
            paper_trading: true,
        };

        let whisperer = DexScreenerWhisperer::new(strategy, true, true);
        let uniswap = lookup_notable_dex(Some("uniswap")).expect("known dex");
        let pancakeswap = lookup_notable_dex(Some("pancakeswap")).expect("known dex");

        assert!(whisperer.strategy_dex_bonus(uniswap) > whisperer.strategy_dex_bonus(pancakeswap));
        assert_eq!(whisperer.strategy_dex_fit_label(uniswap), "primary");
    }
}
