"""
Asymmetric Strike Team — Main Entry Point
==========================================
Pipeline: Whisperer → Actuary → Slinger → Reaper

Run modes:
  python main.py                    # Paper trading, single cycle
  python main.py --strategy degen  # Pick a strategy
  python main.py --loop             # Continuous scanning loop
  USE_REAL_EXECUTION=true python main.py  # Live execution
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


def build_banner(strategy: str, mode: str):
    print("\n" + "=" * 60)
    print("🚀  ASYMMETRIC STRIKE TEAM")
    print(f"   Strategy : {strategy.upper()}")
    print(f"   Mode     : {mode}")
    print("=" * 60 + "\n")


def run_cycle(strategy: str = "degen", paper_mode: bool = True) -> bool:
    """
    Run a single scan → assess → execute → monitor cycle.
    Returns True if a trade was placed, False otherwise.
    """
    from agents.whisperer import Whisperer
    from agents.actuary import Actuary
    from agents.slinger import Slinger
    from agents.reaper import Reaper
    from core.models import RiskLevel

    # --- Init agents ---
    whisperer = Whisperer()
    actuary = Actuary(max_allowed_tax=0.25)
    slinger = Slinger()
    reaper = Reaper(
        take_profit_pct=100.0,
        stop_loss_pct=-30.0,
        trailing_stop_pct=15.0,
        poll_interval_sec=5.0,
        paper_mode=paper_mode,
    )

    # --- Step 1: Whisperer scans for signals ---
    print("-" * 60)
    signal = whisperer.scan_firehose()
    if not signal:
        logger.warning("Whisperer returned no signal. Skipping cycle.")
        return False

    # --- Step 2: Actuary assesses risk (always returns, never None) ---
    print("-" * 60)
    assessment = actuary.assess_risk(signal)

    if assessment.risk_level == RiskLevel.REJECTED:
        print(f"🛡️  [Actuary] Token REJECTED. Standing down this cycle.\n")
        return False

    # --- Step 3: Slinger executes ---
    print("-" * 60)
    order = slinger.execute_order(assessment, chain_id=signal.chain)

    if not order:
        logger.warning("Slinger returned no order. Pipeline ended early.")
        return False

    # --- Step 4: Reaper monitors ---
    print("-" * 60)
    reaper.take_position(order)
    reaper.start_monitoring()

    try:
        time.sleep(30)  # Monitor for 30 seconds per cycle
    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    reaper.stop_monitoring()
    summary = reaper.get_portfolio_summary()
    print(f"\n💀 [Reaper] Session summary: {summary}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Asymmetric Strike Team")
    parser.add_argument("--strategy", default="degen", help="Strategy profile to use")
    parser.add_argument("--loop", action="store_true", help="Run continuous scanning loop")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds (default: 60)")
    args = parser.parse_args()

    use_real = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
    rpc_url = os.getenv("ETH_RPC_URL")
    private_key = os.getenv("PRIVATE_KEY")

    paper_mode = True
    if use_real and rpc_url and private_key:
        paper_mode = False
        logger.warning("⚠️  REAL EXECUTION MODE ENABLED — live transactions will be sent!")
    elif use_real:
        logger.warning("USE_REAL_EXECUTION=true but ETH_RPC_URL or PRIVATE_KEY missing. Falling back to paper mode.")

    mode_label = "PAPER TRADING" if paper_mode else "🚨 LIVE EXECUTION"
    build_banner(args.strategy, mode_label)

    if args.loop:
        print(f"🔄 Continuous mode — scanning every {args.interval}s. Ctrl+C to stop.\n")
        cycle_count = 0
        while True:
            try:
                cycle_count += 1
                print(f"\n{'='*60}")
                print(f"CYCLE #{cycle_count}")
                print(f"{'='*60}")
                run_cycle(strategy=args.strategy, paper_mode=paper_mode)
                print(f"\nNext scan in {args.interval}s...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n\n🛑 Shutdown requested. Exiting cleanly.")
                sys.exit(0)
    else:
        run_cycle(strategy=args.strategy, paper_mode=paper_mode)
        print("\n✅ Single cycle complete.")


if __name__ == "__main__":
    main()
