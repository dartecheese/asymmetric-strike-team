use async_trait::async_trait;
use ast_core::{Result, RiskAssessment, Signal};
use ast_safety::AuthorizedOrder;

#[async_trait]
pub trait Slinger: Send + Sync {
    async fn route(&self, signal: &Signal, risk: &RiskAssessment) -> Result<AuthorizedOrder>;
}

pub struct NullSlinger;

#[async_trait]
impl Slinger for NullSlinger {
    async fn route(&self, _signal: &Signal, _risk: &RiskAssessment) -> Result<AuthorizedOrder> {
        Err(ast_core::AstError::Validation("no execution venue configured".into()))
    }
}
