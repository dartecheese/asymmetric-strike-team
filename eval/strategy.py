"""Per-strategy stats from data/learning/{strategy}.jsonl and data/ledger/{strategy}.jsonl.

Counts events by type, totals fills/orders/risk-checks/safety-blocks, and
extracts entry-vs-exit pairs where possible. For 'lab is not closing trades'
diagnostics this is more useful than the global portfolio view because it
surfaces which strategies are actually firing vs which are silent.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(os.environ.get("AST_DATA_DIR", "data"))
LEARNING_DIR = DATA_DIR / "learning"
LEDGER_DIR = DATA_DIR / "ledger"

# Strategies are config-defined, but discovery from files is fine for eval.
KNOWN_STRATEGIES = (
    "thrive", "swift", "echo", "bridge", "flow", "clarity", "nurture", "insight",
)


@dataclass
class StrategyStats:
    name: str
    learning_events: dict[str, int] = field(default_factory=dict)
    ledger_events: dict[str, int] = field(default_factory=dict)
    fills: int = 0
    orders: int = 0
    signals: int = 0
    risk_checks: int = 0
    safety_blocks: int = 0
    last_event_ts_ms: int = 0
    total_fees_usd: float = 0.0
    total_executed_notional_usd: float = 0.0
    avg_slippage_bps: float = 0.0


def _iter_jsonl(path: Path):
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


def _safe_float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _strategy_stats(name: str) -> StrategyStats:
    s = StrategyStats(name=name)

    # learning/{name}.jsonl — categorize by record_type
    learning_counter: Counter[str] = Counter()
    last_ts = 0
    for rec in _iter_jsonl(LEARNING_DIR / f"{name}.jsonl"):
        rtype = rec.get("record_type", "unknown")
        learning_counter[rtype] += 1
        ts = int(rec.get("timestamp_ms") or 0)
        if ts > last_ts:
            last_ts = ts
        # Note: 'safety' records with status 'blocked' indicate a circuit-breaker hit.
        if rtype == "safety" and str(rec.get("status", "")).lower() == "blocked":
            s.safety_blocks += 1
    s.learning_events = dict(learning_counter)
    s.signals = learning_counter.get("signal", 0)
    s.risk_checks = learning_counter.get("risk", 0)
    s.fills = learning_counter.get("fill", 0)
    s.orders = learning_counter.get("order", 0)
    s.last_event_ts_ms = last_ts

    # ledger/{name}.jsonl — fills carry execution details
    ledger_counter: Counter[str] = Counter()
    fee_total = 0.0
    notional_total = 0.0
    slippages: list[float] = []
    for rec in _iter_jsonl(LEDGER_DIR / f"{name}.jsonl"):
        rtype = rec.get("record_type", "unknown")
        ledger_counter[rtype] += 1
        if rtype == "fill_tracked":
            fee_total += _safe_float(rec.get("fee_usd"))
            notional_total += _safe_float(rec.get("executed_notional_usd"))
            slip = rec.get("slippage_bps")
            if slip is not None:
                slippages.append(_safe_float(slip))
    s.ledger_events = dict(ledger_counter)
    s.total_fees_usd = fee_total
    s.total_executed_notional_usd = notional_total
    s.avg_slippage_bps = sum(slippages) / len(slippages) if slippages else 0.0

    return s


def per_strategy_stats(strategies=KNOWN_STRATEGIES) -> list[StrategyStats]:
    return [_strategy_stats(s) for s in strategies]
