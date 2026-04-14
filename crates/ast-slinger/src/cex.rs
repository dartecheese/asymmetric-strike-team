use ast_core::{ExecutionOrder, Result};
use async_trait::async_trait;
use rust_decimal::Decimal;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CexQuote {
    pub expected_fill: Decimal,
}

#[async_trait]
pub trait CexVenue: Send + Sync {
    async fn quote_order(&self, order: &ExecutionOrder) -> Result<CexQuote>;
}

#[derive(Debug, Default)]
pub struct CexExecutor;

#[async_trait]
impl CexVenue for CexExecutor {
    async fn quote_order(&self, _order: &ExecutionOrder) -> Result<CexQuote> {
        Err(ast_core::AstError::Validation(
            "CEX executor skeleton does not yet provide live quotes".into(),
        ))
    }
}
