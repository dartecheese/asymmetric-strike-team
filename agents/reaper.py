import time
import threading
import logging
import json
import urllib.request
import urllib.error
from typing import Optional
from core.models import ExecutionOrder
from core.position_store import PositionStore

logger = logging.getLogger("Reaper")

# DexScreener price endpoint — free, no API key
DEXSCREENER_PRICE_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"

# Chain ID → DexScreener chain slug mapping
CHAIN_SLUGS = {
    "1": "ethereum",
    "56": "bsc",
    "42161": "arbitrum",
    "8453": "base",
    "ethereum": "ethereum",
    "bsc": "bsc",
    "arbitrum": "arbitrum",
    "base": "base",
}


def fetch_token_price_usd(token_address: str) -> Optional[float]:
    """
    Fetch the current USD price for a token via DexScreener.
    Returns None if unavailable.
    """
    url = DEXSCREENER_PRICE_URL.format(address=token_address)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AsymmetricStrikeTeam/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        pairs = data.get("pairs") or []
        if not pairs:
            return None
        # Use the highest-liquidity pair
        best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
        price_str = best.get("priceUsd")
        return float(price_str) if price_str else None
    except Exception as e:
        logger.warning(f"Price fetch failed for {token_address}: {e}")
        return None


class Position:
    def __init__(self, order: ExecutionOrder):
        self.token_address = order.token_address
        self.chain = getattr(order, "chain", "1")
        self.amount_usd = order.amount_usd
        self.entry_price_usd = order.entry_price_usd  # Set by Slinger at execution
        self.entry_value = order.amount_usd
        self.current_value = order.amount_usd
        self.peak_value = order.amount_usd
        self.status = "ACTIVE"  # ACTIVE | FREE_RIDE | STOPPED | CLOSED
        self.pnl_pct = 0.0
        self.last_price_usd: Optional[float] = order.entry_price_usd


