# Asymmetric Strike Team
## High-Velocity DeFi Trading System

**Version:** 1.2.0  
**Status:** Production-ready (paper trading)  
**License:** MIT  
**GitHub:** `dartecheese/asymmetric-strike-team`

---

## Executive Summary

The **Asymmetric Strike Team** is an autonomous, multi-agent DeFi trading system designed for high-velocity, high-risk/high-reward cryptocurrency trading. Built on a modular agent architecture, it scans social and on-chain signals, assesses risk in real-time, executes trades with extreme slippage tolerance, and monitors positions with ruthless stop-loss/take-profit logic.

Unlike traditional quant systems that optimize for Sharpe ratio, this system embraces **asymmetric risk profiles**: small principal at risk, massive upside potential. It's built for the "degen" market segment where speed and conviction outweigh traditional due diligence.

## Core Philosophy

> **"Better to lose 100% of a small position than 10% of your entire portfolio."**

The system operates on three principles:

1. **Velocity over precision** — Find signals fast, execute faster
2. **Asymmetric risk** — Small position sizes, extreme upside targets
3. **Ruthless defense** — Extract principal at +100%, cut losses at -30%

## Architecture

### Agent-Based Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                    ASYMMETRIC STRIKE TEAM               │
├─────────────────────────────────────────────────────────┤
│ 1. WHISPERER  → Social/Smart Money velocity scanning   │
│ 2. ACTUARY    → Real-time risk assessment (GoPlus API) │
│ 3. SLINGER    → Direct Web3 router execution           │
│ 4. REAPER     → Position monitoring & defense          │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
DexScreener API → Whisperer → TradeSignal
      ↓
   GoPlus API → Actuary → RiskAssessment
      ↓
Web3 Router → Slinger → ExecutionOrder
      ↓
PositionStore → Reaper → Portfolio Defense
```

## Agent Details

### 1. Whisperer
**Purpose:** Surface high-momentum tokens from social and on-chain activity.

**Data sources:**
- DexScreener `/token-profiles/latest` — newly listed tokens
- DexScreener `/token-boosts/top` — paid narrative signals
- Volume velocity scoring (24h volume / liquidity ratio)
- Price momentum (1h, 6h change)
- Freshness bonus (<1h old tokens)

**Output:** `TradeSignal` with token address, chain, narrative score (0-100), reasoning.

### 2. Actuary
**Purpose:** Fast heuristic risk assessment using GoPlus Security API.

**Checks:**
- Honeypot detection
- Buy/sell tax percentages
- Liquidity lock status
- Open-source verification

**Features:**
- 5-minute cache to avoid API rate limits
- Conservative fallback when API unavailable (never returns `None`)
- Strategy-specific tax tolerance (degen: 30%, sniper: 0%)

**Output:** `RiskAssessment` with risk level (LOW/MEDIUM/HIGH/REJECTED) and max allocation.

### 3. Slinger
**Purpose:** Direct Web3 router execution bypassing UIs.

**Capabilities:**
- Multi-chain support: Ethereum, BSC, Arbitrum, Base
- Strategy-specific slippage (1-30%)
- Strategy-specific gas multipliers (1-3x)
- Private mempool routing (Flashbots) for MEV protection
- Real entry price capture from DexScreener

**Output:** `ExecutionOrder` with token, amount, slippage, gas, entry price.

### 4. Reaper
**Purpose:** Portfolio defense with asymmetric profit-taking.

**Triggers:**
- **Free Ride:** Extract principal at +100% gain
- **Stop Loss:** Liquidate at -30% loss
- **Trailing Stop:** Lock in gains after free ride (-15% from peak)

**Features:**
- Real-time price polling via DexScreener
- Persistent position state (survives restarts)
- Paper trading simulation mode
- Portfolio summary and P&L tracking

## Strategy Profiles

Eight pre-configured trading personalities:

| Strategy | Risk | Slippage | Gas Multiplier | TP/SL | Team Composition |
|----------|------|----------|----------------|-------|------------------|
| **Degen Ape** | High | 30% | 3.0x | +100%/-50% | Whisperer → Actuary → Slinger → Reaper |
| **Safe Sniper** | Low | 5% | 1.2x | +20%/-10% | Full forensics + private mempool |
| **Shadow Clone** | Medium | 10% | 2.0x | +50%/-20% | Copy-trades smart money wallets |
| **Arb Hunter** | Low | 1% | 1.0x | +1%/-1% | Cross-DEX arbitrage, pure math |
| **Oracle's Eye** | Medium | 8% | 1.8x | +75%/-15% | Macro indicators + whale tracking |
| **Liquidity Sentinel** | Medium | 3% | 1.3x | +30%/-8% | Market structure analysis |
| **Yield Alchemist** | Low | 2% | 1.1x | +15%/-5% | DeFi yield optimization |
| **Forensic Sniper** | Very Low | 2% | 1.0x | +50%/-5% | Extreme due diligence |

## Technical Stack

- **Language:** Python 3.14+
- **Web3:** `web3.py`, `eth-account`
- **APIs:** DexScreener (free), GoPlus Security
- **Data Models:** Pydantic v2
- **Persistence:** Atomic JSON writes via `PositionStore`
- **Logging:** Structured logging with rotation
- **Testing:** 36-test comprehensive suite

## Installation

```bash
git clone https://github.com/dartecheese/asymmetric-strike-team
cd asymmetric-strike-team
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Paper Trading (Default)
```bash
python main.py --strategy degen
```

