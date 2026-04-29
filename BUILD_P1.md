# Build P1: Agent Logic + Event Bus + WebSocket + Paper Trading

## Prerequisites

P0 is complete in this workspace. All 7 crates compile. Use the existing types in `ast-core` (Token, ExecutionOrder, Position, RiskLevel, Venue, StrategyProfile, Usd).

## Task A: Strategy Profiles (config)

In `config/default.toml`, define 8 strategy profiles with the new names:

```toml
[strategies.thrive]
description = "Aggressive high-growth entries"
max_position_size_usd = 500
max_slippage_bps = 300
risk_tolerance = "high"
scan_interval_seconds = 30

[strategies.swift]
description = "Fast entry on new pairs"
max_position_size_usd = 200
max_slippage_bps = 200
risk_tolerance = "medium"
scan_interval_seconds = 15

[strategies.echo]
description = "Mirrors smart wallet moves"
max_position_size_usd = 300
max_slippage_bps = 150
risk_tolerance = "medium"
scan_interval_seconds = 60

[strategies.bridge]
description = "Cross-venue arbitrage"
max_position_size_usd = 400
max_slippage_bps = 50
risk_tolerance = "low"
scan_interval_seconds = 10

[strategies.flow]
description = "Liquidity event plays"
max_position_size_usd = 250
max_slippage_bps = 200
risk_tolerance = "medium"
scan_interval_seconds = 30

[strategies.clarity]
description = "Oracle manipulation detection"
max_position_size_usd = 350
max_slippage_bps = 100
risk_tolerance = "low"
scan_interval_seconds = 60

[strategies.nurture]
description = "Yield cultivation"
max_position_size_usd = 150
max_slippage_bps = 100
risk_tolerance = "low"
scan_interval_seconds = 120

[strategies.insight]
description = "Contract-analysis-based opportunities"
max_position_size_usd = 200
max_slippage_bps = 250
risk_tolerance = "high"
scan_interval_seconds = 45

[paper_trading]
enabled = true
initial_balance_usd = 10000
default_slippage_model = "simulated"
```

## Task B: Agent Logic (P1 from taskboard)

### ast-whisperer (Signal Discovery)
- Read-only DexScreener API polling via reqwest
- Rate-limited async scanning  
- Returns typed `Signal` structs (token, chain, price, volume, liquidity, timestamp)
- Mock data for paper mode when APIs unavailable

### ast-actuary (Risk Engine)
- GoPlus API for honeypot/tax checks (or mock in paper mode)
- Per-factor risk scoring
- Returns `RiskAssessment` with aggregate decision (Accept/Reject/Review)
- Unknown/unverified tokens → HIGH risk default

### ast-slinger (Execution Router)
- Paper mode: simulate fills with configurable slippage model
- Trait-based `VenueResolver` for routing
- ExecutionOrder construction with validation
- Returns `ExecutionResult` with fill price, slippage, status

### ast-reaper (Position Manager)
- Position state machine from P0 types
- File-based persistence (temp file → fsync → rename)
- Stop-loss / take-profit logic for paper mode
- Periodic position monitoring

## Task C: Event Bus for Agent Conversations

Each agent decision must emit a structured JSON event. These events stream to the dashboard:

```rust
pub enum AgentEvent {
    SignalDiscovered {
        strategy: String,
        signal: Signal,
        timestamp: Instant,
    },
    RiskAssessed {
        strategy: String,
        signal_id: String,
        assessment: RiskAssessment,
        timestamp: Instant,
    },
    OrderConstructed {
        strategy: String,
        order: ExecutionOrder,
        timestamp: Instant,
    },
    OrderFilled {
        strategy: String,
        order_id: String,
        result: ExecutionResult,
        timestamp: Instant,
    },
    PositionUpdated {
        strategy: String,
        position: Position,
        timestamp: Instant,
    },
    Error {
        strategy: String,
        agent: String, // "whisperer" | "actuary" | "slinger" | "reaper"
        message: String,
        timestamp: Instant,
    },
}
```

Use `tokio::sync::broadcast` channel as the event bus. Each pipeline broadcasts events. The WebSocket handler subscribes to the broadcast and forwards to connected dashboard clients.

## Task D: WebSocket + HTTP Endpoint (in ast-observe or added to main)

Add to `src/main.rs`:

1. **axum HTTP server** on port 8989 (non-conflicting with OpenClaw's 18788)
2. **WebSocket endpoint** at `/ws` that streams AgentEvent JSON to connected clients
3. **REST endpoints:**
   - `GET /health` — system status, active strategies, uptime
   - `GET /strategies` — list all 8 strategies with their config and current status
   - `GET /events` — recent events (last 100, as SSE or JSON array)
4. Spawn the HTTP server alongside the trading pipelines using `tokio::select!`

## Task E: Pipeline Orchestration (main.rs redesign)

Instead of a single pipeline loop, spawn 8 parallel pipelines, one per strategy:

```rust
// For each strategy in config:
let event_tx = broadcast::Sender::clone(&global_event_tx);
tokio::spawn(async move {
    let whisperer = Whisperer::new(strategy.clone(), event_tx.clone());
    let actuary = Actuary::new(strategy.clone(), event_tx.clone());
    let slinger = Slinger::new(strategy.clone(), event_tx.clone());
    let reaper = Reaper::new(strategy.clone(), event_tx.clone());
    
    loop {
        let signals = whisperer.scan().await;
        for signal in signals {
            let risk = actuary.assess(&signal).await;
            event_tx.send(AgentEvent::RiskAssessed { ... });
            if risk.acceptable() {
                let order = slinger.route(&signal, &risk).await;
                let result = slinger.execute(order).await;
                reaper.track(result).await;
            }
        }
        reaper.monitor().await;
        tokio::time::sleep(strategy.scan_interval).await;
    }
});
```

## Task F: Acceptance Criteria

1. `cargo build` succeeds
2. `cargo test` passes (add at least basic unit tests)
3. `cargo clippy` passes
4. Binary starts, prints startup banner with all 8 strategy profiles
5. WebSocket at `ws://localhost:8989/ws` streams agent events
6. REST health endpoint returns JSON at `http://localhost:8989/health`
7. Paper trading mode: simulated fills, no real chain calls
8. Each strategy runs independently with its own scan interval
9. Graceful shutdown on Ctrl+C (cleanup all 8 pipelines + HTTP server)
10. No hardcoded secrets — DEEPSEEK_API_KEY from env or .env
