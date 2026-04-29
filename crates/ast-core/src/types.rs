use std::collections::BTreeMap;
use std::fmt;

use alloy_primitives::Address;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

use crate::CoreError;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Chain {
    Ethereum,
    Arbitrum,
    Base,
    Solana,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Token {
    pub address: Address,
    pub chain: Chain,
    pub symbol: String,
    pub decimals: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(transparent)]
pub struct Usd(pub Decimal);

impl Usd {
    pub fn new(value: Decimal) -> Result<Self, CoreError> {
        if value.is_sign_negative() {
            return Err(CoreError::Validation(
                "usd amounts cannot be negative".to_owned(),
            ));
        }

        Ok(Self(value))
    }

    pub fn zero() -> Self {
        Self(Decimal::ZERO)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(transparent)]
pub struct TokenAmount(pub Decimal);

impl TokenAmount {
    pub fn new(value: Decimal) -> Result<Self, CoreError> {
        if value <= Decimal::ZERO {
            return Err(CoreError::Validation(
                "token amount must be greater than zero".to_owned(),
            ));
        }

        Ok(Self(value))
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PositionState {
    Pending,
    Open,
    StopLossHit,
    FreeRide,
    Closing,
    Closed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RiskLevel {
    Low,
    Medium,
    High,
    Critical,
    Rejected,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RiskDecision {
    Accept,
    Reject,
    Review,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Venue {
    Dex { chain: Chain, router: Address },
    Cex { exchange: String, pair: String },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StrategyProfile {
    pub name: String,
    pub description: String,
    pub max_position_size_usd: Usd,
    pub max_slippage_bps: u16,
    pub risk_tolerance: RiskLevel,
    pub scan_interval_seconds: u64,
    pub paper_trading: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Signal {
    pub id: String,
    pub token: Token,
    pub venue: Venue,
    pub price_usd: Usd,
    pub volume_24h_usd: Usd,
    pub liquidity_usd: Usd,
    pub target_notional_usd: Usd,
    pub timestamp_ms: u64,
    pub metadata: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RiskFactor {
    pub name: String,
    pub score: u8,
    pub details: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RiskAssessment {
    pub level: RiskLevel,
    pub decision: RiskDecision,
    pub rationale: String,
    pub approved_notional_usd: Usd,
    pub factors: Vec<RiskFactor>,
}

impl RiskAssessment {
    pub fn acceptable(&self) -> bool {
        matches!(self.decision, RiskDecision::Accept)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExecutionOrder {
    pub id: String,
    pub strategy: String,
    pub signal_id: String,
    pub token: Token,
    pub venue: Venue,
    pub amount: TokenAmount,
    pub notional_usd: Usd,
    pub limit_price_usd: Usd,
    pub max_slippage_bps: u16,
}

#[derive(Debug, Clone, Default)]
pub struct ExecutionOrderBuilder {
    id: Option<String>,
    strategy: Option<String>,
    signal_id: Option<String>,
    token: Option<Token>,
    venue: Option<Venue>,
    amount: Option<TokenAmount>,
    notional_usd: Option<Usd>,
    limit_price_usd: Option<Usd>,
    max_slippage_bps: Option<u16>,
}

impl ExecutionOrder {
    pub fn builder() -> ExecutionOrderBuilder {
        ExecutionOrderBuilder::default()
    }
}

impl ExecutionOrderBuilder {
    pub fn id(mut self, id: impl Into<String>) -> Self {
        self.id = Some(id.into());
        self
    }

    pub fn strategy(mut self, strategy: impl Into<String>) -> Self {
        self.strategy = Some(strategy.into());
        self
    }

    pub fn signal_id(mut self, signal_id: impl Into<String>) -> Self {
        self.signal_id = Some(signal_id.into());
        self
    }

    pub fn token(mut self, token: Token) -> Self {
        self.token = Some(token);
        self
    }

    pub fn venue(mut self, venue: Venue) -> Self {
        self.venue = Some(venue);
        self
    }

    pub fn amount(mut self, amount: TokenAmount) -> Self {
        self.amount = Some(amount);
        self
    }

    pub fn notional_usd(mut self, notional_usd: Usd) -> Self {
        self.notional_usd = Some(notional_usd);
        self
    }

    pub fn limit_price_usd(mut self, limit_price_usd: Usd) -> Self {
        self.limit_price_usd = Some(limit_price_usd);
        self
    }

    pub fn max_slippage_bps(mut self, max_slippage_bps: u16) -> Self {
        self.max_slippage_bps = Some(max_slippage_bps);
        self
    }

    pub fn build(self) -> Result<ExecutionOrder, CoreError> {
        Ok(ExecutionOrder {
            id: self
                .id
                .ok_or_else(|| CoreError::Validation("id is required".to_owned()))?,
            strategy: self
                .strategy
                .ok_or_else(|| CoreError::Validation("strategy is required".to_owned()))?,
            signal_id: self
                .signal_id
                .ok_or_else(|| CoreError::Validation("signal_id is required".to_owned()))?,
            token: self
                .token
                .ok_or_else(|| CoreError::Validation("token is required".to_owned()))?,
            venue: self
                .venue
                .ok_or_else(|| CoreError::Validation("venue is required".to_owned()))?,
            amount: self
                .amount
                .ok_or_else(|| CoreError::Validation("amount is required".to_owned()))?,
            notional_usd: self
                .notional_usd
                .ok_or_else(|| CoreError::Validation("notional_usd is required".to_owned()))?,
            limit_price_usd: self.limit_price_usd.ok_or_else(|| {
                CoreError::Validation("limit_price_usd is required".to_owned())
            })?,
            max_slippage_bps: self.max_slippage_bps.ok_or_else(|| {
                CoreError::Validation("max_slippage_bps is required".to_owned())
            })?,
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionStatus {
    Filled,
    Rejected,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExecutionResult {
    pub order_id: String,
    pub status: ExecutionStatus,
    pub fill_price_usd: Usd,
    pub filled_amount: TokenAmount,
    pub slippage_bps: u16,
    pub notional_usd: Usd,
    pub venue: Venue,
    pub timestamp_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Position {
    pub id: String,
    pub strategy: String,
    pub signal_id: String,
    pub token: Token,
    pub state: PositionState,
    pub venue: Venue,
    pub quantity: TokenAmount,
    pub entry_price_usd: Usd,
    pub current_price_usd: Usd,
    pub entry_notional_usd: Usd,
    pub realized_pnl_usd: Usd,
    pub stop_loss_price_usd: Usd,
    pub take_profit_price_usd: Usd,
    pub monitor_passes: u64,
    pub updated_at_ms: u64,
}

impl fmt::Display for Chain {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let value = match self {
            Self::Ethereum => "ethereum",
            Self::Arbitrum => "arbitrum",
            Self::Base => "base",
            Self::Solana => "solana",
        };

        f.write_str(value)
    }
}

pub type TradingSignal = Signal;

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use alloy_primitives::Address;
    use rust_decimal::Decimal;

    use super::{
        Chain, ExecutionOrder, ExecutionStatus, RiskDecision, RiskLevel, Signal, Token,
        TokenAmount, Usd, Venue,
    };

    #[test]
    fn execution_order_builder_requires_all_fields() {
        let result = ExecutionOrder::builder().build();
        assert!(result.is_err());
    }

    #[test]
    fn token_amount_must_be_positive() {
        let result = TokenAmount::new(Decimal::ZERO);
        assert!(result.is_err());
    }

    #[test]
    fn execution_order_builder_accepts_valid_input() {
        let token = Token {
            address: Address::ZERO,
            chain: Chain::Base,
            symbol: "AST".to_owned(),
            decimals: 18,
        };
        let order = ExecutionOrder::builder()
            .id("order-1")
            .strategy("swift")
            .signal_id("signal-1")
            .token(token.clone())
            .venue(Venue::Dex {
                chain: Chain::Base,
                router: Address::ZERO,
            })
            .amount(TokenAmount::new(Decimal::new(10, 0)).expect("amount should be valid"))
            .notional_usd(Usd::new(Decimal::new(100, 0)).expect("usd should be valid"))
            .limit_price_usd(Usd::new(Decimal::new(100, 0)).expect("usd should be valid"))
            .max_slippage_bps(75)
            .build()
            .expect("order should build");

        assert_eq!(order.token, token);
    }

    #[test]
    fn risk_decision_acceptability_is_explicit() {
        let assessment = super::RiskAssessment {
            level: RiskLevel::Low,
            decision: RiskDecision::Accept,
            rationale: "ok".to_owned(),
            approved_notional_usd: Usd::new(Decimal::ONE).expect("valid usd"),
            factors: Vec::new(),
        };

        assert!(assessment.acceptable());
    }

    #[test]
    fn signal_serializes() {
        let signal = Signal {
            id: "signal".to_owned(),
            token: Token {
                address: Address::ZERO,
                chain: Chain::Base,
                symbol: "AST".to_owned(),
                decimals: 18,
            },
            venue: Venue::Dex {
                chain: Chain::Base,
                router: Address::ZERO,
            },
            price_usd: Usd::new(Decimal::ONE).expect("valid usd"),
            volume_24h_usd: Usd::new(Decimal::new(1000, 0)).expect("valid usd"),
            liquidity_usd: Usd::new(Decimal::new(2000, 0)).expect("valid usd"),
            target_notional_usd: Usd::new(Decimal::new(100, 0)).expect("valid usd"),
            timestamp_ms: 1,
            metadata: BTreeMap::new(),
        };

        let json = serde_json::to_string(&signal).expect("signal should serialize");
        assert!(json.contains("\"signal\""));
        let status = ExecutionStatus::Filled;
        assert_eq!(
            serde_json::to_string(&status).expect("status should serialize"),
            "\"filled\""
        );
    }
}
