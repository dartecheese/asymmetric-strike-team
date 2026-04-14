"""
Asymmetric Strike Team — Enhanced Version
==========================================
Includes:
1. Enhanced Whisperer with sentiment analysis
2. Unified Slinger (DEX + CEX execution)
3. Better error handling and validation
4. Multi-venue execution routing
"""
import os
import sys
import time
import logging
import argparse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MainEnhanced")


def list_strategies():
    from strategy_factory import StrategyFactory
    factory = StrategyFactory()
    print("\n📋 Available Strategies:\n")
    for key, profile in factory.profiles.items():
        agents = []
        if profile.whisperer: agents.append("Whisperer")
        if profile.shadow:    agents.append("Shadow")
        if profile.oracle:    agents.append("Oracle")
        if profile.sentinel:  agents.append("Sentinel")
        if profile.sleuth:    agents.append("Sleuth")
        if profile.pathfinder: agents.append("Pathfinder")
        if profile.alchemist:  agents.append("Alchemist")
        agents += ["Actuary", "Slinger", "Reaper"]

        print(f"  [{key}] {profile.name}")
        print(f"    {profile.description}")
        print(f"    Team   : {' → '.join(agents)}")
        print(f"    TP/SL  : +{profile.reaper.take_profit_pct:.0f}% / {profile.reaper.stop_loss_pct:.0f}%")
        print(f"    Slippage: {profile.slinger.base_slippage_tolerance*100:.0f}% | Gas: {profile.slinger.gas_premium_multiplier}x")
        print()


def build_banner(strategy_name: str, mode: str, enhanced: bool = True):
    print("\n" + "=" * 70)
    print("🚀  ASYMMETRIC STRIKE TEAM - ENHANCED")
    print(f"   Strategy : {strategy_name}")
    print(f"   Mode     : {mode}")
    if enhanced:
        print("   Features : Sentiment Analysis + Unified Execution (DEX/CEX)")
    print("=" * 70 + "\n")


