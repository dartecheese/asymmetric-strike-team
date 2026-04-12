# 🚀 Asymmetric Strike Team

**High-Velocity DeFi Trading System**  
*Paper trading ready • 8 strategy profiles • Real-time risk assessment*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-36%20passed-brightgreen)](test_system.py)

> **Asymmetric risk, symmetric execution.**  
> Small positions, massive upside targets, ruthless defense.

---

## 🎯 Quick Start

```bash
# Clone & setup
git clone https://github.com/dartecheese/asymmetric-strike-team
cd asymmetric-strike-team
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run paper trading
python main.py --strategy degen

# Continuous scanning
python main.py --strategy sniper --loop --interval 60

# List all strategies
python main.py --list
```

## 📊 What It Does

1. **Scans** DexScreener for high-momentum tokens
2. **Assesses** risk via GoPlus Security API (honeypots, taxes)
3. **Executes** via direct Web3 router calls (Uniswap, PancakeSwap, etc.)
4. **Monitors** with asymmetric TP/SL (+100% extract principal, -30% cut loss)

## 🏗️ Architecture

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

## 🎪 Strategy Profiles

| Strategy | Risk | Slippage | TP/SL | Description |
|----------|------|----------|-------|-------------|
| **Degen Ape** | High | 30% | +100%/-50% | Momentum-based, ignores forensics for speed |
| **Safe Sniper** | Low | 5% | +20%/-10% | Full forensics + MEV protection |
| **Shadow Clone** | Medium | 10% | +50%/-20% | Copy-trades smart money wallets |
| **Arb Hunter** | Low | 1% | +1%/-1% | Cross-DEX arbitrage, pure math |
| **Oracle's Eye** | Medium | 8% | +75%/-15% | Macro + whale tracking |
| **Liquidity Sentinel** | Medium | 3% | +30%/-8% | Market structure analysis |
| **Yield Alchemist** | Low | 2% | +15%/-5% | DeFi yield optimization |
| **Forensic Sniper** | Very Low | 2% | +50%/-5% | Extreme due diligence |

## 🛡️ Safety First

- **Paper trading default** — Must explicitly enable real execution
- **Testnet emphasis** — Sepolia/Görli recommended before mainnet
- **Position size limits** — Max $50 per trade
- **Circuit breakers** — Stop after 3 consecutive losses
- **Atomic persistence** — Positions survive crashes

## 📈 Performance

- **Whisperer scan:** ~2.2s (real DexScreener API)
- **Actuary assessment:** <500ms (5-min cache)
- **Slinger execution:** ~2.1s (includes price fetch)
- **Reaper monitoring:** <100ms per position
- **Full pipeline:** 5-10s per cycle

## 📚 Documentation

- **[WHITEPAPER.md](WHITEPAPER.md)** — Comprehensive technical overview
- **[REAL_EXECUTION_GUIDE.md](REAL_EXECUTION_GUIDE.md)** — Live trading setup
- **[test_system.py](test_system.py)** — 36-test validation suite

## 🚨 Warning

**This is experimental software. Real funds can be lost.**

- Slippage, MEV, honeypots, rug pulls
- No warranty — authors assume no liability
- Test extensively on Sepolia first
- Start small (0.01 ETH positions)
- Monitor actively — do not leave unattended

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass (`python test_system.py`)
5. Submit a pull request

## 📄 License

MIT — see [LICENSE](LICENSE) file.

---

*Built with ❤️ by the OpenClaw community.*  
*GitHub: [dartecheese/asymmetric-strike-team](https://github.com/dartecheese/asymmetric-strike-team)*
