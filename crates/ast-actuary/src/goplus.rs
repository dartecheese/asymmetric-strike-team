use std::{
    collections::HashMap,
    sync::Arc,
    time::{Duration, Instant},
};

use ast_core::{
    AstError, Result, RiskAssessment, RiskFactor, RiskFactorScore, RiskLevel, Signal, Usd,
};
use reqwest::Client;
use rust_decimal::Decimal;
use rust_decimal::prelude::ToPrimitive;
use serde::Deserialize;
use tokio::sync::Mutex;
use tracing::warn;

use crate::Actuary;

const GOPLUS_BASE_URL: &str = "https://api.gopluslabs.io";
const DEFAULT_TIMEOUT_MS: u64 = 5_000;
const DEFAULT_CACHE_TTL_SECS: u64 = 300;
const DEFAULT_RETRIES: u8 = 2;

#[derive(Debug, Clone)]
pub struct GoPlusConfig {
    pub base_url: String,
    pub request_timeout: Duration,
    pub retries: u8,
    pub cache_ttl: Duration,
}

impl Default for GoPlusConfig {
    fn default() -> Self {
        Self {
            base_url: GOPLUS_BASE_URL.to_string(),
            request_timeout: Duration::from_millis(DEFAULT_TIMEOUT_MS),
            retries: DEFAULT_RETRIES,
            cache_ttl: Duration::from_secs(DEFAULT_CACHE_TTL_SECS),
        }
    }
}

#[derive(Debug, Clone)]
pub struct ActuaryConfig {
    pub max_allowed_tax: Decimal,
    pub fallback_allocation_usd: Decimal,
    pub medium_allocation_usd: Decimal,
    pub high_allocation_usd: Decimal,
}

impl Default for ActuaryConfig {
    fn default() -> Self {
        Self {
            max_allowed_tax: Decimal::new(20, 2),
            fallback_allocation_usd: Decimal::from(25),
            medium_allocation_usd: Decimal::from(50),
            high_allocation_usd: Decimal::from(30),
        }
    }
}

#[derive(Debug)]
pub struct GoPlusClient {
    http: Client,
    config: GoPlusConfig,
}

impl GoPlusClient {
    pub fn new(config: GoPlusConfig) -> Result<Self> {
        let http = Client::builder()
            .timeout(config.request_timeout)
            .user_agent("AsymmetricStrikeTeam/0.1")
            .build()
            .map_err(|error| AstError::Config(format!("failed to build GoPlus client: {error}")))?;

        Ok(Self { http, config })
    }

    pub async fn fetch_token_security(
        &self,
        chain_id: &str,
        token_address: &str,
    ) -> Result<Option<TokenSecurity>> {
        let path = format!("/api/v1/token_security/{chain_id}?contract_addresses={token_address}");
        let url = format!("{}{}", self.config.base_url, path);

        for attempt in 1..=self.config.retries {
            match self.http.get(&url).send().await {
                Ok(response) => {
                    let response = response.error_for_status().map_err(|error| {
                        map_reqwest_error("GoPlus", self.config.request_timeout, error)
                    })?;
                    let payload = response.json::<GoPlusResponse>().await.map_err(|error| {
                        AstError::ExternalService {
                            service: "GoPlus",
                            message: format!("invalid JSON response: {error}"),
                        }
                    })?;

                    if payload.code != 1 {
                        return Ok(None);
                    }

                    let key = token_address.to_lowercase();
                    return Ok(payload.result.and_then(|result| result.get(&key).cloned()));
                }
                Err(error) if attempt < self.config.retries => {
                    warn!(attempt, error = %error, "GoPlus request failed, retrying");
                    tokio::time::sleep(Duration::from_millis(250)).await;
                }
                Err(error) => {
                    return Err(map_reqwest_error(
                        "GoPlus",
                        self.config.request_timeout,
                        error,
                    ));
                }
            }
        }

        Ok(None)
    }
}

#[derive(Debug)]
pub struct GoPlusActuary {
    client: Arc<GoPlusClient>,
    config: ActuaryConfig,
    cache: Mutex<HashMap<String, CachedAssessment>>,
}

impl GoPlusActuary {
    pub fn new(client_config: GoPlusConfig, actuary_config: ActuaryConfig) -> Result<Self> {
        Ok(Self {
            client: Arc::new(GoPlusClient::new(client_config)?),
            config: actuary_config,
            cache: Mutex::new(HashMap::new()),
        })
    }

    async fn cached_assessment(&self, signal: &Signal) -> Option<RiskAssessment> {
        let key = cache_key(signal);
        let cache = self.cache.lock().await;
        cache
            .get(&key)
            .filter(|entry| entry.expires_at > Instant::now())
            .map(|entry| entry.assessment.clone())
    }

