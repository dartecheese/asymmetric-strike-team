# Asymmetric Strike Team

Asymmetric Strike Team (AST) is a local-first crypto trading lab built for **paper trading now** and structured so real execution can be added later without pretending it already exists.

Today, AST is honest about what it is:
- **live market/risk discovery** where possible
- **paper-only execution**
- **file-backed portfolio, ledger, and learning logs**
- **operator dashboard** for team control, portfolio state, logs, and troubleshooting

## Current runtime

AST currently runs locally:
- **backend / API:** `http://127.0.0.1:8989`
- **dashboard:** `http://127.0.0.1:5173`

## What it does

AST runs 8 strategy teams:
- `thrive`
- `swift`
- `echo`
- `bridge`
- `flow`
- `clarity`
- `nurture`
- `insight`

Each strategy is composed of role agents:
- **Whisperer** — finds candidate trades from market data
- **Actuary** — scores trade risk
- **Safety** — applies hard guards before execution
- **Slinger** — simulates order execution in paper mode
- **Reaper** — tracks positions and marks portfolio state
- **Critic** — records after-action reflection and learning output

## Paper mode only

AST is currently **paper-trading only** for execution.

That means:
- no wallet signing
- no real swap submission
- no live capital movement
- `--mode live` remains guarded until real execution infrastructure exists

## Live data and risk pipeline

### Market data discovery

AST uses a layered feed pipeline:
1. **DexScreener** primary discovery
2. **GeckoTerminal** secondary discovery
3. **cached live signals** if providers are temporarily failing
4. **paper mock fallback** when running paper mode and live discovery is exhausted

### Risk checks

AST uses:
1. **GoPlus** primary risk checks
2. **Honeypot.is** secondary checks
3. **heuristic fallback** in paper mode when live checks fail

## Newly wired notable DEX coverage

AST now explicitly filters and ranks discovery around 5 notable DEX venues:
- **Uniswap**
- **Aerodrome**
- **PancakeSwap**
- **SushiSwap**
- **Camelot**

### What “wired up” means here

For live pair discovery, AST now:
- recognizes these DEX IDs from provider responses
- filters out non-target venues from the discovery/ranking pass
- boosts eligible pairs from these venues in scoring
- attaches `dex_id` and `dex_label` metadata to emitted signals

This keeps the framework focused on recognizable, liquid venues instead of treating every discovered pair as equal.

## Dashboard capabilities

The dashboard includes:
- per-team **Start / Pause / Stop** controls
- multi-select strategy viewing
- operator mode/readiness summary
- holdings and portfolio visibility
- raw event logs
- troubleshooting page with:
  - websocket diagnostics
  - API endpoint health
  - recent backend/runtime errors
  - paused/stopped team warnings
  - one-click troubleshooting log copy

## State, ledgers, and learning logs

AST writes local state under `data/`, including:
- position state
- portfolio state
- per-strategy ledger JSONL
- learning/event corpora for later tuning and replay

Paper resets can be done safely with archived prior state instead of destructive deletion.

## Running locally

### Backend

```bash
cargo run -- --mode paper --fresh-paper
```

### Dashboard

```bash
cd dashboard
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## Development checks

### Rust

```bash
cargo test --workspace
```

### Dashboard

```bash
cd dashboard
npm run build
```

## Project posture

AST is built for:
- realistic paper-trading iteration
- visible operator UX
- inspectable logs and learning traces
- conservative safety around anything that looks like live trading

It is **not** yet a live trading bot, and the README is intentionally direct about that.
