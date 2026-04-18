#!/usr/bin/env python3
"""
Fine-Tuning Optimizer for QWNT Trading Bots
Optimizes strategy parameters, risk management, and execution settings.
"""

import json
import time
import statistics
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import numpy as np
from scipy import optimize
import asyncio

@dataclass
class StrategyParameters:
    """Strategy parameters for fine-tuning"""
    # Risk Management
    stop_loss_pct: float = 0.30  # -30% stop loss
    take_profit_pct: float = 1.00  # +100% take profit
    trailing_stop_pct: float = 0.10  # 10% trailing stop
    max_position_size_eth: float = 0.1  # Max 0.1 ETH per position
    max_portfolio_risk: float = 0.05  # Max 5% portfolio risk per trade
    
    # Execution Parameters
    max_slippage_pct: float = 2.0  # Max 2% slippage
    gas_price_multiplier: float = 1.2  # 20% above base fee
    priority_fee_gwei: float = 2.0  # Priority fee in Gwei
    use_flashbots: bool = True  # Use Flashbots for MEV protection
    bundle_txs: bool = True  # Bundle multiple transactions
    
    # Signal Filtering
    min_signal_strength: float = 0.7  # Minimum signal confidence
    min_volume_eth: float = 100.0  # Minimum 100 ETH volume
    min_liquidity_eth: float = 500.0  # Minimum 500 ETH liquidity
    max_age_minutes: int = 5  # Max 5 minutes old signal
    
    # Strategy-Specific
    momentum_window: int = 10  # 10-period momentum
    volatility_threshold: float = 0.15  # 15% volatility threshold
    social_sentiment_weight: float = 0.3  # 30% weight to social sentiment
    whale_activity_weight: float = 0.4  # 40% weight to whale activity
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StrategyParameters':
        return cls(**data)

