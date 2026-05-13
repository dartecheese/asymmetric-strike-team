"""
Whisperer — Social/Smart Money velocity scanning.

Data sources (all free, no API key):
  1. DexScreener /token-profiles/latest  — newly listed/boosted tokens
  2. DexScreener /search                 — trending search queries
  3. DexScreener /token-boosts/top       — paid-boost tokens (narrative signal)
  4. DexScreener /token-boosts/active    — currently active boosts
  5. DexScreener pair liquidity/volume   — volume velocity scoring

Scoring model:
  - Base score from boost activity and new profile listing
  - Volume velocity bonus (24h volume vs liquidity ratio)
  - Freshness bonus (discovered < 5 min ago)
  - Social source multiplier (boosted = more narrative)

Returns the highest-scoring unseen token as a TradeSignal.
"""

import json
import time
import logging
import urllib.request
import urllib.error
from typing import Optional
from core.models import TradeSignal

logger = logging.getLogger("Whisperer")

# Supported chains and their GoPlus chain IDs
SUPPORTED_CHAINS = {
    "ethereum": "1",
    "bsc": "56",
    "arbitrum": "42161",
    "base": "8453",
    "solana": None,   # Not EVM — skip for now
    "polygon": "137",
}

DEXSCREENER_BASE = "https://api.dexscreener.com"


