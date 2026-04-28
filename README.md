# Asymmetric Strike Team

_Fetch five-minute whispers from the chain. Let it be slow. Let it be local. Let it grind through the history of Bitcoin, Ethereum, Solana like a stone wheel making flour._

**GitHub:** `dartecheese/asymmetric-strike-team` **| License:** MIT

This is a machine for extracting signals from DeFi markets — local, persistent, runs forever unless you stop it. Four agents talk to each other: one fetches, one thinks, one moves, one tends. Together they loop data into decisions.

Supports both **rules-based** (fast, battle-tested) and **AI-powered** (LLM reasoning for every decision) modes. AI runs locally on Apple Silicon via MLX — no API keys, no cloud.

---

## One Command to Start

```bash
grind --once                    # Single AI pipeline turn (default: MLX 7B)
grind                           # Continuous loop every 5 minutes
grind --no-model                # Rules-based mode (no AI)
```

Or via Makefile:

```bash
make once    make run    make rules    make logs
```

---

## The Four Parts

**Whisperer** — Fetches. Scans DexScreener for tokens with velocity, freshness, and narrative momentum. Returns signals.

**Actuary** — Thinks. Runs each signal through GoPlus for honeypot detection, tax analysis, and liquidity verification. Returns risk levels.

**Slinger** — Moves. Takes an approved signal, builds a transaction with appropriate slippage and gas, sends it through the chain.

**Reaper** — Tends. Watches open positions. Extracts principal at +100%. Cuts losses at -30%. Never gets attached.

---

## AI Agent Pipeline (`ai_agents/`)

Each agent can optionally use a local LLM for reasoning on top of the existing rules-based logic. Ships with two inference backends:

| Backend | How | Best For |
|---------|-----|----------|
| `MLXEngine` | Apple Metal (`mlx-lm`) | M1-M5 Macs — native, fast, no setup |
| `OllamaEngine` | Ollama HTTP API | Linux / Intel Macs |

Default model: `mlx-community/Qwen2.5-7B-Instruct-4bit` (~4GB RAM, runs comfortably on 16GB M5).

```bash
grind --model mlx-community/Qwen2.5-7B-Instruct-4bit
grind --model qwen3:8b                               # Ollama if available
grind --no-model                                      # Skip AI entirely
```

Graceful fallback: every AI agent degrades to rules-based logic if the model is unavailable.

---

## Strategy Profiles

| Mode | Description | Risk |
|------|-------------|------|
| Degen | Follow momentum fast, ask questions later | High |
| Sniper | Full forensics, private mempool, small targets | Low |
| Shadow Clone | Track wallets that seem to know something | Medium |
| Arb Hunter | Pure math across DEX pairs | Low |
| Oracle's Eye | Watch macro signals and large wallets | Medium |
| Liquidity Sentinel | Read market structure, find structural plays | Medium |
| Yield Alchemist | Optimize DeFi yield positions | Low |
| Forensic Sniper | Extreme due diligence on every target | Very Low |

---

## Installation

```bash
# From source
git clone https://github.com/dartecheese/asymmetric-strike-team
cd asymmetric-strike-team
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Install the CLI + optional background service
./install.sh                # CLI only (grind command)
./install.sh --service      # CLI + 5-min LaunchAgent
```

The LaunchAgent runs the pipeline every 300 seconds and logs to `logs/`.

---

## Technical Stack

Python 3.14, web3.py, Pydantic v2, mlx-lm (AI), ollama (AI).  
DexScreener API for data, GoPlus Security API for risk.  
JSON files for persistence — no database, no cloud.

36 tests cover the pipeline. Run `python test_system.py` to verify.

**Performance:**

| Agent | Time |
|-------|------|
| Whisperer scan | ~2s |
| Actuary (GoPlus) | ~500ms cached, ~2s fresh |
| Slinger execution | ~2s |
| Reaper tick | <100ms |
| Full AI cycle (MLX) | ~15s (model loads cached) |
| Full rules cycle | ~5-10s |

---

## Safety

- Paper mode is default. Real execution requires explicit flags and a funded wallet.
- Testnet first. Sepolia recommended.
- Max $50 per trade in real mode.
- Stops after 3 consecutive losses or 5% daily drawdown.
- Keep your private keys offline. Slinger loads them from environment.

This is experimental software. Real funds can be lost to slippage, MEV, honeypots, and rug pulls. No warranty. The authors assume no liability. Start small. Monitor actively.

---

*The wheel turns. The flour comes out. That's the whole deal.*