class FineTuningOptimizer:
    """
    Bayesian optimization for trading bot parameters
    Uses historical simulation to find optimal parameters
    """
    
    def __init__(self, historical_data_path: Optional[str] = None):
        self.params = StrategyParameters()
        self.historical_data = self._load_historical_data(historical_data_path)
        self.optimization_history = []
        
    def _load_historical_data(self, path: Optional[str]) -> List[Dict]:
        """Load historical trading data for backtesting"""
        # In production, load from database or API
        # For now, return mock data
        return [
            {
                'timestamp': datetime.now().isoformat(),
                'token': 'ETH',
                'entry_price': 3000.0,
                'exit_price': 3500.0,
                'profit_pct': 16.67,
                'signal_strength': 0.85,
                'volume_eth': 1500.0,
                'slippage_pct': 0.5
            },
            {
                'timestamp': datetime.now().isoformat(),
                'token': 'UNI',
                'entry_price': 10.0,
                'exit_price': 8.5,
                'profit_pct': -15.0,
                'signal_strength': 0.65,
                'volume_eth': 300.0,
                'slippage_pct': 1.2
            }
        ]
    
    def evaluate_strategy(self, params: StrategyParameters) -> Dict:
        """
        Evaluate strategy performance with given parameters
        Returns metrics: Sharpe ratio, win rate, max drawdown, etc.
        """
        # Simulate trading with these parameters
        trades = self._simulate_trades(params)
        
        if not trades:
            return {
                'sharpe_ratio': -10.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 100.0,
                'total_return_pct': -100.0
            }
        
        returns = [t['profit_pct'] for t in trades]
        winning_trades = [r for r in returns if r > 0]
        
        # Calculate metrics
        avg_return = statistics.mean(returns) if returns else 0
        std_return = statistics.stdev(returns) if len(returns) > 1 else 1.0
        sharpe_ratio = avg_return / std_return if std_return > 0 else 0
        
        win_rate = len(winning_trades) / len(returns) if returns else 0
        
        # Calculate profit factor (gross profit / gross loss)
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = abs(sum(r for r in returns if r < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 10.0
        
        # Calculate max drawdown
        cumulative_returns = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        max_drawdown = abs(min(drawdowns)) if len(drawdowns) > 0 else 0
        
        total_return = sum(returns)
        
        return {
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'total_return_pct': total_return,
            'num_trades': len(trades),
            'avg_return': avg_return
        }
    
    def _simulate_trades(self, params: StrategyParameters) -> List[Dict]:
        """Simulate trades with given parameters"""
        trades = []
        
        # Apply parameter filters to historical data
        for trade in self.historical_data:
            # Check signal strength filter
            if trade['signal_strength'] < params.min_signal_strength:
                continue
                
            # Check volume filter
            if trade['volume_eth'] < params.min_volume_eth:
                continue
                
            # Apply stop loss and take profit
            profit_pct = trade['profit_pct']
            
            # Simulate stop loss
            if profit_pct <= -params.stop_loss_pct * 100:
                profit_pct = -params.stop_loss_pct * 100
                
            # Simulate take profit
            if profit_pct >= params.take_profit_pct * 100:
                profit_pct = params.take_profit_pct * 100
            
            # Apply slippage
            effective_profit = profit_pct - trade['slippage_pct']
            
            trades.append({
                **trade,
                'adjusted_profit_pct': effective_profit,
                'applied_stop_loss': profit_pct <= -params.stop_loss_pct * 100,
                'applied_take_profit': profit_pct >= params.take_profit_pct * 100
            })
        
        return trades
    
    def optimize_parameters(self, iterations: int = 50) -> StrategyParameters:
        """
        Bayesian optimization to find best parameters
        Maximizes Sharpe ratio while controlling risk
        """
        print(f"\n🔍 Starting Bayesian Optimization ({iterations} iterations)")
        print("=" * 60)
        
        best_score = -float('inf')
        best_params = self.params
        
        for i in range(iterations):
            # Generate candidate parameters
            candidate = self._generate_candidate_params()
            
            # Evaluate
            metrics = self.evaluate_strategy(candidate)
            score = self._calculate_score(metrics)
            
            # Track history
            self.optimization_history.append({
                'iteration': i,
                'params': candidate.to_dict(),
                'metrics': metrics,
                'score': score
            })
            
            # Update best
            if score > best_score:
                best_score = score
                best_params = candidate
                
                print(f"Iteration {i+1}: New best score = {score:.4f}")
                print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}, Win Rate: {metrics['win_rate']:.1%}")
                print(f"  Stop Loss: {candidate.stop_loss_pct:.1%}, Take Profit: {candidate.take_profit_pct:.1%}")
            
            # Early stopping if we've converged
            if i > 10 and abs(score - best_score) < 0.01:
                print(f"✅ Convergence reached at iteration {i+1}")
                break
        
        print(f"\n🏆 Optimization Complete!")
        print(f"Best Score: {best_score:.4f}")
        final_metrics = self.evaluate_strategy(best_params)
        self._print_metrics(final_metrics)
        
        return best_params
    
    def _generate_candidate_params(self) -> StrategyParameters:
        """Generate candidate parameters using Bayesian optimization"""
        # Start from current best or random
        if np.random.random() < 0.3 and self.optimization_history:
            # Exploit: perturb best parameters
            best = self.optimization_history[-1]['params']
            base = StrategyParameters.from_dict(best)
        else:
            # Explore: random parameters
            base = StrategyParameters()
        
        # Add Gaussian noise
        return StrategyParameters(
            # Risk Management (bounded)
            stop_loss_pct=max(0.05, min(0.5, base.stop_loss_pct + np.random.normal(0, 0.05))),
            take_profit_pct=max(0.5, min(3.0, base.take_profit_pct + np.random.normal(0, 0.1))),
            trailing_stop_pct=max(0.05, min(0.3, base.trailing_stop_pct + np.random.normal(0, 0.02))),
            max_position_size_eth=max(0.01, min(1.0, base.max_position_size_eth + np.random.normal(0, 0.05))),
            max_portfolio_risk=max(0.01, min(0.2, base.max_portfolio_risk + np.random.normal(0, 0.01))),
            
            # Execution Parameters
            max_slippage_pct=max(0.1, min(5.0, base.max_slippage_pct + np.random.normal(0, 0.5))),
            gas_price_multiplier=max(1.0, min(2.0, base.gas_price_multiplier + np.random.normal(0, 0.1))),
            priority_fee_gwei=max(0.1, min(10.0, base.priority_fee_gwei + np.random.normal(0, 1.0))),
            use_flashbots=base.use_flashbots if np.random.random() < 0.8 else not base.use_flashbots,
            bundle_txs=base.bundle_txs if np.random.random() < 0.8 else not base.bundle_txs,
            
            # Signal Filtering
            min_signal_strength=max(0.3, min(0.95, base.min_signal_strength + np.random.normal(0, 0.05))),
            min_volume_eth=max(10.0, min(1000.0, base.min_volume_eth + np.random.normal(0, 50))),
            min_liquidity_eth=max(100.0, min(5000.0, base.min_liquidity_eth + np.random.normal(0, 200))),
            max_age_minutes=max(1, min(30, base.max_age_minutes + int(np.random.normal(0, 2)))),
            
            # Strategy-Specific
            momentum_window=max(5, min(30, base.momentum_window + int(np.random.normal(0, 3)))),
            volatility_threshold=max(0.05, min(0.5, base.volatility_threshold + np.random.normal(0, 0.05))),
            social_sentiment_weight=max(0.0, min(1.0, base.social_sentiment_weight + np.random.normal(0, 0.1))),
            whale_activity_weight=max(0.0, min(1.0, base.whale_activity_weight + np.random.normal(0, 0.1)))
        )
    
    def _calculate_score(self, metrics: Dict) -> float:
        """
        Calculate optimization score
        Higher is better
        """
        sharpe = metrics['sharpe_ratio']
        win_rate = metrics['win_rate']
        profit_factor = metrics['profit_factor']
        max_dd = metrics['max_drawdown']
        num_trades = metrics['num_trades']
        
        # Base score: Sharpe ratio (most important)
        score = sharpe * 2.0
        
        # Bonus for high win rate
        score += win_rate * 0.5
        
        # Bonus for high profit factor
        score += min(profit_factor, 5.0) * 0.3
        
        # Penalty for high drawdown
        score -= max_dd * 3.0
        
        # Penalty for too few trades
        if num_trades < 5:
            score -= (5 - num_trades) * 0.2
        
        return score
    
    def _print_metrics(self, metrics: Dict):
        """Print performance metrics"""
        print("\n📊 OPTIMIZED METRICS:")
        print("=" * 40)
        print(f"Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}")
        print(f"Win Rate:          {metrics['win_rate']:.1%}")
        print(f"Profit Factor:     {metrics['profit_factor']:.2f}")
        print(f"Max Drawdown:      {metrics['max_drawdown']:.1%}")
        print(f"Total Return:      {metrics['total_return_pct']:.1f}%")
        print(f"Number of Trades:  {metrics['num_trades']}")
        print(f"Average Return:    {metrics['avg_return']:.1f}%")
        print("=" * 40)
    
    def save_optimization_results(self, filename: str = "optimization_results.json"):
        """Save optimization history to file"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'best_params': best_params.to_dict() if 'best_params' in locals() else self.params.to_dict(),
            'optimization_history': self.optimization_history,
            'final_metrics': self.evaluate_strategy(best_params) if 'best_params' in locals() else {}
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Results saved to {filename}")
    
    def generate_config_file(self, params: StrategyParameters, filename: str = "optimized_config.py"):
        """Generate Python config file with optimized parameters"""
        config = f'''"""
Optimized Trading Configuration
Generated by FineTuningOptimizer on {datetime.now().isoformat()}
"""

# Risk Management
STOP_LOSS_PCT = {params.stop_loss_pct}  # {params.stop_loss_pct:.1%}
TAKE_PROFIT_PCT = {params.take_profit_pct}  # {params.take_profit_pct:.1%}
TRAILING_STOP_PCT = {params.trailing_stop_pct}  # {params.trailing_stop_pct:.1%}
MAX_POSITION_SIZE_ETH = {params.max_position_size_eth}
MAX_PORTFOLIO_RISK = {params.max_portfolio_risk}  # {params.max_portfolio_risk:.1%}

# Execution Parameters
MAX_SLIPPAGE_PCT = {params.max_slippage_pct}  # {params.max_slippage_pct:.1%}
GAS_PRICE_MULTIPLIER = {params.gas_price_multiplier}
PRIORITY_FEE_GWEI = {params.priority_fee_gwei}
USE_FLASHBOTS = {params.use_flashbots}
BUNDLE_TXS = {params.bundle_txs}

# Signal Filtering
MIN_SIGNAL_STRENGTH = {params.min_signal_strength}
MIN_VOLUME_ETH = {params.min_volume_eth}
MIN_LIQUIDITY_ETH = {params.min_liquidity_eth}
MAX_AGE_MINUTES = {params.max_age_minutes}

# Strategy-Specific
MOMENTUM_WINDOW = {params.momentum_window}
VOLATILITY_THRESHOLD = {params.volatility_threshold}  # {params.volatility_threshold:.1%}
SOCIAL_SENTIMENT_WEIGHT = {params.social_sentiment_weight}
WHALE_ACTIVITY_WEIGHT = {params.whale_activity_weight}

# Derived parameters
POSITION_SIZE_ETH = min(
    MAX_POSITION_SIZE_ETH,
    MAX_PORTFOLIO_RISK * PORTFOLIO_VALUE_ETH  # Assuming PORTFOLIO_VALUE_ETH is defined elsewhere
)
'''
        
        with open(filename, 'w') as f:
            f.write(config)
        
        print(f"✅ Config file generated: {filename}")

# Main execution
if __name__ == "__main__":
    # Quick test
    optimizer = FineTuningOptimizer()
    params = optimizer.params
    print(f"Initial stop loss: {params.stop_loss_pct:.1%}")
    print(f"Initial take profit: {params.take_profit_pct:.1%}")
    
    # Quick evaluation
    metrics = optimizer.evaluate_strategy(params)
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")