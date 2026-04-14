pub mod dexscreener;

use std::time::Duration;

use ast_core::{AstError, Result, Signal};
use async_trait::async_trait;

pub use dexscreener::{DexScreenerClient, DexScreenerConfig, DexScreenerWhisperer};

#[async_trait]
pub trait Whisperer: Send + Sync {
    async fn scan(&self) -> Result<Vec<Signal>>;

    async fn scan_with_timeout(&self, timeout: Duration) -> Result<Vec<Signal>> {
        tokio::time::timeout(timeout, self.scan())
            .await
            .map_err(|_| AstError::Timeout {
                service: "whisperer.scan",
                duration_ms: timeout.as_millis() as u64,
            })?
    }
}

pub struct NullWhisperer;

#[async_trait]
impl Whisperer for NullWhisperer {
    async fn scan(&self) -> Result<Vec<Signal>> {
        Ok(Vec::new())
    }
}
