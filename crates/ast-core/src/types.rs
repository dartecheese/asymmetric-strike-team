use std::fmt;
use std::str::FromStr;

use rust_decimal::{Decimal, RoundingStrategy};
use serde::{Deserialize, Serialize};

use crate::error::{AstError, Result};

macro_rules! validated_string_newtype {
    ($name:ident, $label:literal) => {
        #[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord, Hash)]
        #[serde(transparent)]
        pub struct $name(String);

        impl $name {
            pub fn new(value: impl Into<String>) -> Result<Self> {
                let value = value.into().trim().to_owned();
                if value.is_empty() {
                    return Err(AstError::Validation(format!(
                        "{} must not be empty",
                        $label
                    )));
                }
                Ok(Self(value))
            }

            pub fn as_str(&self) -> &str {
                &self.0
            }
        }

        impl fmt::Display for $name {
            fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str(&self.0)
            }
        }

        impl TryFrom<String> for $name {
            type Error = AstError;

            fn try_from(value: String) -> Result<Self> {
                Self::new(value)
            }
        }

        impl TryFrom<&str> for $name {
            type Error = AstError;

            fn try_from(value: &str) -> Result<Self> {
                Self::new(value)
            }
        }

        impl From<$name> for String {
            fn from(value: $name) -> Self {
                value.0
            }
        }
    };
}

validated_string_newtype!(Chain, "chain");
validated_string_newtype!(Address, "address");
validated_string_newtype!(Symbol, "symbol");
validated_string_newtype!(Router, "router");
validated_string_newtype!(ExchangeName, "exchange");
validated_string_newtype!(TradingPair, "pair");

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Token {
    pub address: Address,
    pub chain: Chain,
    pub symbol: Symbol,
    pub decimals: u8,
}

impl Token {
    pub fn new(
        address: impl Into<String>,
        chain: impl Into<String>,
        symbol: impl Into<String>,
        decimals: u8,
    ) -> Result<Self> {
        if decimals > 38 {
            return Err(AstError::Validation(
                "token decimals must be between 0 and 38".into(),
            ));
        }

        Ok(Self {
            address: Address::new(address)?,
            chain: Chain::new(chain)?,
            symbol: Symbol::new(symbol)?,
            decimals,
        })
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(transparent)]
pub struct Usd(pub Decimal);

impl Usd {
    pub fn new(value: Decimal) -> Result<Self> {
        if value.is_sign_negative() {
            return Err(AstError::Validation("USD amount must be non-negative".into()));
        }
        Ok(Self(value.round_dp_with_strategy(
            2,
            RoundingStrategy::MidpointAwayFromZero,
        )))
    }

    pub const fn zero() -> Self {
        Self(Decimal::ZERO)
    }

    pub fn value(self) -> Decimal {
        self.0
    }

    pub const fn raw(&self) -> Decimal {
        self.0
    }
}

impl fmt::Display for Usd {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "${}", self.0)
    }
}

impl FromStr for Usd {
    type Err = AstError;

