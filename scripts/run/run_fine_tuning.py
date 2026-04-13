#!/usr/bin/env python3
"""
Run fine-tuning optimization for QWNT trading bots
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fine_tuning_optimizer import FineTuningOptimizer, StrategyParameters

async def main():
    print("🔧 QWNT Trading Bot Fine-Tuning")
    print("=" * 60)
    
    # Initialize optimizer
    optimizer = FineTuningOptimizer()
    
    # Show current parameters
    print("\n📋 CURRENT PARAMETERS:")
    current_params = optimizer.params
    for key, value in current_params.to_dict().items():
        if isinstance(value, float) and 'pct' in key:
            print(f"  {key}: {value:.1%}")
        elif isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")
    
    # Evaluate current performance
    print("\n📊 CURRENT PERFORMANCE:")
    current_metrics = optimizer.evaluate_strategy(current_params)
    optimizer._print_metrics(current_metrics)
    
    # Run optimization
    print("\n🚀 STARTING OPTIMIZATION...")
    print("This will run Bayesian optimization to find better parameters.")
    print("Press Ctrl+C to stop early.\n")
    
    try:
        # Run optimization
        optimized_params = optimizer.optimize_parameters(iterations=30)
        
        # Save results
        optimizer.save_optimization_results("fine_tuning_results.json")
        
        # Generate config file
        optimizer.generate_config_file(optimized_params, "optimized_trading_config.py")
        
        # Show improvement
        print("\n📈 IMPROVEMENT SUMMARY:")
        print("=" * 40)
        
        optimized_metrics = optimizer.evaluate_strategy(optimized_params)
        
        print(f"Sharpe Ratio:  {current_metrics['sharpe_ratio']:.2f} → {optimized_metrics['sharpe_ratio']:.2f}")
        print(f"Win Rate:      {current_metrics['win_rate']:.1%} → {optimized_metrics['win_rate']:.1%}")
        print(f"Profit Factor: {current_metrics['profit_factor']:.2f} → {optimized_metrics['profit_factor']:.2f}")
        print(f"Max Drawdown:  {current_metrics['max_drawdown']:.1%} → {optimized_metrics['max_drawdown']:.1%}")
        
        improvement = (optimized_metrics['sharpe_ratio'] - current_metrics['sharpe_ratio']) / abs(current_metrics['sharpe_ratio']) * 100
        print(f"\n✅ Overall Improvement: {improvement:+.1f}%")
        
        # Key parameter changes
        print("\n🔑 KEY PARAMETER CHANGES:")
        print("-" * 40)
        
        key_params = ['stop_loss_pct', 'take_profit_pct', 'min_signal_strength', 'max_slippage_pct']
        for param in key_params:
            old = getattr(current_params, param)
            new = getattr(optimized_params, param)
            if 'pct' in param:
                print(f"  {param}: {old:.1%} → {new:.1%}")
            else:
                print(f"  {param}: {old:.3f} → {new:.3f}")
        
        print("\n🎯 Next steps:")
        print("1. Review optimized_trading_config.py")
        print("2. Test with paper trading")
        print("3. Deploy to live trading with small position sizes")
        print("4. Monitor performance and re-optimize weekly")
        
    except KeyboardInterrupt:
        print("\n🛑 Optimization stopped by user")
        if optimizer.optimization_history:
            # Use best found so far
            best_entry = max(optimizer.optimization_history, key=lambda x: x['score'])
            best_params = StrategyParameters.from_dict(best_entry['params'])
            optimizer.generate_config_file(best_params, "partially_optimized_config.py")
            print("✅ Partially optimized config saved")

if __name__ == "__main__":
    asyncio.run(main())