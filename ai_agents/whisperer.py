"""AI Whisperer — fetches DexScreener data, then asks the LLM to reason about it.

The existing Whisperer code (agents/whisperer.py) handles the data fetching.
This wrapper takes the raw signals it finds, feeds them to the model,
and asks the model to rank and justify the best signal.
"""

import time
import logging
from typing import Optional
from core.models import TradeSignal
from agents.whisperer import Whisperer as BaseWhisperer
from .engine import OllamaEngine as ModelEngine

logger = logging.getLogger("AIWhisperer")

WHISPERER_SYSTEM_PROMPT = """You are the Whisperer — the part of a trading machine that reads the news.

Your job: look at raw market signals from DexScreener and identify which tokens are worth pursuing. You are not a trader — you are a scout. You bring back intelligence and let others decide what to do with it.

Evaluate signals on:
1. **Momentum** — Is volume high relative to liquidity? That means real money moving.
2. **Freshness** — Tokens under an hour old haven't been picked over. Fresh meat.
3. **Narrative** — Boosted tokens have paid attention. Someone thinks this is worth shouting about.
4. **Substance** — Does it have real liquidity (>$10k)? Is the chain active?
5. **Suspicion** — Extremely new tokens with massive boosts but no liquidity are suspicious.

Be honest. If nothing is interesting, say so. Don't force a signal."""


class AIWhisperer:
    """LLM-enhanced Whisperer — fetches data via existing code, reasons via model."""

    def __init__(self, engine: ModelEngine, base: Optional[BaseWhisperer] = None):
        self.engine = engine
        self.base = base or BaseWhisperer()

    def scan(self, strategy: str = "degen") -> Optional[TradeSignal]:
        """Run one full scan. Returns the best signal, or None."""
        print("\n[Whisperer] Scanning DexScreener...")

        # Step 1: Fetch raw signals via existing code
        signals = self.base.scan_top_n(n=10)
        if not signals:
            print("[Whisperer] No raw signals from DexScreener.")
            return None

        print(f"[Whisperer] Found {len(signals)} raw candidates. Calling model for reasoning...")

        # Step 2: Build a prompt with the raw data
        candidates_text = ""
        for i, sig in enumerate(signals, 1):
            candidates_text += (
                f"\nCandidate {i}:\n"
                f"  Token: {sig.token_address[:16]}...\n"
                f"  Chain: {sig.chain}\n"
                f"  Raw score: {sig.narrative_score}\n"
                f"  Reasoning: {sig.reasoning}\n"
            )

        user_prompt = (
            f"You are running the '{strategy}' strategy.\n\n"
            f"Here are the raw candidates from DexScreener:\n{candidates_text}\n\n"
            f"Analyze these candidates and pick the single best one.\n"
            f"Return JSON with:\n"
            f"  - selected: index of the best candidate (1-{len(signals)}), or null if none\n"
            f"  - confidence: 0-100 how confident you are in this pick\n"
            f"  - reasoning: one-sentence why this one\n"
            f"  - concerns: one-sentence what to watch out for, or null\n"
        )

        result = self.engine.chat_structured(WHISPERER_SYSTEM_PROMPT, user_prompt)
        if result is None:
            print("[Whisperer] Model call failed. Falling back to highest-scored raw signal.")
            return signals[0]

        selected_idx = result.get("selected")
        if selected_idx is None:
            print("[Whisperer] Model returned no selection.")
            return None

        try:
            idx = int(selected_idx) - 1
            if idx < 0 or idx >= len(signals):
                print(f"[Whisperer] Model returned out-of-range index {selected_idx}. Using top signal.")
                return signals[0]

            selected = signals[idx]
            # Enhance reasoning with model's analysis
            enhanced_reasoning = (
                f"{selected.reasoning}\n"
                f"Model analysis: {result.get('reasoning', '')}"
            )
            if result.get("concerns"):
                enhanced_reasoning += f"\nConcerns: {result['concerns']}"

            print(f"[Whisperer] Selected candidate #{selected_idx} (confidence: {result.get('confidence', '?')})")
            print(f"  Reasoning: {result.get('reasoning', '')}")

            return TradeSignal(
                token_address=selected.token_address,
                chain=selected.chain,
                narrative_score=result.get("confidence", selected.narrative_score),
                reasoning=enhanced_reasoning,
                discovered_at=time.time(),
            )

        except (ValueError, IndexError):
            print(f"[Whisperer] Bad index from model. Using top signal.")
            return signals[0]
