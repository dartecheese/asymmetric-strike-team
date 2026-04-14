"""
Asymmetric Strike Team — Professional Edition
=============================================
Includes:
1. Configuration management
2. Risk management layer
3. Performance tracking
4. Enhanced execution (DEX + CEX)
5. Sentiment analysis
6. Professional error handling
"""
import os
import sys
import time
import logging
import argparse
from datetime import datetime

from config_manager import ConfigManager, ExecutionMode
from agents.risk_manager import RiskManager
from agents.performance_tracker import PerformanceTracker
from agents.enhanced_whisperer import EnhancedWhisperer
from agents.actuary import Actuary
from agents.unified_slinger import UnifiedSlinger
from agents.reaper import Reaper
from core.models import RiskLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MainPro")


def build_banner(config_manager: ConfigManager):
    """Build professional banner."""
    config = config_manager.config
    mode = "🚨 LIVE EXECUTION" if config_manager.is_real_mode() else "📄 PAPER TRADING"
    
    print("\n" + "=" * 70)
    print("🚀  ASYMMETRIC STRIKE TEAM - PROFESSIONAL EDITION")
    print(f"   Mode     : {mode}")
    print(f"   Strategy : {config.default_strategy.upper()}")
    print(f"   Features : Risk Mgmt | Performance Tracking | Unified Execution")
    print("=" * 70 + "\n")


def initialize_system(config_manager: ConfigManager):
    """Initialize all system components."""
    config = config_manager.config
    strategy_config = config_manager.get_strategy_config()
    
    print("🔄 Initializing system components...")
    
    # 1. Risk Manager
    risk_manager = RiskManager(
        max_portfolio_size_usd=config.risk.max_portfolio_size_usd,
        max_position_size_pct=config.risk.max_position_size_pct,
        max_daily_loss_pct=config.risk.max_daily_loss_pct,
        max_correlation_threshold=config.risk.max_correlation_threshold,
        circuit_breaker_volatility=config.risk.circuit_breaker_volatility
    )
    
    # 2. Performance Tracker
    performance_tracker = PerformanceTracker(
        db_path=config.performance_db_path
    ) if config.enable_performance_tracking else None
    
    # 3. Enhanced Whisperer
    whisperer = EnhancedWhisperer(
        min_velocity_score=strategy_config.whisperer_min_score,
        use_sentiment=config.enable_sentiment and strategy_config.use_sentiment
    )
    
    # 4. Actuary
    actuary = Actuary(
        max_allowed_tax=strategy_config.actuary_max_tax_pct / 100,
        strict_mode=strategy_config.actuary_strict_mode
    )
    
    # 5. Unified Slinger
    slinger = UnifiedSlinger()
    slinger.set_strategy_params(
        slippage=strategy_config.slinger_slippage_pct / 100,
        gas_multiplier=strategy_config.slinger_gas_multiplier,
        private_mempool=strategy_config.slinger_private_mempool
    )
    
    # 6. Reaper
    reaper = Reaper(
        take_profit_pct=strategy_config.reaper_take_profit_pct,
        stop_loss_pct=strategy_config.reaper_stop_loss_pct,
        trailing_stop_pct=strategy_config.reaper_trailing_stop_pct,
        poll_interval_sec=5.0,
        paper_mode=not config_manager.is_real_mode(),
    )
    
    print("✅ System initialization complete")
    
    return {
        'risk_manager': risk_manager,
        'performance_tracker': performance_tracker,
        'whisperer': whisperer,
        'actuary': actuary,
        'slinger': slinger,
        'reaper': reaper,
        'strategy_config': strategy_config
    }


