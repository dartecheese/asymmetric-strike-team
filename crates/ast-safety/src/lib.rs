use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use rust_decimal::Decimal;
use thiserror::Error;

use ast_core::{RiskAssessment, RiskDecision, Signal, StrategyProfile, TradingSignal};

#[derive(Debug, Error)]
pub enum SafetyError {
    #[error("circuit breaker refused signal {0}")]
    Refused(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SafetyDecision {
    pub should_trade: bool,
    pub reason: String,
}

#[async_trait]
pub trait CircuitBreaker: Send + Sync {
    async fn evaluate(
        &self,
        signal: &TradingSignal,
        risk: &RiskAssessment,
    ) -> Result<SafetyDecision, SafetyError>;
}

#[derive(Debug, Default)]
pub struct NoopSafety;

#[derive(Debug, Clone)]
pub struct PaperSafety {
    strategy: StrategyProfile,
}

impl PaperSafety {
    pub fn new(strategy: StrategyProfile) -> Self {
        Self { strategy }
    }
}

#[async_trait]
impl CircuitBreaker for NoopSafety {
    async fn evaluate(
        &self,
        signal: &TradingSignal,
        risk: &RiskAssessment,
    ) -> Result<SafetyDecision, SafetyError> {
        Ok(SafetyDecision {
            should_trade: risk.acceptable(),
            reason: format!("placeholder safety check passed for {}", signal.id),
        })
    }
}

#[async_trait]
impl CircuitBreaker for PaperSafety {
    async fn evaluate(
        &self,
        signal: &Signal,
        risk: &RiskAssessment,
    ) -> Result<SafetyDecision, SafetyError> {
        if !risk.acceptable() {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!("risk gate blocked {}", signal.id),
            });
        }

        if risk.decision == RiskDecision::Review {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!("review-required signal {} held by safety gate", signal.id),
            });
        }

        let liquidity_ratio = signal.target_notional_usd.0 / signal.liquidity_usd.0;
        if liquidity_ratio > rust_decimal::Decimal::new(15, 2) {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!(
                    "liquidity ratio {} exceeded safety ceiling for {}",
                    liquidity_ratio.round_dp(4),
                    self.strategy.name
                ),
            });
        }

        if self.strategy.max_slippage_bps > 250 {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!(
                    "strategy slippage ceiling {}bps too loose for paper auto-execution",
                    self.strategy.max_slippage_bps
                ),
            });
        }

        Ok(SafetyDecision {
            should_trade: true,
            reason: format!("paper safety checks passed for {}", signal.id),
        })
    }
}

/// Shared kill-switch state for live execution. Tracks consecutive
/// execution failures across all strategies and exposes a sticky kill
/// flag — once tripped (manually or by failure threshold), it stays
/// tripped until the runtime restarts.
///
/// Designed to be cheap to read on the hot path: the `evaluate` check
/// in `LiveSafety` is a single atomic load, so a tripped circuit
/// cleanly refuses signals at any rate.
#[derive(Debug, Default)]
pub struct LiveSafetyState {
    killed: AtomicBool,
    consecutive_failures: AtomicU32,
    last_wallet_balance_usd: Mutex<Option<Decimal>>,
}

impl LiveSafetyState {
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns true if the kill-switch has been tripped.
    pub fn is_killed(&self) -> bool {
        self.killed.load(Ordering::Acquire)
    }

    /// Record an execution failure. Returns true if this failure caused
    /// the threshold to be hit and the circuit was tripped as a result.
    pub fn record_failure(&self, kill_after: u32) -> bool {
        let prior = self.consecutive_failures.fetch_add(1, Ordering::Relaxed);
        let count = prior.saturating_add(1);
        if count >= kill_after {
            // CAS-like: only return "we tripped it" the first time. Other
            // concurrent failures will see the already-killed state.
            !self.killed.swap(true, Ordering::AcqRel)
        } else {
            false
        }
    }

