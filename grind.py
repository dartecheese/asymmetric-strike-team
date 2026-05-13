#!/usr/bin/env python3
"""
grind.py — Grinding Wheel

Fetch five-minute whispers from the chain. Let it be slow. Let it be local.
Let it grind through the history of Bitcoin, Ethereum, Solana like a stone
wheel making flour.

Usage:
    python grind.py                          # Default: qwen3:8b, degen strategy
    python grind.py --model qwen3:8b         # Any Ollama model
    python grind.py --strategy sniper        # Any strategy profile
    python grind.py --interval 300           # Loop every 5 minutes
    python grind.py --once                   # Single pass, no loop
    python grind.py --dry-run               # Fetch data but skip model calls
    python grind.py --no-model               # Use existing rules-based agents
"""

import argparse
import logging
import os
import subprocess
import sys
import time

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("grind")


def ensure_ollama_running() -> bool:
    """Check if Ollama is running, start it if not."""
    import urllib.request
    import json

    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        pass

    print("[grind] Ollama not running. Starting it...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for it to be ready
        for _ in range(10):
            time.sleep(1)
            try:
                req = urllib.request.Request("http://localhost:11434/api/tags")
                with urllib.request.urlopen(req, timeout=2):
                    print("[grind] Ollama is ready.")
                    return True
            except Exception:
                continue
        print("[grind] Failed to start Ollama.")
        return False
    except FileNotFoundError:
        print("[grind] 'ollama' not found on PATH.")
        return False


def build_agents(engine=None, use_ai=True):
    """Build the agents, wired together through the shared engine."""
    if use_ai and engine is not None:
        from ai_agents import AIWhisperer, AIActuary, AISlinger, AIReaper, Researcher

        whisperer = AIWhisperer(engine)
        actuary = AIActuary(engine)
        researcher = Researcher(engine)

        from agents.slinger import Slinger as BaseSlinger
        slinger = AISlinger(engine, base=BaseSlinger())

        reaper = AIReaper(engine)

        print(f"[grind] AI agents loaded. Engine: {engine.info}")
        return whisperer, actuary, researcher, slinger, reaper
    else:
        # No-model mode — wrap existing agents with a consistent interface
        from agents.whisperer import Whisperer as BaseWhisperer
        from agents.actuary import Actuary
        from agents.slinger import Slinger
        from agents.reaper import Reaper as BaseReaper

        class RulesWhisperer:
            """Wraps the rules-based Whisperer with a unified scan() interface."""
            def __init__(self):
                self.base = BaseWhisperer()
            def scan(self, strategy="degen"):
                return self.base.scan_firehose()

        class RulesActuary:
            """Wraps Actuary with assess() interface."""
            def __init__(self):
                self.base = Actuary()
            def assess(self, signal, strategy="degen"):
                return self.base.assess_risk(signal)

        class RulesSlinger:
            """Wraps Slinger with plan() interface."""
            def __init__(self):
                self.base = Slinger()
            def plan(self, signal, assessment, strategy="degen"):
                return self.base.execute_order(assessment, signal.chain)

        class RulesReaper:
            """Wraps Reaper with check_position() interface."""
            def __init__(self):
                self.base = BaseReaper()
            def check_position(self, order, strategy="degen"):
                return {"action": "hold", "reasoning": "rules-based reaper", "prices": {}}

        whisperer = RulesWhisperer()
        actuary = RulesActuary()
        slinger = RulesSlinger()
        reaper = RulesReaper()

        print("[grind] Rules-based agents loaded (no AI).")
        # No researcher in rules-only mode — preserve 5-tuple shape with None.
        return whisperer, actuary, None, slinger, reaper


def _record_decision(signal, assessment, strategy, verdict, entered: bool):
    """Append a researcher decision to memory for later replay/learning."""
    try:
        from ai_agents.memory import DecisionRecord, record_decision
        import time as _t
        record_decision(DecisionRecord(
            ts=_t.time(),
            strategy=strategy,
            token_address=signal.token_address,
            chain=signal.chain,
            narrative_score=signal.narrative_score,
            risk_level=assessment.risk_level.value,
            buy_tax=assessment.buy_tax,
            sell_tax=assessment.sell_tax,
            liquidity_locked=assessment.liquidity_locked,
            rating=verdict.rating.value,
            confidence=verdict.confidence,
            bull_summary=verdict.bull_summary,
            bear_summary=verdict.bear_summary,
            verdict_reasoning=verdict.reasoning,
            entered=entered,
        ))
    except Exception as e:
        logger.warning(f"decision memory write failed: {e}")


def run_pipeline(whisperer, actuary, researcher, slinger, reaper,
                 strategy="degen", dry_run=False):
    """Run one full pipeline turn. Returns True if a trade was made."""
    print("\n" + "=" * 60)
    print(f"[grind] Pipeline turn — strategy: {strategy}")
    if dry_run:
        print("[grind] DRY RUN — no model calls, no execution")
    print("=" * 60)

    try:
        # === WHISPERER ===
        print("\n--- Whisperer: Fetching signals ---")
        signal = whisperer.scan(strategy=strategy)

        if not signal:
            print("[grind] No signal found. Pipeline complete.")
            return False

        print(f"[grind] Signal: {signal.token_address[:16]}... "
              f"(score: {signal.narrative_score})")

        # === ACTUARY ===
        print("\n--- Actuary: Assessing risk ---")
        assessment = actuary.assess(signal, strategy=strategy)

        if not assessment or assessment.risk_level.value == "REJECTED":
            print("[grind] Risk assessment rejected. Pipeline complete.")
            return False

        print(f"[grind] Risk: {assessment.risk_level.value} | "
              f"Max alloc: ${assessment.max_allocation_usd:.0f}")

        # === RESEARCHER (Bull/Bear debate) ===
        verdict = None
        if researcher is not None and not dry_run:
            print("\n--- Researcher: Bull/Bear debate ---")
            verdict = researcher.deliberate(signal, assessment, strategy=strategy)
            if verdict is None:
                print("[grind] Researcher unavailable; proceeding on Actuary alone.")
            elif verdict.is_veto:
                print(f"[grind] Researcher VETO ({verdict.rating.value}). Skipping.")
                _record_decision(signal, assessment, strategy, verdict, entered=False)
                return False
            elif not verdict.is_entry:
                print(f"[grind] Researcher HOLD ({verdict.rating.value}). Skipping.")
                _record_decision(signal, assessment, strategy, verdict, entered=False)
                return False
            else:
                # Scale Actuary's max allocation by the rating tier.
                scaled = assessment.max_allocation_usd * verdict.size_multiplier
                assessment = assessment.model_copy(update={"max_allocation_usd": scaled})
                print(f"[grind] Sizing scaled to ${scaled:.0f} "
                      f"(x{verdict.size_multiplier} from {verdict.rating.value}).")

        # === SLINGER ===
        print("\n--- Slinger: Planning execution ---")
        if dry_run:
            print("[grind] DRY RUN — skipping execution.")
            order = None
        else:
            order = slinger.plan(signal, assessment, strategy=strategy)

        if not order:
            print("[grind] No execution order produced. Pipeline complete.")
            return False

        print(f"[grind] Order: {order.action} ${order.amount_usd:.0f} @ "
              f"{order.slippage_tolerance:.0%} slippage")

        # Persist the decision so future debates can recall it with realized PnL.
        if verdict is not None:
            _record_decision(signal, assessment, strategy, verdict, entered=True)

        # === REAPER (if we have a position to track) ===
        if order:
            print("\n--- Reaper: Setting position watch ---")
            # The existing Reaper handles ongoing monitoring via PositionStore
            # For now, we do a single initial check
            check = reaper.check_position(order, strategy=strategy)
            print(f"[grind] Reaper says: {check['action']} — {check.get('reasoning', '')}")

        return True

    except KeyboardInterrupt:
        print("\n[grind] Interrupted.")
        raise
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Grinding Wheel — local DeFi signal extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--model", default="mlx-community/Qwen2.5-7B-Instruct-4bit",
                        help="LLM model (MLX on Apple Silicon, or Ollama name)")
    parser.add_argument("--strategy", default="degen",
                        choices=["degen", "sniper", "shadow_clone", "arb_hunter",
                                 "oracle_eye", "liquidity_sentinel",
                                 "yield_alchemist", "forensic_sniper"],
                        help="Trading strategy profile (default: degen)")
    parser.add_argument("--interval", type=int, default=300,
                        help="Seconds between pipeline loops (default: 300)")
    parser.add_argument("--once", action="store_true",
                        help="Run a single pipeline turn, then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch data but skip model calls and execution")
    parser.add_argument("--no-model", action="store_true",
                        help="Use existing rules-based agents instead of AI")

    args = parser.parse_args()

    print()
    print("  ╭─────────────────────────────────────╮")
    print("  │        Grinding Wheel               │")
    print("  │  slow · local · persistent          │")
    print("  ╰─────────────────────────────────────╯")
    print()
    print(f"  Model:    {args.model if not args.no_model else 'rules-based'}")
    print(f"  Strategy: {args.strategy}")
    print(f"  Interval: {args.interval}s")
    print(f"  Dry run:  {'yes' if args.dry_run else 'no'}")
    print()

    # === SETUP ===
    engine = None
    if not args.no_model and not args.dry_run:
        if args.model.startswith("mlx-"):
            # MLX model — skip Ollama entirely, load via MLX
            from ai_agents.engine import MLXEngine
            engine = MLXEngine(args.model)
            if not engine.ensure_loaded():
                print("[grind] MLX model failed to load. Falling back to rules.")
                args.no_model = True
            else:
                print(f"  [Engine] Using MLX ({args.model})")
        else:
            ensure_ollama_running()  # Best-effort — may or may not work
            from ai_agents.engine import auto_select_engine
            engine = auto_select_engine(args.model)
            if engine is None:
                print("[grind] No local model backend. Falling back to rules.")
                args.no_model = True

    whisperer, actuary, researcher, slinger, reaper = build_agents(
        engine, use_ai=not args.no_model
    )

    # === PIPELINE LOOP ===
    try:
        while True:
            made_trade = run_pipeline(
                whisperer, actuary, researcher, slinger, reaper,
                strategy=args.strategy,
                dry_run=args.dry_run,
            )

            if args.once:
                break

            if made_trade:
                print(f"\n[grind] Trade executed. Waiting {args.interval}s for next turn...")
            else:
                print(f"\n[grind] No trade this turn. Waiting {args.interval}s...")

            print()
            # Shorter wait if a trade just happened, full interval otherwise
            wait = 60 if made_trade else args.interval
            for remaining in range(wait, 0, -1):
                if remaining % 60 == 0:
                    mins = remaining // 60
                    print(f"  next scan in {mins}m...", end="\r")
                elif remaining < 10:
                    print(f"  next scan in {remaining}s...", end="\r")
                time.sleep(1)
            print(" " * 30, end="\r")  # Clear the line

    except KeyboardInterrupt:
        print("\n[grind] Wheel stopped. ✋")
        return 0


if __name__ == "__main__":
    sys.exit(main())