def _get(url: str, timeout: int = 8) -> Optional[dict]:
    """Simple GET with error handling."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AsymmetricStrikeTeam/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning(f"GET {url} failed: {e}")
        return None


def _score_pair(pair: dict) -> float:
    """
    Score a DEX pair for momentum/velocity.
    Higher = more interesting.
    """
    score = 0.0

    # Volume velocity: 24h volume / liquidity (how fast is it being traded relative to pool size)
    vol_24h = float((pair.get("volume") or {}).get("h24", 0) or 0)
    liquidity = float((pair.get("liquidity") or {}).get("usd", 1) or 1)
    velocity = vol_24h / max(liquidity, 1)
    score += min(velocity * 10, 40)  # Cap at 40 pts

    # Price change bonuses
    h1_change = abs(float((pair.get("priceChange") or {}).get("h1", 0) or 0))
    h6_change = abs(float((pair.get("priceChange") or {}).get("h6", 0) or 0))
    score += min(h1_change, 20)   # Cap at 20 pts
    score += min(h6_change / 2, 10)  # Cap at 10 pts

    # Freshness: pairs created recently get a bonus
    created_at = pair.get("pairCreatedAt")
    if created_at:
        age_hours = (time.time() * 1000 - created_at) / 3_600_000
        if age_hours < 1:
            score += 20
        elif age_hours < 6:
            score += 10
        elif age_hours < 24:
            score += 5

    # Liquidity floor — ignore dust pools
    if liquidity < 10_000:
        score -= 50

    return score


class Whisperer:
    """
    The Whisperer: Real DexScreener-based signal scanner.
    Combines token profile listings, boost activity, and pair velocity
    to surface high-momentum tokens for the Actuary to assess.
    """

    def __init__(self, min_velocity_score: int = 50, min_liquidity_usd: float = 10_000):
        self.seen_tokens: set = set()
        self.min_velocity_score = min_velocity_score
        self.min_liquidity_usd = min_liquidity_usd

    def _fetch_new_profiles(self) -> list[dict]:
        """Fetch newly updated token profiles from DexScreener."""
        data = _get(f"{DEXSCREENER_BASE}/token-profiles/latest/v1")
        if not data or not isinstance(data, list):
            return []
        return [
            p for p in data
            if p.get("chainId") in SUPPORTED_CHAINS
            and SUPPORTED_CHAINS[p["chainId"]] is not None  # EVM only
        ]

    def _fetch_boosted_tokens(self) -> list[dict]:
        """Fetch top boosted tokens — paid attention = narrative signal."""
        # /active/v1 is deprecated (404), use /top/v1
        data = _get(f"{DEXSCREENER_BASE}/token-boosts/top/v1")
        if not data or not isinstance(data, list):
            return []
        return [
            p for p in data
            if p.get("chainId") in SUPPORTED_CHAINS
            and SUPPORTED_CHAINS[p["chainId"]] is not None
        ]

    def _fetch_pair_data(self, chain_id: str, token_address: str) -> Optional[dict]:
        """Fetch pair data for a specific token to get volume/liquidity metrics."""
        data = _get(f"{DEXSCREENER_BASE}/latest/dex/tokens/{token_address}")
        if not data:
            return None
        pairs = data.get("pairs") or []
        # Filter to matching chain and minimum liquidity
        chain_pairs = [
            p for p in pairs
            if p.get("chainId") in SUPPORTED_CHAINS
            and float((p.get("liquidity") or {}).get("usd", 0) or 0) >= self.min_liquidity_usd
        ]
        if not chain_pairs:
            return None
        # Return the highest-liquidity pair
        return max(chain_pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0))

    def _build_reasoning(self, profile: dict, pair: Optional[dict], score: float, source: str) -> str:
        parts = [f"Source: {source} | Score: {score:.0f}"]
        if pair:
            vol = (pair.get("volume") or {}).get("h24", 0)
            liq = (pair.get("liquidity") or {}).get("usd", 0)
            h1 = (pair.get("priceChange") or {}).get("h1", 0)
            parts.append(f"24h Vol: ${float(vol or 0):,.0f} | Liq: ${float(liq or 0):,.0f} | 1h Δ: {h1}%")
        desc = (profile.get("description") or "")[:120]
        if desc:
            parts.append(f"Desc: {desc}")
        return " | ".join(parts)

    def scan_firehose(self) -> Optional[TradeSignal]:
        """
        Main scan loop. Returns the best unseen signal found, or None.
        """
        print("🗣️  [Whisperer] Scanning DexScreener for velocity spikes and narrative signals...")

        candidates: list[dict] = []  # {token_address, chain_id, score, profile, pair, source}

        # --- Source 1: New token profiles ---
        profiles = self._fetch_new_profiles()
        logger.info(f"New profiles found: {len(profiles)}")

        for profile in profiles:
            addr = profile.get("tokenAddress", "")
            chain = profile.get("chainId", "")
            chain_id = SUPPORTED_CHAINS.get(chain)
            if not addr or not chain_id or addr in self.seen_tokens:
                continue

            pair = self._fetch_pair_data(chain_id, addr)
            score = _score_pair(pair) + 10 if pair else 5  # Bonus for having a pair at all

            candidates.append({
                "token_address": addr,
                "chain_id": chain_id,
                "score": score,
                "profile": profile,
                "pair": pair,
                "source": "new_profile",
            })

        # --- Source 2: Boosted tokens (paid attention = narrative) ---
        boosted = self._fetch_boosted_tokens()
        logger.info(f"Boosted tokens found: {len(boosted)}")

        for profile in boosted:
            addr = profile.get("tokenAddress", "")
            chain = profile.get("chainId", "")
            chain_id = SUPPORTED_CHAINS.get(chain)
            if not addr or not chain_id or addr in self.seen_tokens:
                continue

            # Check if already in candidates from profiles
            existing = next((c for c in candidates if c["token_address"].lower() == addr.lower()), None)
            if existing:
                existing["score"] += 15  # Boost score if it appears in both sources
                existing["source"] = "new_profile+boost"
                continue

            pair = self._fetch_pair_data(chain_id, addr)
            boost_amount = float(profile.get("totalAmount", 0) or 0)
            score = _score_pair(pair) + 15 + min(boost_amount / 100, 15) if pair else 15

            candidates.append({
                "token_address": addr,
                "chain_id": chain_id,
                "score": score,
                "profile": profile,
                "pair": pair,
                "source": "boost",
            })

        if not candidates:
            print("🗣️  [Whisperer] No new EVM candidates found this scan.")
            return None

        # --- Rank and pick the best ---
        candidates.sort(key=lambda c: c["score"], reverse=True)
        best = candidates[0]

        # Filter out low-score noise (inclusive — score equal to threshold is accepted)
        if best["score"] < self.min_velocity_score:
            print(f"🗣️  [Whisperer] Best candidate score {best['score']:.0f} below threshold {self.min_velocity_score}. Skipping.")
            return None

        # Mark as seen
        self.seen_tokens.add(best["token_address"])

        narrative_score = min(int(best["score"]), 100)
        reasoning = self._build_reasoning(best["profile"], best["pair"], best["score"], best["source"])

        print(f"🗣️  [Whisperer] 🚨 SIGNAL: {best['token_address'][:12]}... on chain {best['chain_id']}")
        print(f"   Score: {narrative_score} | {best['source']}")
        if best["pair"]:
            vol = (best["pair"].get("volume") or {}).get("h24", "?")
            liq = (best["pair"].get("liquidity") or {}).get("usd", "?")
            h1 = (best["pair"].get("priceChange") or {}).get("h1", "?")
            print(f"   24h Vol: ${float(vol or 0):,.0f} | Liq: ${float(liq or 0):,.0f} | 1h: {h1}%")

        return TradeSignal(
            token_address=best["token_address"],
            chain=best["chain_id"],
            narrative_score=narrative_score,
            reasoning=reasoning,
            discovered_at=time.time(),
        )

    def scan_top_n(self, n: int = 5) -> list[TradeSignal]:
        """
        Return the top N signals from this scan (for multi-position strategies).
        """
        print(f"🗣️  [Whisperer] Scanning for top {n} signals...")
        signals = []
        # Temporarily allow re-scanning seen tokens for multi-signal use
        original_seen = set(self.seen_tokens)

        profiles = self._fetch_new_profiles()
        boosted = self._fetch_boosted_tokens()
        all_profiles = {p.get("tokenAddress", ""): p for p in profiles + boosted}

        candidates = []
        for addr, profile in all_profiles.items():
            chain = profile.get("chainId", "")
            chain_id = SUPPORTED_CHAINS.get(chain)
            if not addr or not chain_id:
                continue
            pair = self._fetch_pair_data(chain_id, addr)
            score = _score_pair(pair) if pair else 0
            candidates.append({"token_address": addr, "chain_id": chain_id, "score": score, "profile": profile, "pair": pair, "source": "scan_top_n"})

        candidates.sort(key=lambda c: c["score"], reverse=True)

        for c in candidates[:n]:
            if c["score"] < 10:
                continue
            self.seen_tokens.add(c["token_address"])
            signals.append(TradeSignal(
                token_address=c["token_address"],
                chain=c["chain_id"],
                narrative_score=min(int(c["score"]), 100),
                reasoning=self._build_reasoning(c["profile"], c["pair"], c["score"], c["source"]),
                discovered_at=time.time(),
            ))

        return signals


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    w = Whisperer(min_velocity_score=10)
    signal = w.scan_firehose()
    if signal:
        print(f"\n✅ Signal: {signal.token_address} | Chain: {signal.chain} | Score: {signal.narrative_score}")
        print(f"   {signal.reasoning}")
    else:
        print("\n❌ No signal found.")
