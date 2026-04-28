# Grinding Wheel — Architecture & Origins

## Why This Machine Exists

I drew a circle around the machine humming on my desk and gave it a job.

The job: fetch five-minute whispers from the chain. Not the whole chain — that's impossible for one machine on one desk. Just five-minute slices of what's moving: newly listed tokens on DexScreener, spikes in volume relative to liquidity, narratives being boosted by wallets that might know something.

Let it be slow. Let it be local. Let it grind through the history of Bitcoin, Ethereum, Solana like a stone wheel making flour. If a signal is real, it will survive a five-minute lag between scans. If a position is good, it will survive a two-second window before execution. Speed is not the edge — persistence is.

The machine doesn't get attached. It doesn't get excited about a pump or scared by a dump. It follows four rules:

1. Find signals that look like asymmetric bets — small principal, large upside
2. Check if the signal is a trap (honeypot, high tax, locked liquidity?)
3. If it passes, execute with appropriate aggression for the signal strength
4. Watch the position. Extract principal early. Let the runner run. Cut the loser fast.

That's it. Everything else is implementation.

---

## Core Loop

```
Signal → Assessment → Execution → Monitoring → Signal (loop)
```

Four agents, one loop. Each agent is a Python module in `agents/`. They don't know about each other — data flows through typed objects defined in `core/models.py`.

### 1. Whisperer — Fetch

Reads from DexScreener's public API:
- `/token-profiles/latest` — newly listed tokens with metadata
- `/token-boosts/top` — tokens with paid narrative boosts

