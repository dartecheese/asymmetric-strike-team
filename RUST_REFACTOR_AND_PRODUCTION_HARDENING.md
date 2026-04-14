# ASYMMETRIC STRIKE TEAM — Rust Refactor & Production Hardening

**Objective:** Refactor the Asymmetric Strike Team from Python prototype to a production-grade Rust trading system. Rust is the primary language for all latency-sensitive, safety-critical, and execution paths. Python or other languages are acceptable ONLY where Rust provides no meaningful advantage (scripting, data exploration, ML model prototyping, dashboard UI).

**Total:** 30 tasks · 6 phases
**Deployment Gate:** All P0 + P1 + P2 before live capital. P3 before degen tokens. P4+P5 for unattended ops.
**Order of operations:** P0 → P1 → P2 → P3 → P4 → P5. Do not skip phases.

---

## Why Rust

- **Speed:** Nanosecond-precision execution matters for DeFi sniping, MEV protection, and fast exit triggers. Python's GIL and interpreter overhead are unacceptable for live trading.
- **Safety:** Rust's ownership model eliminates entire classes of runtime bugs — no null pointer panics, no data races, no silent type coercion. For code that touches wallets, this is non-negotiable.
- **Concurrency:** Tokio async runtime gives us real concurrent monitoring of multiple positions, chains, and API feeds without Python's threading nightmares.
- **Memory:** No garbage collector pauses during critical execution windows.
- **Ecosystem:** `ethers-rs` / `alloy` for on-chain interaction, `reqwest` for API calls, `serde` for serialization, `sqlx` for persistence — mature, fast, well-maintained crates.

### Language decision matrix

| Component | Language | Rationale |
|---|---|---|
| Core trading engine | **Rust** | Latency, safety, concurrency |
| Execution / TX broadcasting | **Rust** | Speed critical, must not panic |
| Risk engine (Actuary) | **Rust** | Runs in hot path before every trade |
| Position management (Reaper) | **Rust** | State machine correctness, persistence safety |
| Signal discovery (Whisperer) | **Rust** | Async API polling, fast filtering |
| On-chain analysis modules | **Rust** | Direct RPC calls, contract decoding |
| Dashboard / monitoring UI | **React/TypeScript** | Frontend — Rust adds nothing here |
| Strategy backtesting / research | **Python** | Acceptable — not in live path, benefits from pandas/numpy ecosystem |
| One-off data scripts | **Python** | Acceptable — exploratory, not production |
| ML model prototyping | **Python** | Acceptable — if/when ML models are added, inference can be compiled to ONNX and called from Rust |

---

## P0: PROJECT SCAFFOLD & ARCHITECTURE [CRITICAL]

Stand up the Rust project structure. This phase produces no trading logic — just the skeleton everything else builds on.

### P0-1 — Initialize Rust workspace (1 hr)

Create a Cargo workspace with the following crate structure:

```text
asymmetric-strike-team/
├── Cargo.toml (workspace root)
├── crates/
│ ├── ast-core/ (shared types, config, errors)
│ ├── ast-whisperer/ (signal discovery)
│ ├── ast-actuary/ (risk engine)
│ ├── ast-slinger/ (execution routing)
│ ├── ast-reaper/ (position management & exits)
│ ├── ast-safety/ (circuit breakers, kill switches)
│ └── ast-observe/ (logging, metrics, health)
├── src/
│ └── main.rs (single canonical entrypoint)
├── config/
│ └── default.toml (all configuration)
├── scripts/ (Python research/backtest scripts, clearly separated)
└── dashboard/ (React/TS monitoring UI)
```

- **Acceptance:** `cargo build` succeeds. `cargo test` runs (even if 0 tests). Each crate compiles independently. Single `main.rs` entrypoint that imports and orchestrates all crates.

### P0-2 — Define core types and config system (2-3 hrs)

In `ast-core`, define all shared types with strong typing:

