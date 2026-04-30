use async_trait::async_trait;
use reqwest::Client;
use rust_decimal::prelude::ToPrimitive;
use rust_decimal::Decimal;
use serde::Deserialize;
use serde_json::Value;
use thiserror::Error;
use tracing::warn;

use ast_core::{Chain, RiskAssessment, RiskDecision, RiskFactor, RiskLevel, Signal, StrategyProfile, Usd};

#[derive(Debug, Error)]
pub enum ActuaryError {
    #[error("request failed: {0}")]
    Request(String),
    #[error("response parsing failed: {0}")]
    Parse(String),
    #[error("risk assessment failed: {0}")]
    Risk(String),
}

#[async_trait]
pub trait RiskAssessor: Send + Sync {
    async fn assess(&self, signal: &Signal) -> Result<RiskAssessment, ActuaryError>;
}

#[derive(Debug, Clone)]
pub struct GoPlusActuary {
    strategy: StrategyProfile,
    client: Client,
    paper_mode: bool,
    live_risk_checks_in_paper: bool,
}

#[derive(Debug, Clone)]
struct HoneypotSummary {
    is_honeypot: bool,
    buy_tax_bps: u16,
    sell_tax_bps: u16,
    risk_level: u8,
    risk: String,
}

impl GoPlusActuary {
    pub fn new(strategy: StrategyProfile, paper_mode: bool, live_risk_checks_in_paper: bool) -> Self {
        Self {
            strategy,
            client: Client::builder()
                .user_agent("asymmetric-strike-team/0.1")
                .build()
                .unwrap_or_else(|_| Client::new()),
            paper_mode,
            live_risk_checks_in_paper,
        }
    }

    async fn fetch_goplus_score(&self, signal: &Signal) -> Result<Option<GoPlusSummary>, ActuaryError> {
        if !matches!(signal.token.chain, Chain::Ethereum | Chain::Arbitrum | Chain::Base)
            || signal.token.address.is_zero()
        {
            return Ok(None);
        }

        let chain_id = match signal.token.chain {
            Chain::Ethereum => "1",
            Chain::Arbitrum => "42161",
            Chain::Base => "8453",
            Chain::Solana => return Ok(None),
        };

        let url = format!(
            "https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={}",
            signal.token.address
        );
        let payload = self.get_json_with_retries(&url).await?;
        let response = serde_json::from_value::<GoPlusResponse>(payload)
            .map_err(|error| ActuaryError::Parse(error.to_string()))?;
        Ok(response.result.into_iter().next().map(|(_, summary)| summary))
    }

    async fn fetch_honeypot_summary(&self, signal: &Signal) -> Result<Option<HoneypotSummary>, ActuaryError> {
        if !matches!(signal.token.chain, Chain::Ethereum | Chain::Arbitrum | Chain::Base)
            || signal.token.address.is_zero()
        {
            return Ok(None);
        }

        let chain_id = match signal.token.chain {
            Chain::Ethereum => "1",
            Chain::Arbitrum => "42161",
            Chain::Base => "8453",
            Chain::Solana => return Ok(None),
        };
        let url = format!(
            "https://api.honeypot.is/v2/IsHoneypot?address={}&chainID={chain_id}",
            signal.token.address
        );
        let payload = self.get_json_with_retries(&url).await?;

        let is_honeypot = payload
            .get("honeypotResult")
            .and_then(|value| value.get("isHoneypot"))
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let buy_tax_bps = decimal_bps(payload.get("simulationResult").and_then(|value| value.get("buyTax")));
        let sell_tax_bps = decimal_bps(payload.get("simulationResult").and_then(|value| value.get("sellTax")));
        let risk_level = payload
            .get("summary")
            .and_then(|value| value.get("riskLevel"))
            .and_then(Value::as_u64)
            .and_then(|value| u8::try_from(value).ok())
            .unwrap_or(5);
        let risk = payload
            .get("summary")
            .and_then(|value| value.get("risk"))
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_owned();

        Ok(Some(HoneypotSummary {
            is_honeypot,
            buy_tax_bps,
            sell_tax_bps,
            risk_level,
            risk,
        }))
    }

    async fn get_json_with_retries(&self, url: &str) -> Result<Value, ActuaryError> {
        let mut last_error = None;
        for delay_ms in [0u64, 250, 750] {
            if delay_ms > 0 {
                tokio::time::sleep(std::time::Duration::from_millis(delay_ms)).await;
            }
            match self.client.get(url).send().await {
                Ok(response) => {
                    let status = response.status();
                    if status.is_success() {
                        return response
                            .json::<Value>()
                            .await
                            .map_err(|error| ActuaryError::Parse(error.to_string()));
                    }
                    last_error = Some(format!("status {status}"));
                }
                Err(error) => last_error = Some(error.to_string()),
            }
        }

        Err(ActuaryError::Request(format!(
            "request failed after retries: {}",
            last_error.unwrap_or_else(|| "unknown error".to_owned())
        )))
    }

