use async_trait::async_trait;
use thiserror::Error;

use ast_core::{RiskAssessment, RiskDecision, Signal, StrategyProfile, TradingSignal};

#[derive(Debug, Error)]
pub enum SafetyError {
    #[error("circuit breaker refused signal {0}")]
    Refused(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SafetyDecision {
    pub should_trade: bool,
    pub reason: String,
}

#[async_trait]
pub trait CircuitBreaker: Send + Sync {
    async fn evaluate(
        &self,
        signal: &TradingSignal,
        risk: &RiskAssessment,
    ) -> Result<SafetyDecision, SafetyError>;
}

#[derive(Debug, Default)]
pub struct NoopSafety;

#[derive(Debug, Clone)]
pub struct PaperSafety {
    strategy: StrategyProfile,
}

impl PaperSafety {
    pub fn new(strategy: StrategyProfile) -> Self {
        Self { strategy }
    }
}

#[async_trait]
impl CircuitBreaker for NoopSafety {
    async fn evaluate(
        &self,
        signal: &TradingSignal,
        risk: &RiskAssessment,
    ) -> Result<SafetyDecision, SafetyError> {
        Ok(SafetyDecision {
            should_trade: risk.acceptable(),
            reason: format!("placeholder safety check passed for {}", signal.id),
        })
    }
}

#[async_trait]
impl CircuitBreaker for PaperSafety {
    async fn evaluate(
        &self,
        signal: &Signal,
        risk: &RiskAssessment,
    ) -> Result<SafetyDecision, SafetyError> {
        if !risk.acceptable() {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!("risk gate blocked {}", signal.id),
            });
        }

        if risk.decision == RiskDecision::Review {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!("review-required signal {} held by safety gate", signal.id),
            });
        }

        let liquidity_ratio = signal.target_notional_usd.0 / signal.liquidity_usd.0;
        if liquidity_ratio > rust_decimal::Decimal::new(15, 2) {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!(
                    "liquidity ratio {} exceeded safety ceiling for {}",
                    liquidity_ratio.round_dp(4),
                    self.strategy.name
                ),
            });
        }

        if self.strategy.max_slippage_bps > 250 {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!(
                    "strategy slippage ceiling {}bps too loose for paper auto-execution",
                    self.strategy.max_slippage_bps
                ),
            });
        }

        Ok(SafetyDecision {
            should_trade: true,
            reason: format!("paper safety checks passed for {}", signal.id),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::{CircuitBreaker, PaperSafety};
    use ast_core::{
        Chain, RiskAssessment, RiskDecision, RiskLevel, Signal, StrategyProfile, Token, Usd, Venue,
    };
    use rust_decimal::Decimal;
    use std::collections::BTreeMap;

    fn strategy(max_slippage_bps: u16) -> StrategyProfile {
        StrategyProfile {
            name: "swift".to_owned(),
            description: "Fast entry on new pairs".to_owned(),
            max_position_size_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            max_slippage_bps,
            risk_tolerance: RiskLevel::Medium,
            scan_interval_seconds: 15,
            paper_trading: true,
        }
    }

    fn signal() -> Signal {
        Signal {
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
            price_usd: Usd::new(Decimal::ONE).expect("valid usd"),
            volume_24h_usd: Usd::new(Decimal::new(100_000, 0)).expect("valid usd"),
            liquidity_usd: Usd::new(Decimal::new(500_000, 0)).expect("valid usd"),
            target_notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            timestamp_ms: 1,
            metadata: BTreeMap::new(),
        }
    }

    fn accepted_risk() -> RiskAssessment {
        RiskAssessment {
            level: RiskLevel::Low,
            decision: RiskDecision::Accept,
            rationale: "ok".to_owned(),
            approved_notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            factors: Vec::new(),
        }
    }

    #[tokio::test]
    async fn paper_safety_allows_healthy_signal() {
        let safety = PaperSafety::new(strategy(200));
        let decision = safety.evaluate(&signal(), &accepted_risk()).await.expect("decision");

        assert!(decision.should_trade);
    }

    #[tokio::test]
    async fn paper_safety_blocks_loose_slippage_profiles() {
        let safety = PaperSafety::new(strategy(300));
        let decision = safety.evaluate(&signal(), &accepted_risk()).await.expect("decision");

        assert!(!decision.should_trade);
    }
}
