#!/usr/bin/env python3
import sys
sys.path.append('.')
from agents.actuary import Actuary
from core.models import TradeSignal, RiskLevel
import time

print("Testing Actuary with invalid assessment data...")

actuary = Actuary(max_allowed_tax=0.25)

# Create a signal
signal = TradeSignal(
    token_address='0x6982508145454Ce325dDbE47a25d4ec3d2311933',
    chain='1',
    narrative_score=85,
    reasoning='Test',
    discovered_at=time.time()
)

# Mock the _build_assessment to return invalid data
original_build = actuary._build_assessment

def mock_build_with_invalid(token_address, parsed):
    # Return assessment with negative max_allocation_usd
    return original_build(token_address, {
        "is_honeypot": False,
        "buy_tax": 0.05,
        "sell_tax": 0.05,
        "liquidity_locked": True,
        "source": "test",
        "max_allocation_usd": -100.0  # Invalid negative value
    })

actuary._build_assessment = mock_build_with_invalid

print("\nTesting with invalid max_allocation_usd...")
try:
    result = actuary.assess_risk(signal)
    print(f"Result: {result.risk_level} | Max alloc: ${result.max_allocation_usd}")
    print(f"Note: Should be REJECTED with $0 allocation due to validation error")
except Exception as e:
    print(f"Exception (should be caught): {type(e).__name__}: {e}")

# Restore original
actuary._build_assessment = original_build

print("\n" + "="*60)
print("Testing Slinger with invalid order data...")

from agents.slinger import Slinger
from core.models import RiskAssessment

# Create an invalid assessment
invalid_assessment = RiskAssessment(
    token_address='0x123...',
    is_honeypot=False,
    buy_tax=0.05,
    sell_tax=0.05,
    liquidity_locked=True,
    risk_level=RiskLevel.MEDIUM,
    max_allocation_usd=-50.0,  # Invalid negative
    warnings=[]
)

slinger = Slinger()
print("\nTrying to execute order with negative amount...")
order = slinger.execute_order(invalid_assessment, chain_id="1")
if order is None:
    print("✓ Slinger correctly returned None for invalid order")
else:
    print(f"✗ Slinger returned order: {order}")