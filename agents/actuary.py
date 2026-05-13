import json
import urllib.request
import urllib.error
import logging
import time
from typing import Optional
from core.models import TradeSignal, RiskAssessment, RiskLevel

logger = logging.getLogger("Actuary")

# Fallback used when GoPlus API is unavailable
CONSERVATIVE_FALLBACK = {
    "is_honeypot": False,
    "buy_tax": 0.05,   # Assume 5% tax (cautious)
    "sell_tax": 0.05,
    "liquidity_locked": False,
    "source": "fallback"
}

class Actuary:
    """
    The Actuary: Fast heuristic risk assessment.
    Uses GoPlus API to detect honeypots, high taxes, and locked liquidity.
    Falls back to conservative defaults if the API is unavailable.
    """
    def __init__(self, max_allowed_tax: float = 0.20, api_timeout: int = 8, retries: int = 2):
        self.max_allowed_tax = max_allowed_tax
        self.api_timeout = api_timeout
        self.retries = retries
        self._cache: dict = {}  # Simple in-process cache: address -> (timestamp, result)
        self._cache_ttl = 300   # 5 minutes

    def _fetch_goplus(self, chain_id: str, token_address: str) -> Optional[dict]:
        """Call GoPlus API with retries. Returns raw token data dict or None."""
        url = (
            f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
            f"?contract_addresses={token_address}"
        )
        for attempt in range(1, self.retries + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AsymmetricStrikeTeam/1.0"})
                with urllib.request.urlopen(req, timeout=self.api_timeout) as resp:
                    data = json.loads(resp.read().decode())
                if data.get("code") != 1:
                    logger.warning(f"GoPlus non-success code: {data.get('message')}")
                    return None
                result = data.get("result", {})
                # GoPlus keys by lowercased address
                token_data = result.get(token_address.lower()) or result.get(token_address)
                return token_data
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                logger.warning(f"GoPlus attempt {attempt}/{self.retries} failed: {e}")
                if attempt < self.retries:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"GoPlus unexpected error: {e}")
                return None
        return None

    def _parse_token_data(self, token_data: dict) -> dict:
        """Parse raw GoPlus token data into normalised fields."""
        is_honeypot = token_data.get("is_honeypot", "0") == "1"
        is_open_source = token_data.get("is_open_source", "0") == "1"
        liquidity_locked = token_data.get("lp_holders") is not None  # rough proxy

        def safe_float(val, default=0.0) -> float:
            try:
                return float(val) if val not in (None, "", "null") else default
            except (ValueError, TypeError):
                return default

        buy_tax = safe_float(token_data.get("buy_tax"), 0.0)
        sell_tax = safe_float(token_data.get("sell_tax"), 0.0)

        return {
            "is_honeypot": is_honeypot,
            "buy_tax": buy_tax,
            "sell_tax": sell_tax,
            "liquidity_locked": liquidity_locked,
            "is_open_source": is_open_source,
            "source": "goplus"
        }

    def _build_assessment(self, token_address: str, parsed: dict) -> RiskAssessment:
        """Turn parsed token data into a RiskAssessment."""
        warnings = []
        source_tag = "" if parsed["source"] == "goplus" else " [⚠️ FALLBACK DATA]"

        if parsed["source"] == "fallback":
            warnings.append("GoPlus API unavailable — using conservative fallback values.")

        if parsed["is_honeypot"]:
            warnings.append("CRITICAL: HONEYPOT DETECTED.")
        if parsed["buy_tax"] > 0.10:
            warnings.append(f"High buy tax: {parsed['buy_tax']*100:.1f}%")
        if parsed["sell_tax"] > 0.10:
            warnings.append(f"High sell tax: {parsed['sell_tax']*100:.1f}%")
        if not parsed["liquidity_locked"]:
            warnings.append("Liquidity lock unconfirmed.")

        # Determine risk level
        hard_reject = (
            parsed["is_honeypot"]
            or parsed["sell_tax"] > self.max_allowed_tax
            or parsed["buy_tax"] > self.max_allowed_tax
        )

        if hard_reject:
            risk = RiskLevel.REJECTED
            max_alloc = 0.0
            warnings.append("Trade REJECTED — honeypot or excessive tax.")
        elif parsed["buy_tax"] > 0.05 or parsed["sell_tax"] > 0.05 or not parsed["liquidity_locked"]:
            risk = RiskLevel.HIGH
            max_alloc = 30.0
        elif parsed["source"] == "fallback":
            risk = RiskLevel.HIGH   # Always HIGH when we couldn't verify
            max_alloc = 25.0
        else:
            risk = RiskLevel.MEDIUM
            max_alloc = 50.0

        try:
            return RiskAssessment(
                token_address=token_address,
                is_honeypot=parsed["is_honeypot"],
                buy_tax=parsed["buy_tax"],
                sell_tax=parsed["sell_tax"],
                liquidity_locked=parsed["liquidity_locked"],
                risk_level=risk,
                max_allocation_usd=max_alloc,
                warnings=warnings
            )
        except Exception as e:
            logger.error(f"Failed to create RiskAssessment: {e}")
            # Return a safe default REJECTED assessment
            return RiskAssessment(
                token_address=token_address,
                is_honeypot=True,  # Assume worst
                buy_tax=1.0,
                sell_tax=1.0,
                liquidity_locked=False,
                risk_level=RiskLevel.REJECTED,
                max_allocation_usd=0.0,
                warnings=[f"Validation error: {str(e)}"]
            )

    def assess_risk(self, signal: TradeSignal) -> RiskAssessment:
        """
        Main entry point. Always returns a RiskAssessment (never None).
        Falls back to conservative defaults if GoPlus is unreachable.
        """
        print(f"🛡️  [Actuary] Auditing {signal.token_address} on chain {signal.chain}...")

        # Cache check
        cache_key = f"{signal.chain}:{signal.token_address.lower()}"
        if cache_key in self._cache:
            ts, cached = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                print(f"🛡️  [Actuary] Cache hit — skipping API call.")
                return cached

        # Try GoPlus
        token_data = self._fetch_goplus(signal.chain, signal.token_address)

        if token_data:
            parsed = self._parse_token_data(token_data)
        else:
            logger.warning("GoPlus unavailable — using conservative fallback.")
            parsed = dict(CONSERVATIVE_FALLBACK)

        assessment = self._build_assessment(signal.token_address, parsed)

        # Store in cache
        self._cache[cache_key] = (time.time(), assessment)

        print(f"🛡️  [Actuary] Result: {assessment.risk_level.value} | Alloc: ${assessment.max_allocation_usd}")
        for w in assessment.warnings:
            print(f"   ⚠️  {w}")
        print(f"   Tax: Buy {assessment.buy_tax*100:.1f}% | Sell {assessment.sell_tax*100:.1f}%")

        return assessment


if __name__ == "__main__":
    import time as _time
    logging.basicConfig(level=logging.INFO)

    from core.models import TradeSignal

    actuary = Actuary(max_allowed_tax=0.25)

    # Test 1: Real token (PEPE on Ethereum)
    signal = TradeSignal(
        token_address="0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        chain="1",
        narrative_score=85,
        reasoning="High social velocity",
        discovered_at=_time.time()
    )
    result = actuary.assess_risk(signal)
    print(f"\nFinal: {result.risk_level} | ${result.max_allocation_usd}\n")

    # Test 2: Bogus address (forces fallback)
    bad_signal = TradeSignal(
        token_address="0x0000000000000000000000000000000000000000",
        chain="1",
        narrative_score=50,
        reasoning="Unknown token",
        discovered_at=_time.time()
    )
    result2 = actuary.assess_risk(bad_signal)
    print(f"\nFinal: {result2.risk_level} | ${result2.max_allocation_usd}")
