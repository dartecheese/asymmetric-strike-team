use async_trait::async_trait;
use ast_core::{Result, RiskAssessment, Signal};

#[async_trait]
pub trait Actuary: Send + Sync {
    async fn assess(&self, signal: &Signal) -> Result<RiskAssessment>;
}

pub struct NullActuary;

#[async_trait]
impl Actuary for NullActuary {
    async fn assess(&self, signal: &Signal) -> Result<RiskAssessment> {
        Ok(ast_core::RiskAssessment {
            token: signal.token.clone(),
            risk_level: ast_core::RiskLevel::High,
            max_allocation_usd: ast_core::Usd::new(rust_decimal::Decimal::new(100, 0))?,
        })
    }
}
