pub mod cex;
pub mod dex;
pub mod gas;
pub mod slippage;
pub mod tx_manager;
pub mod venue_resolver;

use async_trait::async_trait;
use ast_core::{ExecutionOrder, Result, RiskAssessment, Signal};

#[async_trait]
pub trait Slinger: Send + Sync {
    async fn route(&self, signal: &Signal, risk: &RiskAssessment) -> Result<ExecutionOrder>;
}

pub struct NullSlinger;

#[async_trait]
impl Slinger for NullSlinger {
    async fn route(&self, _signal: &Signal, _risk: &RiskAssessment) -> Result<ExecutionOrder> {
        Err(ast_core::AstError::Validation(
            "no execution venue configured".into(),
        ))
    }
}

pub struct RoutingSlinger<R> {
    resolver: R,
}

impl<R> RoutingSlinger<R> {
    pub fn new(resolver: R) -> Self {
        Self { resolver }
    }
}

#[async_trait]
impl<R> Slinger for RoutingSlinger<R>
where
    R: venue_resolver::VenueResolver + Send + Sync,
{
    async fn route(&self, signal: &Signal, risk: &RiskAssessment) -> Result<ExecutionOrder> {
        let venue = self.resolver.resolve_venue(signal, risk).await?;
        ExecutionOrder::builder()
            .token(signal.token.clone())
            .venue(venue)
            .amount_usd(risk.max_allocation_usd)
            .build()
    }
}

pub use cex::{CexExecutor, CexQuote, CexVenue};
pub use dex::{DexConfig, DexQuote, DexSwapExecutor, DexVenue};
pub use gas::{GasConfig, GasEstimator, GasParams};
pub use slippage::{SlippageCheck, SlippageGuard};
pub use tx_manager::{NonceManager, PendingTx, TxMonitor};
pub use venue_resolver::{ChainVenueResolver, StaticVenueResolver, VenueResolver};