def run_professional_cycle(components: dict, config_manager: ConfigManager) -> bool:
    """
    Run professional trading cycle with risk management and tracking.
    """
    risk_manager = components['risk_manager']
    performance_tracker = components['performance_tracker']
    whisperer = components['whisperer']
    actuary = components['actuary']
    slinger = components['slinger']
    reaper = components['reaper']
    strategy_config = components['strategy_config']
    
    cycle_start = time.time()
    print(f"\n⏰ Cycle started at {datetime.fromtimestamp(cycle_start).strftime('%H:%M:%S')}")
    print("-" * 70)
    
    # --- Step 1: Enhanced Whisperer scan ---
    print("🗣️  [Whisperer] Scanning with sentiment analysis...")
    signal = whisperer.scan_firehose()
    
    if not signal:
        print("   No signal found this cycle.")
        return False
    
    print(f"   Signal: {signal.token_address[:10]}... (score: {signal.narrative_score})")
    print(f"   {signal.reasoning[:100]}...")
    
    # --- Step 2: Actuary risk assessment ---
    print("-" * 70)
    print("🛡️  [Actuary] Assessing token risk...")
    assessment = actuary.assess_risk(signal)
    
    if assessment.risk_level == RiskLevel.REJECTED:
        print(f"   ❌ Token REJECTED by Actuary")
        return False
    
    if strategy_config.actuary_strict_mode and assessment.risk_level == RiskLevel.HIGH:
        print(f"   ❌ Strict mode: HIGH risk token rejected")
        return False
    
    print(f"   ✅ Approved: {assessment.risk_level.value}")
    print(f"   Max allocation: ${assessment.max_allocation_usd:.0f}")
    
    # --- Step 3: Risk Manager check ---
    print("-" * 70)
    print("🛡️  [Risk Manager] Portfolio-level risk check...")
    
    # Create proposed order for risk check
    from core.models import ExecutionOrder
    
    proposed_order = ExecutionOrder(
        token_address=signal.token_address,
        chain=signal.chain,
        action="BUY",
        amount_usd=assessment.max_allocation_usd,
        slippage_tolerance=strategy_config.slinger_slippage_pct / 100,
        gas_premium_gwei=0.0,  # Will be set by slinger
        entry_price_usd=None,  # Will be set by slinger
        is_cex=False  # Will be determined by unified slinger
    )
    
    # Check with risk manager
    allowed, reason = risk_manager.can_open_position(assessment, proposed_order)
    if not allowed:
        print(f"   ❌ Risk Manager rejected: {reason}")
        return False
    
    print(f"   ✅ Risk check passed")
    
    # --- Step 4: Unified Slinger execution ---
    print("-" * 70)
    print("🔫 [Unified Slinger] Executing trade...")
    
    # Determine venue
    token_lower = signal.token_address.lower()
    cex_tokens = {
        "0x6982508145454ce325ddbe47a25d4ec3d2311933": "PEPE/USDT",
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "ETH/USDT",
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "BTC/USDT",
    }
    symbol = cex_tokens.get(token_lower)
    chain_id = "cex" if symbol else signal.chain
    
    # Execute order
    order = slinger.execute_order(assessment, chain_id=chain_id, symbol=symbol)
    
    if not order:
        print("   ❌ Slinger failed to generate order")
        return False
    
    venue = "CEX" if order.is_cex else "DEX"
    print(f"   ✅ {venue} order generated: ${order.amount_usd:.0f}")
    
    # --- Step 5: Register with Risk Manager and Performance Tracker ---
    print("-" * 70)
    print("📊 [Tracking] Registering trade...")
    
    # Generate trade ID
    trade_id = f"{signal.token_address[:8]}_{int(time.time())}"
    
    # Register with risk manager
    risk_manager.register_position(order)
    
    # Register with performance tracker
    if performance_tracker:
        tags = []
        if order.is_cex:
            tags.append("cex_listed")
        if signal.narrative_score > 80:
            tags.append("high_velocity")
        if "sentiment" in signal.reasoning.lower():
            tags.append("sentiment_boost")
        
        performance_tracker.record_trade_entry(
            trade_id=trade_id,
            strategy=config_manager.config.default_strategy,
            order=order,
            tags=tags
        )
    
    # --- Step 6: Reaper monitoring ---
    print("-" * 70)
    print("💀 [Reaper] Taking position...")
    
    reaper.take_position(order)
    
    # Monitor for a short period (in production, this would run until exit)
    monitor_seconds = 30
    print(f"   Monitoring for {monitor_seconds}s...")
    
    try:
        for i in range(monitor_seconds):
            time.sleep(1)
            if i % 10 == 0:
                print(f"   ...{monitor_seconds - i}s remaining")
    except KeyboardInterrupt:
        print("\n   Monitoring interrupted")
    
    # Stop monitoring (in production, reaper would run continuously)
    reaper.stop_monitoring()
    
    # --- Step 7: Cycle completion ---
    print("-" * 70)
    print("📈 [Cycle Complete]")
    
    # Print risk status
    risk_manager.print_status()
    
    # Print performance if available
    if performance_tracker:
        performance_tracker.print_performance_report(config_manager.config.default_strategy)
    
    cycle_duration = time.time() - cycle_start
    print(f"⏱️  Cycle duration: {cycle_duration:.1f}s")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Asymmetric Strike Team - Professional Edition")
    parser.add_argument("--config", default="config.yaml",
                        help="Configuration file path (default: config.yaml)")
    parser.add_argument("--strategy", 
                        help="Override default strategy")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuous scanning loop")
    parser.add_argument("--interval", type=int,
                        help="Seconds between scans (overrides config)")
    parser.add_argument("--status", action="store_true",
                        help="Show system status and exit")
    parser.add_argument("--export", action="store_true",
                        help="Export performance data to CSV and exit")
    args = parser.parse_args()
    
    # Initialize configuration
    config_manager = ConfigManager(args.config)
    
    # Override strategy if specified
    if args.strategy:
        if args.strategy not in config_manager.config.strategies:
            print(f"❌ Strategy '{args.strategy}' not found. Available: {list(config_manager.config.strategies.keys())}")
            sys.exit(1)
        config_manager.config.default_strategy = args.strategy
    
    # Override interval if specified
    if args.interval:
        config_manager.config.loop_interval_seconds = args.interval
    
    # Show banner
    build_banner(config_manager)
    
    # Show configuration summary
    config_manager.print_summary()
    
    # Export performance data if requested
    if args.export:
        if config_manager.config.enable_performance_tracking:
            tracker = PerformanceTracker(config_manager.config.performance_db_path)
            tracker.export_to_csv("performance_export.csv")
            print("✅ Performance data exported to performance_export.csv")
        else:
            print("❌ Performance tracking is disabled in configuration")
        sys.exit(0)
    
    # Show status if requested
    if args.status:
        # Initialize components to show status
        components = initialize_system(config_manager)
        components['risk_manager'].print_status()
        if components['performance_tracker']:
            components['performance_tracker'].print_performance_report()
        sys.exit(0)
    
    # Initialize system components
    components = initialize_system(config_manager)
    
    # Run in loop mode or single cycle
    if args.loop:
        print(f"🔄 Continuous mode — scanning every {config_manager.config.loop_interval_seconds}s")
        print("Press Ctrl+C to stop\n")
        
        cycle_count = 0
        successful_cycles = 0
        
        try:
            while True:
                cycle_count += 1
                print(f"\n{'='*70}")
                print(f"  CYCLE #{cycle_count}")
                print(f"{'='*70}")
                
                success = run_professional_cycle(components, config_manager)
                if success:
                    successful_cycles += 1
                
                success_rate = (successful_cycles / cycle_count) * 100 if cycle_count > 0 else 0
                print(f"\n📊 Cycle {cycle_count}: {successful_cycles} successful ({success_rate:.1f}% success rate)")
                
                # Wait for next cycle
                wait_time = config_manager.config.loop_interval_seconds
                print(f"\n⏳ Next scan in {wait_time}s...")
                time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Shutdown requested by user")
            
            # Final status report
            print("\n" + "=" * 70)
            print("📊 FINAL STATISTICS")
            print("=" * 70)
            print(f"Total Cycles: {cycle_count}")
            print(f"Successful Cycles: {successful_cycles}")
            print(f"Success Rate: {success_rate:.1f}%")
            
            components['risk_manager'].print_status()
            if components['performance_tracker']:
                components['performance_tracker'].print_performance_report()
            
            print("\n✅ System shutdown complete")
            sys.exit(0)
            
    else:
        # Single cycle mode
        success = run_professional_cycle(components, config_manager)
        
        if success:
            print("\n✅ Cycle completed successfully")
        else:
            print("\n⚠️  Cycle completed without trade")
        
        # Show final status
        components['risk_manager'].print_status()
        if components['performance_tracker']:
            components['performance_tracker'].print_performance_report()


if __name__ == "__main__":
    main()