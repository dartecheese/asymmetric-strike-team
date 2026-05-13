#!/usr/bin/env python3
"""AST eval CLI — `python bin/eval.py`.

Reads data/ produced by grind, writes a markdown + JSON report to
eval_results/. Read-only against data/.

Usage:
    python bin/eval.py                       # full report
    python bin/eval.py --no-benchmark        # skip ETH comparison
    python bin/eval.py --downsample 0        # keep every portfolio tick
    AST_DATA_DIR=/tmp/x python bin/eval.py   # alternate data root
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Run from repo root so `eval` package resolves.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.portfolio import load_portfolio_curve
from eval.metrics import equity_metrics
from eval.strategy import per_strategy_stats
from eval.benchmark import eth_buy_and_hold
from eval.report import write_report, render_markdown


def main() -> int:
    p = argparse.ArgumentParser(description="AST evaluation harness")
    p.add_argument("--downsample", type=int, default=60,
                   help="seconds per portfolio bucket (0 = no downsampling)")
    p.add_argument("--no-benchmark", action="store_true",
                   help="skip ETH buy-and-hold comparison")
    p.add_argument("--out", type=Path, default=ROOT / "eval_results",
                   help="output directory for the report")
    p.add_argument("--stdout", action="store_true",
                   help="print markdown to stdout instead of writing files")
    args = p.parse_args()

    print("[eval] loading portfolio curve...", file=sys.stderr)
    curve = load_portfolio_curve(downsample_seconds=args.downsample)
    print(f"[eval]   {len(curve)} points", file=sys.stderr)

    print("[eval] computing equity metrics...", file=sys.stderr)
    metrics = equity_metrics(curve)

    print("[eval] computing per-strategy stats...", file=sys.stderr)
    strategies = per_strategy_stats()

    benchmark = None
    if not args.no_benchmark and curve:
        print("[eval] computing ETH buy-and-hold benchmark...", file=sys.stderr)
        benchmark = eth_buy_and_hold(curve[0].ts_ms, curve[-1].ts_ms)

    generated_at_ms = int(time.time() * 1000)
    start_ts_ms = curve[0].ts_ms if curve else 0
    end_ts_ms = curve[-1].ts_ms if curve else 0

    if args.stdout:
        print(render_markdown(metrics, strategies, benchmark, generated_at_ms,
                              points=curve, start_ts_ms=start_ts_ms,
                              end_ts_ms=end_ts_ms))
        return 0

    md_path, json_path = write_report(args.out, metrics, strategies, benchmark,
                                       generated_at_ms, points=curve,
                                       start_ts_ms=start_ts_ms,
                                       end_ts_ms=end_ts_ms)
    print(f"[eval] wrote {md_path}", file=sys.stderr)
    print(f"[eval] wrote {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
