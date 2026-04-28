"""AI Slinger — plans execution strategy via LLM, builds transactions via existing code.

The existing Slinger code (agents/slinger.py) handles the actual Web3 transaction building.
This wrapper asks the LLM to choose execution parameters (slippage, gas premium, routing)
based on the signal and risk assessment, then passes them to the existing Slinger.
"""

import logging
from typing import Optional
from core.models import TradeSignal, RiskAssessment, ExecutionOrder
from agents.slinger import Slinger as BaseSlinger
from .engine import OllamaEngine as ModelEngine

logger = logging.getLogger("AISlinger")

SLINGER_SYSTEM_PROMPT = """You are the Slinger — the part of a trading machine that moves.

Your job: given a signal and a risk assessment, decide the execution parameters. You don't build transactions — you decide HOW to build them.

Consider:
1. **Slippage** — High for urgent trades (degen), low for precision (arb). Base on the strategy and the volatility of the token.
2. **Gas premium** — High when you need to be first (sniper), low when you can wait (yield). Multiply base gas (~30 gwei) by 1-3x.
3. **Mempool** — Private (Flashbots) for sniper/forensic strategies to avoid MEV. Public is fine for most others.
4. **Position size** — Never exceed the Actuary's max_allocation_usd. For high-risk signals, consider going smaller.
5. **Chain routing** — Most trades route through the native pair (WETH/token). Only mention alternatives if there's a specific reason.

Be decisive. Pick specific numbers. Don't hedge."""


class AISlinger:
    """LLM-enhanced Slinger — plans execution params, builds transactions with existing code."""

    # Strategy-specific defaults as fallback
    STRATEGY_DEFAULTS = {
        "degen": {"slippage": 0.30, "gas_mult": 3.0, "mempool": "public"},
        "sniper": {"slippage": 0.05, "gas_mult": 1.2, "mempool": "private"},
        "shadow_clone": {"slippage": 0.10, "gas_mult": 2.0, "mempool": "public"},
        "arb_hunter": {"slippage": 0.01, "gas_mult": 1.0, "mempool": "private"},
        "oracle_eye": {"slippage": 0.08, "gas_mult": 1.8, "mempool": "public"},
        "liquidity_sentinel": {"slippage": 0.03, "gas_mult": 1.3, "mempool": "public"},
        "yield_alchemist": {"slippage": 0.02, "gas_mult": 1.1, "mempool": "public"},
        "forensic_sniper": {"slippage": 0.02, "gas_mult": 1.0, "mempool": "private"},
    }

    def __init__(self, engine: ModelEngine, base: Optional[BaseSlinger] = None):
        self.engine = engine
        self.base = base or BaseSlinger()

    def plan(self,
             signal: TradeSignal,
             assessment: RiskAssessment,
             strategy: str = "degen") -> Optional[ExecutionOrder]:
        """Plan execution for a signal+assessment pair. Returns ExecutionOrder or None."""
        if not assessment or assessment.risk_level.value == "REJECTED":
            print("[Slinger] Assessment rejected. Standing down.")
            return None

        print(f"\n[Slinger] Planning execution for {signal.token_address[:16]}...")

        defaults = self.STRATEGY_DEFAULTS.get(strategy, self.STRATEGY_DEFAULTS["degen"])

        user_prompt = (
            f"Strategy: {strategy}\n\n"
            f"Signal:\n"
            f"  Token: {signal.token_address}\n"
            f"  Chain: {signal.chain}\n"
            f"  Score: {signal.narrative_score}/100\n\n"
            f"Risk assessment:\n"
            f"  Level: {assessment.risk_level.value}\n"
            f"  Max allocation: ${assessment.max_allocation_usd:.0f}\n"
            f"  Buy tax: {assessment.buy_tax:.1%}\n"
            f"  Sell tax: {assessment.sell_tax:.1%}\n"
            f"  Honeypot: {'yes' if assessment.is_honeypot else 'no'}\n\n"
            f"Strategy defaults:\n"
            f"  Slippage: {defaults['slippage']:.0%}\n"
            f"  Gas multiplier: {defaults['gas_mult']}x\n"
            f"  Mempool: {defaults['mempool']}\n\n"
            f"Return JSON:\n"
            f"  - action: \"BUY\"\n"
            f"  - amount_usd: USD amount to allocate (max ${assessment.max_allocation_usd:.0f})\n"
            f"  - slippage_tolerance: 0-1 float (e.g. 0.15 for 15%)\n"
            f"  - gas_multiplier: 1.0-3.0 float\n"
            f"  - use_private_mempool: true or false\n"
            f"  - reasoning: short sentence\n"
        )

        result = self.engine.chat_structured(SLINGER_SYSTEM_PROMPT, user_prompt)

        if result is None:
            print("[Slinger] Model call failed. Using strategy defaults.")
            return self._plan_from_defaults(signal, assessment, defaults)

        # Parse model output
        amount = result.get("amount_usd", defaults["slippage"])
        if not isinstance(amount, (int, float)) or amount <= 0:
            amount = min(assessment.max_allocation_usd * 0.5, 50.0)

        slippage = result.get("slippage_tolerance", defaults["slippage"])
        if not isinstance(slippage, (int, float)):
            slippage = defaults["slippage"]

        gas_mult = result.get("gas_multiplier", defaults["gas_mult"])
        if not isinstance(gas_mult, (int, float)):
            gas_mult = defaults["gas_mult"]

        use_private = result.get("use_private_mempool", defaults["mempool"] == "private")

        # Apply to the base Slinger
        self.base._strategy_slippage = slippage
        self.base._strategy_gas_multiplier = gas_mult
        self.base._use_private_mempool = use_private

        reasoning = result.get("reasoning", "")
        print(f"[Slinger] Plan: ${amount:.0f} @ {slippage:.0%} slippage, "
              f"{gas_mult:.1f}x gas, {'private' if use_private else 'public'} mempool")
        if reasoning:
            print(f"  {reasoning}")

        # Build the execution order via existing Slinger code
        order = self.base.execute_order(assessment, signal.chain)

        if order:
            order.amount_usd = min(amount, assessment.max_allocation_usd)
            order.slippage_tolerance = slippage
            order.gas_premium_gwei = 30.0 * gas_mult

        return order

    def _plan_from_defaults(self, signal, assessment, defaults) -> ExecutionOrder:
        """Fallback — use strategy defaults."""
        self.base._strategy_slippage = defaults["slippage"]
        self.base._strategy_gas_multiplier = defaults["gas_mult"]
        self.base._use_private_mempool = defaults["mempool"] == "private"
        return self.base.execute_order(assessment, signal.chain)