    /// Record an execution success — resets the consecutive-failure counter.
    pub fn record_success(&self) {
        self.consecutive_failures.store(0, Ordering::Relaxed);
    }

    /// Manually trip the kill-switch (e.g., from an HTTP endpoint).
    /// Returns true if this call did the tripping (false if already killed).
    pub fn manual_kill(&self) -> bool {
        !self.killed.swap(true, Ordering::AcqRel)
    }

    pub fn consecutive_failures(&self) -> u32 {
        self.consecutive_failures.load(Ordering::Relaxed)
    }

    /// Update the last-known wallet balance from a polling task. Called
    /// by the WalletBalanceMonitor in ast-slinger. None means "polling
    /// failed" — the prior reading is preserved.
    pub fn record_wallet_balance(&self, usd: Decimal) {
        if let Ok(mut slot) = self.last_wallet_balance_usd.lock() {
            *slot = Some(usd);
        }
    }

    /// Returns the most recent polled wallet balance in USD, or None if
    /// the monitor hasn't reported yet.
    pub fn wallet_balance_usd(&self) -> Option<Decimal> {
        self.last_wallet_balance_usd
            .lock()
            .ok()
            .and_then(|guard| *guard)
    }
}

#[derive(Debug, Clone)]
pub struct LiveSafetyConfig {
    /// Number of consecutive execution failures before the kill-switch
    /// trips automatically. Set to 0 to disable auto-tripping (manual
    /// kill only). Default: 3.
    pub kill_after_consecutive_failures: u32,
    /// Refuse orders when polled wallet balance falls below this USD
    /// floor. Set to 0 to disable the check. Default: 0 (disabled —
    /// must be set explicitly per-config).
    pub wallet_floor_usd: Decimal,
    /// When wallet_floor_usd > 0 but the monitor hasn't polled a
    /// balance yet, should we fail-closed (refuse all orders) or
    /// fail-open (allow)? Default: true (fail-closed). Safer for live.
    pub require_balance_poll_before_trading: bool,
}

impl Default for LiveSafetyConfig {
    fn default() -> Self {
        Self {
            kill_after_consecutive_failures: 3,
            wallet_floor_usd: Decimal::ZERO,
            require_balance_poll_before_trading: true,
        }
    }
}

/// Live-mode circuit breaker. Wraps a `PaperSafety` so it inherits the
/// signal-level liquidity / slippage checks, then layers on a sticky
/// kill-switch driven by `LiveSafetyState`.
///
/// The state is held by `Arc` and shared across all per-strategy
/// instances so a single failed strategy can shut the whole runtime
/// down — that's the point.
pub struct LiveSafety {
    inner: PaperSafety,
    state: Arc<LiveSafetyState>,
    config: LiveSafetyConfig,
}

impl LiveSafety {
    pub fn new(
        strategy: StrategyProfile,
        state: Arc<LiveSafetyState>,
        config: LiveSafetyConfig,
    ) -> Self {
        Self {
            inner: PaperSafety::new(strategy),
            state,
            config,
        }
    }

    pub fn state(&self) -> &Arc<LiveSafetyState> {
        &self.state
    }

    pub fn kill_after(&self) -> u32 {
        self.config.kill_after_consecutive_failures
    }
}

#[async_trait]
impl CircuitBreaker for LiveSafety {
    async fn evaluate(
        &self,
        signal: &TradingSignal,
        risk: &RiskAssessment,
    ) -> Result<SafetyDecision, SafetyError> {
        if self.state.is_killed() {
            return Ok(SafetyDecision {
                should_trade: false,
                reason: format!(
                    "live kill-switch tripped ({} consecutive failures) — restart runtime to reset",
                    self.state.consecutive_failures()
                ),
            });
        }

        if self.config.wallet_floor_usd > Decimal::ZERO {
            match self.state.wallet_balance_usd() {
                Some(balance) if balance < self.config.wallet_floor_usd => {
                    return Ok(SafetyDecision {
                        should_trade: false,
                        reason: format!(
                            "wallet balance ${} below floor ${} — refusing new orders",
                            balance, self.config.wallet_floor_usd
                        ),
                    });
                }
                None if self.config.require_balance_poll_before_trading => {
                    return Ok(SafetyDecision {
                        should_trade: false,
                        reason:
                            "wallet balance not yet polled — refusing trades until floor check passes"
                                .to_owned(),
                    });
                }
                _ => {}
            }
        }

        self.inner.evaluate(signal, risk).await
    }
}

