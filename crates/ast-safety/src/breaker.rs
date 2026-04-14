use std::collections::BTreeSet;

use ast_core::{AstError, ExecutionOrder, Result, Usd, Venue};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuthorizedOrder(pub ExecutionOrder);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CooldownPolicy {
    pub trigger_consecutive_losses: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SafetyConfig {
    pub max_daily_loss_usd: Usd,
    pub disabled_chains: BTreeSet<String>,
    pub max_concurrent_positions: u32,
    pub wallet_balance_floor_usd: Usd,
    pub cooldown: Option<CooldownPolicy>,
}

impl Default for SafetyConfig {
    fn default() -> Self {
        Self {
            max_daily_loss_usd: Usd::new(rust_decimal::Decimal::new(500, 0))
                .expect("default daily loss budget is valid"),
            disabled_chains: BTreeSet::new(),
            max_concurrent_positions: 5,
            wallet_balance_floor_usd: Usd::zero(),
            cooldown: None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SafetyContext {
    pub realized_loss_usd: Usd,
    pub unrealized_loss_usd: Usd,
    pub wallet_balance_usd: Usd,
    pub open_positions: u32,
    pub consecutive_losses: u32,
    pub cooldown_active: bool,
}

impl Default for SafetyContext {
    fn default() -> Self {
        Self {
            realized_loss_usd: Usd::zero(),
            unrealized_loss_usd: Usd::zero(),
            wallet_balance_usd: Usd::zero(),
            open_positions: 0,
            consecutive_losses: 0,
            cooldown_active: false,
        }
    }
}

#[derive(Debug, Clone)]
pub struct SafetyBreaker {
    config: SafetyConfig,
}

impl SafetyBreaker {
    pub fn new(config: SafetyConfig) -> Self {
        Self { config }
    }

    pub fn authorize(
        &self,
        order: ExecutionOrder,
        context: &SafetyContext,
    ) -> Result<AuthorizedOrder> {
        self.check_daily_loss(context)?;
        self.check_chain(order.venue(), context)?;
        self.check_position_limit(context)?;
        self.check_wallet_floor(context)?;
        self.check_cooldown(context)?;

        Ok(AuthorizedOrder(order))
    }

    fn check_daily_loss(&self, context: &SafetyContext) -> Result<()> {
        let total_loss = context.realized_loss_usd.raw() + context.unrealized_loss_usd.raw();
        if total_loss > self.config.max_daily_loss_usd.raw() {
            return Err(AstError::SafetyViolation(format!(
                "daily loss budget exceeded: {} > {}",
                total_loss,
                self.config.max_daily_loss_usd.raw()
            )));
        }

        Ok(())
    }

    fn check_chain(&self, venue: &Venue, _context: &SafetyContext) -> Result<()> {
        if let Venue::Dex { chain, .. } = venue {
            if self.config.disabled_chains.contains(chain.as_str()) {
                return Err(AstError::SafetyViolation(format!(
                    "trading disabled on chain {}",
                    chain.as_str()
                )));
            }
        }

        Ok(())
    }

    fn check_position_limit(&self, context: &SafetyContext) -> Result<()> {
        if context.open_positions >= self.config.max_concurrent_positions {
            return Err(AstError::SafetyViolation(format!(
                "max concurrent positions reached: {} >= {}",
                context.open_positions, self.config.max_concurrent_positions
            )));
        }

        Ok(())
    }

    fn check_wallet_floor(&self, context: &SafetyContext) -> Result<()> {
        if context.wallet_balance_usd.raw() <= self.config.wallet_balance_floor_usd.raw() {
            return Err(AstError::SafetyViolation(format!(
                "wallet balance floor reached: {} <= {}",
                context.wallet_balance_usd.raw(),
                self.config.wallet_balance_floor_usd.raw()
            )));
        }

        Ok(())
    }

    fn check_cooldown(&self, context: &SafetyContext) -> Result<()> {
        if let Some(cooldown) = &self.config.cooldown {
            if context.cooldown_active
                && context.consecutive_losses >= cooldown.trigger_consecutive_losses
            {
                return Err(AstError::SafetyViolation(format!(
                    "cooldown active after {} consecutive losses",
                    context.consecutive_losses
                )));
            }
        }

        Ok(())
    }
}

impl Default for SafetyBreaker {
    fn default() -> Self {
        Self::new(SafetyConfig::default())
    }
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeSet;

    use ast_core::{ExecutionOrder, PositionState, Token, Usd, Venue};
    use rust_decimal::Decimal;

    use super::{CooldownPolicy, SafetyBreaker, SafetyConfig, SafetyContext};

    fn usd(amount: i64) -> Usd {
        Usd::new(Decimal::new(amount, 0)).expect("amount should be valid")
    }

    fn dex_order(chain: &str) -> ExecutionOrder {
        ExecutionOrder::builder()
            .token(Token::new("0xdeadbeef", chain, "AST", 18).expect("valid token"))
            .venue(Venue::dex(chain, "router").expect("valid venue"))
            .amount_usd(usd(100))
            .build()
            .expect("order should be valid")
    }

    #[test]
    fn rejects_when_daily_loss_budget_is_exceeded() {
        let breaker = SafetyBreaker::default();
        let context = SafetyContext {
            realized_loss_usd: usd(400),
            unrealized_loss_usd: usd(200),
            wallet_balance_usd: usd(1_000),
            ..SafetyContext::default()
        };

        assert!(breaker.authorize(dex_order("8453"), &context).is_err());
    }

    #[test]
    fn rejects_when_chain_is_disabled() {
        let mut disabled_chains = BTreeSet::new();
        disabled_chains.insert("8453".into());
        let breaker = SafetyBreaker::new(SafetyConfig {
            disabled_chains,
            ..SafetyConfig::default()
        });
        let context = SafetyContext {
            wallet_balance_usd: usd(1_000),
            ..SafetyContext::default()
        };

        assert!(breaker.authorize(dex_order("8453"), &context).is_err());
    }

    #[test]
    fn rejects_when_position_limit_is_reached() {
        let breaker = SafetyBreaker::new(SafetyConfig {
            max_concurrent_positions: 2,
            ..SafetyConfig::default()
        });
        let context = SafetyContext {
            wallet_balance_usd: usd(1_000),
            open_positions: 2,
            ..SafetyContext::default()
        };

        assert!(breaker.authorize(dex_order("1"), &context).is_err());
    }

    #[test]
    fn rejects_when_wallet_balance_floor_is_reached() {
        let breaker = SafetyBreaker::new(SafetyConfig {
            wallet_balance_floor_usd: usd(250),
            ..SafetyConfig::default()
        });
        let context = SafetyContext {
            wallet_balance_usd: usd(250),
            ..SafetyContext::default()
        };

        assert!(breaker.authorize(dex_order("1"), &context).is_err());
    }

    #[test]
    fn rejects_when_loss_cooldown_is_active() {
        let breaker = SafetyBreaker::new(SafetyConfig {
            cooldown: Some(CooldownPolicy {
                trigger_consecutive_losses: 2,
            }),
            ..SafetyConfig::default()
        });
        let context = SafetyContext {
            wallet_balance_usd: usd(1_000),
            consecutive_losses: 2,
            cooldown_active: true,
            ..SafetyContext::default()
        };

        assert!(breaker.authorize(dex_order("1"), &context).is_err());
    }

    #[test]
    fn authorizes_when_context_is_within_limits() {
        let breaker = SafetyBreaker::default();
        let context = SafetyContext {
            wallet_balance_usd: usd(1_000),
            ..SafetyContext::default()
        };

        assert!(breaker.authorize(dex_order("8453"), &context).is_ok());
    }
}
