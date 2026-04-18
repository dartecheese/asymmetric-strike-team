#!/usr/bin/env python3
"""
Integrate optimized QWNT parameters into the trading system
Updates configuration files and creates parameter validation
"""

import json
import os
from datetime import datetime

def load_optimized_params():
    """Load optimized parameters from results file"""
    try:
        with open("realistic_qwnt_results.json", "r") as f:
            data = json.load(f)
        return data["best_params"], data["best_metrics"]
    except FileNotFoundError:
        print("❌ Optimized results not found. Run realistic_fine_tune.py first.")
        return None, None

def create_parameter_validator(params, metrics):
    """Create a parameter validation module"""
    validator_code = f'''"""
Parameter Validator for Optimized QWNT Trading
Generated {datetime.now().isoformat()}
Validates trading parameters against optimization constraints
"""

import logging

logger = logging.getLogger("ParamValidator")

class ParameterValidator:
    """Validate trading parameters against optimization constraints"""
    
    def __init__(self):
        # Optimization targets
        self.expected_metrics = {{
            "sharpe_ratio": {metrics.get('sharpe', 1.5):.2f},
            "win_rate": {metrics.get('win_rate', 0.7):.3f},
            "max_drawdown": {metrics.get('max_drawdown', 5.0):.1f},
            "profit_factor": {metrics.get('profit_factor', 2.0):.1f}
        }}
        
        # Parameter bounds (from optimization)
        self.parameter_bounds = {{
            "stop_loss": ({params.get('stop_loss', 0.15) * 0.8:.3f}, {params.get('stop_loss', 0.25) * 1.2:.3f}),
            "take_profit": ({params.get('take_profit', 0.3) * 0.8:.3f}, {params.get('take_profit', 0.6) * 1.2:.3f}),
            "position_size_eth": (0.001, {params.get('position_size_eth', 0.05) * 2:.3f}),
            "max_slippage_pct": (0.1, {params.get('max_slippage_pct', 2.0) * 1.5:.1f}),
            "min_signal_strength": ({params.get('min_signal_strength', 0.7) * 0.9:.2f}, 0.99)
        }}
    
    def validate_parameters(self, **kwargs):
        """Validate trading parameters"""
        violations = []
        
        for param_name, value in kwargs.items():
            if param_name in self.parameter_bounds:
                min_val, max_val = self.parameter_bounds[param_name]
                if value < min_val or value > max_val:
                    violations.append(
                        f"{{param_name}}={{value}} outside bounds [{{min_val:.3f}}, {{max_val:.3f}}]"
                    )
        
        if violations:
            logger.warning(f"Parameter violations: {{'; '.join(violations)}}")
            return False, violations
        
        return True, []
    
    def check_performance(self, actual_metrics):
        """Check if actual performance matches expected"""
        warnings = []
        
        for metric_name, expected in self.expected_metrics.items():
            actual = actual_metrics.get(metric_name)
            if actual is not None:
                # Allow 20% deviation
                if abs(actual - expected) / expected > 0.2:
                    warnings.append(
                        f"{{metric_name}}: expected={{expected:.2f}}, actual={{actual:.2f}}"
                    )
        
        if warnings:
            logger.warning(f"Performance deviations: {{'; '.join(warnings)}}")
            return False, warnings
        
        return True, []

# Default optimized parameters
OPTIMIZED_PARAMS = {{
    # Risk Management
    "STOP_LOSS": {params.get('stop_loss', 0.18)},
    "TAKE_PROFIT": {params.get('take_profit', 0.40)},
    "TRAILING_STOP": {params.get('trailing_stop', 0.09)},
    "POSITION_SIZE_ETH": {params.get('position_size_eth', 0.01)},
    "MAX_PORTFOLIO_RISK": {params.get('max_portfolio_risk', 0.016)},
    
    # Execution
    "MAX_SLIPPAGE_PCT": {params.get('max_slippage_pct', 2.8)},
    "GAS_PRICE_MULTIPLIER": {params.get('gas_price_multiplier', 1.22)},
    "USE_MEV_PROTECTION": {params.get('use_mev_protection', True)},
    
    # Signal Filtering
    "MIN_SIGNAL_STRENGTH": {params.get('min_signal_strength', 0.74)},
    "MIN_VOLUME_ETH": {params.get('min_volume_eth', 123.0)},
    "MAX_SIGNAL_AGE_MIN": {params.get('max_signal_age_min', 5)},
    
    # Strategy
    "MOMENTUM_LOOKBACK": {params.get('momentum_lookback', 15)},
    "VOLATILITY_CAP_PCT": {params.get('volatility_cap_pct', 0.304)}
}}

def get_optimized_param(param_name, default=None):
    """Get optimized parameter with fallback"""
    return OPTIMIZED_PARAMS.get(param_name, default)

# Export for easy import
__all__ = ['ParameterValidator', 'OPTIMIZED_PARAMS', 'get_optimized_param']
'''
    
    with open("optimized_param_validator.py", "w") as f:
        f.write(validator_code)
    
    print("✅ Created optimized_param_validator.py")

