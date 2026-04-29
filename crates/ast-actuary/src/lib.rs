use async_trait::async_trait;
use reqwest::Client;
use rust_decimal::prelude::ToPrimitive;
use rust_decimal::Decimal;
use serde::Deserialize;
use thiserror::Error;

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
}

impl GoPlusActuary {
    pub fn new(strategy: StrategyProfile, paper_mode: bool) -> Self {
        Self {
            strategy,
            client: Client::new(),
            paper_mode,
        }
    }

    async fn fetch_goplus_score(&self, signal: &Signal) -> Result<Option<GoPlusSummary>, ActuaryError> {
        if self.paper_mode || !matches!(signal.token.chain, Chain::Ethereum | Chain::Arbitrum | Chain::Base) {
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
        let response = self
            .client
            .get(url)
            .send()
            .await
            .map_err(|error| ActuaryError::Request(error.to_string()))?;
        let status = response.status();
        if !status.is_success() {
            return Err(ActuaryError::Request(format!(
                "goplus returned status {status}"
            )));
        }

        let payload = response
            .json::<GoPlusResponse>()
            .await
            .map_err(|error| ActuaryError::Parse(error.to_string()))?;

        Ok(payload.result.into_iter().next().map(|(_, summary)| summary))
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

        let volume_score = if signal.volume_24h_usd.0 < Decimal::new(100_000, 0) {
            30
        } else {
            10
        };
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
}

#[async_trait]
impl RiskAssessor for GoPlusActuary {
    async fn assess(&self, signal: &Signal) -> Result<RiskAssessment, ActuaryError> {
        if self.paper_mode {
            return self.paper_assessment(signal);
        }

        let Some(summary) = self.fetch_goplus_score(signal).await? else {
            return Ok(RiskAssessment {
                level: RiskLevel::High,
                decision: RiskDecision::Review,
                rationale: "token could not be verified; defaulting to high risk".to_owned(),
                approved_notional_usd: Usd::zero(),
                factors: vec![RiskFactor {
                    name: "verification".to_owned(),
                    score: 80,
                    details: "missing GoPlus verification".to_owned(),
                }],
            });
        };

        let mut factors = Vec::new();
        let mut aggregate = 0u16;

        let honeypot_score = if summary.is_honeypot.as_deref() == Some("1") {
            100
        } else {
            0
        };
        aggregate += honeypot_score;
        factors.push(RiskFactor {
            name: "honeypot".to_owned(),
            score: honeypot_score as u8,
            details: format!("is_honeypot={}", summary.is_honeypot.unwrap_or_else(|| "unknown".to_owned())),
        });

        let buy_tax = parse_basis_points(summary.buy_tax.as_deref());
        aggregate += u16::from((buy_tax / 10).min(50));
        factors.push(RiskFactor {
            name: "buy_tax".to_owned(),
            score: (buy_tax / 10).min(50),
            details: format!("buy tax {} bps", buy_tax),
        });

        let sell_tax = parse_basis_points(summary.sell_tax.as_deref());
        aggregate += u16::from((sell_tax / 10).min(50));
        factors.push(RiskFactor {
            name: "sell_tax".to_owned(),
            score: (sell_tax / 10).min(50),
            details: format!("sell tax {} bps", sell_tax),
        });

        let (level, decision) = if honeypot_score >= 100 || aggregate >= 90 {
            (RiskLevel::Rejected, RiskDecision::Reject)
        } else if aggregate >= 50 {
            (RiskLevel::High, RiskDecision::Review)
        } else {
            (RiskLevel::Low, RiskDecision::Accept)
        };

        let approved_notional_usd = if matches!(decision, RiskDecision::Accept) {
            signal.target_notional_usd.clone()
        } else {
            Usd::zero()
        };

        Ok(RiskAssessment {
            level,
            decision,
            rationale: "GoPlus token security assessment".to_owned(),
            approved_notional_usd,
            factors,
        })
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

        let assessment = GoPlusActuary::new(strategy, true)
            .assess(&signal)
            .await
            .expect("assessment should succeed");

        assert_eq!(assessment.decision, RiskDecision::Accept);
    }
}
