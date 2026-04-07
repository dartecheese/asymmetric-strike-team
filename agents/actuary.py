import json
import urllib.request
from typing import Optional
from core.models import TradeSignal, RiskAssessment, RiskLevel

class Actuary:
    """
    The Actuary: Fast heuristic risk assessment.
    Uses GoPlus API to detect honeypots, high taxes, and locked liquidity.
    """
    def __init__(self, max_allowed_tax: float = 0.20):
        self.max_allowed_tax = max_allowed_tax

    def assess_risk(self, signal: TradeSignal) -> Optional[RiskAssessment]:
        print(f"🛡️ [Actuary] Running rapid heuristic audit via GoPlus API on {signal.token_address}...")
        url = f"https://api.gopluslabs.io/api/v1/token_security/{signal.chain}?contract_addresses={signal.token_address}"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                res = data.get("result", {}).get(signal.token_address.lower(), {})
                
                is_honeypot = res.get("is_honeypot", "0") == "1"
                buy_tax = float(res.get("buy_tax", "0") or 0)
                sell_tax = float(res.get("sell_tax", "0") or 0)
                
                warnings = []
                if is_honeypot: warnings.append("CRITICAL: HONEYPOT DETECTED.")
                if buy_tax > 0.1: warnings.append(f"High buy tax: {buy_tax*100:.1f}%")
                if sell_tax > 0.1: warnings.append(f"High sell tax: {sell_tax*100:.1f}%")
                
                risk = RiskLevel.HIGH
                max_alloc = 50.0 # Base allocation for degen plays
                
                if is_honeypot or sell_tax > self.max_allowed_tax or buy_tax > self.max_allowed_tax:
                    risk = RiskLevel.REJECTED
                    max_alloc = 0.0
                    warnings.append("Trade REJECTED due to honeypot or excessive tax.")
                    
                assessment = RiskAssessment(
                    token_address=signal.token_address,
                    is_honeypot=is_honeypot,
                    buy_tax=buy_tax,
                    sell_tax=sell_tax,
                    liquidity_locked=True, # Assuming locked for this heuristic, should be queried in prod
                    risk_level=risk,
                    max_allocation_usd=max_alloc,
                    warnings=warnings
                )
                
                print(f"🛡️ [Actuary] Risk Assessment: {risk.value}")
                for w in warnings: print(f"   ⚠️ {w}")
                print(f"   Tax Profile: Buy {buy_tax*100:.1f}% | Sell {sell_tax*100:.1f}%")
                return assessment
                
        except Exception as e:
            print(f"🛡️ [Actuary] API request failed: {e}. Defaulting to REJECTED.")
            return None
