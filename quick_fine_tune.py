#!/usr/bin/env python3
"""
Quick fine-tuning for QWNT trading bots
"""

import json
import statistics
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np

@dataclass
class StrategyParams:
    """Simplified strategy parameters"""
    stop_loss: float = 0.30
    take_profit: float = 1.00
    min_signal: float = 0.7
    max_slippage: float = 2.0
    position_size: float = 0.1

def evaluate_params(params: StrategyParams) -> dict:
    """Evaluate parameters with mock data"""
    # Mock trade data
    trades = [
        {"profit": 0.25, "signal": 0.8, "slippage": 0.5},
        {"profit": -0.15, "signal": 0.6, "slippage": 1.0},
        {"profit": 0.50, "signal": 0.9, "slippage": 0.3},
        {"profit": -0.10, "signal": 0.7, "slippage": 0.8},
        {"profit": 0.35, "signal": 0.85, "slippage": 0.4},
    ]
    
    filtered_trades = []
    for trade in trades:
        # Apply signal filter
        if trade["signal"] < params.min_signal:
            continue
            
        # Apply stop loss and take profit
        profit = trade["profit"]
        if profit <= -params.stop_loss:
            profit = -params.stop_loss
        elif profit >= params.take_profit:
            profit = params.take_profit
            
        # Apply slippage
        profit -= trade["slippage"] / 100  # Convert % to decimal
        
        filtered_trades.append(profit)
    
    if not filtered_trades:
        return {"sharpe": -10, "win_rate": 0, "avg_profit": -100}
    
    # Calculate metrics
    avg = statistics.mean(filtered_trades)
    std = statistics.stdev(filtered_trades) if len(filtered_trades) > 1 else 1.0
    sharpe = avg / std if std > 0 else 0
    
    wins = sum(1 for p in filtered_trades if p > 0)
    win_rate = wins / len(filtered_trades)
    
    return {
        "sharpe": sharpe,
        "win_rate": win_rate,
        "avg_profit": avg * 100,  # as percentage
        "num_trades": len(filtered_trades)
    }

def optimize():
    """Simple optimization loop"""
    print("🔧 QWNT Trading Bot Fine-Tuning")
    print("=" * 50)
    
    best_score = -float('inf')
    best_params = None
    best_metrics = None
    
    history = []
    
    for i in range(100):
        # Generate random parameters
        params = StrategyParams(
            stop_loss=np.random.uniform(0.1, 0.5),
            take_profit=np.random.uniform(0.5, 2.0),
            min_signal=np.random.uniform(0.5, 0.95),
            max_slippage=np.random.uniform(0.5, 5.0),
            position_size=np.random.uniform(0.05, 0.5)
        )
        
        # Evaluate
        metrics = evaluate_params(params)
        
        # Score (higher is better)
        score = metrics["sharpe"] * 2 + metrics["win_rate"] - abs(metrics["avg_profit"]) * 0.01
        
        history.append({
            "iteration": i,
            "params": asdict(params),
            "metrics": metrics,
            "score": score
        })
        
        # Update best
        if score > best_score:
            best_score = score
            best_params = params
            best_metrics = metrics
            
            print(f"Iteration {i+1}: Score={score:.3f}, Sharpe={metrics['sharpe']:.2f}, Win={metrics['win_rate']:.1%}")
    
    print(f"\n🏆 OPTIMIZATION COMPLETE")
    print("=" * 50)
    print(f"Best Score: {best_score:.3f}")
    print(f"Sharpe Ratio: {best_metrics['sharpe']:.2f}")
    print(f"Win Rate: {best_metrics['win_rate']:.1%}")
    print(f"Avg Profit: {best_metrics['avg_profit']:.1f}%")
    print(f"Trades: {best_metrics['num_trades']}")
    
    print(f"\n🔑 OPTIMIZED PARAMETERS:")
    print(f"Stop Loss: {best_params.stop_loss:.1%}")
    print(f"Take Profit: {best_params.take_profit:.1%}")
    print(f"Min Signal: {best_params.min_signal:.0%}")
    print(f"Max Slippage: {best_params.max_slippage:.1f}%")
    print(f"Position Size: {best_params.position_size:.3f} ETH")
    
    # Save results
    results = {
        "timestamp": datetime.now().isoformat(),
        "best_params": asdict(best_params),
        "best_metrics": best_metrics,
        "optimization_history": history[:10]  # Save first 10 for reference
    }
    
    with open("fine_tune_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to fine_tune_results.json")
    
    # Generate config
    config = f"""# Optimized QWNT Trading Config
# Generated {datetime.now().isoformat()}

STOP_LOSS = {best_params.stop_loss}  # {best_params.stop_loss:.1%}
TAKE_PROFIT = {best_params.take_profit}  # {best_params.take_profit:.1%}
MIN_SIGNAL_STRENGTH = {best_params.min_signal}  # {best_params.min_signal:.0%}
MAX_SLIPPAGE_PCT = {best_params.max_slippage}  # {best_params.max_slippage:.1f}%
POSITION_SIZE_ETH = {best_params.position_size}

# Expected Performance
# Sharpe Ratio: {best_metrics['sharpe']:.2f}
# Win Rate: {best_metrics['win_rate']:.1%}
# Avg Profit: {best_metrics['avg_profit']:.1f}%
"""
    
    with open("optimized_qwnt_config.py", "w") as f:
        f.write(config)
    
    print(f"✅ Config saved to optimized_qwnt_config.py")

if __name__ == "__main__":
    optimize()