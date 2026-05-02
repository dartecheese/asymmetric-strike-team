use async_trait::async_trait;
use rust_decimal::Decimal;
use thiserror::Error;

use crate::Position;

/// What you get back from a successful on-chain close. Used by the
/// Reaper to set realized PnL based on the actual ETH received from
/// the sell, not just the position's last marked price.
#[derive(Debug, Clone)]
pub struct CloseReceipt {
    pub tx_hash: String,
    pub eth_received_usd: Decimal,
    pub fee_usd: Decimal,
    pub block_number: u64,
}

#[derive(Debug, Error)]
pub enum CloseError {
    #[error("close validation failed: {0}")]
    Validation(String),
    #[error("close execution failed: {0}")]
    Execution(String),
    #[error("close skipped: {0}")]
    Skipped(String),
}

/// Adapter for live-mode position closes. The Reaper calls this when
/// a stop-loss triggers. In paper mode, the runtime supplies no
/// executor and the Reaper just file-marks the position closed —
/// matches existing behavior. In live mode, this submits a token →
/// ETH swap and returns the actual ETH received, so realized PnL
/// reflects what really happened on-chain.
///
/// Lives in `ast-core` so both `ast-reaper` (consumer) and
/// `ast-slinger` (provider) can reference it without a cycle.
#[async_trait]
pub trait LiveCloseExecutor: Send + Sync {
    /// Execute a position close. Implementors should:
    /// 1. Convert `position.quantity` (Decimal) to a raw token-unit
    ///    integer using `position.token.decimals`.
    /// 2. Submit a sell swap (with the right router for the chain).
    /// 3. Wait for the receipt — return Err if the swap reverts.
    /// 4. Compute realized USD from the actual ETH received.
    async fn close_position(&self, position: &Position) -> Result<CloseReceipt, CloseError>;
}
