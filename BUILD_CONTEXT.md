# Build Context for P0 — Scaffold & Architecture

## Goal

Build all of Phase 0 from the AST_Rust_Refactor_Taskboard.md. This is the Rust skeleton — no trading logic yet, just the workspace, types, config, pipeline, and error handling.

## Tasks

### P0-1: Initialize Rust workspace

Create Cargo workspace at project root:

```
Cargo.toml              (workspace root)
crates/
  ast-core/             (shared types, config, errors)
  ast-whisperer/        (signal discovery — shell crate for now)
  ast-actuary/          (risk engine — shell crate for now)
  ast-slinger/          (execution routing — shell crate for now)
  ast-reaper/           (position management — shell crate for now)
  ast-safety/           (circuit breakers — shell crate for now)
  ast-observe/          (logging, metrics — shell crate for now)
src/
  main.rs               (single canonical entrypoint)
config/
  default.toml          (all configuration)
scripts/                (Python research scripts, clearly separated)
```

- `cargo build` succeeds
- `cargo test` runs (even if 0 tests)
- Each crate compiles independently
- Single `main.rs` entrypoint that imports and orchestrates all crates
- `Cargo.toml` workspace members = all 7 crates

### P0-2: Define core types and config system (in ast-core)

Define all shared types with strong typing:

- `Token` (address, chain, symbol, decimals)
- `ExecutionOrder` (validated with builder pattern, amount > 0 enforced at compile-level via newtypes)
- `Position` (with explicit state enum: `Pending | Open | StopLossHit | FreeRide | Closing | Closed`)
- `RiskLevel` enum (`Low | Medium | High | Critical | Rejected`)
- `Venue` enum (`Dex { chain, router } | Cex { exchange, pair }`)
- `StrategyProfile` (loaded from TOML config)
- All USD amounts as a `Usd` newtype wrapping `rust_decimal::Decimal` — no floating point anywhere near money.

Config system using `config` crate: load from `config/default.toml`, override with env vars, override with CLI args. Secrets (API keys) ONLY from env vars.

Key crates: `serde`, `serde_json`, `config`, `rust_decimal`, `thiserror`, `anyhow`

### P0-3: Async runtime and pipeline skeleton (in src/main.rs)

Wire up Tokio async runtime. Implement the core trading loop as an async pipeline:

```
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

### P0-4: Error handling strategy

Use `thiserror` for each crate. Consistent approach:
- Trading errors (API down, bad response) → log + retry. Never panic.
- Execution errors (TX failed, slippage exceeded) → log + alert + state update. Never panic.
- Configuration errors (missing key, bad value) → panic at startup ONLY.
- State corruption (position file invalid) → log + alert + refuse to trade.

No `unwrap()` in any production code path. `expect()` allowed ONLY for startup config loading.

## DeepSeek API Key

The key is: sk-97290665d586498e9b4d0b3fd33f2468
This is stored in `.env` and should be loaded from `DEEPSEEK_API_KEY` env var at runtime.
DO NOT hardcode this key in any source file. Use `std::env::var("DEEPSEEK_API_KEY")`.

## Recommended Crate Stack

| Purpose | Crate |
|---|---|
| Async runtime | `tokio` (full features) |
| HTTP client | `reqwest` |
| On-chain | `alloy` (preferred) |
| Serialization | `serde` + `serde_json` |
| Config | `config` |
| Decimal math | `rust_decimal` |
| Error handling | `thiserror` + `anyhow` |
| Logging | `tracing` + `tracing-subscriber` |
| HTTP server | `axum` |
| CLI | `clap` |

## Acceptance Criteria

1. `cargo build` succeeds with no warnings
2. `cargo test` passes
3. `cargo clippy` passes with no warnings (except deliberate `#[allow(...)]`)
4. `cargo doc --no-deps` builds documentation
5. Running `./target/debug/asymmetric-strike-team` starts, runs the pipeline loop once, and shuts down gracefully on Ctrl+C
6. No `unwrap()` in production code (check with `grep -r "unwrap()" crates/ | grep -v "#\[cfg(test)\]"`)
7. All types defined in P0-2 compile with Serialize/Deserialize
8. Config loads from `config/default.toml` with env var overrides
