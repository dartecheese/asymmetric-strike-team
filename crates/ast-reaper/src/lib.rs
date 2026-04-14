use async_trait::async_trait;
use ast_core::Result;
use ast_safety::AuthorizedOrder;

#[async_trait]
pub trait Reaper: Send + Sync {
    async fn track(&self, order: AuthorizedOrder) -> Result<()>;
    async fn monitor_positions(&self) -> Result<()>;
}

pub struct NullReaper;

#[async_trait]
impl Reaper for NullReaper {
    async fn track(&self, _order: AuthorizedOrder) -> Result<()> {
        Ok(())
    }

    async fn monitor_positions(&self) -> Result<()> {
        Ok(())
    }
}