### Continuous Scanning
```bash
python main.py --strategy sniper --loop --interval 60
```

### List All Strategies
```bash
python main.py --list
```

### Live Execution (Danger!)
```bash
export USE_REAL_EXECUTION=true
export ETH_RPC_URL="https://eth.llamarpc.com"
export PRIVATE_KEY="0x..."
python main.py --strategy degen
```

## Safety Features

1. **Paper Trading Default** — Must explicitly enable real execution
2. **Testnet Recommendation** — Strong emphasis on Sepolia testing first
3. **Position Size Limits** — Max $50 per trade (configurable)
4. **Circuit Breakers** — Stop trading after 3 consecutive losses
5. **Daily Drawdown Cap** — Stop if daily drawdown >5%
6. **Input Validation** — Pydantic models reject malformed orders
7. **Atomic Persistence** — No corruption on crash

## Performance Metrics

| Component | Latency | Throughput |
|-----------|---------|------------|
| Whisperer scan | 2-3s | 1 signal/scan |
| Actuary assessment | 500ms (cache) / 2s (API) | Unlimited (cached) |
| Slinger order build | 2s | 1 order/assessment |
| Reaper tick | <100ms | 10 positions concurrently |
| Full pipeline cycle | 5-10s | 6-12 trades/hour |

## Roadmap

### Phase 1 (Complete)
- [x] Core 4-agent architecture
- [x] Real DexScreener + GoPlus integration
- [x] 8 strategy profiles
- [x] Paper trading simulation
- [x] Persistent position state
- [x] Comprehensive test suite

### Phase 2 (Next)
- Multi-position support (parallel signal processing)
- Telegram/Discord alerting
- Performance dashboard (Grafana)
- Backtesting framework
- Yield farming integration

### Phase 3 (Future)
- Cross-chain arbitrage engine
- Flash loan integration
- On-chain limit orders
- Governance token staking
- DAO-managed treasury

## Risk Disclosure

**This is experimental software. Use at your own risk.**

- **Real funds can be lost** — Slippage, MEV, honeypots, rug pulls
- **No warranty** — The authors assume no liability
- **Test extensively** on Sepolia/Görli before mainnet
- **Start small** — 0.01 ETH position sizes recommended
- **Monitor actively** — Do not leave unattended

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass (`python test_system.py`)
5. Submit a pull request

## License

MIT License — see `LICENSE` file.

## Contact

- **GitHub:** [dartecheese/asymmetric-strike-team](https://github.com/dartecheese/asymmetric-strike-team)
- **Issues:** GitHub Issues tracker
- **Discord:** OpenClaw community

---

*"In the land of the blind, the one-eyed man is king. In the land of the degen, the fast bot is god."*