    async fn store_assessment(&self, signal: &Signal, assessment: RiskAssessment) {
        let key = cache_key(signal);
        let expires_at = Instant::now() + self.client.config.cache_ttl;
        self.cache.lock().await.insert(
            key,
            CachedAssessment {
                assessment,
                expires_at,
            },
        );
    }

    fn build_assessment(
        &self,
        signal: &Signal,
        security: Option<TokenSecurity>,
    ) -> Result<RiskAssessment> {
        let mut warnings = Vec::new();
        let mut factors = Vec::new();

        let Some(security) = security else {
            warnings.push(
                "Token could not be verified through GoPlus; defaulting to HIGH risk.".to_string(),
            );
            factors.push(RiskFactorScore {
                factor: RiskFactor::UnknownToken,
                risk_level: RiskLevel::High,
                score_bps: 8_500,
                summary: "GoPlus returned no verified token security record".to_string(),
            });

            return Ok(RiskAssessment {
                token: signal.token.clone(),
                risk_level: RiskLevel::High,
                max_allocation_usd: Usd::new(self.config.fallback_allocation_usd)?,
                provider: "goplus".to_string(),
                factors,
                warnings,
            });
        };

        let parsed = ParsedSecurity::from_api(security);

        if parsed.is_honeypot {
            warnings.push("GoPlus flagged the token as a honeypot.".to_string());
        }
        if parsed.buy_tax > Decimal::new(10, 2) {
            warnings.push(format!("Buy tax elevated at {}%.", parsed.buy_tax));
        }
        if parsed.sell_tax > Decimal::new(10, 2) {
            warnings.push(format!("Sell tax elevated at {}%.", parsed.sell_tax));
        }
        if !parsed.liquidity_locked {
            warnings.push("Liquidity lock is unverified.".to_string());
        }
        if !parsed.is_open_source {
            warnings.push("Contract source is not verified as open source.".to_string());
        }

        factors.push(RiskFactorScore {
            factor: RiskFactor::Honeypot,
            risk_level: if parsed.is_honeypot {
                RiskLevel::Rejected
            } else {
                RiskLevel::Low
            },
            score_bps: if parsed.is_honeypot { 10_000 } else { 500 },
            summary: if parsed.is_honeypot {
                "Honeypot flag set by GoPlus".to_string()
            } else {
                "No honeypot flag reported".to_string()
            },
        });
        factors.push(RiskFactorScore {
            factor: RiskFactor::BuyTax,
            risk_level: tax_risk_level(parsed.buy_tax, self.config.max_allowed_tax),
            score_bps: tax_score_bps(parsed.buy_tax),
            summary: format!("Buy tax reported at {}%", parsed.buy_tax),
        });
        factors.push(RiskFactorScore {
            factor: RiskFactor::SellTax,
            risk_level: tax_risk_level(parsed.sell_tax, self.config.max_allowed_tax),
            score_bps: tax_score_bps(parsed.sell_tax),
            summary: format!("Sell tax reported at {}%", parsed.sell_tax),
        });
        factors.push(RiskFactorScore {
            factor: RiskFactor::LiquidityLock,
            risk_level: if parsed.liquidity_locked {
                RiskLevel::Medium
            } else {
                RiskLevel::High
            },
            score_bps: if parsed.liquidity_locked { 4_000 } else { 8_000 },
            summary: if parsed.liquidity_locked {
                "LP holder data exists; liquidity lock proxy looks present".to_string()
            } else {
                "No LP lock proxy detected".to_string()
            },
        });
        factors.push(RiskFactorScore {
            factor: RiskFactor::ContractVerification,
            risk_level: if parsed.is_open_source {
                RiskLevel::Low
            } else {
                RiskLevel::Medium
            },
            score_bps: if parsed.is_open_source { 2_000 } else { 6_000 },
            summary: if parsed.is_open_source {
                "Contract is open source".to_string()
            } else {
                "Contract source is unverified".to_string()
            },
        });

        let hard_reject = parsed.is_honeypot
            || parsed.buy_tax > self.config.max_allowed_tax
            || parsed.sell_tax > self.config.max_allowed_tax;

        let risk_level = if hard_reject {
            RiskLevel::Rejected
        } else if parsed.buy_tax > Decimal::new(5, 2)
            || parsed.sell_tax > Decimal::new(5, 2)
            || !parsed.liquidity_locked
        {
            RiskLevel::High
        } else {
            RiskLevel::Medium
        };

        let max_allocation_usd = match risk_level {
            RiskLevel::Rejected => Usd::new(Decimal::new(1, 2))?,
            RiskLevel::High => Usd::new(self.config.high_allocation_usd)?,
            _ => Usd::new(self.config.medium_allocation_usd)?,
        };

        Ok(RiskAssessment {
            token: signal.token.clone(),
            risk_level,
            max_allocation_usd,
            provider: "goplus".to_string(),
            factors,
            warnings,
        })
    }
}

