#!/usr/bin/env python3
import sys
sys.path.append('.')
from agents.slinger import Slinger
from core.models import RiskAssessment, RiskLevel

print("Testing Slinger with invalid order data (valid address)...")

# Create an invalid assessment with valid address
invalid_assessment = RiskAssessment(
    token_address='0x0000000000000000000000000000000000000000',  # Valid format
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

print("\n" + "="*60)
print("Testing with zero amount...")

zero_assessment = RiskAssessment(
    token_address='0x0000000000000000000000000000000000000000',
    is_honeypot=False,
    buy_tax=0.05,
    sell_tax=0.05,
    liquidity_locked=True,
    risk_level=RiskLevel.MEDIUM,
    max_allocation_usd=0.0,  # Zero amount (should also fail gt=0)
    warnings=[]
)

order2 = slinger.execute_order(zero_assessment, chain_id="1")
if order2 is None:
    print("✓ Slinger correctly returned None for zero amount")
else:
    print(f"✗ Slinger returned order: {order2}")