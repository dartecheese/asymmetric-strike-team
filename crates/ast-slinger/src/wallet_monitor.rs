use alloy::{
    network::EthereumWallet,
    primitives::{Address, U256},
    providers::{Provider, ProviderBuilder},
    signers::local::PrivateKeySigner,
    transports::http::reqwest::Url,
};
use ast_core::LiveExecutionConfig;
use rust_decimal::Decimal;

use crate::SlingerError;

type Result<T> = std::result::Result<T, SlingerError>;

/// Polls native chain-currency balance for the live wallet and reports
/// it as a USD-denominated `Decimal`. The runtime spins one of these
/// in a tokio task and feeds the result into `LiveSafetyState` so the
/// circuit breaker can refuse trades when the wallet runs dry.
///
/// One-shot — call `poll_balance_usd()` from a loop with whatever
/// cadence makes sense (Base = cheap to poll, can do every ~10s;
/// Ethereum = back off to ~30-60s to be polite to your RPC budget).
pub struct WalletBalanceMonitor {
    config: LiveExecutionConfig,
    wallet_address: Address,
}

impl WalletBalanceMonitor {
    pub fn new(config: LiveExecutionConfig) -> Result<Self> {
        if config.private_key.is_empty() {
            return Err(SlingerError::OrderValidation(
                "wallet monitor requires a private key".into(),
            ));
        }
        if config.rpc_url.is_empty() {
            return Err(SlingerError::OrderValidation(
                "wallet monitor requires an rpc_url".into(),
            ));
        }
        let signer: PrivateKeySigner = config
            .private_key
            .parse()
            .map_err(|_| SlingerError::OrderValidation("invalid private key".into()))?;
        Ok(Self {
            wallet_address: signer.address(),
            config,
        })
    }

    pub fn wallet_address(&self) -> Address {
        self.wallet_address
    }

    /// Query the current native-chain balance and convert to USD via
    /// `config.eth_price_usd`. Returns the USD value as a `Decimal`.
    pub async fn poll_balance_usd(&self) -> Result<Decimal> {
        if self.config.eth_price_usd.is_zero() {
            return Err(SlingerError::OrderValidation(
                "eth_price_usd is zero — set an oracle price before polling".into(),
            ));
        }

        let signer: PrivateKeySigner = self
            .config
            .private_key
            .parse()
            .map_err(|_| SlingerError::OrderValidation("invalid private key".into()))?;
        let url: Url = self
            .config
            .rpc_url
            .parse()
            .map_err(|_| SlingerError::OrderValidation("invalid rpc_url".into()))?;
        let wallet = EthereumWallet::from(signer);
        let provider = ProviderBuilder::new().wallet(wallet).on_http(url);

        let balance: U256 = provider
            .get_balance(self.wallet_address)
            .await
            .map_err(|e| SlingerError::ExternalService {
                service: "rpc",
                message: format!("get_balance({}) failed: {e}", self.wallet_address),
            })?;

        let balance_dec = Decimal::from_str_exact(&balance.to_string()).map_err(|e| {
            SlingerError::Execution(format!("balance U256 → Decimal: {e}"))
        })?;
        let one_eth_in_wei =
            Decimal::new(1_000_000_000_000_000_000i64, 0);
        let balance_eth = balance_dec / one_eth_in_wei;
        let balance_usd = (balance_eth * self.config.eth_price_usd).round_dp(8);
        Ok(balance_usd.max(Decimal::ZERO))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const TEST_KEY: &str =
        "0x0000000000000000000000000000000000000000000000000000000000000001";

    #[test]
    fn monitor_rejects_empty_private_key() {
        let cfg = LiveExecutionConfig {
            private_key: String::new(),
            rpc_url: "http://localhost:8545".into(),
            ..LiveExecutionConfig::default()
        };
        assert!(WalletBalanceMonitor::new(cfg).is_err());
    }

    #[test]
    fn monitor_rejects_empty_rpc_url() {
        let cfg = LiveExecutionConfig {
            private_key: TEST_KEY.into(),
            rpc_url: String::new(),
            ..LiveExecutionConfig::default()
        };
        assert!(WalletBalanceMonitor::new(cfg).is_err());
    }

    #[test]
    fn monitor_rejects_invalid_private_key() {
        let cfg = LiveExecutionConfig {
            private_key: "not-a-key".into(),
            rpc_url: "http://localhost:8545".into(),
            ..LiveExecutionConfig::default()
        };
        assert!(WalletBalanceMonitor::new(cfg).is_err());
    }

    #[test]
    fn monitor_derives_wallet_address_from_key() {
        let cfg = LiveExecutionConfig {
            private_key: TEST_KEY.into(),
            rpc_url: "http://localhost:8545".into(),
            ..LiveExecutionConfig::default()
        };
        let monitor = WalletBalanceMonitor::new(cfg).expect("monitor builds");
        // Private key 0x0...01 maps to a known well-defined address.
        // We don't hardcode it here — just assert it's not the zero address.
        assert_ne!(monitor.wallet_address(), Address::ZERO);
    }

    #[tokio::test]
    async fn poll_rejects_when_eth_price_is_zero() {
        let cfg = LiveExecutionConfig {
            private_key: TEST_KEY.into(),
            rpc_url: "http://localhost:8545".into(),
            eth_price_usd: Decimal::ZERO,
            ..LiveExecutionConfig::default()
        };
        let monitor = WalletBalanceMonitor::new(cfg).expect("monitor builds");
        assert!(monitor.poll_balance_usd().await.is_err());
    }
}