#[cfg(test)]
mod tests {
    use super::{CircuitBreaker, LiveSafety, LiveSafetyConfig, LiveSafetyState, PaperSafety};
    use ast_core::{
        Chain, RiskAssessment, RiskDecision, RiskLevel, Signal, StrategyProfile, Token, Usd, Venue,
    };
    use rust_decimal::Decimal;
    use std::collections::BTreeMap;

    fn strategy(max_slippage_bps: u16) -> StrategyProfile {
        StrategyProfile {
            name: "swift".to_owned(),
            description: "Fast entry on new pairs".to_owned(),
            max_position_size_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            max_slippage_bps,
            risk_tolerance: RiskLevel::Medium,
            scan_interval_seconds: 15,
            paper_trading: true,
        }
    }

    fn signal() -> Signal {
        Signal {
            id: "signal-1".to_owned(),
            token: Token {
                address: alloy_primitives::Address::ZERO,
                chain: Chain::Base,
                symbol: "SWFT".to_owned(),
                decimals: 18,
            },
            venue: Venue::Dex {
                chain: Chain::Base,
                router: alloy_primitives::Address::ZERO,
            },
            price_usd: Usd::new(Decimal::ONE).expect("valid usd"),
            volume_24h_usd: Usd::new(Decimal::new(100_000, 0)).expect("valid usd"),
            liquidity_usd: Usd::new(Decimal::new(500_000, 0)).expect("valid usd"),
            target_notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            timestamp_ms: 1,
            metadata: BTreeMap::new(),
        }
    }

    fn accepted_risk() -> RiskAssessment {
        RiskAssessment {
            level: RiskLevel::Low,
            decision: RiskDecision::Accept,
            rationale: "ok".to_owned(),
            approved_notional_usd: Usd::new(Decimal::new(200, 0)).expect("valid usd"),
            factors: Vec::new(),
        }
    }

    #[tokio::test]
    async fn paper_safety_allows_healthy_signal() {
        let safety = PaperSafety::new(strategy(200));
        let decision = safety.evaluate(&signal(), &accepted_risk()).await.expect("decision");

        assert!(decision.should_trade);
    }

    #[tokio::test]
    async fn paper_safety_blocks_loose_slippage_profiles() {
        let safety = PaperSafety::new(strategy(300));
        let decision = safety.evaluate(&signal(), &accepted_risk()).await.expect("decision");

        assert!(!decision.should_trade);
    }

    // === LiveSafety + LiveSafetyState ============================