class Reaper:
    """
    The Reaper: Portfolio Defense.
    - Polls real prices from DexScreener
    - FREE RIDE: extract principal at +100%
    - STOP LOSS: liquidate at -30%
    - TRAILING STOP: locks in gains after peak
    - Persists all positions to disk — survives restarts
    """
    def __init__(
        self,
        take_profit_pct: float = 100.0,
        stop_loss_pct: float = -30.0,
        trailing_stop_pct: float = 15.0,
        poll_interval_sec: float = 10.0,
        paper_mode: bool = True,
    ):
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.poll_interval = poll_interval_sec
        self.paper_mode = paper_mode

        self.positions: dict[str, Position] = {}
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None
        self.store = PositionStore()

        # Restore any active positions from disk
        self._restore_positions()

    def _restore_positions(self):
        """Load active positions from disk on startup."""
        saved = self.store.load_active()
        if not saved:
            return
        print(f"💀 [Reaper] Restoring {len(saved)} position(s) from disk...")
        for p in saved:
            try:
                from core.models import ExecutionOrder
                order = ExecutionOrder(
                    token_address=p["token_address"],
                    chain=p.get("chain", "1"),
                    action="BUY",
                    amount_usd=p["amount_usd"],
                    slippage_tolerance=0.15,
                    gas_premium_gwei=30.0,
                    entry_price_usd=p.get("entry_price_usd"),
                )
                pos = Position(order)
                pos.current_value = p.get("current_value", pos.entry_value)
                pos.peak_value    = p.get("peak_value",    pos.entry_value)
                pos.status        = p.get("status",        "ACTIVE")
                pos.pnl_pct       = p.get("pnl_pct",       0.0)
                pos.last_price_usd = p.get("last_price_usd")
                self.positions[p["token_address"]] = pos
                print(f"   ↩  {p['token_address'][:14]}...  [{pos.status}]  ${pos.current_value:.2f}  {pos.pnl_pct:+.1f}%")
            except Exception as e:
                logger.warning(f"Could not restore position {p.get('token_address','?')[:12]}: {e}")

    def take_position(self, order: ExecutionOrder):
        """Register a new position to monitor."""
        if not order:
            logger.warning("take_position called with None order — skipping.")
            return

        pos = Position(order)
        self.positions[order.token_address] = pos
        self.store.save_position(pos)  # Persist immediately

        print(f"💀 [Reaper] Position opened: {order.token_address[:10]}...")
        print(f"   Entry value : ${order.amount_usd:.2f}")
        print(f"   Take profit : +{self.take_profit_pct:.0f}%")
        print(f"   Stop loss   : {self.stop_loss_pct:.0f}%")
        print(f"   Trailing    : -{self.trailing_stop_pct:.0f}% from peak")

    def _update_position(self, pos: Position) -> str:
        """
        Fetch current price and update position value.
        Returns action: 'hold' | 'free_ride' | 'stop' | 'trail_stop'
        """
        if self.paper_mode or pos.entry_price_usd is None:
            # Paper mode: simulate a random walk for demo purposes
            import random
            drift = random.uniform(-0.05, 0.08)
            pos.current_value = pos.current_value * (1 + drift)
        else:
            # Live mode: fetch real price from DexScreener
            current_price = fetch_token_price_usd(pos.token_address)
            if current_price is None:
                # Fall back to last known price if fetch fails
                if pos.last_price_usd:
                    logger.warning(f"Price fetch failed for {pos.token_address[:10]}... — using last known price.")
                    current_price = pos.last_price_usd
                else:
                    logger.warning(f"No price data at all for {pos.token_address[:10]}... — holding.")
                    return "hold"
            pos.last_price_usd = current_price
            price_ratio = current_price / pos.entry_price_usd
            pos.current_value = pos.entry_value * price_ratio

        # Track peak
        if pos.current_value > pos.peak_value:
            pos.peak_value = pos.current_value

        pos.pnl_pct = ((pos.current_value - pos.entry_value) / pos.entry_value) * 100

        # --- Decision logic ---
        # 1. Stop loss
        if pos.pnl_pct <= self.stop_loss_pct:
            return "stop"

        # 2. Free ride (extract principal at take-profit)
        if pos.pnl_pct >= self.take_profit_pct and pos.status == "ACTIVE":
            return "free_ride"

        # 3. Trailing stop (only after free-ride or if profitable)
        if pos.status == "FREE_RIDE":
            drawdown_from_peak = ((pos.current_value - pos.peak_value) / pos.peak_value) * 100
            if drawdown_from_peak <= -self.trailing_stop_pct:
                return "trail_stop"

        return "hold"

    def _execute_action(self, pos: Position, action: str):
        """Handle triggered actions and persist state."""
        if action == "stop":
            pos.status = "STOPPED"
            print(f"\n💀 [Reaper] ⛔ STOP LOSS hit on {pos.token_address[:10]}...")
            print(f"   PnL: {pos.pnl_pct:.1f}% | Value: ${pos.current_value:.2f}")
            print(f"   Position liquidated.")
            self.store.save_position(pos)

        elif action == "free_ride":
            pos.status = "FREE_RIDE"
            print(f"\n💀 [Reaper] ⚡ FREE RIDE triggered on {pos.token_address[:10]}...")
            print(f"   +{pos.pnl_pct:.1f}% reached. Extracting principal (${pos.entry_value:.2f}).")
            print(f"   Moonbag remains. Trailing stop armed at -{self.trailing_stop_pct:.0f}% from peak.")
            self.store.save_position(pos)

        elif action == "trail_stop":
            pos.status = "CLOSED"
            profit = pos.current_value - pos.entry_value
            print(f"\n💀 [Reaper] 🎯 TRAILING STOP fired on {pos.token_address[:10]}...")
            print(f"   Closed moonbag at ${pos.current_value:.2f} | Profit: +${profit:.2f}")
            self.store.save_position(pos)

        elif action == "hold":
            direction = "📈" if pos.pnl_pct >= 0 else "📉"
            print(
                f"💀 [Reaper] Tick | {pos.token_address[:10]}... | "
                f"${pos.current_value:.2f} | {direction} {pos.pnl_pct:+.1f}%"
            )
            self.store.save_position(pos)  # Persist every tick

    def _monitor_loop(self):
        """Background monitoring loop."""
        print(f"💀 [Reaper] Monitoring started ({'paper' if self.paper_mode else 'live'} mode)")
        while self._monitoring:
            active = [p for p in self.positions.values() if p.status in ("ACTIVE", "FREE_RIDE")]
            if not active:
                print("💀 [Reaper] No active positions. Idling...")
                time.sleep(self.poll_interval)
                continue

            for pos in active:
                action = self._update_position(pos)
                self._execute_action(pos, action)

            time.sleep(self.poll_interval)

        print("💀 [Reaper] Monitoring stopped.")

    def start_monitoring(self):
        """Start background monitoring thread."""
        if self._monitoring:
            logger.warning("Monitoring already running.")
            return
        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop_monitoring(self):
        """Stop the monitoring thread."""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_portfolio_summary(self) -> dict:
        """Return a summary of all positions."""
        summary = {
            "total_positions": len(self.positions),
            "active": 0,
            "free_ride": 0,
            "stopped": 0,
            "closed": 0,
            "total_value_usd": 0.0,
            "total_pnl_pct": 0.0,
        }
        for pos in self.positions.values():
            summary[pos.status.lower().replace(" ", "_")] = (
                summary.get(pos.status.lower().replace(" ", "_"), 0) + 1
            )
            summary["total_value_usd"] += pos.current_value
        return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    reaper = Reaper(
        take_profit_pct=100.0,
        stop_loss_pct=-30.0,
        trailing_stop_pct=15.0,
        poll_interval_sec=2.0,
        paper_mode=True,
    )

    order = ExecutionOrder(
        token_address="0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        chain="1",
        action="BUY",
        amount_usd=100.0,
        slippage_tolerance=0.30,
        gas_premium_gwei=50.0,
        entry_price_usd=None,  # paper mode — will simulate
    )

    reaper.take_position(order)
    reaper.start_monitoring()

    try:
        time.sleep(30)
    except KeyboardInterrupt:
        pass

    reaper.stop_monitoring()
    print("\nPortfolio:", reaper.get_portfolio_summary())
