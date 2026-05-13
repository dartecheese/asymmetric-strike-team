"""Risk/return metrics for an equity curve.

Sharpe is annualized assuming continuously sampled returns; we infer the
sampling cadence from the median tick spacing rather than hard-coding daily.
Max drawdown is the worst peak-to-trough trough on the absolute equity series.

No external deps — pure stdlib math, so the harness runs in any AST venv
without numpy.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

SECONDS_PER_YEAR = 365.25 * 24 * 3600


@dataclass
class EquityMetrics:
    n_points: int
    duration_seconds: float
    start_equity: float
    end_equity: float
    total_return_pct: float
    cagr_pct: float
    sharpe_annualized: float
    max_drawdown_pct: float
    max_drawdown_at_ts_ms: int
    realized_pnl_usd: float
    unrealized_pnl_usd: float
    fees_paid_usd: float


def returns_from_equity(equity: list[float]) -> list[float]:
    """Simple period-over-period returns. First point produces no return."""
    if len(equity) < 2:
        return []
    out = []
    prev = equity[0]
    for cur in equity[1:]:
        if prev <= 0:
            out.append(0.0)
        else:
            out.append((cur - prev) / prev)
        prev = cur
    return out


def _annualized_sharpe(returns: list[float], avg_period_seconds: float,
                      rf_annual: float = 0.0) -> float:
    """Risk-free defaults to 0 — crypto convention; T-bill correction is noise
    at the scale of these returns."""
    if len(returns) < 2 or avg_period_seconds <= 0:
        return 0.0
    mean = statistics.fmean(returns)
    try:
        sd = statistics.stdev(returns)
    except statistics.StatisticsError:
        return 0.0
    if sd == 0:
        return 0.0
    periods_per_year = SECONDS_PER_YEAR / avg_period_seconds
    rf_per_period = rf_annual / periods_per_year
    return (mean - rf_per_period) / sd * math.sqrt(periods_per_year)


def _max_drawdown(equity: list[float], timestamps_ms: list[int]) -> tuple[float, int]:
    """Return (max_drawdown_pct as positive number, ts_ms at trough)."""
    if not equity:
        return 0.0, 0
    peak = equity[0]
    worst = 0.0
    worst_ts = timestamps_ms[0] if timestamps_ms else 0
    for ts, v in zip(timestamps_ms, equity):
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > worst:
                worst = dd
                worst_ts = ts
    return worst * 100.0, worst_ts


def equity_metrics(points) -> EquityMetrics:
    """Compute summary risk/return metrics from a PortfolioPoint sequence."""
    if not points:
        return EquityMetrics(
            n_points=0, duration_seconds=0.0,
            start_equity=0.0, end_equity=0.0,
            total_return_pct=0.0, cagr_pct=0.0,
            sharpe_annualized=0.0, max_drawdown_pct=0.0,
            max_drawdown_at_ts_ms=0,
            realized_pnl_usd=0.0, unrealized_pnl_usd=0.0,
            fees_paid_usd=0.0,
        )

    equity = [p.equity_usd for p in points]
    timestamps = [p.ts_ms for p in points]
    duration_seconds = max(0, (timestamps[-1] - timestamps[0]) / 1000.0)
    avg_period = duration_seconds / max(1, len(points) - 1)

    start, end = equity[0], equity[-1]
    total_return_pct = ((end - start) / start * 100.0) if start > 0 else 0.0
    cagr_pct = 0.0
    if start > 0 and duration_seconds > 0 and end > 0:
        years = duration_seconds / SECONDS_PER_YEAR
        if years > 0:
            cagr_pct = (math.pow(end / start, 1.0 / years) - 1.0) * 100.0

    rets = returns_from_equity(equity)
    sharpe = _annualized_sharpe(rets, avg_period)
    mdd_pct, mdd_ts = _max_drawdown(equity, timestamps)

    return EquityMetrics(
        n_points=len(points),
        duration_seconds=duration_seconds,
        start_equity=start,
        end_equity=end,
        total_return_pct=total_return_pct,
        cagr_pct=cagr_pct,
        sharpe_annualized=sharpe,
        max_drawdown_pct=mdd_pct,
        max_drawdown_at_ts_ms=mdd_ts,
        realized_pnl_usd=points[-1].realized_pnl_usd,
        unrealized_pnl_usd=points[-1].unrealized_pnl_usd,
        fees_paid_usd=points[-1].fees_paid_usd,
    )