- `Token` (address, chain, symbol, decimals)
- `ExecutionOrder` (validated with builder pattern, amount > 0 enforced at compile-level via newtypes)
- `Position` (with explicit state enum: `Pending | Open | StopLossHit | FreeRide | Closing | Closed`)
- `RiskLevel` enum (`Low | Medium | High | Critical | Rejected`)
- `Venue` enum (`Dex { chain, router } | Cex { exchange, pair }`)
- `StrategyProfile` (loaded from TOML config)
- All USD amounts as a `Usd` newtype wrapping `rust_decimal::Decimal` — no floating point anywhere near money.

Config system using `config` crate: load from `config/default.toml`, override with env vars, override with CLI args. Secrets (API keys, private keys) ONLY from env vars, never in config files.

- **Files:** `crates/ast-core/src/types.rs`, `crates/ast-core/src/config.rs`, `crates/ast-core/src/error.rs`
- **Acceptance:** All types compile with serde Serialize/Deserialize. Config loads from TOML. `Usd` type prevents accidental f64 math on money. Position state transitions enforced by methods that return `Result<Position, InvalidTransition>`.

### P0-3 — Async runtime and pipeline skeleton (2-3 hrs)

Wire up Tokio async runtime in `main.rs`. Implement the core trading loop as an async pipeline:

```text
loop {
 signals = whisperer.scan().await
 for signal in signals {
 risk = actuary.assess(&signal).await
 if risk.acceptable() {
 order = slinger.route(&signal, &risk).await
 reaper.track(order).await
 }
 }
 reaper.monitor_positions().await
 sleep(interval).await
}
```

Use `tokio::select!` for concurrent position monitoring alongside signal scanning. Graceful shutdown on SIGINT/SIGTERM.

- **Files:** `src/main.rs`
- **Acceptance:** Binary starts, runs loop, shuts down cleanly on Ctrl+C. All crate boundaries are async trait interfaces.

### P0-4 — Error handling strategy (1-2 hrs)

Define error types using `thiserror` for each crate. Implement a consistent strategy:

- Trading errors (API down, bad response) → log + retry + circuit break. Never panic.
- Execution errors (TX failed, slippage exceeded) → log + alert + position state update. Never panic.
- Configuration errors (missing key, bad value) → panic at startup ONLY. Fail fast, fail loud.
- State corruption (position file invalid) → log + alert + refuse to trade until manual review. Never silently continue.

No `unwrap()` in any code path that touches execution or money. `expect()` allowed ONLY at startup for config loading.

- **Files:** `crates/ast-core/src/error.rs`, all crate error modules
- **Acceptance:** `grep -r "unwrap()" crates/` returns zero hits outside of test modules and startup config.

---

## P1: CODE HEALTH — KILL THE PYTHON GHOSTS [CRITICAL]

Migrate the working Python logic into the Rust skeleton. This is not a rewrite from scratch — port the proven logic, fix the known bugs, drop the dead weight.

### P1-1 — Port and fix Reaper position management (3-4 hrs)

Rewrite `agents/reaper.py` in Rust. Fix the `_restore_positions()` bug (unreachable code after `continue`). Implement:

- Position state machine with enforced transitions (from P0-2 types)
- Atomic persistence: write to temp file → fsync → rename. Use `serde_json` for serialization.
- File integrity check on restore (checksum or magic bytes)
- Stop-loss → free-ride transition logic

- **Files:** `crates/ast-reaper/src/lib.rs`, `crates/ast-reaper/src/persistence.rs`, `crates/ast-reaper/src/state_machine.rs`
- **Acceptance:** Integration test: save 3 positions → kill process → restart → all 3 restored. Corrupted file → detected. Invalid state transition → compile error or explicit Result::Err.

### P1-2 — Port Whisperer signal discovery (2-3 hrs)

Rewrite DexScreener-based discovery in Rust using `reqwest` + `serde`. Port the signal logic: token profiles, boosts, liquidity checks, volume velocity, short-horizon price movement.