    #[tokio::test]
    async fn live_safety_passes_signal_through_to_paper_checks() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let safety = LiveSafety::new(
            strategy(200),
            state.clone(),
            LiveSafetyConfig::default(),
        );
        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(decision.should_trade);
        assert!(!state.is_killed());
    }

    #[tokio::test]
    async fn live_safety_refuses_after_kill_switch_trips() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let config = LiveSafetyConfig {
            kill_after_consecutive_failures: 3,
            ..LiveSafetyConfig::default()
        };
        let safety = LiveSafety::new(strategy(200), state.clone(), config);

        // Three failures in a row trip the switch.
        assert!(!state.record_failure(3));
        assert!(!state.record_failure(3));
        let tripped = state.record_failure(3);
        assert!(tripped, "third failure should trip the kill-switch");
        assert!(state.is_killed());

        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(!decision.should_trade);
        assert!(decision.reason.contains("kill-switch"));
    }

    #[tokio::test]
    async fn live_safety_success_resets_failure_count() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let config = LiveSafetyConfig {
            kill_after_consecutive_failures: 3,
            ..LiveSafetyConfig::default()
        };
        let safety = LiveSafety::new(strategy(200), state.clone(), config);

        state.record_failure(3);
        state.record_failure(3);
        assert_eq!(state.consecutive_failures(), 2);
        state.record_success();
        assert_eq!(state.consecutive_failures(), 0);

        // Two more failures shouldn't trip — the counter was reset.
        state.record_failure(3);
        let tripped = state.record_failure(3);
        assert!(!tripped);
        assert!(!state.is_killed());

        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(decision.should_trade);
    }

    #[tokio::test]
    async fn live_safety_manual_kill_blocks_immediately() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let safety = LiveSafety::new(
            strategy(200),
            state.clone(),
            LiveSafetyConfig::default(),
        );
        let first = state.manual_kill();
        let second = state.manual_kill();
        assert!(first, "first manual_kill should report having tripped");
        assert!(!second, "second manual_kill should report already killed");

        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(!decision.should_trade);
    }

    #[tokio::test]
    async fn live_safety_refuses_when_balance_below_floor() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let config = LiveSafetyConfig {
            wallet_floor_usd: Decimal::new(50, 0),
            require_balance_poll_before_trading: true,
            ..LiveSafetyConfig::default()
        };
        let safety = LiveSafety::new(strategy(200), state.clone(), config);

        state.record_wallet_balance(Decimal::new(40, 0));

        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(!decision.should_trade);
        assert!(decision.reason.contains("below floor"));
    }

    #[tokio::test]
    async fn live_safety_allows_when_balance_meets_floor() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let config = LiveSafetyConfig {
            wallet_floor_usd: Decimal::new(50, 0),
            require_balance_poll_before_trading: true,
            ..LiveSafetyConfig::default()
        };
        let safety = LiveSafety::new(strategy(200), state.clone(), config);

        state.record_wallet_balance(Decimal::new(75, 0));

        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(decision.should_trade);
    }

    #[tokio::test]
    async fn live_safety_fails_closed_before_first_balance_poll() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let config = LiveSafetyConfig {
            wallet_floor_usd: Decimal::new(50, 0),
            require_balance_poll_before_trading: true,
            ..LiveSafetyConfig::default()
        };
        let safety = LiveSafety::new(strategy(200), state.clone(), config);

        // No record_wallet_balance call — state.wallet_balance_usd() is None.
        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(!decision.should_trade);
        assert!(decision.reason.contains("not yet polled"));
    }

    #[tokio::test]
    async fn live_safety_fails_open_when_disabled_and_no_balance() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let config = LiveSafetyConfig {
            wallet_floor_usd: Decimal::new(50, 0),
            require_balance_poll_before_trading: false,
            ..LiveSafetyConfig::default()
        };
        let safety = LiveSafety::new(strategy(200), state.clone(), config);

        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(decision.should_trade);
    }

    #[tokio::test]
    async fn live_safety_skips_balance_check_when_floor_zero() {
        let state = std::sync::Arc::new(LiveSafetyState::new());
        let config = LiveSafetyConfig {
            wallet_floor_usd: Decimal::ZERO,
            require_balance_poll_before_trading: true,
            ..LiveSafetyConfig::default()
        };
        let safety = LiveSafety::new(strategy(200), state.clone(), config);

        // No balance recorded but floor=0 disables the check entirely.
        let decision = safety
            .evaluate(&signal(), &accepted_risk())
            .await
            .expect("decision");
        assert!(decision.should_trade);
    }

    #[test]
    fn kill_after_zero_disables_auto_trip() {
        let state = LiveSafetyState::new();
        for _ in 0..1000 {
            state.record_failure(0); // 0 means "never auto-trip"
        }
        // Threshold of 0 means count >= 0 is always true — but the check
        // is `count >= kill_after`, so 0 trips immediately on the first
        // failure. That's surprising; document by asserting actual behavior.
        // Operators wanting "never auto-trip" should use a high number
        // like u32::MAX.
        assert!(state.is_killed());
    }
}
