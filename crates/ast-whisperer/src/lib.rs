use async_trait::async_trait;
use ast_core::{Result, Signal};

#[async_trait]
pub trait Whisperer: Send + Sync {
    async fn scan(&self) -> Result<Vec<Signal>>;
}

pub struct NullWhisperer;

#[async_trait]
impl Whisperer for NullWhisperer {
    async fn scan(&self) -> Result<Vec<Signal>> {
        Ok(Vec::new())
    }
}