- **Files:** `crates/ast-whisperer/src/lib.rs`, `crates/ast-whisperer/src/dexscreener.rs`
- **Acceptance:** Async scan returns typed `Signal` structs. Rate limiting on API calls. Graceful handling of API downtime.

### P1-3 — Port Actuary risk assessment (2-3 hrs)

Rewrite GoPlus-based risk checks in Rust. Port existing logic: honeypot detection, buy/sell tax check, liquidity lock proxy. Keep the good default behavior: unknown/unverified tokens → HIGH risk.

- **Files:** `crates/ast-actuary/src/lib.rs`, `crates/ast-actuary/src/goplus.rs`
- **Acceptance:** Returns typed `RiskAssessment` with per-factor scoring. Unknown tokens default HIGH. All API calls have timeout + retry.

### P1-4 — Consolidate and port UnifiedSlinger execution (3-4 hrs)

Resolve the `agents/unified_slinger.py` vs `execution/unified_slinger.py` duplication. Port the canonical version to Rust. Use `ethers-rs` or `alloy` for on-chain TX construction. Use exchange client crates for CEX.

Remove the hardcoded token→CEX address mapping. Replace with a proper `VenueResolver` trait that can be implemented per-exchange.

- **Files:** `crates/ast-slinger/src/lib.rs`, `crates/ast-slinger/src/venue_resolver.rs`, `crates/ast-slinger/src/dex.rs`, `crates/ast-slinger/src/cex.rs`
- **Acceptance:** Single execution crate. No duplication. Venue routing is trait-based. Invalid pair construction (USDT/USDT) is impossible via type system.

### P1-5 — Archive Python codebase (30 min)

Move entire original Python codebase to `/archive/python-prototype/`. Keep it for reference but make it clear it is NOT the production system.

- **Files:** `/archive/python-prototype/`
- **Acceptance:** Root directory contains only Rust workspace, config, scripts, and dashboard. No Python in the hot path.

---

## P2: EXECUTION SAFETY [HIGH] 🔴 REQUIRED FOR LIVE

The guardrails between your wallet and ruin. No live funds until every P2 task is complete.

### P2-1 — Implement SafetyBreaker circuit breaker system (3-4 hrs)

`ast-safety` crate. Central `SafetyBreaker` struct that wraps all pre-trade checks:

- **Max daily loss:** Configurable (default $500 USD). Tracks realized + unrealized PnL. Breaker trips → all trading halted until manual reset or next UTC day.
- **Per-chain kill switch:** Disable trading on specific chains without stopping the whole system.
- **Max concurrent positions:** Default 5. Configurable per strategy.
- **Wallet balance floor:** Never trade if wallet balance would drop below reserve threshold.
- **Cooldown after loss:** Optional configurable pause after consecutive losing trades.

SafetyBreaker check MUST be called and pass before any `ExecutionOrder` is constructed. This is enforced by the type system: `ExecutionOrder` can only be created via `SafetyBreaker::authorize()` which returns `Result<AuthorizedOrder, SafetyViolation>`.

- **Files:** `crates/ast-safety/src/lib.rs`, `crates/ast-safety/src/breaker.rs`
- **Acceptance:** Each limit tested in isolation. No code path can submit a trade without passing through SafetyBreaker. Type system enforces this — you literally cannot construct an order without authorization.

### P2-2 — Slippage protection (2-3 hrs)

Max slippage configured per strategy profile in basis points. Before TX submission: calculate expected vs worst-case output. If slippage exceeds threshold → reject order, log, alert.

For DEX trades: set `amountOutMinimum` explicitly based on slippage config. Never submit a swap with 100% slippage tolerance.

- **Files:** `crates/ast-slinger/src/slippage.rs`
- **Acceptance:** Config: `max_slippage_bps = 300`. Simulated 5% slippage swap → rejected with clear error.

### P2-3 — TX lifecycle manager (3-4 hrs)

Full transaction lifecycle handling:

- **Nonce tracking:** Per-wallet, per-chain nonce manager. Prevent collisions on rapid-fire trades.
- **Stuck TX detection:** Poll TX status. If pending > configurable timeout → option to speed up (replace-by-fee with higher gas) or drop.
- **Confirmation tracking:** Wait for N confirmations before considering TX final.
- **Gas estimation:** Query current gas prices. Apply configurable multiplier. Cap at max gas price.

- **Files:** `crates/ast-slinger/src/tx_manager.rs`, `crates/ast-slinger/src/gas.rs`
- **Acceptance:** Test: submit TX → simulate stuck → system detects within timeout → handles (speed up or abandon). No nonce collisions under concurrent trade submission.

### P2-4 — API health monitor and circuit breaker (2-3 hrs)

Track health of all external dependencies (DexScreener, GoPlus, RPC endpoints, exchange APIs). If endpoint fails N times in M minutes:

- Pause that dependency
- Log the outage with timestamp
- Attempt periodic health checks
- Resume on successful response
- If critical dependency (RPC) is down → halt all trading on that chain

- **Files:** `crates/ast-safety/src/api_health.rs`
- **Acceptance:** Mock API returning 500s → system pauses after 3 failures in 5 minutes → resumes on recovery. RPC down → chain-specific trading halted.

---

## P3: RISK MODEL UPGRADE [HIGH]

Actuary gets real teeth. Current GoPlus-only checks are minimum viable. These additions are strongly recommended before trading any high-risk DeFi tokens.

### P3-1 — Holder concentration analysis (2-3 hrs)

Before any trade: query on-chain for top token holders. Scoring:

- Top 10 wallets hold >60% supply (excluding known LP/burn/null addresses) → HIGH risk
- Single wallet >20% → CRITICAL
- Deployer still holds >10% → flag
- Use direct RPC calls to token contract `balanceOf` for top holders, not just third-party APIs

- **Files:** `crates/ast-actuary/src/holders.rs`, `crates/ast-core/src/on_chain.rs`
- **Acceptance:** Known rug tokens → correctly flagged. Established tokens (WETH, UNI) → pass. LP/burn addresses excluded from concentration calc.

### P3-2 — Deployer behavior profiling (3-4 hrs)

Check deployer wallet history via block explorer API or direct RPC:

- How many tokens has this deployer launched?
- What happened to previous tokens? (rug pattern: deploy → add LP → remove LP within days)
- Cross-chain deployer correlation (same deployer on multiple chains = higher sophistication, could be legit or serial scammer)
- Build a simple reputation score, persist per-deployer

- **Files:** `crates/ast-actuary/src/deployer.rs`
- **Acceptance:** Known scam deployer → flagged. First-time deployer → neutral (not penalized, not trusted). Serial deployer with rug history → CRITICAL.

### P3-3 — Contract privilege and upgradeability scoring (2-3 hrs)

Go beyond raw GoPlus output. Directly analyze contract bytecode/ABI for:

- Active `mint()` function → risk factor
- `blacklist()` / `whitelist()` functions → risk factor
- `Ownable` with ownership NOT renounced → risk factor
- Proxy/upgradeable pattern (EIP-1967, UUPS) → HIGH risk (owner can change contract logic post-deployment)
- `pause()` function → risk factor

Score each factor independently. Aggregate into contract privilege risk score.

- **Files:** `crates/ast-actuary/src/contract_analysis.rs`
- **Acceptance:** Upgradeable proxy → +HIGH. Mint + owner not renounced → +CRITICAL. Renounced ownership + no mint + no proxy → clean.

### P3-4 — LP lock analysis (1-2 hrs)

Check LP token lock status:

- Is LP locked? (check common lockers: Team.Finance, Unicrypt, PinkSale, etc.)
- Lock duration remaining
- If LP unlocks within 24hrs → flag as imminent risk
- If LP not locked at all on a token < 7 days old → CRITICAL

- **Files:** `crates/ast-actuary/src/lp_lock.rs`
- **Acceptance:** Locked LP (30+ days remaining) → acceptable. Unlocked LP on new token → CRITICAL flag.

