use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

use crate::error::{AstError, Result};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Token {
    pub address: String,
    pub chain: String,
    pub symbol: String,
    pub decimals: u8,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct Usd(pub Decimal);

impl Usd {
    pub fn new(value: Decimal) -> Result<Self> {
        if value.is_sign_negative() || value.is_zero() {
            return Err(AstError::Validation("USD amount must be positive".into()));
        }
        Ok(Self(value))
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
    Dex { chain: String, router: String },
    Cex { exchange: String, pair: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionOrder {
    pub token: Token,
    pub venue: Venue,
    pub amount_usd: Usd,
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

        Ok(Self { state: next, ..self })
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
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskAssessment {
    pub token: Token,
    pub risk_level: RiskLevel,
    pub max_allocation_usd: Usd,
}

impl RiskAssessment {
    pub fn acceptable(&self) -> bool {
        !matches!(self.risk_level, RiskLevel::Critical | RiskLevel::Rejected)
    }
}
