"""5-tier entry rating shared by the researcher debate and the critic reflection.

Modeled on TradingAgents' rating scale, adapted for crypto entry decisions
(not portfolio rotation). STRONG_AVOID is the explicit veto — distinct from
RiskLevel.REJECTED, which is a safety-gate veto.
"""

from enum import Enum


class EntryRating(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"          # do not enter; not actively bearish
    AVOID = "AVOID"        # actively bearish; skip
    STRONG_AVOID = "STRONG_AVOID"  # hard veto from researcher debate

    @property
    def is_entry(self) -> bool:
        return self in (EntryRating.STRONG_BUY, EntryRating.BUY)

    @property
    def is_veto(self) -> bool:
        return self in (EntryRating.AVOID, EntryRating.STRONG_AVOID)

    @property
    def size_multiplier(self) -> float:
        """How much of Actuary's max_allocation_usd to deploy."""
        return {
            EntryRating.STRONG_BUY: 1.0,
            EntryRating.BUY: 0.6,
            EntryRating.HOLD: 0.0,
            EntryRating.AVOID: 0.0,
            EntryRating.STRONG_AVOID: 0.0,
        }[self]


def parse_rating(raw: str) -> EntryRating:
    """Parse a model's rating string with reasonable forgiveness."""
    if not raw:
        return EntryRating.HOLD
    s = raw.strip().upper().replace(" ", "_").replace("-", "_")
    try:
        return EntryRating(s)
    except ValueError:
        # Common model variants
        if s in ("BUY_STRONG", "STRONGBUY"):
            return EntryRating.STRONG_BUY
        if s in ("AVOID_STRONG", "STRONGAVOID", "VETO", "REJECT"):
            return EntryRating.STRONG_AVOID
        if s in ("SELL", "BEARISH"):
            return EntryRating.AVOID
        if s in ("NEUTRAL", "WAIT", "PASS"):
            return EntryRating.HOLD
        return EntryRating.HOLD
