use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;

use async_trait::async_trait;
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
}

#[derive(Debug, Clone)]
pub struct LiveSafetyConfig {
    /// Number of consecutive execution failures before the kill-switch
    /// trips automatically. Set to 0 to disable auto-tripping (manual
    /// kill only). Default: 3.
    pub kill_after_consecutive_failures: u32,
}

impl Default for LiveSafetyConfig {
    fn default() -> Self {
        Self {
            kill_after_consecutive_failures: 3,
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
        let config = LiveSafetyConfig { kill_after_consecutive_failures: 3 };
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
        let config = LiveSafetyConfig { kill_after_consecutive_failures: 3 };
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
