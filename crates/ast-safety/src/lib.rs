use ast_core::{ExecutionOrder, Result};

#[derive(Debug, Clone)]
pub struct AuthorizedOrder(pub ExecutionOrder);

#[derive(Debug, Default)]
pub struct SafetyBreaker;

impl SafetyBreaker {
    pub fn authorize(&self, order: ExecutionOrder) -> Result<AuthorizedOrder> {
        Ok(AuthorizedOrder(order))
    }
}
