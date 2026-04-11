# Asymmetric Strike Team

A high-risk, high-reward ("degen") DeFi trading system powered by an autonomous 4-agent assembly. Designed to capitalize on fast-moving social narratives while enforcing ruthless capital preservation rules.

## 🚀 Features

- **Real Web3.py Execution**: Live blockchain transactions with automatic paper/real mode switching
- **Multi-Chain Support**: Ethereum, Base, and extensible to any EVM chain
- **8 Strategy Profiles**: From degen ape to forensic sniper
- **Unified Execution**: Single interface for paper trading and live execution
- **Comprehensive Testing**: Full test suite for safe deployment

## The Assembly

1. **The Whisperer**: Scans social firehoses (Twitter, Telegram, DexScreener) for narrative spikes and smart money velocity.
2. **The Actuary**: Rapid heuristic security auditor. Uses GoPlus API to check for honeypots and excessive taxes.
3. **The Slinger**: Direct Web3 execution. Bypasses UIs, constructing raw router calldata (Uniswap V2, etc.) with high slippage tolerances to guarantee block inclusion.
4. **The Reaper**: Portfolio defense monitor. Executes a strict "Free Ride" protocol (extract principal at +100%) and a kill-switch stop loss (liquidate at -30%).

## ⚡ Quick Start

### 1. Installation
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
Copy and edit the environment file:
```bash
cp .env.example .env
# Edit .env with your RPC URL and private key
```

### 3. Test First
```bash
# Test paper trading
python cli.py

# Test real execution setup
python test_real_execution.py
```

### 4. Run
```bash
# Interactive CLI
python cli.py

# Or run specific strategy
python cli.py --strategy degen

# Dashboard (web interface)
python dashboard.py
```

## 🔧 Advanced Configuration

### Environment Variables (.env)
```env
# Execution Mode (true for live, false for paper)
USE_REAL_EXECUTION=false

# Ethereum RPC (any EVM chain)
ETH_RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY

# Wallet Private Key
PRIVATE_KEY=0xYourPrivateKeyHere

# Optional: GoPlus API for honeypot detection
GOPLUS_API_KEY=your_goplus_api_key_here

# Default strategy
DEFAULT_STRATEGY=degen
```

### Available Strategies
```bash
python cli.py --list
```

1. **`degen`** - High risk, momentum-based (15-30% slippage)
2. **`sniper`** - Safe, MEV-protected (5% slippage)
3. **`shadow_clone`** - Copy trading from smart money wallets
4. **`arb_hunter`** - Cross-DEX arbitrage hunting
5. **`oracle_eye`** - Macro indicators + whale tracking
6. **`liquidity_sentinel`** - Market structure analysis
7. **`yield_alchemist`** - DeFi yield optimization
8. **`forensic_sniper`** - Deep due diligence

## 🔗 Multi-Chain Support

The system supports multiple EVM chains. Current configurations:

- **Ethereum** (Chain ID: 1) - Uniswap V2 router
- **Base** (Chain ID: 8453) - Base Swap router
- **Extensible**: Add any EVM chain with Uniswap V2 compatible router

To add a new chain, update the router and WETH addresses in `agents/slinger.py`.

## 🧪 Testing

### Paper Trading (Default)
```bash
USE_REAL_EXECUTION=false python cli.py
```

### Real Execution Test
```bash
# Test on Sepolia testnet first!
python test_real_execution.py
```

### Integration Test
```bash
python test_integration.py
```

## 📁 Project Structure

```
asymmetric_trading/
├── agents/                    # Core agent implementations
│   ├── whisperer.py          # Social signal scanning
│   ├── actuary.py           # Risk assessment
│   ├── slinger.py           # Transaction generation
│   └── reaper.py            # Position monitoring
├── execution/                # Execution layer
│   ├── slinger.py           # Paper trading execution
│   ├── real_slinger.py      # Real Web3.py execution
│   └── unified_slinger.py   # Automatic mode switching
├── core/                     # Data models
│   └── models.py            # Pydantic models
├── strategy_factory.py      # 8 strategy profiles
├── strategy_runner.py       # Pipeline orchestration
├── strategy_runner_real.py  # Enhanced with real execution
├── cli.py                   # Command-line interface
├── dashboard.py             # Web dashboard
├── main.py                  # Main execution script
├── test_real_execution.py   # Real execution test suite
├── test_integration.py      # Integration tests
├── REAL_EXECUTION_GUIDE.md  # Comprehensive guide
└── requirements.txt         # Python dependencies
```

## 🚨 Safety & Warnings

⚠️ **CRITICAL WARNINGS:**

1. **NEVER** use mainnet private keys without understanding risks
2. **ALWAYS** test on testnet (Sepolia) first
3. **START** with small amounts
4. **MONITOR** gas prices - real execution spends ETH
5. The system uses high slippage tolerances (15-30% for degen mode)

### Recommended Testnet Setup
1. Get Sepolia test ETH from a faucet
2. Use Sepolia RPC: `https://sepolia.infura.io/v3/YOUR_KEY`
3. Test with `degen` strategy first
4. Monitor transactions on https://sepolia.etherscan.io/

## 🔄 Recent Updates

### Web3.py Execution Layer Integration
- Added real Web3.py transaction execution
- Unified slinger for automatic paper/real mode switching
- Enhanced strategy runner with real execution support
- Comprehensive test suite
- Multi-chain extensibility

## 📞 Support

For issues:
1. Check `REAL_EXECUTION_GUIDE.md` for detailed instructions
2. Run test suite: `python test_integration.py`
3. Start with paper trading mode first

*Disclaimer: This is experimental software for high-risk DeFi environments. Use at your own risk. Real execution spends real cryptocurrency. Trade responsibly.*