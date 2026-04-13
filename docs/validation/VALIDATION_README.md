# Paper Trading Validation Guide

## Overview
This guide outlines the process for validating the Asymmetric Strike Team trading system in paper trading mode. The goal is to ensure the system operates reliably before considering live execution.

## Quick Start

### 1. Basic System Check
```bash
# Check all files exist
python3 check_agents.py

# List available strategies  
python3 main.py --list

# Run single cycle test
python3 test_one_cycle.py
```

### 2. Paper Trading Test (24 hours)
```bash
# Start 24-hour paper trading test
python3 run_48h_test.py --duration 24 --strategy degen

# Or use the simple version
python3 run_48h_test_simple.py
```

### 3. MCP Integration Test
```bash
# Test MCP integration
python3 test_mcp_integration_simple.py

# Run with MCP mode
python3 main_mcp_integrated.py --strategy degen --mcp-mode hybrid
```

## Validation Phases

### Phase 1: Basic Pipeline ✅
- [x] **Whisperer**: Scans DexScreener for tokens
- [x] **Actuary**: Assesses risk via GoPlus API (with fallback)
- [x] **Slinger**: Builds transactions (paper mode)
- [x] **Reaper**: Monitors positions with TP/SL

**Test Script**: `test_system.py`

### Phase 2: Strategy Profiles ✅
- [x] **8 Profiles**: degen, sniper, shadow_clone, arb_hunter, oracle_eye, liquidity_sentinel, yield_alchemist, forensic_sniper
- [x] **Profile Loading**: All profiles load correctly
- [x] **Parameter Flow**: Strategy params flow to all agents

**Test Script**: `test_system.py --all-strategies`

### Phase 3: MCP Integration ✅
- [x] **PHANTOM Agent**: MCP-based CEX execution
- [x] **Signal Conversion**: DEX→CEX format translation
- [x] **Execution Modes**: hybrid, mcp-only, traditional

**Test Script**: `test_mcp_integration_simple.py`

### Phase 4: Paper Trading Validation 🔄
- [ ] **24-Hour Test**: Continuous operation
- [ ] **Performance Metrics**: Track scans, assessments, paper trades
- [ ] **Error Recovery**: Handle API failures gracefully

**Test Script**: `run_48h_test.py`

## Monitoring During Validation

### Log Files
- `logs/` - System logs with timestamps
- `data/positions.json` - Paper trading positions
- `monitoring_reports/` - Performance reports

### Key Metrics to Watch
1. **Scan Cycles**: Should complete every 5 minutes (300s)
2. **API Success Rate**: >95% for external APIs
3. **Error Rate**: <1% of operations
4. **Memory Usage**: Stable over time
5. **CPU Usage**: Reasonable for scanning operations

### Common Issues & Solutions

#### Issue: GoPlus API Failures
**Solution**: System has fallback to conservative defaults (5% tax assumption)

#### Issue: DexScreener Rate Limiting  
**Solution**: Built-in delays between requests

#### Issue: Network Timeouts
**Solution**: Retry logic with exponential backoff

#### Issue: Invalid Token Data
**Solution**: Validation layer filters malformed data

## Success Criteria

### Must Have (Blocking Issues)
- [ ] System runs for 24h without fatal crashes
- [ ] All 8 strategy profiles work correctly
- [ ] Error handling prevents system crashes
- [ ] Paper trading positions tracked accurately

### Should Have (Important)
- [ ] Performance metrics collected
- [ ] Logs are readable and informative
- [ ] Configuration is easy to modify
- [ ] Documentation is up-to-date

### Nice to Have (Optional)
- [ ] Web dashboard for monitoring
- [ ] Telegram/Discord alerts
- [ ] Historical performance analysis
- [ ] Automated report generation

## Validation Report

After completing validation, create a report with:

1. **Executive Summary**: Overall system status
2. **Test Results**: Pass/fail for each test
3. **Performance Metrics**: Quantitative results
4. **Issues Found**: Bugs or limitations discovered
5. **Recommendations**: Next steps and improvements

**Template**: See `validation_report_template.md`

## Next Steps After Validation

### If Validation PASSES:
1. **Security Audit**: Review code for security issues
2. **API Key Setup**: Get testnet API keys for CEX
3. **Small Live Test**: Test with minimal real funds
4. **Monitoring Setup**: Production monitoring and alerts

### If Validation FAILS:
1. **Issue Triage**: Prioritize blocking issues
2. **Fix & Retest**: Address issues and retest
3. **Documentation**: Update docs with lessons learned
4. **Re-evaluate**: Consider architectural changes if needed

## Resources

- **System Documentation**: `README.md`, `REAL_EXECUTION_GUIDE.md`
- **MCP Integration**: `RUN_MCP_INTEGRATION.md`, `MCP_WIRING_SUMMARY.md`
- **Testing**: `TESTING_PLAN.md`, `test_system.py`
- **Performance**: `PERFORMANCE_ANALYSIS.md`, `OPTIMIZATION_PLAN.md`

## Support

For issues during validation:
1. Check logs in `logs/` directory
2. Review error messages in console
3. Consult documentation links above
4. Check for known issues in `CHANGELOG.md`

---

**Validation Owner**: Asymmetric Strike Team  
**Last Updated**: 2026-04-13  
**Status**: Phase 4 in progress (Paper Trading Validation)