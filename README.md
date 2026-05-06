# Asymmetric Strike Team

Asymmetric Strike Team (AST) is a **local-first crypto trading lab** designed for **paper trading now** with enough structure, observability, and operator tooling to become a real execution system later.

It is intentionally honest about its current posture:
- **live market discovery** when providers are healthy
- **paper-only execution**
- **file-backed state, ledger, and learning logs**
- **operator dashboard** for control, portfolio inspection, troubleshooting, and onboarding

---

## Current runtime

AST runs locally on this machine by default:
- **backend / API:** `http://127.0.0.1:8989`
- **dashboard:** `http://127.0.0.1:5173`

This is not a public hosted product yet.

---

## What AST is for

AST is built to help you:
- test multiple crypto strategy styles in parallel
- inspect why a trade was accepted, rejected, or marked poorly
- collect better paper-trading logs for later tuning
- understand whether system activity is translating into actual portfolio quality

The goal is not fake “AI trader” vibes. The goal is an inspectable trading lab with honest operator UX.

---

## Strategy teams

AST currently runs 8 strategy teams:
- `thrive` — aggressive high-growth entries
- `swift` — fast response to new opportunities
- `echo` — smart-money style mirroring
- `bridge` — cross-venue arbitrage focus
- `flow` — liquidity and movement-based plays
- `clarity` — cleaner, more defensive setups
- `nurture` — slower, steadier yield-oriented setups
- `insight` — research-heavy, contract-analysis-driven opportunities

Each strategy can be started, paused, or stopped independently from the dashboard.

---

## Agent roles

Each strategy is composed of role agents:
- **Whisperer** — discovers candidate trades from market data
- **Actuary** — scores risk and screens contracts/taxes/liquidity
- **Safety** — applies hard safety gates
- **Slinger** — builds paper orders and simulates execution
- **Reaper** — tracks positions, marks market value, and updates P&L
- **Critic** — records after-action reflection and learning traces

The dashboard includes hover help for these roles so a new operator can learn the system in place.

---

## Pipeline gates

Between Safety approval and Slinger routing, every signal passes through two universal gates that apply to both paper and live mode. They prevent the failure mode where the simulator opens the same trade thousands of times because the underlying signal keeps re-firing.

**1. Per-strategy capacity gate**

Each strategy gets a budget of `paper_trading.initial_balance_usd / num_strategies`. With the default $10,000 initial balance and 8 configured strategies, each strategy can hold up to `$1,250 × 0.95 = $1,187.50` in open notional at once (5% reserve preserved). New entries that would exceed this are skipped and an event is emitted to the bus tagged `signal_skipped` with `reason = strategy_budget_exhausted`.

This is the paper-mode equivalent of the live `wallet_floor_usd` check. It runs in addition to the live wallet check when in `--mode live`, so over-leverage is gated even if both checks are active.

**2. Per-strategy duplicate-position gate**

If a strategy already has an active position (`Open`, `FreeRide`, `Closing`, or `Pending`) for the same `(symbol, chain)` tuple, the new signal is skipped with `reason = duplicate_open_position`. Different strategies can hold the same token (they have different sizing, exit rules, and risk tolerance), but a single strategy can't double up on the same trade.

Both gates emit `signal_skipped` events visible in the dashboard event feed and the per-strategy ledger, so it's easy to see why a signal didn't route.

---

## Paper mode only

AST is currently **paper-trading only** for execution.

That means:
- no wallet signing
- no real swap submission
- no live capital movement
- `--mode live` remains guarded until real execution infrastructure exists

Live discovery and live risk checks may still be used in paper mode when available.

---

## Market data and risk pipeline

### Market data

AST currently uses a layered market data stack:
1. **DexScreener** primary discovery
2. **GeckoTerminal** secondary discovery
3. **shared provider cache/cooldown layer** to reduce duplicate requests and survive temporary rate limits
4. **cached live fallback** when a provider is cooling down or failing
5. **paper mock fallback** when live discovery is exhausted in paper mode

### Risk checks

AST currently uses:
1. **GoPlus** primary risk checks
2. **Honeypot.is** secondary checks
3. **heuristic fallback** in paper mode when external checks fail

---

## Notable DEX coverage

AST now explicitly recognizes and prioritizes 5 notable DEX venues in live discovery:
- **Uniswap**
- **Aerodrome**
- **PancakeSwap**
- **SushiSwap**
- **Camelot**

Signals now carry venue metadata such as:
- `dex_id`
- `dex_label`
- `strategy_dex_fit`

That lets AST rank venues differently depending on strategy instead of treating every discovered pool as equally useful.

---

## Dashboard pages

AST’s dashboard is meant to be usable by someone who did not build the system.

### 1. Dashboard
Use this page to:
- view active team panels
- start / pause / stop each strategy
- filter which teams are visible
- inspect live logs and explanations
- see quick-start/runtime guidance

### 2. Portfolio
Use this page to:
- inspect total cash, equity, invested capital, and P&L
- review holdings across all strategies in one place
- compare strategy-level portfolio contribution
- tell whether system activity is improving the portfolio or just generating noise

### 3. Tutorial
Use this page to:
- onboard new operators quickly
- understand what the main pages are for
- learn how to interpret common rejection/error patterns
- avoid confusing paper-execution rejections with infrastructure problems

### 4. Troubleshooting
Use this page to:
- inspect websocket health
- inspect API endpoint health
- review recent backend/runtime errors
- detect paused/stopped teams
- copy a structured troubleshooting report with one click

---

## Understanding common failures

Not every error means the system is broken.

### Trade rejection errors
Examples:
- `simulated slippage ... exceeds configured max`
- `simulated fill ratio ... too low for execution`

These usually mean:
- poor liquidity
- overly large position sizing for the venue
- weak discovery quality
- a strategy that needs tighter pre-trade filters

These are usually **trade quality problems**, not connectivity problems.

### Provider/rate-limit issues
Examples:
- `429 Too Many Requests`
- provider fetch failures or cooldowns

These usually mean:
- the system is leaning too hard on a source
- provider orchestration needs improvement
- cached/stale fallback is doing recovery work in the background

These are usually **market data infrastructure problems**, not strategy logic problems.

---

## State, ledgers, and learning logs

AST writes local state under `data/`, including:
- position state
- portfolio state
- per-strategy ledger JSONL
- learning/event corpora for later replay and tuning
- archived paper sessions when `--fresh-paper` is used

This is meant to make paper trading inspectable and training-friendly.

---

## Running locally

### Backend

```bash
cargo run -- --mode paper
```

Fresh paper session with archival of prior state:

```bash
cargo run -- --mode paper --fresh-paper
```

### Dashboard

```bash
cd dashboard
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

---

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

---

## Current limitations

AST is not yet a live trading bot.

Missing pieces for real execution still include things like:
- wallet signing flow
- RPC execution path
- swap routing/execution adapters
- live kill-switch handling
- real-money operational safety envelope

Until those exist, AST should be treated as a high-observability paper-trading lab.

---

## Project posture

AST is built for:
- realistic paper-trading iteration
- visible operator UX
- inspectable logs and learning traces
- safe local experimentation
- blunt honesty about what is and is not live-ready

That directness is intentional.