# MCP Integration - Running Instructions

## Overview
The MCP integration wires the traditional Asymmetric Strike Team pipeline with the new MCP architecture. This allows:
- **Traditional DEX execution** via Slinger (Web3.py)
- **CEX execution** via PHANTOM MCP agent (CCXT)
- **Hybrid execution** using both DEX and CEX

## Files Created
1. `main_mcp_integrated.py` - Main entry point with MCP integration
2. `test_mcp_integration_simple.py` - Test suite for the integration
3. `test_mcp_quick.py` - Quick import test

## Running Modes

### 1. Quick Test (Verify Imports)
```bash
cd asymmetric_trading
python3 -c "
import sys
sys.path.append('.')
from main_mcp_integrated import convert_signal_to_mcp_format
print('✅ MCP integration imports work')
"
```

### 2. Single Cycle - Hybrid Mode (Default)
```bash
cd asymmetric_trading
python3 main_mcp_integrated.py --strategy degen --mcp-mode hybrid
```
- Uses both DEX (Slinger) and CEX (PHANTOM MCP)
- Default strategy: degen

### 3. Single Cycle - MCP-Only Mode
```bash
cd asymmetric_trading
python3 main_mcp_integrated.py --strategy sniper --mcp-mode mcp-only
```
- Uses only CEX execution via PHANTOM MCP
- Strategy: sniper (more conservative)

### 4. Single Cycle - Traditional Mode
```bash
cd asymmetric_trading
python3 main_mcp_integrated.py --strategy degen --mcp-mode traditional
```
- Uses only DEX execution (original pipeline)
- Disables MCP integration

### 5. Continuous Scanning
```bash
cd asymmetric_trading
python3 main_mcp_integrated.py --loop --interval 300 --strategy degen --mcp-mode hybrid
```
- Runs continuous scanning every 5 minutes (300 seconds)
- Hybrid execution mode
- Press Ctrl+C to stop

### 6. List All Strategies
```bash
cd asymmetric_trading
python3 main_mcp_integrated.py --list
```

## MCP Agent Configuration

### PHANTOM Agent Settings
The PHANTOM agent is configured differently based on strategy:

**Degen Strategy:**
- Min confidence: 0.65
- Max position size: 2.0% of portfolio
- Higher risk tolerance

**Sniper Strategy:**
- Min confidence: 0.80  
- Max position size: 0.5% of portfolio
- Lower risk tolerance

### Signal Conversion
Traditional signals are automatically converted to MCP format:
- Token symbol → Trading pair (e.g., ETH → ETH/USDT)
- Chain → Exchange mapping (e.g., ethereum → binance)
- Risk assessment → Confidence score

## Execution Flow

### Hybrid Mode Flow:
```
1. Whisperer scans for signals
2. Actuary assesses risk
3. IF signal passes:
   - DEX: Slinger executes on-chain (if hybrid/traditional)
   - CEX: PHANTOM executes via CCXT MCP (if hybrid/mcp-only)
4. Reaper monitors positions
```

### Paper vs Live Mode:
- **Paper mode**: Simulated execution (default)
- **Live mode**: Real execution (set `USE_REAL_EXECUTION=true`)

## Logging
Results are logged to:
- `logs/mcp_integration_<timestamp>.json` - Cycle results
- `data/phantom_executions.json` - PHANTOM agent executions
- Console output with colored indicators

## Integration Points

### 1. Signal Conversion
Traditional signals → MCP format via `convert_signal_to_mcp_format()`

### 2. Agent Initialization  
MCP agents initialized via `initialize_mcp_agents()` based on mode

### 3. Execution Routing
Signals routed to appropriate executor based on mode:
- Traditional → Slinger (DEX)
- MCP → PHANTOM (CEX)
- Hybrid → Both

### 4. Risk Parameters
Strategy-specific risk params flow to both traditional and MCP agents

## Next Steps for Production

### 1. Get API Keys
- Binance Testnet API keys for CCXT MCP
- TradingView MCP setup

### 2. Enable Live Execution
```bash
export USE_REAL_EXECUTION=true
export BINANCE_API_KEY=your_key
export BINANCE_API_SECRET=your_secret
python3 main_mcp_integrated.py --strategy degen
```

### 3. Add More MCP Servers
- TradingView for technical analysis
- Santiment for sentiment data
- Dune for on-chain analytics

### 4. Performance Monitoring
- Add performance tracking database
- Implement risk limits
- Add circuit breakers

## Troubleshooting

### Import Errors
If you get import errors:
```bash
cd asymmetric_trading
export PYTHONPATH=.:$PYTHONPATH
python3 main_mcp_integrated.py --list
```

### PHANTOM Agent Not Found
Make sure `agents/phantom_mcp_agent.py` exists:
```bash
ls -la agents/phantom_mcp_agent.py
```

### MCP Config Missing
Default config is used if `mcp_config.json` not found. To create one:
```json
{
  "mcpServers": {
    "ccxt": {
      "command": "npx",
      "args": ["-y", "@lazydino/ccxt-mcp"]
    }
  }
}
```

## Example Output
```
🚀  ASYMMETRIC STRIKE TEAM - MCP INTEGRATED EDITION
   Strategy : degen
   Mode     : PAPER
   MCP Mode : hybrid

🔗 MCP Integration Status:
   • PHANTOM Agent: ✅ Available
   • Mode: hybrid
   • Execution: DEX + CEX Hybrid

🔄 CYCLE #1 - 20:45:30
...
✅ DEX Trade (Slinger): ETH @ $3500.00
✅ CEX Trade (PHANTOM MCP): ETH/USDT @ $3498.50
```

## Summary
The MCP integration successfully wires the traditional trading pipeline with the new MCP architecture, providing:
- **Backward compatibility** with existing DEX execution
- **Forward compatibility** with MCP-based CEX execution  
- **Flexible routing** via hybrid/traditional/mcp-only modes
- **Strategy-aware** risk parameter propagation