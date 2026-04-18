use std::collections::HashSet;

use async_trait::async_trait;
use ast_core::{Result, RiskAssessment, Router, Signal, Venue};

#[async_trait]
pub trait VenueResolver: Send + Sync {
    async fn resolve_venue(&self, signal: &Signal, risk: &RiskAssessment) -> Result<Venue>;
}

/// Routes EVM chains to DEX and everything else to CEX.
/// EVM chain identifiers accepted: name (ethereum, base, arbitrum, …) or decimal chain ID.
pub struct ChainVenueResolver {
    dex_router: Router,
    cex_exchange: String,
    evm_chains: HashSet<String>,
}

impl ChainVenueResolver {
    pub fn new(dex_router: Router, cex_exchange: impl Into<String>) -> Self {
        let evm_chains = [
            "ethereum", "eth", "1",
            "base", "8453",
            "arbitrum", "arb", "42161",
            "optimism", "op", "10",
            "polygon", "matic", "137",
            "bnb", "bsc", "56",
            "avalanche", "avax", "43114",
            "scroll", "534352",
            "zksync", "324",
            "linea", "59144",
        ]
        .iter()
        .map(|s| s.to_string())
        .collect();

        Self {
            dex_router,
            cex_exchange: cex_exchange.into(),
            evm_chains,
        }
    }

    fn is_evm(&self, chain: &str) -> bool {
        self.evm_chains.contains(&chain.to_lowercase())
    }
}

#[async_trait]
impl VenueResolver for ChainVenueResolver {
    async fn resolve_venue(&self, signal: &Signal, _risk: &RiskAssessment) -> Result<Venue> {
        let chain = signal.token.chain.as_str();
        if self.is_evm(chain) {
            Venue::dex(chain, self.dex_router.as_str())
        } else {
            // Non-EVM or explicit "cex" chain — route to CEX as SYMBOL/USDT
            let pair = format!("{}/USDT", signal.token.symbol.as_str().to_uppercase());
            Venue::cex(&self.cex_exchange, pair)
        }
    }
}

/// Always routes to the same venue. Useful for single-chain paper trading.
#[derive(Debug, Clone)]
pub struct StaticVenueResolver {
    venue: Venue,
}

impl StaticVenueResolver {
    pub fn new(venue: Venue) -> Self {
        Self { venue }
    }
}

#[async_trait]
impl VenueResolver for StaticVenueResolver {
    async fn resolve_venue(&self, _signal: &Signal, _risk: &RiskAssessment) -> Result<Venue> {
        Ok(self.venue.clone())
    }
}

#[cfg(test)]
mod tests {
    use ast_core::{Chain, Router, Token, Usd, Venue};
    use rust_decimal::Decimal;

    use super::*;

    fn make_signal(chain: &str, symbol: &str) -> Signal {
        Signal {
            token: Token::new("0xabc", chain, symbol, 18).expect("token valid"),
            confidence_bps: 5000,
            source: ast_core::SignalSource::DexProfile,
            reasoning: String::new(),
            metrics: Default::default(),
        }
    }

    fn dummy_risk() -> RiskAssessment {
        RiskAssessment {
            token: Token::new("0xabc", "ethereum", "TEST", 18).expect("token valid"),
            risk_level: ast_core::RiskLevel::Low,
            max_allocation_usd: Usd::new(Decimal::new(10, 0)).expect("usd valid"),
            provider: "test".into(),
            factors: vec![],
            warnings: vec![],
        }
    }

    #[tokio::test]
    async fn evm_chain_routes_to_dex() {
        let router = Router::new("0xUniV2Router").expect("router valid");
        let resolver = ChainVenueResolver::new(router, "binance");
        let signal = make_signal("ethereum", "PEPE");
        let risk = dummy_risk();
        let venue = resolver.resolve_venue(&signal, &risk).await.expect("resolve");
        assert!(matches!(venue, Venue::Dex { .. }));
    }

    #[tokio::test]
    async fn non_evm_chain_routes_to_cex() {
        let router = Router::new("0xUniV2Router").expect("router valid");
        let resolver = ChainVenueResolver::new(router, "binance");
        let signal = make_signal("solana", "BONK");
        let risk = dummy_risk();
        let venue = resolver.resolve_venue(&signal, &risk).await.expect("resolve");
        assert!(matches!(venue, Venue::Cex { .. }));
    }
}
