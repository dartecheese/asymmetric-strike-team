"""ETH buy-and-hold benchmark over the same window as the portfolio curve.

OHLCV is sourced from data/ohlcv/base_0x4200000000000000000000000000000000000006.json
(WETH on Base, hourly bars). The benchmark answer is the percentage move in
ETH between the closing bar nearest the portfolio start and the closing bar
nearest the portfolio end.

If the OHLCV file is missing or the requested window falls outside its
coverage, returns None — the caller should report that honestly rather than
fabricate a number.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(os.environ.get("AST_DATA_DIR", "data"))
# OHLCV files are keyed by chain_first10hex.json (see data/ohlcv/), so WETH on Base
# is base_0x4200000000.json (not the full 0x42...06 address).
ETH_OHLCV = DATA_DIR / "ohlcv" / "base_0x4200000000.json"


@dataclass
class BenchmarkResult:
    label: str
    start_price_usd: float
    end_price_usd: float
    return_pct: float
    coverage_ratio: float  # what fraction of the eval window the OHLCV actually covers
    ohlcv_first_ts_ms: int = 0
    ohlcv_last_ts_ms: int = 0
    eval_first_ts_ms: int = 0
    eval_last_ts_ms: int = 0
    stale_reason: str = ""  # non-empty when window falls outside OHLCV coverage


def _load_ohlcv(path: Path) -> list[list[float]]:
    if not path.exists():
        return []
    try:
        blob = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    bars = blob.get("ohlcv") or []
    return [b for b in bars if isinstance(b, list) and len(b) >= 5]


def _close_at_or_before(bars: list[list[float]], target_ts_seconds: float) -> tuple[float, float] | None:
    """Return (ts_seconds, close_usd) of the bar at-or-before target. Bars are
    [ts_seconds, open, high, low, close, volume]. Assumes ascending ts."""
    chosen = None
    for b in bars:
        ts = float(b[0])
        if ts > target_ts_seconds:
            break
        chosen = (ts, float(b[4]))
    return chosen


def _close_at_or_after(bars: list[list[float]], target_ts_seconds: float) -> tuple[float, float] | None:
    for b in bars:
        ts = float(b[0])
        if ts >= target_ts_seconds:
            return (ts, float(b[4]))
    return None


def eth_buy_and_hold(start_ts_ms: int, end_ts_ms: int,
                     path: Path | None = None) -> BenchmarkResult | None:
    """Buy ETH at the close nearest the portfolio start, sell at the close nearest the end."""
    bars = _load_ohlcv(path or ETH_OHLCV)
    if not bars:
        return None

    start_s = start_ts_ms / 1000.0
    end_s = end_ts_ms / 1000.0
    first_bar_ts = float(bars[0][0])
    last_bar_ts = float(bars[-1][0])

    # Detect non-overlap: if the OHLCV ends before the eval starts (or vice versa)
    # we should not fabricate a return from edge prices.
    stale_reason = ""
    if last_bar_ts < start_s:
        days_stale = (start_s - last_bar_ts) / 86400.0
        stale_reason = f"OHLCV ends {days_stale:.1f}d before the eval window"
    elif first_bar_ts > end_s:
        days_future = (first_bar_ts - end_s) / 86400.0
        stale_reason = f"OHLCV starts {days_future:.1f}d after the eval window"

    start_pick = _close_at_or_after(bars, start_s) or (first_bar_ts, float(bars[0][4]))
    end_pick = _close_at_or_before(bars, end_s) or (last_bar_ts, float(bars[-1][4]))

    if start_pick[1] <= 0:
        return None

    return_pct = (end_pick[1] - start_pick[1]) / start_pick[1] * 100.0

    requested = max(1.0, end_s - start_s)
    overlap_start = max(start_pick[0], first_bar_ts, start_s)
    overlap_end = min(end_pick[0], last_bar_ts, end_s)
    covered = max(0.0, overlap_end - overlap_start)
    coverage = min(1.0, covered / requested)

    return BenchmarkResult(
        label="ETH buy-and-hold (WETH on Base)",
        start_price_usd=start_pick[1],
        end_price_usd=end_pick[1],
        return_pct=return_pct,
        coverage_ratio=coverage,
        ohlcv_first_ts_ms=int(first_bar_ts * 1000),
        ohlcv_last_ts_ms=int(last_bar_ts * 1000),
        eval_first_ts_ms=start_ts_ms,
        eval_last_ts_ms=end_ts_ms,
        stale_reason=stale_reason,
    )
