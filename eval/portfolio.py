"""Parse data/learning/portfolio.jsonl into a clean equity curve.

The portfolio log is dense (one entry per tick — ~32 entries/second observed)
so we down-sample to one point per minute by default to keep returns math
stable. Equity is parsed as float; the ledger uses string-encoded Decimals
to avoid binary-FP loss, but for Sharpe/MDD the float precision is fine.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

DEFAULT_PORTFOLIO_LOG = Path(os.environ.get("AST_DATA_DIR", "data")) / "learning" / "portfolio.jsonl"


@dataclass(frozen=True)
class PortfolioPoint:
    ts_ms: int
    equity_usd: float
    cash_usd: float
    invested_usd: float
    market_value_usd: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float
    fees_paid_usd: float
    open_positions: int
    closed_positions: int


def _coerce_float(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _iter_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_portfolio_curve(path: Path | None = None,
                         downsample_seconds: int = 60,
                         start_after_ms: int = 0,
                         end_before_ms: int = 0) -> list[PortfolioPoint]:
    """Return the global-portfolio equity curve, down-sampled to one point per bucket.

    Down-sampling keeps the last record in each bucket — equity is monotone-ish
    over short windows so this introduces minimal smoothing. Set
    downsample_seconds=0 to keep every tick.

    start_after_ms / end_before_ms (both ms epoch) clip the window. Useful for
    skipping historical anomalies — e.g. the pre-2026-05-06 data where the
    per-strategy capacity gate hadn't been added yet and equity tracked $2M+ of
    spurious intent. 0 means no clip on that side.
    """
    src = path or DEFAULT_PORTFOLIO_LOG
    bucket_ms = max(0, downsample_seconds) * 1000
    last_in_bucket: dict[int, PortfolioPoint] = {}
    ordered: list[PortfolioPoint] = []

    for rec in _iter_jsonl(src):
        if rec.get("record_type") != "global_portfolio":
            continue
        ts = int(rec.get("timestamp_ms", 0))
        if ts == 0:
            continue
        if start_after_ms and ts < start_after_ms:
            continue
        if end_before_ms and ts > end_before_ms:
            continue
        pt = PortfolioPoint(
            ts_ms=ts,
            equity_usd=_coerce_float(rec.get("equity_usd")),
            cash_usd=_coerce_float(rec.get("cash_balance_usd")),
            invested_usd=_coerce_float(rec.get("invested_usd")),
            market_value_usd=_coerce_float(rec.get("market_value_usd")),
            realized_pnl_usd=_coerce_float(rec.get("realized_pnl_usd")),
            unrealized_pnl_usd=_coerce_float(rec.get("unrealized_pnl_usd")),
            fees_paid_usd=_coerce_float(rec.get("fees_paid_usd")),
            open_positions=int(rec.get("open_positions", 0) or 0),
            closed_positions=int(rec.get("closed_positions", 0) or 0),
        )
        if bucket_ms == 0:
            ordered.append(pt)
        else:
            last_in_bucket[ts // bucket_ms] = pt

    if bucket_ms != 0:
        for k in sorted(last_in_bucket):
            ordered.append(last_in_bucket[k])

    return ordered
