"""Decision memory — append-only JSONL log of agent decisions with realized-PnL feedback.

Two responsibilities:
  1. record_decision: persist a decision at entry time (signal features + verdict)
  2. recall_similar: fetch N past decisions for the same (strategy, chain) tuple,
     joined with realized PnL if a position has since closed.

The retrieval is intentionally cheap (linear scan of the tail) — the corpus is
small in the paper-trading regime and the join needs to read fresh outcomes
each call. If this grows past ~50k records we can swap in a vector index, but
not before.

Realized PnL is read lazily from data/positions/{position_id}.json — that file
is the existing per-position record written by Reaper on close.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

DATA_DIR = Path(os.environ.get("AST_DATA_DIR", "data"))
MEMORY_PATH = DATA_DIR / "decision_memory.jsonl"
OUTCOMES_PATH = DATA_DIR / "decision_outcomes.jsonl"
POSITIONS_JSON = DATA_DIR / "positions.json"


@dataclass
class DecisionRecord:
    ts: float
    strategy: str
    token_address: str
    chain: str
    narrative_score: int
    risk_level: str
    buy_tax: float
    sell_tax: float
    liquidity_locked: bool
    rating: str
    confidence: int
    bull_summary: str
    bear_summary: str
    verdict_reasoning: str
    entered: bool = True  # False if researcher vetoed; outcomes won't join

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


def record_decision(rec: DecisionRecord) -> None:
    """Append a decision to the memory log. Idempotent over a single process run."""
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_PATH.open("a") as f:
        f.write(rec.to_json() + "\n")


def _iter_records():
    if not MEMORY_PATH.exists():
        return
    with MEMORY_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _realized_pnl(token_address: str) -> Optional[float]:
    """Return realized PnL pct for a closed position keyed by token address.

    Looks up two sources:
      1. data/decision_outcomes.jsonl — durable append-only log written when
         a position closes (survives PositionStore.remove_position).
      2. data/positions.json — live store; used while position is still
         present with status == CLOSED but not yet outcome-logged.
    Outcomes log wins when both exist (it's the authoritative close record).
    Stored values are percentages (e.g. 12.3 means +12.3%); we normalize to
    decimal fractions (0.123) for downstream formatters.
    """
    if not token_address:
        return None
    key = token_address.lower()

    # 1. Outcomes log (most recent wins).
    if OUTCOMES_PATH.exists():
        latest = None
        try:
            with OUTCOMES_PATH.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("token_address", "").lower() == key:
                        latest = rec
        except OSError:
            latest = None
        if latest is not None:
            pnl = latest.get("realized_pnl_pct")
            if pnl is not None:
                return _normalize_pnl(pnl)

    # 2. Live positions store fallback (in case close hasn't been logged yet).
    if POSITIONS_JSON.exists():
        try:
            store = json.loads(POSITIONS_JSON.read_text())
        except (json.JSONDecodeError, OSError):
            store = {}
        entry = store.get(key)
        if entry and str(entry.get("status", "")).upper() in ("CLOSED", "STOPPED"):
            pnl = entry.get("pnl_pct")
            if pnl is not None:
                return _normalize_pnl(pnl)

    return None


def _normalize_pnl(raw) -> Optional[float]:
    """Coerce a PnL value to a decimal fraction. Handles either form
    (12.3 → 0.123, 0.123 → 0.123). Values with |x| > 5 are assumed to be
    percentages; anything smaller is treated as already-fractional."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return v / 100.0 if abs(v) > 5 else v


def recall_similar(strategy: str,
                   chain: str,
                   limit: int = 5,
                   max_age_days: int = 30) -> list[dict]:
    """Return up to `limit` past decisions for this (strategy, chain) tuple,
    most recent first, each joined with realized_pnl_pct if available."""
    cutoff = time.time() - max_age_days * 86400
    matches: list[dict] = []
    # Iterate full file; reverse at the end. File stays small in paper regime.
    for rec in _iter_records():
        if rec.get("ts", 0) < cutoff:
            continue
        if rec.get("strategy") != strategy:
            continue
        if rec.get("chain") != chain:
            continue
        rec["realized_pnl_pct"] = _realized_pnl(rec.get("token_address"))
        matches.append(rec)
    return list(reversed(matches))[:limit]


def format_for_prompt(records: list[dict]) -> str:
    """Render recalled decisions into a compact prompt block.

    Realized outcomes are surfaced prominently — that's the signal we want
    the model to learn from."""
    if not records:
        return "  (no comparable past decisions on file)"
    lines = []
    for r in records:
        pnl = r.get("realized_pnl_pct")
        if pnl is None:
            outcome = "open/unknown"
        else:
            outcome = f"{pnl:+.1%}"
        lines.append(
            f"  - {r.get('token_address', '?')[:10]}... "
            f"rated {r.get('rating', '?')} (conf {r.get('confidence', '?')}), "
            f"risk={r.get('risk_level', '?')}, outcome={outcome}"
        )
    return "\n".join(lines)


def record_outcome(token_address: str,
                   realized_pnl_pct: float,
                   final_status: str = "CLOSED",
                   reason: str = "") -> None:
    """Append a position-close outcome so future debates can recall realized PnL.

    Called when a position is being closed/removed. The outcomes file is the
    durable join key for decision_memory.jsonl — it survives
    PositionStore.remove_position(). Idempotent in the weak sense: writing
    duplicate outcomes is allowed, the latest wins on lookup."""
    if not token_address:
        return
    OUTCOMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.time(),
        "token_address": token_address.lower(),
        "realized_pnl_pct": realized_pnl_pct,
        "final_status": final_status,
        "reason": reason,
    }
    with OUTCOMES_PATH.open("a") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")
