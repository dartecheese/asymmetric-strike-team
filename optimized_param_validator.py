"""
Parameter Validator for Optimized QWNT Trading
Generated 2026-04-12T00:18:11.743712
Validates trading parameters against optimization constraints
"""

import logging

logger = logging.getLogger("ParamValidator")

class ParameterValidator:
    """Validate trading parameters against optimization constraints"""
    
    def __init__(self):
        # Optimization targets
        self.expected_metrics = {
            "sharpe_ratio": 1.93,
            "win_rate": 0.981,
            "max_drawdown": 1.5,
            "profit_factor": 111.1
        }
        
        # Parameter bounds (from optimization)
        self.parameter_bounds = {
            "stop_loss": (0.146, 0.218),
            "take_profit": (0.321, 0.482),
            "position_size_eth": (0.001, 0.020),
            "max_slippage_pct": (0.1, 4.3),
            "min_signal_strength": (0.67, 0.99)
        }
    
    def validate_parameters(self, **kwargs):
        """Validate trading parameters"""
        violations = []
        
        for param_name, value in kwargs.items():
            if param_name in self.parameter_bounds:
                min_val, max_val = self.parameter_bounds[param_name]
                if value < min_val or value > max_val:
                    violations.append(
                        f"{param_name}={value} outside bounds [{min_val:.3f}, {max_val:.3f}]"
                    )
        
        if violations:
            logger.warning(f"Parameter violations: {'; '.join(violations)}")
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
                        f"{metric_name}: expected={expected:.2f}, actual={actual:.2f}"
                    )
        
        if warnings:
            logger.warning(f"Performance deviations: {'; '.join(warnings)}")
            return False, warnings
        
        return True, []

# Default optimized parameters
OPTIMIZED_PARAMS = {
    # Risk Management
    "STOP_LOSS": 0.1819530823544352,
    "TAKE_PROFIT": 0.40147800114156,
    "TRAILING_STOP": 0.09438792431998763,
    "POSITION_SIZE_ETH": 0.01,
    "MAX_PORTFOLIO_RISK": 0.01591948499793019,
    
    # Execution
    "MAX_SLIPPAGE_PCT": 2.8443684388088672,
    "GAS_PRICE_MULTIPLIER": 1.2191965224873682,
    "USE_MEV_PROTECTION": True,
    
    # Signal Filtering
    "MIN_SIGNAL_STRENGTH": 0.7438278427378023,
    "MIN_VOLUME_ETH": 123.041534472,
    "MAX_SIGNAL_AGE_MIN": 5,
    
    # Strategy
    "MOMENTUM_LOOKBACK": 15,
    "VOLATILITY_CAP_PCT": 0.303885889761787
}

def get_optimized_param(param_name, default=None):
    """Get optimized parameter with fallback"""
    return OPTIMIZED_PARAMS.get(param_name, default)

# Export for easy import
__all__ = ['ParameterValidator', 'OPTIMIZED_PARAMS', 'get_optimized_param']
