"""Bull/Bear researcher — adapted from TradingAgents' structured debate.

One round only (TradingAgents allows N; AST caps to 1 to keep per-signal token
cost bounded). Three calls:
  1. Bull researcher: argues entry, given signal + risk + memory of past trades
  2. Bear researcher: argues against, given the same context plus the bull case
  3. Manager: synthesizes both into an EntryRating + confidence + reasoning

Runs between Actuary and Slinger. A STRONG_AVOID verdict vetoes the trade; a
BUY/STRONG_BUY scales position size via EntryRating.size_multiplier on top of
Actuary's max_allocation_usd.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from core.models import TradeSignal, RiskAssessment
from .engine import OllamaEngine as ModelEngine
from .rating import EntryRating, parse_rating
from .memory import recall_similar, format_for_prompt

logger = logging.getLogger("Researcher")

BULL_SYSTEM = """You are the Bull Researcher in a trading committee.

Your job: argue the strongest case for entering this trade, in 2-3 specific bullets.
Ground your case in the actual signal and risk data — do not invent numbers.
Past comparable trades and their realized outcomes are provided; weigh them.

Be assertive but honest. If the bull case is weak, say it's weak — do not fabricate."""

BEAR_SYSTEM = """You are the Bear Researcher in a trading committee.

Your job: argue against entering this trade, in 2-3 specific bullets.
You have just heard the Bull case. Address its strongest claims directly.
Past comparable trades and their realized outcomes are provided; weigh them.

Be assertive but honest. If you cannot find a real bear case, say so — do not fabricate."""

MANAGER_SYSTEM = """You are the Research Manager. Bull and Bear have presented their cases.

Decide an EntryRating: STRONG_BUY, BUY, HOLD, AVOID, or STRONG_AVOID.

Decision rules:
  - STRONG_BUY: bull case is concrete and bear case is weak/refuted
  - BUY: bull case is real but bear case has legitimate concerns
  - HOLD: cases are balanced and there is no clear edge — do not enter
  - AVOID: bear case clearly outweighs bull
  - STRONG_AVOID: bear case identifies a likely loss or honeypot-tier risk; veto

Past comparable trades and their realized outcomes are in the context — if a
strategy/chain combo has a poor track record, weight toward AVOID.

Return ONLY JSON. No prose outside the JSON."""


@dataclass
class ResearcherVerdict:
    rating: EntryRating
    confidence: int  # 0-100
    bull_summary: str
    bear_summary: str
    reasoning: str

    @property
    def is_entry(self) -> bool:
        return self.rating.is_entry

    @property
    def is_veto(self) -> bool:
        return self.rating.is_veto

    @property
    def size_multiplier(self) -> float:
        return self.rating.size_multiplier


def _format_context(signal: TradeSignal, assessment: RiskAssessment,
                    strategy: str, memory_block: str) -> str:
    return (
        f"Strategy: {strategy}\n"
        f"Token: {signal.token_address}\n"
        f"Chain: {signal.chain}\n"
        f"Narrative score: {signal.narrative_score}/100\n"
        f"Whisperer reasoning: {signal.reasoning}\n\n"
        f"Risk assessment:\n"
        f"  Level: {assessment.risk_level.value}\n"
        f"  Honeypot: {assessment.is_honeypot}\n"
        f"  Buy tax: {assessment.buy_tax:.1%}\n"
        f"  Sell tax: {assessment.sell_tax:.1%}\n"
        f"  Liquidity locked: {assessment.liquidity_locked}\n"
        f"  Max allocation: ${assessment.max_allocation_usd:.0f}\n"
        f"  Warnings: {'; '.join(assessment.warnings) or 'none'}\n\n"
        f"Past comparable decisions (most recent first):\n{memory_block}\n"
    )


class Researcher:
    """Bull/Bear/Manager debate. One round, three model calls."""

    def __init__(self, engine: ModelEngine, use_memory: bool = True):
        self.engine = engine
        self.use_memory = use_memory

    def deliberate(self,
                   signal: TradeSignal,
                   assessment: RiskAssessment,
                   strategy: str = "degen") -> Optional[ResearcherVerdict]:
        """Run the debate. Returns None on engine failure (caller decides)."""
        if not signal or not assessment:
            return None

        print("\n[Researcher] Bull/Bear deliberation...")

        memory_block = "  (memory disabled)"
        if self.use_memory:
            past = recall_similar(strategy=strategy, chain=signal.chain, limit=5)
            memory_block = format_for_prompt(past)

        context = _format_context(signal, assessment, strategy, memory_block)

        # --- Bull ---
        bull_prompt = (
            context
            + "\nMake the bull case in 2-3 concrete bullets. "
            "Plain text, no JSON."
        )
        bull = self.engine.chat(BULL_SYSTEM, bull_prompt,
                                temperature=0.4, max_tokens=300)
        if not bull:
            logger.warning("Bull researcher: engine returned nothing")
            return None
        bull = bull.strip()
        print(f"[Researcher]   Bull: {bull[:140].replace(chr(10), ' ')}...")

        # --- Bear ---
        bear_prompt = (
            context
            + f"\nThe Bull just argued:\n{bull}\n\n"
            "Make the bear case in 2-3 concrete bullets, addressing the bull "
            "directly. Plain text, no JSON."
        )
        bear = self.engine.chat(BEAR_SYSTEM, bear_prompt,
                                temperature=0.4, max_tokens=300)
        if not bear:
            logger.warning("Bear researcher: engine returned nothing")
            return None
        bear = bear.strip()
        print(f"[Researcher]   Bear: {bear[:140].replace(chr(10), ' ')}...")

        # --- Manager synthesizes ---
        mgr_prompt = (
            context
            + f"\nBull case:\n{bull}\n\nBear case:\n{bear}\n\n"
            "Return JSON:\n"
            "  - rating: \"STRONG_BUY\" | \"BUY\" | \"HOLD\" | \"AVOID\" | \"STRONG_AVOID\"\n"
            "  - confidence: 0-100\n"
            "  - reasoning: one sentence justifying the rating\n"
        )
        result = self.engine.chat_structured(MANAGER_SYSTEM, mgr_prompt,
                                             temperature=0.2)
        if result is None:
            logger.warning("Manager: structured call failed; defaulting to HOLD")
            return ResearcherVerdict(
                rating=EntryRating.HOLD,
                confidence=0,
                bull_summary=bull,
                bear_summary=bear,
                reasoning="manager call failed; defaulting to HOLD",
            )

        rating = parse_rating(result.get("rating", "HOLD"))
        confidence = int(result.get("confidence", 0) or 0)
        confidence = max(0, min(100, confidence))
        reasoning = (result.get("reasoning") or "").strip() or "no reasoning"

        print(f"[Researcher] Verdict: {rating.value} (conf {confidence})")
        print(f"  {reasoning}")

        return ResearcherVerdict(
            rating=rating,
            confidence=confidence,
            bull_summary=bull,
            bear_summary=bear,
            reasoning=reasoning,
        )
