"""AI Actuary — assesses signal risk via GoPlus, then asks the LLM to reason about it.

The existing Actuary code (agents/actuary.py) handles GoPlus data fetching.
This wrapper passes the raw risk data to the model and asks it to make
a nuanced risk decision — not just a binary pass/fail.
"""

import logging
from typing import Optional
from typing import Optional
from core.models import TradeSignal, RiskAssessment, RiskLevel
from .engine import OllamaEngine as ModelEngine

logger = logging.getLogger("AIActuary")

ACTUARY_SYSTEM_PROMPT = """You are the Actuary — the part of a trading machine that thinks before it acts.

Your job: look at security data for a proposed trade and decide the risk level. You are conservative by nature.

KEY RULES:
1. **LOW risk** = safe to trade. The token looks good. Set max_allocation_usd high.
2. **MEDIUM risk** = caution warranted. Set a modest max_allocation_usd.
3. **HIGH risk** = dangerous but not impossible. Set max_allocation_usd low.
4. **REJECTED** = do NOT trade. Set max_allocation_usd to 0. Only REJECT if honeypot or critical failure.

Evaluate each factor:
- **Honeypot**: yes → automatic REJECT. No exceptions.
- **Buy tax**: 0% is ideal. >10% reduces entry size.
- **Sell tax**: 0% is ideal. >10% makes exits painful.
- **Liquidity locked**: yes → strong positive. **no → this is a serious concern.** Unlocked liquidity means the developer can rug.
- **Strategy context**: more aggressive strategies (degen, sniper) accept higher risk. But clean tokens are still preferred.

Return your assessment as structured JSON. Be specific. Don't hedge — make a call."""


class AIActuary:
    """LLM-enhanced Actuary — fetches risk data via existing code, reasons via model."""

    def __init__(self, engine: ModelEngine, base=None):
        self.engine = engine
        # Import lazily to avoid circular issues
        from agents.actuary import Actuary as BaseActuary
        self.base = base or BaseActuary()

    def assess(self, signal: TradeSignal, strategy: str = "degen") -> Optional[RiskAssessment]:
        """Assess a single signal. Returns RiskAssessment or None (skip)."""
        if not signal:
            return None

        print(f"\n[Actuary] Assessing {signal.token_address[:16]}...")

        # Step 1: Get base risk data from existing Actuary code
        token_data = self.base._fetch_goplus(signal.chain, signal.token_address)

        if token_data:
            parsed = self.base._parse_token_data(token_data)
            is_honeypot = parsed["is_honeypot"]
            buy_tax = parsed["buy_tax"]
            sell_tax = parsed["sell_tax"]
            liquidity_locked = parsed["liquidity_locked"]
            print(f"[Actuary] GoPlus: honeypot={'yes' if is_honeypot else 'no'}, "
                  f"buy_tax={buy_tax:.1%}, sell_tax={sell_tax:.1%}, "
                  f"locked={'yes' if liquidity_locked else 'no'}")
        else:
            from agents.actuary import CONSERVATIVE_FALLBACK
            fb = CONSERVATIVE_FALLBACK
            is_honeypot = fb["is_honeypot"]
            buy_tax = fb["buy_tax"]
            sell_tax = fb["sell_tax"]
            liquidity_locked = fb["liquidity_locked"]
            print("[Actuary] GoPlus unavailable. Using conservative defaults.")

        # Step 2: Call the model for risk reasoning
        user_prompt = (
            f"Strategy: {strategy}\n\n"
            f"Signal:\n"
            f"  Token: {signal.token_address}\n"
            f"  Chain: {signal.chain}\n"
            f"  Score: {signal.narrative_score}/100\n"
            f"  Reasoning: {signal.reasoning}\n\n"
            f"Risk data:\n"
            f"  Honeypot: {'yes' if is_honeypot else 'no'}\n"
            f"  Buy tax: {buy_tax:.1%}\n"
            f"  Sell tax: {sell_tax:.1%}\n"
            f"  Liquidity locked: {'yes' if liquidity_locked else 'no'}\n\n"
            f"Return JSON:\n"
            f"  - risk_level: \"LOW\" | \"MEDIUM\" | \"HIGH\" | \"REJECTED\"\n"
            f"  - max_allocation_usd: max USD to risk (0 if rejected)\n"
            f"  - reasoning: short sentence explaining the call\n"
            f"  - warnings: list of concerns (or empty list)\n"
        )

        result = self.engine.chat_structured(ACTUARY_SYSTEM_PROMPT, user_prompt)

        if result is None:
            print("[Actuary] Model call failed. Using conservative fallback.")
            return self._fallback(signal)

        # Parse model output
        risk_str = result.get("risk_level", "REJECTED")
        try:
            risk_level = RiskLevel(risk_str)
        except ValueError:
            risk_level = RiskLevel.HIGH

        max_alloc = result.get("max_allocation_usd", 0)
        if not isinstance(max_alloc, (int, float)):
            max_alloc = 0

        warnings = result.get("warnings", [])
        reasoning = result.get("reasoning", "No reasoning provided")

        print(f"[Actuary] Risk: {risk_level.value} | Max: ${max_alloc:.0f}")
        print(f"  {reasoning}")
        if warnings:
            for w in warnings:
                print(f"  ⚠ {w}")

        return RiskAssessment(
            token_address=signal.token_address,
            is_honeypot=is_honeypot,
            buy_tax=buy_tax,
            sell_tax=sell_tax,
            liquidity_locked=liquidity_locked,
            risk_level=risk_level,
            max_allocation_usd=max_alloc,
            warnings=warnings or [reasoning],
        )

    def _fallback(self, signal: TradeSignal) -> RiskAssessment:
        """Fallback when the model is unavailable."""
        from agents.actuary import CONSERVATIVE_FALLBACK
        fb = CONSERVATIVE_FALLBACK
        return RiskAssessment(
            token_address=signal.token_address,
            is_honeypot=fb["is_honeypot"],
            buy_tax=fb["buy_tax"],
            sell_tax=fb["sell_tax"],
            liquidity_locked=fb["liquidity_locked"],
            risk_level=RiskLevel.HIGH,
            max_allocation_usd=10.0,  # Tiny allocation when uncertain
            warnings=["Conservative fallback — model unavailable"],
        )
