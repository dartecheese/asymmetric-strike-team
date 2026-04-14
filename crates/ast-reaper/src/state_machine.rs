use ast_core::{AstError, ExecutionOrder, Position, PositionState, Result, Token, Usd, Venue};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ManagedPosition {
    pub token: Token,
    pub venue: Venue,
    pub state: PositionState,
    pub amount_usd: Usd,
    pub entry_value_usd: Usd,
    pub current_value_usd: Usd,
    pub peak_value_usd: Usd,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReaperAction {
    Hold,
    FreeRide,
    StopLoss,
    TrailStop,
}

#[derive(Debug, Clone, Copy)]
pub struct ReaperThresholds {
    pub take_profit_pct: Decimal,
    pub stop_loss_pct: Decimal,
    pub trailing_stop_pct: Decimal,
}

impl Default for ReaperThresholds {
    fn default() -> Self {
        Self {
            take_profit_pct: Decimal::new(100, 0),
            stop_loss_pct: Decimal::new(-30, 0),
            trailing_stop_pct: Decimal::new(15, 0),
        }
    }
}

impl ManagedPosition {
    pub fn from_order(order: ExecutionOrder) -> Result<Self> {
        let token = order.token().clone();
        let amount_usd = order.amount_usd();
        let venue = order.venue().clone();

        let position = Position {
            token,
            state: PositionState::Pending,
            amount_usd,
        }
        .transition(PositionState::Open)?;

        Ok(Self {
            token: position.token,
            venue,
            state: position.state,
            amount_usd: position.amount_usd,
            entry_value_usd: position.amount_usd,
            current_value_usd: position.amount_usd,
            peak_value_usd: position.amount_usd,
        })
    }

    pub fn restore(
        token: Token,
        venue: Venue,
        state: PositionState,
        amount_usd: Usd,
        entry_value_usd: Usd,
        current_value_usd: Usd,
        peak_value_usd: Usd,
    ) -> Result<Self> {
        let managed = Self {
            token,
            venue,
            state,
            amount_usd,
            entry_value_usd,
            current_value_usd,
            peak_value_usd,
        };
        managed.validate_restore()?;
        Ok(managed)
    }

    pub fn id(&self) -> String {
        self.token.address.as_str().to_lowercase()
    }

    pub fn evaluate(
        &mut self,
        current_value_usd: Usd,
        thresholds: ReaperThresholds,
    ) -> Result<ReaperAction> {
        self.current_value_usd = current_value_usd;
        if self.current_value_usd.0 > self.peak_value_usd.0 {
            self.peak_value_usd = self.current_value_usd;
        }

        let pnl_pct = self.pnl_pct();
        if self.state == PositionState::Open && pnl_pct <= thresholds.stop_loss_pct {
            self.state = self.transition(PositionState::StopLossHit)?;
            return Ok(ReaperAction::StopLoss);
        }

        if self.state == PositionState::Open && pnl_pct >= thresholds.take_profit_pct {
            self.state = self.transition(PositionState::FreeRide)?;
            return Ok(ReaperAction::FreeRide);
        }

        if self.state == PositionState::FreeRide {
            let drawdown_pct = self.drawdown_pct();
            if drawdown_pct <= -thresholds.trailing_stop_pct {
                self.state = self.transition(PositionState::Closing)?;
                return Ok(ReaperAction::TrailStop);
            }
        }

        Ok(ReaperAction::Hold)
    }

    pub fn close(self) -> Result<Self> {
        let next_state = self.transition(PositionState::Closed)?;
        Ok(Self {
            state: next_state,
            ..self
        })
    }

    pub fn pnl_pct(&self) -> Decimal {
        ((self.current_value_usd.0 - self.entry_value_usd.0) / self.entry_value_usd.0)
            * Decimal::new(100, 0)
    }

    pub fn drawdown_pct(&self) -> Decimal {
        ((self.current_value_usd.0 - self.peak_value_usd.0) / self.peak_value_usd.0)
            * Decimal::new(100, 0)
    }

    pub fn is_active(&self) -> bool {
        matches!(
            self.state,
            PositionState::Pending
                | PositionState::Open
                | PositionState::StopLossHit
                | PositionState::FreeRide
                | PositionState::Closing
        )
    }

    fn transition(&self, next: PositionState) -> Result<PositionState> {
        Position {
            token: self.token.clone(),
            state: self.state.clone(),
            amount_usd: self.amount_usd,
        }
        .transition(next)
        .map(|position| position.state)
    }

    fn validate_restore(&self) -> Result<()> {
        if self.current_value_usd.0 > self.peak_value_usd.0 {
            return Err(AstError::PersistenceCorruption(format!(
                "position {} current value exceeds peak value",
                self.id()
            )));
        }

        if self.entry_value_usd.0 <= Decimal::ZERO {
            return Err(AstError::PersistenceCorruption(format!(
                "position {} has non-positive entry value",
                self.id()
            )));
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn usd(value: i64) -> Usd {
        Usd::new(Decimal::new(value, 0)).expect("valid usd")
    }

    fn sample_position() -> ManagedPosition {
        ManagedPosition::from_order(
            ExecutionOrder::builder()
                .token(Token::new("0xabc", "base", "AST", 18).expect("valid token"))
                .venue(Venue::dex("base", "router").expect("valid venue"))
                .amount_usd(usd(100))
                .build()
                .expect("valid execution order"),
        )
        .expect("position from order")
    }

    #[test]
    fn transitions_to_free_ride_when_take_profit_hits() {
        let mut position = sample_position();
        let action = position
            .evaluate(usd(200), ReaperThresholds::default())
            .expect("evaluate");

        assert_eq!(action, ReaperAction::FreeRide);
        assert_eq!(position.state, PositionState::FreeRide);
    }

    #[test]
    fn rejects_invalid_restore_payloads() {
        let error = ManagedPosition::restore(
            Token::new("0xabc", "base", "AST", 18).expect("valid token"),
            Venue::dex("base", "router").expect("valid venue"),
            PositionState::Open,
            usd(100),
            usd(100),
            usd(120),
            usd(110),
        )
        .expect_err("restore should fail");

        assert!(matches!(error, AstError::PersistenceCorruption(_)));
    }
}