    fn from_str(s: &str) -> Result<Self> {
        let value = Decimal::from_str(s)?;
        Self::new(value)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum PositionState {
    Pending,
    Open,
    StopLossHit,
    FreeRide,
    Closing,
    Closed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
    Critical,
    Rejected,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum Venue {
    Dex {
        chain: Chain,
        router: Router,
    },
    Cex {
        exchange: ExchangeName,
        pair: TradingPair,
    },
}

impl Venue {
    pub fn dex(chain: impl Into<String>, router: impl Into<String>) -> Result<Self> {
        Ok(Self::Dex {
            chain: Chain::new(chain)?,
            router: Router::new(router)?,
        })
    }

    pub fn cex(exchange: impl Into<String>, pair: impl Into<String>) -> Result<Self> {
        Ok(Self::Cex {
            exchange: ExchangeName::new(exchange)?,
            pair: TradingPair::new(pair)?,
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExecutionOrder {
    token: Token,
    venue: Venue,
    amount_usd: Usd,
}

impl ExecutionOrder {
    pub fn builder() -> ExecutionOrderBuilder {
        ExecutionOrderBuilder::default()
    }

    pub fn token(&self) -> &Token {
        &self.token
    }

    pub fn venue(&self) -> &Venue {
        &self.venue
    }

    pub fn amount_usd(&self) -> Usd {
        self.amount_usd
    }
}

#[derive(Debug, Default, Clone)]
pub struct ExecutionOrderBuilder {
    token: Option<Token>,
    venue: Option<Venue>,
    amount_usd: Option<Usd>,
}

impl ExecutionOrderBuilder {
    pub fn token(mut self, token: Token) -> Self {
        self.token = Some(token);
        self
    }

    pub fn venue(mut self, venue: Venue) -> Self {
        self.venue = Some(venue);
        self
    }

    pub fn amount_usd(mut self, amount_usd: Usd) -> Self {
        self.amount_usd = Some(amount_usd);
        self
    }

    pub fn build(self) -> Result<ExecutionOrder> {
        Ok(ExecutionOrder {
            token: self
                .token
                .ok_or_else(|| AstError::Validation("execution order token is required".into()))?,
            venue: self
                .venue
                .ok_or_else(|| AstError::Validation("execution order venue is required".into()))?,
            amount_usd: self.amount_usd.ok_or_else(|| {
                AstError::Validation("execution order amount_usd is required".into())
            })?,
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub token: Token,
    pub state: PositionState,
    pub amount_usd: Usd,
}

impl Position {
    pub fn transition(self, next: PositionState) -> Result<Self> {
        use PositionState::*;
        let allowed = matches!(
            (&self.state, &next),
            (Pending, Open)
                | (Open, StopLossHit)
                | (Open, FreeRide)
                | (Open, Closing)
                | (FreeRide, Closing)
                | (StopLossHit, Closing)
                | (Closing, Closed)
        );

        if !allowed {
            return Err(AstError::InvalidTransition {
                from: self.state.as_str(),
                to: next.as_str(),
            });
        }

        Ok(Self {
            state: next,
            ..self
        })
    }
}

impl PositionState {
    pub const fn as_str(&self) -> &'static str {
        match self {
            Self::Pending => "Pending",
            Self::Open => "Open",
            Self::StopLossHit => "StopLossHit",
            Self::FreeRide => "FreeRide",
            Self::Closing => "Closing",
            Self::Closed => "Closed",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Signal {
    pub token: Token,
    pub confidence_bps: u16,
    pub source: SignalSource,
    pub reasoning: String,
    pub metrics: SignalMetrics,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum SignalSource {
    DexProfile,
    DexBoost,
    DexProfileAndBoost,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SignalMetrics {
    pub liquidity_usd: Option<Decimal>,
    pub volume_24h_usd: Option<Decimal>,
    pub velocity_score: u16,
    pub price_change_h1_bps: i32,
    pub price_change_h6_bps: i32,
    pub freshness_bonus_bps: u16,
    pub boost_score_bps: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskAssessment {
    pub token: Token,
    pub risk_level: RiskLevel,
    pub max_allocation_usd: Usd,
    pub provider: String,
    pub factors: Vec<RiskFactorScore>,
    pub warnings: Vec<String>,
}

impl RiskAssessment {
    pub fn acceptable(&self) -> bool {
        !matches!(self.risk_level, RiskLevel::Critical | RiskLevel::Rejected)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum RiskFactor {
    Honeypot,
    BuyTax,
    SellTax,
    LiquidityLock,
    ContractVerification,
    UnknownToken,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskFactorScore {
    pub factor: RiskFactor,
    pub risk_level: RiskLevel,
    pub score_bps: u16,
    pub summary: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_token() -> Token {
        Token::new("0xabc", "solana", "AST", 9).expect("token should be valid in test")
    }

    #[test]
    fn usd_requires_positive_values() {
        assert!(Usd::new(Decimal::ZERO).is_err());
        assert!(Usd::new(Decimal::new(-1, 0)).is_err());
        assert_eq!(
            Usd::new(Decimal::new(12345, 3))
                .expect("usd should round and stay valid")
                .value(),
            Decimal::new(1235, 2)
        );
    }

    #[test]
    fn execution_order_builder_requires_all_fields() {
        let error = ExecutionOrder::builder()
            .token(sample_token())
            .build()
            .expect_err("builder must reject incomplete order");

        assert!(matches!(error, AstError::Validation(_)));
    }

    #[test]
    fn position_transition_rejects_invalid_state_change() {
        let position = Position {
            token: sample_token(),
            state: PositionState::Pending,
            amount_usd: Usd::new(Decimal::new(100, 0)).expect("usd should be valid in test"),
        };

        let error = position
            .transition(PositionState::Closed)
            .expect_err("pending cannot transition directly to closed");

        assert!(matches!(error, AstError::InvalidTransition { .. }));
    }
}
