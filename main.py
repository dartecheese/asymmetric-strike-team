"""
Asymmetric Strike Team — Main Entry Point
==========================================
Pipeline: Whisperer → Actuary → Slinger → Reaper

Strategy profiles flow through to every agent — pick one and all params adjust:
  degen | sniper | shadow_clone | arb_hunter | oracle_eye | liquidity_sentinel | yield_alchemist | forensic_sniper

Run modes:
  python main.py                              # Paper, degen strategy, single cycle
  python main.py --strategy sniper            # Different strategy profile
  python main.py --loop                       # Continuous scanning
  python main.py --loop --interval 30         # Scan every 30s
  python main.py --list                       # Show all strategies
  USE_REAL_EXECUTION=true python main.py      # Live execution
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
logger = logging.getLogger("Main")


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


def build_banner(strategy_name: str, mode: str):
    print("\n" + "=" * 60)
    print("🚀  ASYMMETRIC STRIKE TEAM")
    print(f"   Strategy : {strategy_name}")
    print(f"   Mode     : {mode}")
    print("=" * 60 + "\n")


def run_cycle(strategy: str = "degen", paper_mode: bool = True) -> bool:
    """
    Run a single scan → assess → execute → monitor cycle.
    Strategy profile flows through to all agent configs.
    Returns True if a trade was placed, False otherwise.
    """
    from strategy_factory import StrategyFactory
    from agents.whisperer import Whisperer
    from agents.actuary import Actuary
    from agents.slinger import Slinger
    from agents.reaper import Reaper
    from core.models import RiskLevel

    factory = StrategyFactory()
    try:
        profile = factory.get_profile(strategy)
    except ValueError as e:
        logger.error(str(e))
        return False

    # --- Build agents from strategy profile ---

    # Whisperer: use profile's velocity score threshold
    whisperer_cfg = profile.whisperer
    min_score = whisperer_cfg.min_velocity_score if whisperer_cfg else 50
    whisperer = Whisperer(min_velocity_score=min_score)

    # Actuary: use profile's tax tolerance and strict mode
    actuary_cfg = profile.actuary
    actuary = Actuary(
        max_allowed_tax=actuary_cfg.max_tax_allowed / 100,  # config stores as %, we use decimal
    )

    # Slinger: use profile's slippage and gas settings
    slinger_cfg = profile.slinger
    slinger = Slinger()
    slinger._strategy_slippage = slinger_cfg.base_slippage_tolerance
    slinger._strategy_gas_multiplier = slinger_cfg.gas_premium_multiplier
    slinger._use_private_mempool = slinger_cfg.use_private_mempool

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
    print(f"   Actuary  : max tax {actuary_cfg.max_tax_allowed:.0f}% | strict={actuary_cfg.strict_mode}")
    print(f"   Slinger  : slippage {slinger_cfg.base_slippage_tolerance*100:.0f}% | private_mempool={slinger_cfg.use_private_mempool}")
    print(f"   Reaper   : TP +{reaper_cfg.take_profit_pct:.0f}% | SL {reaper_cfg.stop_loss_pct:.0f}% | trail -{reaper_cfg.trailing_stop_pct:.0f}%")

    # --- Step 1: Whisperer scans for signals ---
    print("\n" + "-" * 60)
    signal = whisperer.scan_firehose()
    if not signal:
        logger.warning("Whisperer returned no signal this cycle.")
        return False

    print(f"   Score: {signal.narrative_score} | Chain: {signal.chain}")
    print(f"   {signal.reasoning[:120]}")

    # --- Step 2: Actuary assesses risk (always returns, never None) ---
    print("-" * 60)
    assessment = actuary.assess_risk(signal)

    if assessment.risk_level == RiskLevel.REJECTED:
        print(f"🛡️  Token REJECTED by Actuary. Standing down.\n")
        return False

    # Strict mode: also reject HIGH risk tokens
    if actuary_cfg.strict_mode and assessment.risk_level == RiskLevel.HIGH:
        print(f"🛡️  Strict mode: HIGH risk token rejected.\n")
        return False

    # --- Step 3: Slinger executes with strategy params ---
    print("-" * 60)
    order = slinger.execute_order(assessment, chain_id=signal.chain)

    if not order:
        logger.warning("Slinger returned no order.")
        return False

    # --- Step 4: Reaper monitors with strategy TP/SL ---
    print("-" * 60)
    live_price_tag = f"@ ${order.entry_price_usd:.8f}" if order.entry_price_usd else "(no price feed)"
    print(f"💀 [Reaper] Entry price {live_price_tag} | {'LIVE price polling' if not paper_mode and order.entry_price_usd else 'paper sim'}")
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
    parser = argparse.ArgumentParser(description="Asymmetric Strike Team")
    parser.add_argument("--strategy", default="degen",
                        help="Strategy profile (default: degen)")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuous scanning loop")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between scans in loop mode (default: 60)")
    parser.add_argument("--list", action="store_true",
                        help="List all available strategy profiles and exit")
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
    build_banner(args.strategy.upper(), mode_label)

    if args.loop:
        print(f"🔄 Continuous mode — scanning every {args.interval}s. Ctrl+C to stop.\n")
        cycle = 0
        while True:
            try:
                cycle += 1
                print(f"\n{'='*60}\n  CYCLE #{cycle}\n{'='*60}")
                run_cycle(strategy=args.strategy, paper_mode=paper_mode)
                print(f"\n⏳ Next scan in {args.interval}s...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n\n🛑 Shutdown requested. Exiting.")
                sys.exit(0)
    else:
        run_cycle(strategy=args.strategy, paper_mode=paper_mode)
        print("\n✅ Single cycle complete.")


if __name__ == "__main__":
    main()