    fn paper_assessment(&self, signal: &Signal) -> Result<RiskAssessment, ActuaryError> {
        let mut factors = Vec::new();
        let liquidity_ratio = signal.target_notional_usd.0 / signal.liquidity_usd.0;
        let liquidity_score = if liquidity_ratio > Decimal::new(20, 2) { 40 } else { 10 };
        factors.push(RiskFactor {
            name: "liquidity_ratio".to_owned(),
            score: liquidity_score,
            details: format!("notional/liquidity ratio {}", liquidity_ratio.round_dp(4)),
        });

        let volume_score = if signal.volume_24h_usd.0 < Decimal::new(100_000, 0) { 30 } else { 10 };
        factors.push(RiskFactor {
            name: "volume_24h".to_owned(),
            score: volume_score,
            details: format!("24h volume {}", signal.volume_24h_usd.0.round_dp(2)),
        });

        let strategy_score = match self.strategy.risk_tolerance {
            RiskLevel::Low => 25,
            RiskLevel::Medium => 15,
            RiskLevel::High => 5,
            RiskLevel::Critical | RiskLevel::Rejected => 35,
        };
        factors.push(RiskFactor {
            name: "strategy_tolerance".to_owned(),
            score: strategy_score,
            details: format!("strategy risk tolerance {:?}", self.strategy.risk_tolerance),
        });

        let aggregate: u16 = factors.iter().map(|factor| u16::from(factor.score)).sum();
        let (level, decision) = if aggregate >= 75 {
            (RiskLevel::High, RiskDecision::Review)
        } else {
            (RiskLevel::Medium, RiskDecision::Accept)
        };

        let approved_notional = if matches!(decision, RiskDecision::Accept) {
            signal.target_notional_usd.clone()
        } else {
            Usd::new(signal.target_notional_usd.0 / Decimal::TWO)
                .map_err(|error| ActuaryError::Risk(error.to_string()))?
        };

        Ok(RiskAssessment {
            level,
            decision,
            rationale: "paper-mode heuristic assessment".to_owned(),
            approved_notional_usd: approved_notional,
            factors,
        })
    }

    fn build_live_assessment(
        &self,
        signal: &Signal,
        goplus: Option<GoPlusSummary>,
        honeypot: Option<HoneypotSummary>,
    ) -> Result<RiskAssessment, ActuaryError> {
        let mut factors = Vec::new();
        let mut aggregate = 0u16;
        let mut rationale = Vec::new();

        if let Some(summary) = goplus {
            let honeypot_score = if summary.is_honeypot.as_deref() == Some("1") { 100 } else { 0 };
            aggregate += honeypot_score;
            factors.push(RiskFactor {
                name: "goplus_honeypot".to_owned(),
                score: honeypot_score as u8,
                details: format!("is_honeypot={}", summary.is_honeypot.unwrap_or_else(|| "unknown".to_owned())),
            });

            let buy_tax = parse_basis_points(summary.buy_tax.as_deref());
            aggregate += u16::from((buy_tax / 10).min(50));
            factors.push(RiskFactor {
                name: "goplus_buy_tax".to_owned(),
                score: (buy_tax / 10).min(50),
                details: format!("buy tax {} bps", buy_tax),
            });

            let sell_tax = parse_basis_points(summary.sell_tax.as_deref());
            aggregate += u16::from((sell_tax / 10).min(50));
            factors.push(RiskFactor {
                name: "goplus_sell_tax".to_owned(),
                score: (sell_tax / 10).min(50),
                details: format!("sell tax {} bps", sell_tax),
            });
            rationale.push("GoPlus".to_owned());
        }

        if let Some(summary) = honeypot {
            let hp_score = if summary.is_honeypot { 100 } else { 0 };
            aggregate += hp_score;
            factors.push(RiskFactor {
                name: "honeypot_is_honeypot".to_owned(),
                score: hp_score as u8,
                details: format!("is_honeypot={} risk={}", summary.is_honeypot, summary.risk),
            });

            let buy_score = (summary.buy_tax_bps / 10).min(40) as u8;
            aggregate += u16::from(buy_score);
            factors.push(RiskFactor {
                name: "honeypot_buy_tax".to_owned(),
                score: buy_score,
                details: format!("buy tax {} bps", summary.buy_tax_bps),
            });

            let sell_score = (summary.sell_tax_bps / 10).min(40) as u8;
            aggregate += u16::from(sell_score);
            factors.push(RiskFactor {
                name: "honeypot_sell_tax".to_owned(),
                score: sell_score,
                details: format!("sell tax {} bps", summary.sell_tax_bps),
            });

            let level_score = summary.risk_level.saturating_mul(8).min(40);
            aggregate += u16::from(level_score);
            factors.push(RiskFactor {
                name: "honeypot_risk_level".to_owned(),
                score: level_score,
                details: format!("honeypot risk level {} ({})", summary.risk_level, summary.risk),
            });
            rationale.push("Honeypot.is".to_owned());
        }

        if factors.is_empty() {
            return self.paper_assessment(signal);
        }

        let (level, decision) = if aggregate >= 100 {
            (RiskLevel::Rejected, RiskDecision::Reject)
        } else if aggregate >= 60 {
            (RiskLevel::High, RiskDecision::Review)
        } else {
            (RiskLevel::Low, RiskDecision::Accept)
        };

        let approved_notional_usd = match decision {
            RiskDecision::Accept => signal.target_notional_usd.clone(),
            RiskDecision::Review => Usd::new((signal.target_notional_usd.0 * Decimal::new(5, 1)).round_dp(8))
                .map_err(|error| ActuaryError::Risk(error.to_string()))?,
            RiskDecision::Reject => Usd::zero(),
        };

        Ok(RiskAssessment {
            level,
            decision,
            rationale: format!("live token security assessment via {}", rationale.join(" + ")),
            approved_notional_usd,
            factors,
        })
    }
}