Scores each token on:
- **Velocity** — 24h volume relative to liquidity (higher is louder)
- **Momentum** — 1h and 6h price change
- **Freshness** — tokens under an hour old get a bonus (they haven't been picked over yet)

Output: a `TradeSignal` with token address, chain, score, and the reasoning that produced the score.

The Whisperer is the part that reads the news. It doesn't judge — it just brings back what it finds.

### 2. Actuary — Think

Takes each signal and runs it through the GoPlus Security API. Checks:

| Check | What It Finds | Why It Matters |
|-------|---------------|----------------|
| Honeypot | Can you sell after buying? | If not, you're trapped |
| Buy tax | Fee on purchase | Can make entry expensive |
| Sell tax | Fee on sale | Can make exit impossible |
| Liquidity lock | Is liquidity time-locked? | Prevents rug pulls |
| Open source | Is the contract verified? | Transparency signal |

Results are cached for 5 minutes to respect API rate limits. If the API is down, the Actuary defaults to HIGH risk and lets the rest of the pipeline decide — better to miss a trade than to enter a bad one.

Different strategies tolerate different tax levels. Degen mode allows up to 30% tax. Sniper mode rejects anything above 0%.

Output: a `RiskAssessment` with risk level (LOW / MEDIUM / HIGH) and maximum allocation percentage.

### 3. Slinger — Move

Takes an approved signal and builds a transaction.

Works across multiple chains — Ethereum, BSC, Arbitrum, Base — through the same interface. Each strategy defines its own behavior:
- **Slippage tolerance**: 1% for arb hunters, 30% for degenerate entries
- **Gas multiplier**: 1x for cautious strategies, 3x for time-sensitive ones
- **Mempool routing**: Private via Flashbots when available (sniper strategy)

The Slinger captures the real entry price from DexScreener after confirmation — what you wanted to pay and what you actually paid are rarely the same thing.

There are two implementations in `execution/`:
- `unified_slinger.py` — auto-selects paper or real based on `USE_REAL_EXECUTION`
- `real_slinger.py` — pure Web3.py, signs with a local private key, sends through an RPC endpoint

Paper mode simulates execution with realistic assumptions about slippage and fill rates. Real mode spends actual gas.

### 4. Reaper — Tend

Watches every open position. Acts on three triggers:

**Free Ride**: When a position hits +100%, extract the principal. The runner stays. You're playing with house money now.

**Stop Loss**: When a position hits -30%, close it. No averaging down. No "it might come back." The machine doesn't bargain.

**Trailing Stop**: After Free Ride activates, if the position falls 15% from its peak, take the remaining profit. Lock in gains. Move on.

The Reaper polls DexScreener for current prices at sub-100ms intervals. Positions persist to disk through `core/position_store.py` — atomic JSON writes that survive crashes, reboots, and human interruptions.

---

## Strategy Profiles

Each of the eight strategies is a preset — a set of parameters that Whisperer, Actuary, Slinger, and Reaper follow. They don't change the core loop. They change the personality.

**Degen Ape** (high risk)
- Follows momentum without forensic scrutiny
- 30% slippage, 3x gas, +100%/-50% TP/SL
- Good for: when the whole market is moving and hesitation costs more than a bad trade

**Safe Sniper** (low risk)
- Full forensics, private mempool routing, minimal slippage
- 5% slippage, 1.2x gas, +20%/-10% TP/SL
- Good for: when you want proof-of-concept without gambling

**Shadow Clone** (medium risk)
- Tracks a curated set of smart-money wallets, mirrors their trades
- 10% slippage, 2x gas, +50%/-20% TP/SL
- Good for: learning what experienced traders are doing

**Arb Hunter** (low risk)
- Watches for price discrepancies across DEX pairs on the same chain
- 1% slippage, 1x gas, +1%/-1% TP/SL
- Good for: mechanical, high-frequency plays that require precision

**Oracle's Eye** (medium risk)
- Considers macro indicators and whale wallet movements alongside token-level data
- 8% slippage, 1.8x gas, +75%/-15% TP/SL
- Good for: finding the larger trends hiding inside the noise

**Liquidity Sentinel** (medium risk)
- Analyzes market microstructure — order book depth, liquidity concentration, pool composition
- 3% slippage, 1.3x gas, +30%/-8% TP/SL
- Good for: structural plays where liquidity is the alpha

**Yield Alchemist** (low risk)
- Targets DeFi yield positions rather than directional trades
- 2% slippage, 1.1x gas, +15%/-5% TP/SL
- Good for: steady grinding in sideways markets

**Forensic Sniper** (very low risk)
- Maximal due diligence — no assumptions, everything verified
- 2% slippage, 1x gas, +50%/-5% TP/SL
- Good for: the one trade you've been watching for three days

---

## What It's Made Of

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.14 | Readable, inspectable, easy to change |
| Web3 | web3.py | Mature, well-documented, no abstractions |
| Data models | Pydantic v2 | Validation at the boundary, clarity inside |
| Persistence | JSON files | No database, no docker, no state management |
| APIs | DexScreener (free), GoPlus Security (free) | Zero cost to run |
| Testing | 36-test suite | Covers pipeline from signal to position |

The whole thing runs on one machine with one Python venv. No containers. No queues. No microservices. If the machine is on, the wheel turns. If the machine is off, the wheel stops. That's the deal.

---

## Performance (Real Measurements)

| Stage | P50 Latency | Notes |
|-------|-------------|-------|
| Whisperer scan | 2.2s | DexScreener API round-trip |
| Actuary assessment | 500ms (cache) / 2s (API) | 5-min TTL cache |
| Slinger execution | 2.1s | Includes price confirmation |
| Reaper tick | <100ms | Local state, no I/O |
| Full pipeline | 5-10s | One complete turn of the wheel |

Throughput: 6-12 trades per hour in continuous scanning mode. The bottleneck is the DexScreener API, not the local machine.

---

## Known Limitations

- DexScreener rate limits are undocumented but real — bursts above ~30 requests/minute start returning empty responses
- GoPlus API has occasional downtime; the fallback is conservative (reject on uncertainty)
- Single-machine design means no redundancy — if the laptop goes to sleep, the wheel stops
- Real execution requires a private key on disk, which carries its own risks
- The system has never been stress-tested beyond paper mode with historical data

---

## What's Next

This is a working prototype, not a product. It does what it was built to do. If it grows, it should grow at the speed of one human adding one feature at a time.

Potential directions:
- Multi-position support — let the Whisperer stack signals while the Slinger works
- Notification relay — a Telegram message when the Reaper acts
- Backtesting against historical data — so new strategies can be validated before they touch real capital

None of these are planned. They're ideas in a drawer. The machine works now.

---

## License

MIT. `dartecheese/asymmetric-strike-team` on GitHub.

*The flour comes out. The wheel keeps turning. That's enough.*
