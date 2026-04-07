import json
import time
import urllib.request
import os
import sys

# Ensure we can import from core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.models import TradeSignal, RiskAssessment, RiskLevel, ExecutionOrder

def get_whisperer_signal():
    print("🗣️ [Whisperer] Scanning social firehose (Twitter, Telegram, DexScreener)...")
    time.sleep(1.5)
    # Using PEPE token address on Ethereum as a test case for real API data
    print("🗣️ [Whisperer] 🚨 SPIKE DETECTED! High velocity on 0x6982508145454ce325ddbe47a25d4ec3d2311933 (Ethereum)")
    return TradeSignal(
        token_address="0x6982508145454ce325ddbe47a25d4ec3d2311933",
        chain="1",
        narrative_score=95,
        reasoning="Massive influx of smart money wallets. Social velocity up 400%.",
        discovered_at=time.time()
    )

def run_actuary(signal):
    print(f"🛡️ [Actuary] Running rapid heuristic audit via GoPlus API...")
    time.sleep(1)
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
            if buy_tax > 0.1: warnings.append(f"High buy tax: {buy_tax*100}%")
            if sell_tax > 0.1: warnings.append(f"High sell tax: {sell_tax*100}%")
            
            risk = RiskLevel.HIGH
            max_alloc = 50.0
            if is_honeypot or sell_tax > 0.2:
                risk = RiskLevel.REJECTED
                max_alloc = 0.0
                warnings.append("Trade REJECTED due to honeypot or excessive tax.")
                
            assessment = RiskAssessment(
                token_address=signal.token_address,
                is_honeypot=is_honeypot,
                buy_tax=buy_tax,
                sell_tax=sell_tax,
                liquidity_locked=True,
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

def run_slinger(assessment):
    if not assessment or assessment.risk_level == RiskLevel.REJECTED:
        print("🔫 [Slinger] Standing down. Capital preserved.")
        return None
    print(f"🔫 [Slinger] Actuary approved. Generating direct Web3 Router calldata...")
    time.sleep(1.5)
    order = ExecutionOrder(
        token_address=assessment.token_address,
        action="BUY",
        amount_usd=assessment.max_allocation_usd,
        slippage_tolerance=0.15,
        gas_premium_gwei=50.0
    )
    print(f"🔫 [Slinger] >> SIMULATED TX SENT <<")
    print(f"   Target: {order.token_address}")
    print(f"   Value: ${order.amount_usd} USD")
    print(f"   Slippage: {order.slippage_tolerance*100}% | Gas Premium: {order.gas_premium_gwei} Gwei")
    return order

def main():
    print("\\n" + "="*50)
    print("🚀 DEFI STRIKE TEAM: LIVE API SIMULATION")
    print("="*50 + "\\n")
    
    signal = get_whisperer_signal()
    print("-" * 50)
    
    assessment = run_actuary(signal)
    print("-" * 50)
    
    order = run_slinger(assessment)
    print("-" * 50)
    
    if order:
        print("💀 [Reaper] Order confirmed. Active monitoring initiated.")
        print("   Directive 1: FREE RIDE target set at +100% (extract principal)")
        print("   Directive 2: KILL target set at -30% (liquidate remainder)")
        print("💀 [Reaper] Watching blocks...\\n")

if __name__ == '__main__':
    main()