#[async_trait::async_trait]
impl Actuary for GoPlusActuary {
    async fn assess(&self, signal: &Signal) -> Result<RiskAssessment> {
        if let Some(assessment) = self.cached_assessment(signal).await {
            return Ok(assessment);
        }

        let security = match self
            .client
            .fetch_token_security(signal.token.chain.as_str(), signal.token.address.as_str())
            .await
        {
            Ok(security) => security,
            Err(error) => {
                warn!(error = %error, "GoPlus unavailable, using conservative HIGH-risk fallback");
                None
            }
        };

        let assessment = self.build_assessment(signal, security)?;
        self.store_assessment(signal, assessment.clone()).await;
        Ok(assessment)
    }
}

#[derive(Debug, Clone)]
struct CachedAssessment {
    assessment: RiskAssessment,
    expires_at: Instant,
}

#[derive(Debug, Clone, Deserialize)]
struct GoPlusResponse {
    code: i32,
    result: Option<HashMap<String, TokenSecurity>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TokenSecurity {
    pub is_honeypot: Option<String>,
    pub buy_tax: Option<String>,
    pub sell_tax: Option<String>,
    pub is_open_source: Option<String>,
    pub lp_holders: Option<Vec<serde_json::Value>>,
}

#[derive(Debug, Clone)]
struct ParsedSecurity {
    is_honeypot: bool,
    buy_tax: Decimal,
    sell_tax: Decimal,
    is_open_source: bool,
    liquidity_locked: bool,
}

impl ParsedSecurity {
    fn from_api(security: TokenSecurity) -> Self {
        Self {
            is_honeypot: security.is_honeypot.as_deref() == Some("1"),
            buy_tax: parse_tax_percent(security.buy_tax.as_deref()),
            sell_tax: parse_tax_percent(security.sell_tax.as_deref()),
            is_open_source: security.is_open_source.as_deref() == Some("1"),
            liquidity_locked: security.lp_holders.is_some(),
        }
    }
}

fn parse_tax_percent(raw: Option<&str>) -> Decimal {
    let raw = raw.unwrap_or("1");
    Decimal::from_str_exact(raw)
        .ok()
        .map(|value| value * Decimal::from(100))
        .unwrap_or(Decimal::from(100))
}

fn tax_score_bps(percent: Decimal) -> u16 {
    (percent * Decimal::from(100))
        .round()
        .to_u16()
        .unwrap_or(u16::MAX)
        .min(10_000)
}

fn tax_risk_level(percent: Decimal, max_allowed_tax: Decimal) -> RiskLevel {
    if percent > max_allowed_tax {
        RiskLevel::Rejected
    } else if percent > Decimal::new(10, 2) {
        RiskLevel::High
    } else if percent > Decimal::new(5, 2) {
        RiskLevel::Medium
    } else {
        RiskLevel::Low
    }
}

fn cache_key(signal: &Signal) -> String {
    format!(
        "{}:{}",
        signal.token.chain.as_str(),
        signal.token.address.as_str().to_lowercase()
    )
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

#[cfg(test)]
mod tests {
    use super::*;
    use ast_core::{SignalMetrics, SignalSource, Token};

    fn sample_signal() -> Signal {
        Signal {
            token: Token::new("0xabc", "1", "TEST", 18).expect("valid token"),
            confidence_bps: 7_500,
            source: SignalSource::DexProfile,
            reasoning: "test".to_string(),
            metrics: SignalMetrics::default(),
        }
    }

    #[tokio::test]
    async fn unknown_tokens_default_high_risk() {
        let actuary =
            GoPlusActuary::new(GoPlusConfig::default(), ActuaryConfig::default()).unwrap();
        let assessment = actuary.build_assessment(&sample_signal(), None).unwrap();

        assert_eq!(assessment.risk_level, RiskLevel::High);
        assert!(
            assessment
                .warnings
                .iter()
                .any(|warning| warning.contains("defaulting to HIGH risk"))
        );
    }

    #[test]
    fn verified_honeypot_is_rejected() {
        let actuary =
            GoPlusActuary::new(GoPlusConfig::default(), ActuaryConfig::default()).unwrap();
        let assessment = actuary
            .build_assessment(
                &sample_signal(),
                Some(TokenSecurity {
                    is_honeypot: Some("1".to_string()),
                    buy_tax: Some("0.25".to_string()),
                    sell_tax: Some("0.25".to_string()),
                    is_open_source: Some("1".to_string()),
                    lp_holders: Some(Vec::new()),
                }),
            )
            .unwrap();

        assert_eq!(assessment.risk_level, RiskLevel::Rejected);
    }
}