def run_enhanced_cycle(strategy: str = "degen", paper_mode: bool = True) -> bool:
    """
    Run enhanced scan → assess → execute → monitor cycle.
    """
    from strategy_factory import StrategyFactory
    from agents.enhanced_whisperer import EnhancedWhisperer
    from agents.actuary import Actuary
    from agents.unified_slinger import UnifiedSlinger
    from agents.reaper import Reaper
    from core.models import RiskLevel

    factory = StrategyFactory()
    try:
        profile = factory.get_profile(strategy)
    except ValueError as e:
        logger.error(str(e))
        return False

    # --- Build enhanced agents ---

    # Enhanced Whisperer with sentiment analysis
    whisperer_cfg = profile.whisperer
    min_score = whisperer_cfg.min_velocity_score if whisperer_cfg else 50
    whisperer = EnhancedWhisperer(min_velocity_score=min_score, use_sentiment=True)

    # Actuary: use profile's tax tolerance and strict mode
    actuary_cfg = profile.actuary
    actuary = Actuary(
        max_allowed_tax=actuary_cfg.max_tax_allowed / 100,
    )

    # Unified Slinger: DEX + CEX execution
    slinger_cfg = profile.slinger
    slinger = UnifiedSlinger()
    slinger.set_strategy_params(
        slippage=slinger_cfg.base_slippage_tolerance,
        gas_multiplier=slinger_cfg.gas_premium_multiplier,
        private_mempool=slinger_cfg.use_private_mempool
    )

    # Reaper: use profile's TP/SL/trailing settings
    reaper_cfg = profile.reaper
    reaper = Reaper(
        take_profit_pct=reaper_cfg.take_profit_pct,
        stop_loss_pct=reaper_cfg.stop_loss_pct,
        trailing_stop_pct=reaper_cfg.trailing_stop_pct,
        poll_interval_sec=5.0,
        paper_mode=paper_mode,
    )

    print(f"📐 Profile loaded: {profile.name}")
    print(f"   Whisperer : Enhanced with sentiment analysis")
    print(f"   Actuary   : max tax {actuary_cfg.max_tax_allowed:.0f}% | strict={actuary_cfg.strict_mode}")
    print(f"   Slinger   : Unified DEX/CEX | slippage {slinger_cfg.base_slippage_tolerance*100:.0f}%")
    print(f"   Reaper    : TP +{reaper_cfg.take_profit_pct:.0f}% | SL {reaper_cfg.stop_loss_pct:.0f}%")

    # --- Step 1: Enhanced Whisperer scans with sentiment ---
    print("\n" + "-" * 70)
    signal = whisperer.scan_firehose()
    if not signal:
        logger.warning("Enhanced Whisperer returned no signal this cycle.")
        return False

    print(f"   Final Score: {signal.narrative_score} | Chain: {signal.chain}")
    print(f"   {signal.reasoning[:120]}")

    # --- Step 2: Actuary assesses risk ---
    print("-" * 70)
    assessment = actuary.assess_risk(signal)

    if assessment.risk_level == RiskLevel.REJECTED:
        print(f"🛡️  Token REJECTED by Actuary. Standing down.\n")
        return False

    # Strict mode: also reject HIGH risk tokens
    if actuary_cfg.strict_mode and assessment.risk_level == RiskLevel.HIGH:
        print(f"🛡️  Strict mode: HIGH risk token rejected.\n")
        return False

    # --- Step 3: Unified Slinger executes (DEX or CEX) ---
    print("-" * 70)
    
    # Determine if this is a CEX-listed token
    token_lower = signal.token_address.lower()
    cex_tokens = {
        "0x6982508145454ce325ddbe47a25d4ec3d2311933": "PEPE/USDT",  # PEPE
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "ETH/USDT",    # WETH
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "BTC/USDT",    # WBTC
    }
    
    symbol = cex_tokens.get(token_lower)
    if symbol:
        print(f"   CEX-listed token detected: {symbol}")
        chain_id = "cex"
    else:
        symbol = None
        chain_id = signal.chain
    
    order = slinger.execute_order(assessment, chain_id=chain_id, symbol=symbol)

    if not order:
        logger.warning("Unified Slinger returned no order.")
        return False

    # --- Step 4: Reaper monitors ---
    print("-" * 70)
    venue = "CEX" if order.is_cex else "DEX"
    price_info = f"@ ${order.entry_price_usd:.8f}" if order.entry_price_usd else "(paper mode)"
    print(f"💀 [Reaper] {venue} entry {price_info}")
    
    reaper.take_position(order)
    reaper.start_monitoring()

    monitor_duration = 30  # seconds per cycle
    try:
        time.sleep(monitor_duration)
    except KeyboardInterrupt:
        print("\nInterrupted.")

    reaper.stop_monitoring()
    summary = reaper.get_portfolio_summary()
    print(f"\n💀 [Reaper] Summary: {summary}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Asymmetric Strike Team - Enhanced")
    parser.add_argument("--strategy", default="degen",
                        help="Strategy profile (default: degen)")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuous scanning loop")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between scans in loop mode (default: 60)")
    parser.add_argument("--list", action="store_true",
                        help="List all available strategy profiles and exit")
    parser.add_argument("--no-sentiment", action="store_true",
                        help="Disable sentiment analysis")
    parser.add_argument("--venue", choices=["auto", "dex", "cex"], default="auto",
                        help="Execution venue preference (default: auto)")
    args = parser.parse_args()

    if args.list:
        list_strategies()
        return

    use_real = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
    rpc_url  = os.getenv("ETH_RPC_URL")
    priv_key = os.getenv("PRIVATE_KEY")

    paper_mode = True
    if use_real and rpc_url and priv_key:
        paper_mode = False
        logger.warning("⚠️  REAL EXECUTION MODE — live transactions will broadcast!")
    elif use_real:
        logger.warning("USE_REAL_EXECUTION=true but RPC_URL or PRIVATE_KEY missing — defaulting to paper.")

    mode_label = "PAPER TRADING" if paper_mode else "🚨 LIVE EXECUTION"
    build_banner(args.strategy.upper(), mode_label, enhanced=not args.no_sentiment)

    if args.loop:
        print(f"🔄 Continuous mode — scanning every {args.interval}s. Ctrl+C to stop.\n")
        cycle = 0
        while True:
            try:
                cycle += 1
                print(f"\n{'='*70}\n  CYCLE #{cycle}\n{'='*70}")
                run_enhanced_cycle(strategy=args.strategy, paper_mode=paper_mode)
                print(f"\n⏳ Next scan in {args.interval}s...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n\n🛑 Shutdown requested. Exiting.")
                sys.exit(0)
    else:
        run_enhanced_cycle(strategy=args.strategy, paper_mode=paper_mode)
        print("\n✅ Enhanced cycle complete.")


if __name__ == "__main__":
    main()