#[async_trait]
impl RiskAssessor for GoPlusActuary {
    async fn assess(&self, signal: &Signal) -> Result<RiskAssessment, ActuaryError> {
        if self.paper_mode && !self.live_risk_checks_in_paper {
            return self.paper_assessment(signal);
        }

        let goplus = match self.fetch_goplus_score(signal).await {
            Ok(summary) => summary,
            Err(error) if self.paper_mode => {
                warn!(strategy = %self.strategy.name, error = %error, "goplus failed; continuing with fallback providers");
                None
            }
            Err(error) => return Err(error),
        };

        let honeypot = match self.fetch_honeypot_summary(signal).await {
            Ok(summary) => summary,
            Err(error) if self.paper_mode => {
                warn!(strategy = %self.strategy.name, error = %error, "honeypot.is failed; continuing with fallback providers");
                None
            }
            Err(error) => return Err(error),
        };

        if goplus.is_none() && honeypot.is_none() && self.paper_mode {
            return self.paper_assessment(signal);
        }

        self.build_live_assessment(signal, goplus, honeypot)
    }
}

#[derive(Debug, Deserialize)]
struct GoPlusResponse {
    #[serde(default)]
    result: std::collections::BTreeMap<String, GoPlusSummary>,
}

#[derive(Debug, Deserialize)]
struct GoPlusSummary {
    #[serde(default)]
    is_honeypot: Option<String>,
    #[serde(default)]
    buy_tax: Option<String>,
    #[serde(default)]
    sell_tax: Option<String>,
}

fn parse_basis_points(value: Option<&str>) -> u8 {
    let Some(value) = value else {
        return 100;
    };

    match value.parse::<Decimal>() {
        Ok(decimal) => {
            let bps = (decimal * Decimal::new(10_000, 0)).round();
            bps.to_u32()
                .and_then(|value| u8::try_from(value).ok())
                .unwrap_or(100)
        }
        Err(_) => 100,
    }
}

fn decimal_bps(value: Option<&Value>) -> u16 {
    match value {
        Some(Value::Number(number)) => number
            .to_string()
            .parse::<Decimal>()
            .ok()
            .map(|value| ((value * Decimal::new(100, 0)).round()).to_u16().unwrap_or(0))
            .unwrap_or(0),
        Some(Value::String(value)) => value
            .parse::<Decimal>()
            .ok()
            .map(|value| ((value * Decimal::new(100, 0)).round()).to_u16().unwrap_or(0))
            .unwrap_or(0),
        _ => 0,
    }
}

#[cfg(test)]
mod tests {
    use super::GoPlusActuary;
    use crate::RiskAssessor;
    use ast_core::{Chain, RiskDecision, RiskLevel, Signal, StrategyProfile, Token, Usd, Venue};
    use rust_decimal::Decimal;
    use std::collections::BTreeMap;

    #[tokio::test]
    async fn paper_mode_accepts_healthy_signal() {
        let strategy = StrategyProfile {
            name: "swift".to_owned(),
            description: "Fast entry on new pairs".to_owned(),
            max_position_size_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            max_slippage_bps: 200,
            risk_tolerance: RiskLevel::Medium,
            scan_interval_seconds: 15,
            paper_trading: true,
        };
        let signal = Signal {
            id: "signal-1".to_owned(),
            token: Token {
                address: alloy_primitives::Address::ZERO,
                chain: Chain::Base,
                symbol: "SWFT".to_owned(),
                decimals: 18,
            },
            venue: Venue::Dex {
                chain: Chain::Base,
                router: alloy_primitives::Address::ZERO,
            },
            price_usd: Usd::new(Decimal::new(1, 0)).expect("valid usd"),
            volume_24h_usd: Usd::new(Decimal::new(200_000, 0)).expect("valid usd"),
            liquidity_usd: Usd::new(Decimal::new(500_000, 0)).expect("valid usd"),
            target_notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            timestamp_ms: 1,
            metadata: BTreeMap::new(),
        };

        let assessment = GoPlusActuary::new(strategy, true, true)
            .assess(&signal)
            .await
            .expect("assessment should succeed");

        assert_eq!(assessment.decision, RiskDecision::Accept);
    }
}
