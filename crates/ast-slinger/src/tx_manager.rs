use std::collections::HashMap;
use std::time::{Duration, Instant};

use alloy::primitives::{Address, B256};
use alloy::providers::Provider;
use ast_core::{AstError, Result};
use tokio::sync::Mutex;

/// Tracks the next nonce to use per (chain_id, wallet_address).
/// Always queries the chain for the pending nonce on first access,
/// then increments locally to avoid RPC round-trips on rapid trades.
pub struct NonceManager {
    // key: (chain_id, lowercase hex address)
    state: Mutex<HashMap<(u64, String), u64>>,
}

impl Default for NonceManager {
    fn default() -> Self {
        Self {
            state: Mutex::new(HashMap::new()),
        }
    }
}

impl NonceManager {
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns the next nonce for the given wallet. Fetches from chain on first call;
    /// subsequent calls increment locally until `reset` is called.
    pub async fn next_nonce<P: Provider>(
        &self,
        chain_id: u64,
        wallet: Address,
        provider: &P,
    ) -> Result<u64> {
        let key = (chain_id, format!("{wallet:?}").to_lowercase());
        let mut state = self.state.lock().await;

        if let Some(nonce) = state.get_mut(&key) {
            let current = *nonce;
            *nonce += 1;
            return Ok(current);
        }

        // First access: query the chain for pending nonce
        let on_chain = provider
            .get_transaction_count(wallet)
            .await
            .map_err(|e| AstError::ExternalService {
                service: "rpc",
                message: format!("nonce query failed: {e}"),
            })?;

        state.insert(key, on_chain + 1);
        Ok(on_chain)
    }

    /// Invalidates the cached nonce for this wallet, forcing a fresh chain query next time.
    /// Call this after a TX fails due to nonce conflict.
    pub async fn reset(&self, chain_id: u64, wallet: Address) {
        let key = (chain_id, format!("{wallet:?}").to_lowercase());
        self.state.lock().await.remove(&key);
    }
}

/// Records a submitted transaction and when it was sent.
#[derive(Debug, Clone)]
pub struct PendingTx {
    pub hash: B256,
    pub chain_id: u64,
    pub wallet: Address,
    pub nonce: u64,
    pub submitted_at: Instant,
}

impl PendingTx {
    pub fn new(hash: B256, chain_id: u64, wallet: Address, nonce: u64) -> Self {
        Self {
            hash,
            chain_id,
            wallet,
            nonce,
            submitted_at: Instant::now(),
        }
    }
}

/// Monitors pending transactions and detects stuck ones.
pub struct TxMonitor {
    pending: Mutex<Vec<PendingTx>>,
    pub stuck_timeout: Duration,
}

impl TxMonitor {
    pub fn new(stuck_timeout: Duration) -> Self {
        Self {
            pending: Mutex::new(Vec::new()),
            stuck_timeout,
        }
    }

    /// Begin tracking a newly submitted transaction.
    pub async fn track(&self, tx: PendingTx) {
        self.pending.lock().await.push(tx);
    }

    /// Remove a confirmed transaction from tracking.
    pub async fn confirm(&self, hash: B256) {
        self.pending.lock().await.retain(|t| t.hash != hash);
    }

    /// Returns all transactions that have been pending longer than `stuck_timeout`
    /// and are not yet confirmed on chain.
    pub async fn find_stuck<P: Provider>(&self, provider: &P) -> Vec<PendingTx> {
        let now = Instant::now();
        let candidates: Vec<PendingTx> = self
            .pending
            .lock()
            .await
            .iter()
            .filter(|t| now.duration_since(t.submitted_at) > self.stuck_timeout)
            .cloned()
            .collect();

        let mut stuck = Vec::new();
        for tx in candidates {
            let receipt = provider
                .get_transaction_receipt(tx.hash)
                .await
                .ok()
                .flatten();
            if receipt.is_none() {
                stuck.push(tx);
            }
        }
        stuck
    }

    /// Estimate a replacement gas price for speeding up a stuck TX.
    /// Returns at least `current_gas_price * 1.15` (EIP-2929 RBF minimum).
    pub fn replacement_gas_price(current_gas_price: u128) -> u128 {
        (current_gas_price * 115) / 100
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn replacement_gas_price_is_at_least_15_percent_higher() {
        let base: u128 = 10_000_000_000; // 10 gwei
        let replacement = TxMonitor::replacement_gas_price(base);
        assert!(replacement >= base * 115 / 100);
    }
}
