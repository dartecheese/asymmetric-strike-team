use async_trait::async_trait;
use thiserror::Error;

use ast_core::{RiskAssessment, TradingSignal};

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