### P3-5 — Wash trading detection (3-4 hrs)

Analyze recent trading activity for manipulation signals:

- Circular transfers (A→B→A patterns within short windows)
- Same wallet appearing as both buyer and seller
- Volume/unique-holder ratio anomalies (high volume but very few unique traders)
- Suspiciously regular buy intervals (bot-driven volume)

- **Files:** `crates/ast-actuary/src/wash_detection.rs`
- **Acceptance:** Synthetic volume pattern → detected and flagged. Organic trading activity → passes.

---

## P4: STATE, RECOVERY & SIMULATION [MEDIUM]

Survive crashes. Resume cleanly. Never lose track of money. Never trust fake backtests.

### P4-1 — Wallet reconciliation on startup (2-3 hrs)

On boot: query actual on-chain wallet balances for all chains configured. Compare against persisted position data. Flag discrepancies:

- Position says we hold Token X but on-chain balance is 0 → ALERT, mark position as `Orphaned`
- On-chain balance exists for token with no tracked position → ALERT, log as `Untracked`
- Refuse to start trading if reconciliation finds critical discrepancies (configurable: strict mode vs warn mode)

- **Files:** `crates/ast-reaper/src/reconciliation.rs`, `src/main.rs`
- **Acceptance:** Startup with stale position data → discrepancy detected, logged, and surfaced to operator before any trading begins.

### P4-2 — Replace paper trading random walk (3-4 hrs)

Paper mode currently uses random walk — this gives false confidence and is not a valid simulation. Replace with:

- **Option A (preferred):** Replay historical price data from DexScreener or on-chain DEX events. Simulate realistic fills including slippage model.
- **Option B (acceptable):** Forward-test mode — paper mode tracks real live prices but does not submit TX. Simulated fills at current market price + estimated slippage.

Random walk must be completely removed from any path that produces performance metrics.

- **Files:** `crates/ast-reaper/src/paper_engine.rs`
- **Acceptance:** Paper trades reflect real or realistic price movement. No random number generator in any trading simulation path. Performance metrics carry a clear disclaimer if derived from simulation.

### P4-3 — Database persistence upgrade (2-3 hrs)

Move from JSON file persistence to SQLite via `sqlx` (or `rusqlite` for simpler sync option):

- Positions table with full history
- Trade journal table (every decision with context)
- Deployer reputation cache
- API health history

Atomic transactions. WAL mode for concurrent read/write. Migrations via `sqlx-cli` or embedded.

- **Files:** `crates/ast-core/src/db.rs`, `migrations/`
- **Acceptance:** All persistence flows use DB. `PRAGMA integrity_check` passes. Concurrent read/write works.

---

## P5: OBSERVABILITY [MEDIUM]

If you can't see it, you can't trust it. Required for unattended operation.

### P5-1 — Structured logging with tracing (2-3 hrs)

Use the `tracing` crate (industry standard for Rust async). Structured JSON logs with:

- Span context (which component, which trade, which token)
- Levels: TRACE, DEBUG, INFO, WARN, ERROR
- Fields: timestamp, component, action, token_address, chain, amount_usd, result, duration_ms
- Log rotation via `tracing-appender`
- Optional: `tracing-opentelemetry` export for future Grafana/Datadog integration

Zero `println!()` in codebase.

- **Files:** `crates/ast-observe/src/logging.rs`
- **Acceptance:** `grep -r "println!" crates/ src/` returns zero hits outside test modules. All logs are structured JSON. Log rotation works.

### P5-2 — Trade journal / audit trail (2-3 hrs)

Every trade decision logged to DB with full context:

- Signal source (which Whisperer scan, which token, what triggered it)
- Risk assessment (every factor scored, aggregate decision)
- Execution parameters (venue, amount, slippage config, gas)
- Result (fill price, actual slippage, fees, gas cost, final status)
- Timing (signal detected → risk assessed → order submitted → TX confirmed, each with timestamp)

