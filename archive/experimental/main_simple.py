"""
Asymmetric Strike Team — Simple Test Version
============================================
Simplified version for testing the enhanced system.
"""
import os
import sys
import time
import logging
import argparse
from datetime import datetime

from simple_config import SimpleConfig
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
logger = logging.getLogger("MainSimple")


def build_banner(config: SimpleConfig):
    """Build simple banner."""
    mode = "🚨 LIVE EXECUTION" if config.is_real_mode() else "📄 PAPER TRADING"
    
    print("\n" + "=" * 70)
    print("🚀  ASYMMETRIC STRIKE TEAM - SIMPLE TEST")
    print(f"   Mode     : {mode}")
    print(f"   Strategy : {config.default_strategy.upper()}")
    print("=" * 70 + "\n")


def run_simple_cycle(config: SimpleConfig) -> bool:
    """
    Run simple trading cycle.
    """
    # Strategy parameters based on strategy name
    if config.default_strategy == "degen":
        whisperer_min_score = 50
        actuary_max_tax = 0.10  # 10%
        slinger_slippage = 0.30  # 30%
        take_profit = 100.0
        stop_loss = 50.0
    elif config.default_strategy == "sniper":
        whisperer_min_score = 70
        actuary_max_tax = 0.03  # 3%
        slinger_slippage = 0.10  # 10%
        take_profit = 50.0
        stop_loss = 20.0
    else:  # conservative
        whisperer_min_score = 80
        actuary_max_tax = 0.01  # 1%
        slinger_slippage = 0.05  # 5%
        take_profit = 25.0
        stop_loss = 10.0
    
    print(f"📐 Strategy: {config.default_strategy}")
    print(f"   Min Score: {whisperer_min_score} | Max Tax: {actuary_max_tax*100:.0f}%")
    print(f"   Slippage: {slinger_slippage*100:.0f}% | TP: +{take_profit:.0f}% | SL: -{stop_loss:.0f}%")
    
    # Initialize agents
    whisperer = EnhancedWhisperer(min_velocity_score=whisperer_min_score, use_sentiment=config.enable_sentiment)
    actuary = Actuary(max_allowed_tax=actuary_max_tax)
    slinger = UnifiedSlinger()
    slinger.set_strategy_params(slippage=slinger_slippage, gas_multiplier=2.0, private_mempool=False)
    reaper = Reaper(
        take_profit_pct=take_profit,
        stop_loss_pct=stop_loss,
        trailing_stop_pct=25.0,
        poll_interval_sec=5.0,
        paper_mode=not config.is_real_mode(),
    )
    
    cycle_start = time.time()
    print(f"\n⏰ Cycle started at {datetime.fromtimestamp(cycle_start).strftime('%H:%M:%S')}")
    print("-" * 70)
    
    # --- Step 1: Enhanced Whisperer scan ---
    print("🗣️  [Whisperer] Scanning...")
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
    
    print(f"   ✅ Approved: {assessment.risk_level.value}")
    print(f"   Max allocation: ${assessment.max_allocation_usd:.0f}")
    
    # --- Step 3: Unified Slinger execution ---
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
    
    # --- Step 4: Reaper monitoring ---
    print("-" * 70)
    print("💀 [Reaper] Taking position...")
    
    reaper.take_position(order)
    
    # Monitor for a short period
    monitor_seconds = 10
    print(f"   Monitoring for {monitor_seconds}s...")
    
    try:
        for i in range(monitor_seconds):
            time.sleep(1)
            if i % 5 == 0:
                print(f"   ...{monitor_seconds - i}s remaining")
    except KeyboardInterrupt:
        print("\n   Monitoring interrupted")
    
    # Stop monitoring
    reaper.stop_monitoring()
    
    # --- Step 5: Cycle completion ---
    print("-" * 70)
    print("📈 [Cycle Complete]")
    
    cycle_duration = time.time() - cycle_start
    print(f"⏱️  Cycle duration: {cycle_duration:.1f}s")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Asymmetric Strike Team - Simple Test")
    parser.add_argument("--strategy", default="degen",
                        help="Strategy profile (degen, sniper, conservative)")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuous scanning loop")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between scans in loop mode")
    parser.add_argument("--no-sentiment", action="store_true",
                        help="Disable sentiment analysis")
    args = parser.parse_args()
    
    # Load configuration
    config = SimpleConfig.load()
    config.default_strategy = args.strategy
    config.enable_sentiment = not args.no_sentiment
    
    # Show banner
    build_banner(config)
    config.print_summary()
    
    # Run in loop mode or single cycle
    if args.loop:
        print(f"🔄 Continuous mode — scanning every {args.interval}s")
        print("Press Ctrl+C to stop\n")
        
        cycle_count = 0
        successful_cycles = 0
        
        try:
            while True:
                cycle_count += 1
                print(f"\n{'='*70}")
                print(f"  CYCLE #{cycle_count}")
                print(f"{'='*70}")
                
                success = run_simple_cycle(config)
                if success:
                    successful_cycles += 1
                
                success_rate = (successful_cycles / cycle_count) * 100 if cycle_count > 0 else 0
                print(f"\n📊 Cycle {cycle_count}: {successful_cycles} successful ({success_rate:.1f}% success rate)")
                
                # Wait for next cycle
                wait_time = args.interval
                print(f"\n⏳ Next scan in {wait_time}s...")
                time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Shutdown requested by user")
            print(f"\n📊 FINAL: {successful_cycles}/{cycle_count} successful ({success_rate:.1f}%)")
            print("\n✅ System shutdown complete")
            sys.exit(0)
            
    else:
        # Single cycle mode
        success = run_simple_cycle(config)
        
        if success:
            print("\n✅ Cycle completed successfully")
        else:
            print("\n⚠️  Cycle completed without trade")


if __name__ == "__main__":
    main()