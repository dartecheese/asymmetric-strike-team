use ast_core::{ExecutionOrder, Result};
use async_trait::async_trait;
use rust_decimal::Decimal;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DexQuote {
    pub expected_out: Decimal,
    pub amount_out_minimum: Decimal,
}

#[async_trait]
pub trait DexVenue: Send + Sync {
    async fn quote_swap(&self, order: &ExecutionOrder) -> Result<DexQuote>;
}

#[derive(Debug, Default)]
pub struct DexExecutor;

#[async_trait]
impl DexVenue for DexExecutor {
    async fn quote_swap(&self, _order: &ExecutionOrder) -> Result<DexQuote> {
        Err(ast_core::AstError::Validation(
            "DEX executor skeleton does not yet provide live quotes".into(),
        ))
    }
}