This is your edge refinement data. Queryable, exportable.

- **Files:** `crates/ast-observe/src/journal.rs`
- **Acceptance:** After 10 paper trades: full decision history retrievable with all context. Exportable to CSV/JSON.

### P5-3 — Health check HTTP endpoint (1-2 hrs)

Lightweight HTTP server (use `axum` — fast, minimal, async-native) exposing:

- `GET /health` → system status, uptime, active positions count, last scan timestamp, error count
- `GET /positions` → current position summary
- `GET /safety` → circuit breaker status, daily PnL, remaining daily loss budget
- `GET /apis` → health status of all external dependencies

For monitoring from OpenClaw dashboard or any external tool.

- **Files:** `crates/ast-observe/src/health.rs`, `src/main.rs`
- **Acceptance:** All endpoints return JSON. Response time < 10ms. Does not block trading loop.

### P5-4 — PnL tracking and reporting (2-3 hrs)

Real-time and historical profit/loss tracking:

- Per-position PnL (entry price, current price, unrealized PnL, realized PnL)
- Per-strategy PnL
- Daily aggregate PnL
- Track ALL costs: gas fees, exchange fees, slippage cost, funding rates
- Net PnL = gross PnL - all costs
- Expose via health endpoint and persist to DB

- **Files:** `crates/ast-observe/src/pnl.rs`
- **Acceptance:** Dashboard shows: daily PnL, total PnL, worst trade, best trade, win rate, avg hold time, total fees paid. All numbers are net, not gross.

---

## Dependency Map

```text
P0 (Scaffold)
 └──→ P1 (Port to Rust)
 └──→ P2 (Execution Safety) ← LIVE FUNDS GATE
 ├──→ P3 (Risk Model) ← DEGEN TOKEN GATE
 └──→ P4 (State/Recovery)
 └──→ P5 (Observability) ← UNATTENDED OPS GATE
```

## Recommended Rust Crate Stack

| Purpose | Crate | Notes |
|---|---|---|
| Async runtime | `tokio` | Full features: rt-multi-thread, macros, time, signal |
| HTTP client | `reqwest` | Async, connection pooling, timeout config |
| On-chain interaction | `alloy` (preferred) or `ethers-rs` | alloy is the newer, maintained successor |
| Serialization | `serde` + `serde_json` | Derive everywhere |
| Config | `config` | TOML + env var layering |
| Decimal math | `rust_decimal` | No floating point near money |
| Error handling | `thiserror` (library) + `anyhow` (application) | Typed errors in crates, flexible in main |
| Logging | `tracing` + `tracing-subscriber` | Structured, async-aware |
| HTTP server | `axum` | For health/monitoring endpoints |
| Database | `sqlx` (async) or `rusqlite` (sync) | SQLite for simplicity, Postgres if scaling |
| CLI | `clap` | Derive-based arg parsing |
| Testing | `tokio::test` + `mockall` | Async test support + trait mocking |

## Non-Rust Components (Acceptable)

| Component | Language | Location | Rationale |
|---|---|---|---|
| Monitoring dashboard | React + TypeScript | `/dashboard/` | Frontend — Rust adds nothing |
| Strategy research notebooks | Python + Jupyter | `/scripts/research/` | pandas/numpy ecosystem, not in live path |
| Backtest data prep | Python | `/scripts/backtest/` | One-off data wrangling |
| ML model prototyping | Python | `/scripts/ml/` | If needed — inference compiled to ONNX, called from Rust |

---

## Final Notes

- **No `unwrap()` in production code.** Enforce via clippy lint.
- **No `f64` for money.** `rust_decimal::Decimal` or custom `Usd` newtype only.
- **No hardcoded secrets.** Environment variables only, loaded at startup.
- **Every external call has a timeout.** No hanging on dead APIs.
- **Every state change is logged.** If it's not in the log, it didn't happen.
- **Paper mode first.** Run at least 48 hrs of paper trading with realistic simulation before any live capital.
