# Asymmetric Strike Team — Professional Edition

A high-performance, multi-venue DeFi trading system with professional risk management, performance tracking, and unified execution (DEX + CEX).

## 🚀 Features

### Core Trading Engine
- **Multi-venue Execution**: DEX (Web3.py) + CEX (CCXT) unified routing
- **Enhanced Signal Detection**: DexScreener scanning with sentiment analysis
- **Risk Assessment**: GoPlus API integration for token security checks
- **Position Management**: Automated take-profit, stop-loss, trailing stops

### Professional Features
- **Risk Management Layer**: Portfolio-level position sizing, correlation checks, circuit breakers
- **Performance Tracking**: SQLite database with comprehensive metrics (win rate, Sharpe ratio, drawdown)
- **Configuration Management**: YAML config files with environment variable overrides
- **Error Handling**: Professional validation and fallback mechanisms

### Security & Safety
- **Paper Trading Mode**: Safe testing without real funds
- **Circuit Breakers**: Automatic trading pauses during extreme volatility
- **Daily Loss Limits**: Configurable maximum daily loss percentages
- **No Third-Party Dependencies**: All code self-contained (removed risky third-party skills)

## 📁 Project Structure

```
asymmetric_trading/
├── agents/                    # Trading agents
│   ├── whisperer.py          # DexScreener scanner
│   ├── enhanced_whisperer.py # With sentiment analysis
│   ├── actuary.py           # Risk assessment (GoPlus API)
│   ├── slinger.py           # DEX execution (Web3.py)
│   ├── cex_slinger.py       # CEX execution (CCXT)
│   ├── unified_slinger.py   # Smart DEX/CEX routing
│   ├── reaper.py           # Position monitoring
│   ├── risk_manager.py     # Portfolio risk management
│   ├── performance_tracker.py # Trade analytics
│   └── sentiment_enhancer.py # Sentiment analysis
├── core/
│   └── models.py           # Pydantic data models
├── execution/              # Execution layer
├── strategy_factory.py    # Strategy profiles
├── config_manager.py      # Configuration management
├── main_pro.py           # Professional main entry point
├── config.yaml           # Configuration file
├── requirements.txt      # Python dependencies
└── README_PRO.md        # This file
```

## 🚀 Quick Start

### 1. Installation
```bash
# Clone repository
git clone <repository-url>
cd asymmetric_trading

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
```bash
# Copy environment template
cp .env.template .env

# Edit .env file with your settings
# For paper trading, you can leave most fields empty
```

### 3. Run Paper Trading
```bash
# Single cycle test
python main_pro.py

# Continuous mode (scans every 60 seconds)
python main_pro.py --loop

# With specific strategy
python main_pro.py --strategy sniper --loop
```

## ⚙️ Configuration

### Configuration Files
- **`config.yaml`**: Main configuration (created automatically on first run)
- **`.env`**: Environment variables (API keys, RPC URLs)
- **`.env.template`**: Template with all available options

### Key Configuration Options

#### Execution Mode
```yaml
execution_mode: paper  # or "real" for live trading
```

#### Strategies
```yaml
strategies:
  degen:
    description: "High-risk, high-reward degen trading"
    whisperer_min_score: 50
    actuary_max_tax_pct: 10.0
    slinger_slippage_pct: 30.0
    reaper_take_profit_pct: 100.0
    reaper_stop_loss_pct: 50.0
  
  sniper:
    description: "Precision entry on confirmed breakouts"
    whisperer_min_score: 70
    actuary_max_tax_pct: 3.0
    slinger_slippage_pct: 10.0
    reaper_take_profit_pct: 50.0
    reaper_stop_loss_pct: 20.0
  
  conservative:
    description: "Low-risk, high-probability trades"
    whisperer_min_score: 80
    actuary_max_tax_pct: 1.0
    slinger_slippage_pct: 5.0
    reaper_take_profit_pct: 25.0
    reaper_stop_loss_pct: 10.0
```

#### Risk Management
```yaml
risk:
  max_portfolio_size_usd: 10000.0
  max_position_size_pct: 0.10      # 10% max per position
  max_daily_loss_pct: 0.05         # 5% daily loss limit
  max_correlation_threshold: 0.7    # Reject correlated positions
  circuit_breaker_volatility: 0.20  # 20% price move triggers pause
```

## 🎯 Available Commands

### Basic Usage
```bash
# Show configuration summary
python main_pro.py --status

# Run single cycle with default strategy
python main_pro.py

# Run continuous mode
python main_pro.py --loop

# Use specific strategy
python main_pro.py --strategy sniper --loop

# Custom scan interval
python main_pro.py --loop --interval 300  # 5 minutes

