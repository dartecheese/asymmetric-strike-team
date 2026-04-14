pub mod goplus;

use std::time::Duration;

use ast_core::{AstError, Result, RiskAssessment, Signal, Usd};
use async_trait::async_trait;
use rust_decimal::Decimal;

pub use goplus::{ActuaryConfig, GoPlusActuary, GoPlusClient, GoPlusConfig};

#[async_trait]
pub trait Actuary: Send + Sync {
    async fn assess(&self, signal: &Signal) -> Result<RiskAssessment>;

    async fn assess_with_timeout(
        &self,
        signal: &Signal,
        timeout: Duration,
    ) -> Result<RiskAssessment> {
        tokio::time::timeout(timeout, self.assess(signal))
            .await
            .map_err(|_| AstError::Timeout {
                service: "actuary.assess",
                duration_ms: timeout.as_millis() as u64,
            })?
    }
}

pub struct NullActuary;

#[async_trait]
impl Actuary for NullActuary {
    async fn assess(&self, signal: &Signal) -> Result<RiskAssessment> {
        Ok(ast_core::RiskAssessment {
            token: signal.token.clone(),
            risk_level: ast_core::RiskLevel::High,
            max_allocation_usd: Usd::new(Decimal::new(25, 0))?,
            provider: "null".to_string(),
            factors: Vec::new(),
            warnings: vec!["No risk provider configured".to_string()],
        })
    }
}
