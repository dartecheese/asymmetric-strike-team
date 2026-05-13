"""
PositionStore — persistent position state via JSON.

Saves/loads all active positions to disk so the Reaper survives restarts.
File: data/positions.json (auto-created)
"""

import os
import json
import time
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger("PositionStore")

DEFAULT_PATH = Path(__file__).parent.parent / "data" / "positions.json"


class PositionStore:
    """
    Persists position state to disk as JSON.
    Thread-safe via simple file locking (write-then-rename).
    """

    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})
        logger.info(f"PositionStore: {self.path}")

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _read(self) -> dict:
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning("Position file missing or corrupt — starting fresh.")
            return {}

    def _write(self, data: dict):
        """Atomic write via temp file + rename."""
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def save_position(self, position) -> None:
        """
        Persist a Position object to disk.
        Accepts agents.reaper.Position instances.
        """
        data = self._read()
        key = position.token_address.lower()
        data[key] = {
            "token_address":   position.token_address,
            "chain":           getattr(position, "chain", "1"),
            "amount_usd":      position.amount_usd,
            "entry_value":     position.entry_value,
            "current_value":   position.current_value,
            "peak_value":      position.peak_value,
            "entry_price_usd": position.entry_price_usd,
            "last_price_usd":  getattr(position, "last_price_usd", None),
            "status":          position.status,
            "pnl_pct":         position.pnl_pct,
            "saved_at":        time.time(),
        }
        self._write(data)
        logger.debug(f"Saved position: {position.token_address[:12]}... [{position.status}]")

    def load_all(self) -> list[dict]:
        """Return all persisted positions as raw dicts."""
        return list(self._read().values())

    def load_active(self) -> list[dict]:
        """Return only ACTIVE and FREE_RIDE positions."""
        return [p for p in self.load_all() if p.get("status") in ("ACTIVE", "FREE_RIDE")]

    def remove_position(self, token_address: str, reason: str = "") -> None:
        """Remove a closed/stopped position from the store.

        Before deletion, append the final realized PnL to the durable outcomes
        log so the researcher's decision memory can join on it later."""
        data = self._read()
        key = token_address.lower()
        if key in data:
            entry = data[key]
            pnl = entry.get("pnl_pct")
            prev_status = str(entry.get("status", "")).upper()
            # Skip the outcome log if update_status already logged the terminal
            # transition — avoids double-logging on the canonical close flow.
            already_logged = prev_status in ("CLOSED", "STOPPED")
            if pnl is not None and not already_logged:
                try:
                    from ai_agents.memory import record_outcome
                    record_outcome(
                        token_address=token_address,
                        realized_pnl_pct=pnl,
                        final_status=entry.get("status", "CLOSED"),
                        reason=reason or "position_store.remove_position",
                    )
                except Exception as e:
                    logger.warning(f"record_outcome failed: {e}")
            del data[key]
            self._write(data)
            logger.info(f"Removed position: {token_address[:12]}...")

    def update_status(self, token_address: str, status: str, current_value: float = None, pnl_pct: float = None) -> None:
        """Quick status/value update without reloading a full Position object.

        If the new status indicates a terminal state (CLOSED/STOPPED), the
        final PnL is appended to the durable outcomes log so the researcher's
        decision memory can recall it even after the position is removed."""
        data = self._read()
        key = token_address.lower()
        if key not in data:
            logger.warning(f"update_status: {token_address[:12]}... not found in store.")
            return
        prev_status = str(data[key].get("status", "")).upper()
        data[key]["status"] = status
        data[key]["saved_at"] = time.time()
        if current_value is not None:
            data[key]["current_value"] = current_value
        if pnl_pct is not None:
            data[key]["pnl_pct"] = pnl_pct
        self._write(data)

        new_status = str(status).upper()
        is_terminal_now = new_status in ("CLOSED", "STOPPED")
        was_terminal = prev_status in ("CLOSED", "STOPPED")
        if is_terminal_now and not was_terminal:
            final_pnl = pnl_pct if pnl_pct is not None else data[key].get("pnl_pct")
            if final_pnl is not None:
                try:
                    from ai_agents.memory import record_outcome
                    record_outcome(
                        token_address=token_address,
                        realized_pnl_pct=final_pnl,
                        final_status=new_status,
                        reason="position_store.update_status",
                    )
                except Exception as e:
                    logger.warning(f"record_outcome failed: {e}")

    def summary(self) -> dict:
        """Return a quick overview of all persisted positions."""
        all_pos = self.load_all()
        result = {
            "total": len(all_pos),
            "active": 0,
            "free_ride": 0,
            "stopped": 0,
            "closed": 0,
            "total_value_usd": 0.0,
        }
        for p in all_pos:
            status = p.get("status", "").lower().replace(" ", "_")
            result[status] = result.get(status, 0) + 1
            result["total_value_usd"] += p.get("current_value", 0)
        return result

    def print_positions(self) -> None:
        """Pretty-print all persisted positions to stdout."""
        all_pos = self.load_all()
        if not all_pos:
            print("📂 [PositionStore] No saved positions.")
            return

        print(f"\n📂 [PositionStore] {len(all_pos)} position(s):\n")
        for p in all_pos:
            pnl = p.get("pnl_pct", 0)
            arrow = "📈" if pnl >= 0 else "📉"
            age_min = (time.time() - p.get("saved_at", time.time())) / 60
            print(
                f"  {p['token_address'][:14]}...  "
                f"chain={p.get('chain','?')}  "
                f"${p.get('current_value', 0):.2f}  "
                f"{arrow} {pnl:+.1f}%  "
                f"[{p.get('status','?')}]  "
                f"saved {age_min:.0f}m ago"
            )
        print()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)

    store = PositionStore()

    # Simulate a position object
    class FakePosition:
        token_address = "0xABCDEF1234567890abcdef1234567890abcdef12"
        chain = "1"
        amount_usd = 100.0
        entry_value = 100.0
        current_value = 142.0
        peak_value = 155.0
        entry_price_usd = 0.00042
        last_price_usd = 0.00059
        status = "FREE_RIDE"
        pnl_pct = 42.0

    store.save_position(FakePosition())
    store.print_positions()
    print("Summary:", store.summary())
    store.update_status(FakePosition.token_address, "CLOSED", current_value=138.0, pnl_pct=38.0)
    store.print_positions()
    store.remove_position(FakePosition.token_address)
    store.print_positions()