def update_main_config(params):
    """Update main configuration with optimized parameters"""
    # Read current main.py if exists
    main_py_path = "optimized/main.py"
    if not os.path.exists(main_py_path):
        print(f"⚠️  {main_py_path} not found, skipping update")
        return
    
    with open(main_py_path, "r") as f:
        content = f.read()
    
    # Add optimized parameters section if not present
    if "OPTIMIZED_PARAMS" not in content:
        # Find a good place to insert (after imports)
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("class ") or line.startswith("def "):
                insert_idx = i
                break
        
        # Insert optimized params
        params_section = f'''
# Optimized QWNT Parameters (from fine-tuning)
OPTIMIZED_PARAMS = {{
    # Risk Management
    "stop_loss": {params.get('stop_loss', 0.18)},  # {params.get('stop_loss', 0.18):.1%}
    "take_profit": {params.get('take_profit', 0.40)},  # {params.get('take_profit', 0.40):.1%}
    "trailing_stop": {params.get('trailing_stop', 0.09)},  # {params.get('trailing_stop', 0.09):.1%}
    "position_size_eth": {params.get('position_size_eth', 0.01)},
    "max_portfolio_risk": {params.get('max_portfolio_risk', 0.016)},  # {params.get('max_portfolio_risk', 0.016):.1%}
    
    # Execution
    "max_slippage_pct": {params.get('max_slippage_pct', 2.8)},  # {params.get('max_slippage_pct', 2.8):.1f}%
    "gas_price_multiplier": {params.get('gas_price_multiplier', 1.22)},
    "use_mev_protection": {params.get('use_mev_protection', True)},
    
    # Signal Filtering
    "min_signal_strength": {params.get('min_signal_strength', 0.74)},  # {params.get('min_signal_strength', 0.74):.0%}
    "min_volume_eth": {params.get('min_volume_eth', 123.0)},
    "max_signal_age_min": {params.get('max_signal_age_min', 5)},
    
    # Strategy
    "momentum_lookback": {params.get('momentum_lookback', 15)},
    "volatility_cap_pct": {params.get('volatility_cap_pct', 0.304)},  # {params.get('volatility_cap_pct', 0.304):.1%}
}}

# Expected performance metrics
EXPECTED_METRICS = {{
    "sharpe_ratio": 1.93,
    "win_rate": 0.981,
    "avg_profit_per_trade": 0.217,
    "max_drawdown": 0.015,
    "profit_factor": 111.11
}}
'''
        
        lines.insert(insert_idx, params_section)
        content = '\n'.join(lines)
        
        with open(main_py_path, "w") as f:
            f.write(content)
        
        print(f"✅ Updated {main_py_path} with optimized parameters")

