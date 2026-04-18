#!/usr/bin/env python3
import sys
sys.path.append('.')
from agents.actuary import Actuary
from core.models import TradeSignal
import time

print("Testing Actuary with GoPlus API...")
actuary = Actuary(max_allowed_tax=0.25)

# Test 1: Real token (PEPE on Ethereum)
signal = TradeSignal(
    token_address='0x6982508145454Ce325dDbE47a25d4ec3d2311933',
    chain='1',
    narrative_score=85,
    reasoning='Test',
    discovered_at=time.time()
)
result = actuary.assess_risk(signal)
print(f'\nResult: {result.risk_level} | Max alloc: ${result.max_allocation_usd}')
print(f'Warnings: {result.warnings}')

# Test 2: Invalid token (should trigger fallback)
signal2 = TradeSignal(
    token_address='0x0000000000000000000000000000000000000000',
    chain='1',
    narrative_score=50,
    reasoning='Invalid token test',
    discovered_at=time.time()
)
result2 = actuary.assess_risk(signal2)
print(f'\nResult2: {result2.risk_level} | Max alloc: ${result2.max_allocation_usd}')
print(f'Warnings2: {result2.warnings}')