# Export performance data
python main_pro.py --export
```

### Strategy Profiles
1. **`degen`**: High-risk, high-reward (100% TP / 50% SL)
2. **`sniper`**: Precision entries (50% TP / 20% SL)  
3. **`conservative`**: Low-risk trading (25% TP / 10% SL)

## 📊 Performance Tracking

The system automatically tracks all trades in a SQLite database (`trading_performance.db`):

### Metrics Tracked
- Win rate and profit factor
- Maximum drawdown
- Sharpe ratio (simplified)
- Average holding period
- Best/worst trades
- Daily P&L

### Export Data
```bash
python main_pro.py --export
# Exports to performance_export.csv
```

### View Performance Report
```bash
python main_pro.py --status
```

## 🔐 Security & Risk Management

### Built-in Protections
1. **Circuit Breakers**: Automatic pause during 20%+ volatility
2. **Daily Loss Limits**: Configurable maximum daily loss (default: 5%)
3. **Position Sizing**: Maximum 10% of portfolio per position
4. **Correlation Checks**: Rejects highly correlated positions
5. **Token Security**: GoPlus API integration for honeypot detection

### Safe Testing
- **Paper Trading Mode**: Default mode, no real funds required
- **Testnet Exchanges**: CEX testnet support (Binance, Bybit)
- **Safe Defaults**: Conservative parameters out of the box

## 🛠️ Advanced Configuration

### Real Trading Setup
1. Enable real mode in `.env`:
   ```bash
   USE_REAL_EXECUTION=true
   ```

2. Add wallet private key:
   ```bash
   PRIVATE_KEY=your_private_key_here
   ```

3. Configure RPC URLs for DEX trading:
   ```bash
   ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/your_key
   BASE_RPC_URL=https://mainnet.base.org
   ```

4. Add exchange API keys for CEX trading:
   ```bash
   BINANCE_API_KEY=your_key
   BINANCE_API_SECRET=your_secret
   ```

### Custom Strategies
Edit `config.yaml` to create custom strategy profiles:
```yaml
strategies:
  my_custom_strategy:
    description: "My custom trading approach"
    whisperer_min_score: 65
    actuary_max_tax_pct: 5.0
    slinger_slippage_pct: 15.0
    reaper_take_profit_pct: 75.0
    reaper_stop_loss_pct: 30.0
```

## 🚨 Production Deployment

### Recommended Setup
1. **Start with Paper Trading**: Run for 48+ hours to validate performance
2. **Gradual Capital Allocation**: Start with small amounts (≤ $100)
3. **Monitor Closely**: Watch performance metrics daily
4. **Set Conservative Limits**: Use `conservative` strategy initially
5. **Enable Notifications**: Set up Telegram/Discord alerts

### Monitoring Checklist
- [ ] Daily P&L within expected range
- [ ] Win rate > 40% (adjust strategy if lower)
- [ ] Maximum drawdown < 20%
- [ ] No failed transactions or errors
- [ ] Circuit breakers not triggering frequently

## 🐛 Troubleshooting

### Common Issues

**"No API keys found" warning**
- Expected in paper trading mode
- For real trading, add API keys to `.env`

**"ValidationError" exceptions**
- Fixed in current version
- If persists, check Python package versions

**Slow performance**
- Reduce scan interval with `--interval 300`
- Check network connectivity
- Consider upgrading hardware/VPS

**No signals found**
- DexScreener may have rate limits
- Try different time of day
- Adjust `whisperer_min_score` in config

### Logs & Debugging
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main_pro.py

# Check performance database
sqlite3 trading_performance.db "SELECT * FROM trades LIMIT 5;"

# View risk manager state
cat risk_manager_state.json | jq .
```

## 📈 Performance Optimization

### For High-Frequency Trading
1. Reduce `loop_interval_seconds` in config
2. Use `sniper` strategy for faster exits
3. Enable private mempool for DEX trades
4. Use dedicated RPC endpoints

### For Better Risk-Adjusted Returns
1. Use `conservative` strategy
2. Reduce position size (`max_position_size_pct`)
3. Lower daily loss limit (`max_daily_loss_pct`)
4. Enable strict mode in Actuary

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Code formatting
black .
isort .
```

### Architecture Guidelines
- New agents go in `agents/` directory
- Data models in `core/models.py`
- Configuration via `config_manager.py`
- Strategy parameters in `strategy_factory.py`

## 📄 License

MIT License - see LICENSE file for details.

## ⚠️ Disclaimer

**This is experimental software for educational purposes.** 

- Never trade more than you can afford to lose
- Always test thoroughly in paper trading mode first
- Cryptocurrency trading involves significant risk
- Past performance does not guarantee future results
- The developers are not responsible for any financial losses

---

**Happy trading!** 🚀