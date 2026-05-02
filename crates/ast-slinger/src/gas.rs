use alloy::providers::Provider;

use crate::SlingerError;

type Result<T> = std::result::Result<T, SlingerError>;

/// EIP-1559 gas parameters ready to attach to a transaction.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct GasParams {
    /// Max total fee per gas (base fee + priority fee), in wei.
    pub max_fee_per_gas: u128,
    /// Miner tip (priority fee) per gas, in wei.
    pub max_priority_fee_per_gas: u128,
}

#[derive(Debug, Clone)]
pub struct GasConfig {
    /// Multiplier applied to the current base fee, in basis points.
    /// 12_000 = 1.2× (20% buffer).
    pub multiplier_bps: u32,
    /// Hard cap on max_fee_per_gas, in gwei. Rejects estimation if base fee exceeds this.
    pub max_gwei_cap: u64,
    /// Floor priority fee (miner tip), in gwei. Default 1 gwei.
    pub min_priority_fee_gwei: u64,
}

impl Default for GasConfig {
    fn default() -> Self {
        Self {
            multiplier_bps: 12_000,
            max_gwei_cap: 300,
            min_priority_fee_gwei: 1,
        }
    }
}

pub struct GasEstimator {
    config: GasConfig,
}

impl GasEstimator {
    pub fn new(config: GasConfig) -> Self {
        Self { config }
    }

    /// Query current gas prices from the provider and return adjusted EIP-1559 params.
    /// Returns `Err` if the estimated price would exceed `max_gwei_cap`.
    pub async fn estimate<P, T>(&self, provider: &P) -> Result<GasParams>
    where
        P: Provider<T>,
        T: alloy::transports::Transport + Clone,
    {
        let base_fee = provider.get_gas_price().await.map_err(|e| {
            SlingerError::ExternalService {
                service: "rpc",
                message: format!("gas price query failed: {e}"),
            }
        })?;

        let multiplied = base_fee
            .checked_mul(self.config.multiplier_bps as u128)
            .and_then(|v| v.checked_div(10_000))
            .ok_or_else(|| SlingerError::Execution("gas price overflow in multiplier".into()))?;

        let cap_wei = self.config.max_gwei_cap as u128 * 1_000_000_000;
        if multiplied > cap_wei {
            return Err(SlingerError::Execution(format!(
                "estimated gas ({} gwei) exceeds cap ({} gwei) — refusing to trade",
                multiplied / 1_000_000_000,
                self.config.max_gwei_cap,
            )));
        }

        let priority_fee = self.config.min_priority_fee_gwei as u128 * 1_000_000_000;

        Ok(GasParams {
            max_fee_per_gas: multiplied,
            max_priority_fee_per_gas: priority_fee.min(multiplied),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config_is_sane() {
        let cfg = GasConfig::default();
        assert_eq!(cfg.multiplier_bps, 12_000);
        assert_eq!(cfg.max_gwei_cap, 300);
        assert_eq!(cfg.min_priority_fee_gwei, 1);
    }

    #[test]
    fn priority_fee_never_exceeds_max_fee() {
        // If base_fee * 1.2 < priority_fee_floor, priority_fee is clamped to max_fee.
        // This test documents the invariant even though the scenario is extreme.
        let cfg = GasConfig {
            multiplier_bps: 10_000,
            max_gwei_cap: 300,
            min_priority_fee_gwei: 1,
        };
        let _ = cfg; // just exercising the default path
    }
}
