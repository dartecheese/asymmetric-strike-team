# Real Execution Guide for Asymmetric Strike Team

This guide explains how to enable and use real Web3.py execution with the Asymmetric Strike Team trading system.

## 🚀 Quick Start

### 1. Configure Environment
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Test Your Setup
```bash
# Test the integration
python test_real_execution.py

# Test all components
python test_integration.py
```

### 3. Start Trading
```bash
# Interactive CLI
python cli.py

# Or run a specific strategy
python cli.py --strategy degen

# Or use the dashboard
python dashboard.py
```

## 🔧 Configuration

### Environment Variables (.env)

```env
# Execution Mode
USE_REAL_EXECUTION=true

# Ethereum RPC (Required for real execution)
ETH_RPC_URL=https://mainnet.infura.io/v3/YOUR_INFURA_KEY
# or testnet: https://sepolia.infura.io/v3/YOUR_INFURA_KEY

# Wallet Private Key (Required for real execution)
PRIVATE_KEY=0xYourPrivateKeyHere

# Optional: GoPlus API for honeypot detection
GOPLUS_API_KEY=your_goplus_api_key_here
```

### RPC Endpoints

**Free Options:**
- **Infura**: https://infura.io/ (free tier available)
- **Alchemy**: https://www.alchemy.com/ (free tier available)
- **Public RPCs**: https://chainlist.org/ (less reliable)

**Testnets (Recommended for testing):**
- **Sepolia**: `https://sepolia.infura.io/v3/YOUR_KEY`
- **Goerli**: `https://goerli.infura.io/v3/YOUR_KEY`

## 🧪 Testing

### 1. Paper Trading (Default)
```bash
# Paper trading mode (simulation)
USE_REAL_EXECUTION=false python cli.py
```

### 2. Real Execution Test
```bash
# Enable real execution
export USE_REAL_EXECUTION=true
export ETH_RPC_URL=your_rpc_url
export PRIVATE_KEY=your_private_key

# Test connection
python test_real_execution.py
```

### 3. Testnet Testing (RECOMMENDED)
1. Get test ETH from a Sepolia faucet
2. Use Sepolia RPC endpoint
3. Test with small amounts first

## 🏗️ Architecture

### Execution Modes

#### 1. Paper Trading (Default)
- Uses `execution/slinger.py` (mock execution)
- Simulates transactions
- No blockchain connection needed
- Safe for testing strategies

#### 2. Real Execution
- Uses `execution/real_slinger.py` (Web3.py)
- Connects to real RPC endpoint
- Signs and broadcasts real transactions
- Spends real ETH on gas

### Unified Slinger
The `execution/unified_slinger.py` automatically switches between modes based on environment variables.

## 📋 Strategies

### Available Strategies
```bash
python cli.py --list
```

### Strategy Profiles
1. **`degen`** - High risk, momentum-based
2. **`sniper`** - Safe, MEV-protected  
3. **`shadow_clone`** - Copy trading
4. **`arb_hunter`** - Arbitrage hunting
5. **`oracle_eye`** - Macro + whale tracking
6. **`liquidity_sentinel`** - Market structure
7. **`yield_alchemist`** - DeFi optimization
8. **`forensic_sniper`** - Deep due diligence

## ⚠️ Warnings & Safety

### Critical Warnings
1. **NEVER** use mainnet private keys without understanding risks
2. **ALWAYS** test on testnet first
3. **START** with small amounts
4. **MONITOR** gas prices (real execution spends ETH)

### Risk Management
- The system uses high slippage tolerances (15-30% for degen mode)
- Gas premiums can be high (up to 3x multiplier)
- No guarantees of profit - trading is risky

## 🔄 Updates & Integration

### Recent Changes
The system has been updated with:
1. **Real execution integration** in `main.py`
2. **Unified slinger** for automatic mode switching
3. **Enhanced strategy runner** with real execution support
4. **Test suite** for verification

### Files Created/Modified
- `execution/unified_slinger.py` - Unified execution agent
- `strategy_runner_real.py` - Enhanced runner with real execution
- `test_real_execution.py` - Real execution test suite
- `test_integration.py` - Integration test suite
- `integrate_real_execution.py` - Integration script
- `main.py` - Updated with real execution support

## 🚨 Troubleshooting

### Common Issues

#### 1. "ModuleNotFoundError: No module named 'web3'"
```bash
# Install dependencies
pip install -r requirements.txt
```

#### 2. "Failed to connect to RPC"
- Check your RPC URL
- Test connection: `curl -X POST $RPC_URL -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'`
- Try a different RPC provider

#### 3. "Invalid private key"
- Ensure private key starts with `0x`
- Check for typos
- Test with a testnet wallet first

#### 4. "Transaction failed"
- Check gas prices
- Ensure sufficient ETH balance
- Check token approvals (for selling)

## 📈 Monitoring

### Dashboard
```bash
python dashboard.py
```
Then open http://localhost:5000

### Logs
- Check `error.log` for errors
- Check `paper_trading.log` for paper trading activity
- Console output shows real-time activity

## 🎯 Next Steps

### For Testing
1. Configure Sepolia testnet in `.env`
2. Get test ETH from faucet
3. Run `python test_real_execution.py`
4. Test with `degen` strategy

### For Production
1. **Thoroughly** test on testnet
2. Start with **small** amounts on mainnet
3. **Monitor** performance closely
4. Adjust strategy parameters based on results

### Development
1. Add more real-time data sources
2. Implement MEV protection (Flashbots)
3. Add multi-chain support
4. Enhance risk management

## 📞 Support

If you encounter issues:
1. Check the logs
2. Review this guide
3. Test with paper trading first
4. Start small and scale up

Remember: **Real execution spends real money. Trade responsibly.**