def create_deployment_checklist():
    """Create deployment checklist for optimized parameters"""
    checklist = f"""# QWNT TRADING BOT DEPLOYMENT CHECKLIST
# Generated {datetime.now().isoformat()}

## ✅ PRE-DEPLOYMENT CHECKS

### 1. Parameter Validation
- [ ] Run parameter validator test
- [ ] Verify all parameters within optimization bounds
- [ ] Check for any parameter conflicts

### 2. System Integration
- [ ] Integrate optimized_param_validator.py
- [ ] Update main.py with OPTIMIZED_PARAMS
- [ ] Test parameter loading in all agents

### 3. Paper Trading Test
- [ ] Run 24-hour paper trading test
- [ ] Monitor performance vs expected metrics
- [ ] Check for any execution errors
- [ ] Verify stop-loss/take-profit triggers

## 🚀 DEPLOYMENT PHASES

### Phase 1: Conservative Start (Week 1)
- [ ] Use 10% of optimized position size (0.001 ETH)
- [ ] Enable all safety checks
- [ ] Monitor every trade manually
- [ ] Log all parameter validations

### Phase 2: Gradual Scaling (Week 2)
- [ ] Increase to 50% position size if Week 1 successful
- [ ] Enable automated trading during low volatility
- [ ] Continue manual monitoring during high volatility

### Phase 3: Full Deployment (Week 3+)
- [ ] Use 100% optimized position size (0.01 ETH)
- [ ] Enable full automation
- [ ] Implement automatic performance monitoring
- [ ] Set up alerts for parameter violations

## 📊 PERFORMANCE MONITORING

### Daily Checks
- [ ] Sharpe ratio vs expected (1.93)
- [ ] Win rate vs expected (98.1%)
- [ ] Max drawdown vs limit (1.5%)
- [ ] Profit factor vs expected (111.11)

### Weekly Tasks
- [ ] Export performance data
- [ ] Run parameter re-optimization if performance degrades >20%
- [ ] Update parameter bounds based on market changes
- [ ] Review and adjust risk limits

## ⚠️ RISK CONTROLS

### Automatic Triggers
- [ ] Stop trading if daily drawdown > 5%
- [ ] Stop trading if 3 consecutive losing trades
- [ ] Reduce position size if volatility > 30%
- [ ] Pause trading during major news events

### Manual Overrides
- [ ] Emergency stop button accessible
- [ ] Manual position closing capability
- [ ] Parameter adjustment without restart

## 🔧 MAINTENANCE

### Regular Tasks
- [ ] Weekly: Re-optimize parameters with fresh data
- [ ] Monthly: Full system health check
- [ ] Quarterly: Strategy review and update

## 📞 SUPPORT

### Contact Points
- System Alerts: Check logs in optimized.log
- Performance Issues: Review realistic_qwnt_results.json
- Parameter Questions: Check production_qwnt_config.py

## 🎯 SUCCESS CRITERIA

### Short-term (1 month)
- [ ] Achieve Sharpe ratio > 1.5
- [ ] Maintain win rate > 90%
- [ ] Keep max drawdown < 3%

### Long-term (3 months)
- [ ] Consistent profitability
- [ ] Automated re-optimization working
- [ ] System requires minimal manual intervention

---
**Remember**: Start small, monitor closely, scale gradually.
Optimized parameters are based on historical simulation - real markets may differ.
"""
    
    with open("DEPLOYMENT_CHECKLIST.md", "w") as f:
        f.write(checklist)
    
    print("✅ Created DEPLOYMENT_CHECKLIST.md")

def main():
    print("🔧 INTEGRATING OPTIMIZED QWNT PARAMETERS")
    print("=" * 60)
    
    # Load optimized parameters
    params, metrics = load_optimized_params()
    if not params:
        return
    
    print(f"📊 Loaded optimized parameters:")
    print(f"  Stop Loss: {params.get('stop_loss', 0):.1%}")
    print(f"  Take Profit: {params.get('take_profit', 0):.1%}")
    print(f"  Position Size: {params.get('position_size_eth', 0):.3f} ETH")
    print(f"  Expected Sharpe: {metrics.get('sharpe', 0):.2f}")
    print(f"  Expected Win Rate: {metrics.get('win_rate', 0):.1%}")
    
    # Create parameter validator
    create_parameter_validator(params, metrics)
    
    # Update main config
    update_main_config(params)
    
    # Create deployment checklist
    create_deployment_checklist()
    
    print(f"\n✅ Integration complete!")
    print(f"\n📁 Files created/updated:")
    print(f"  1. optimized_param_validator.py - Parameter validation")
    print(f"  2. optimized/main.py - Updated with optimized params")
    print(f"  3. DEPLOYMENT_CHECKLIST.md - Step-by-step deployment guide")
    
    print(f"\n🎯 Next steps:")
    print(f"  1. Review DEPLOYMENT_CHECKLIST.md")
    print(f"  2. Test with paper trading")
    print(f"  3. Deploy gradually following the checklist")

if __name__ == "__main__":
    main()