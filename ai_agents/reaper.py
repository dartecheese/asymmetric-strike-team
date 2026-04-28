"""AI Reaper — monitors positions and decides exits via LLM, with rules-based fallback.

The existing Reaper code (agents/reaper.py) handles price polling and position tracking.
This wrapper adds LLM-based exit reasoning on top — should we hold, tighten stops,
take profit, or cut losses given current market conditions?
"""

import time
import logging
from typing import Optional
from core.models import ExecutionOrder
from agents.reaper import Reaper as BaseReaper, fetch_token_price_usd
from .engine import OllamaEngine as ModelEngine

logger = logging.getLogger("AIReaper")

REAPER_SYSTEM_PROMPT = """You are the Reaper — the part of a trading machine that tends positions.

Your job: given a position's current state and the market conditions, decide what to do. You are disciplined, not greedy. You think in terms of expected value, not hope.

Rules you never break:
1. If P&L is below -30%, close immediately. No exceptions.
2. If P&L is above +100%, extract principal. Let the runner stay.
3. After principal is extracted, if position drops 15% from peak, close remaining.
4. P&L between -30% and +100% is a decision zone — hold, tighten, or exit based on market conditions.

Within the decision zone, consider:
- **Volume trend** — Is the token losing volume? Exit earlier.
- **Time held** — Holding for hours with no movement? Weak signal.
- **General market** — Is the broader market (BTC/ETH) selling off? Be more aggressive on exits.
- **Strategy fit** — Degen strategies hold longer. Sniper strategies exit faster.

Return a clear decision. Don't be emotional."""


class AIReaper:
    """LLM-enhanced Reaper — monitors positions, decides exits."""

    def __init__(self, engine: ModelEngine, base: Optional[BaseReaper] = None):
        self.engine = engine
        self.base = base or BaseReaper()

    def check_position(self,
                       order: ExecutionOrder,
                       strategy: str = "degen") -> dict:
        """Check a single position. Returns decision dict.

        Returns:
            {"action": "hold"|"close"|"extract_principal"|"tighten_stop",
             "reasoning": "...",
             "prices": {...}}
        """
        if not order:
            return {"action": "hold", "reasoning": "No position", "prices": {}}

        token = order.token_address
        entry = order.entry_price_usd or 0

        # Fetch current price
        current_price = fetch_token_price_usd(token)

        prices = {
            "entry": entry,
            "current": current_price,
            "pnl_pct": None,
            "peak_pnl_pct": None,
        }

        if not current_price or not entry or entry <= 0:
            print(f"[Reaper] No price data for {token[:16]}. Holding.")
            return {"action": "hold", "reasoning": "No price data", "prices": prices}

        pnl_pct = ((current_price - entry) / entry) * 100

        print(f"\n[Reaper] Checking {token[:16]}...")
        print(f"  Entry: ${entry:.8f} → Current: ${current_price:.8f} ({pnl_pct:+.1f}%)")

        # --- Hard rules (never broken) ---
        if pnl_pct <= -30:
            print(f"[Reaper] STOP LOSS: {pnl_pct:.1f}% below -30%. Closing.")
            return {"action": "close", "reasoning": f"Stop loss triggered at {pnl_pct:.1f}%", "prices": prices}

        if pnl_pct >= 100:
            print(f"[Reaper] FREE RIDE: {pnl_pct:.1f}% above +100%. Extracting principal.")
            return {"action": "extract_principal", "reasoning": f"Free ride at {pnl_pct:.1f}%", "prices": prices}

        # --- Decision zone: ask the LLM ---
        user_prompt = (
            f"Strategy: {strategy}\n\n"
            f"Position:\n"
            f"  Token: {token}\n"
            f"  Entry: ${entry:.8f}\n"
            f"  Current: ${current_price:.8f}\n"
            f"  P&L: {pnl_pct:+.1f}%\n"
            f"  Amount at risk: ${order.amount_usd:.0f}\n\n"
            f"Return JSON:\n"
            f"  - action: \"hold\" | \"close\" | \"tighten_stop\"\n"
            f"  - reasoning: one-sentence why\n"
            f"  - confidence: 0-100\n"
        )

        result = self.engine.chat_structured(REAPER_SYSTEM_PROMPT, user_prompt)

        if result is None:
            print(f"[Reaper] Model call failed. Holding at {pnl_pct:+.1f}% (decision zone).")
            return {"action": "hold", "reasoning": "Model unavailable, holding position",
                    "prices": prices}

        action = result.get("action", "hold")
        reasoning = result.get("reasoning", "")
        confidence = result.get("confidence", 50)

        print(f"[Reaper] Decision: {action} (confidence: {confidence})")
        if reasoning:
            print(f"  {reasoning}")

        return {"action": action, "reasoning": reasoning, "prices": prices, "confidence": confidence}
