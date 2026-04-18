#!/usr/bin/env python3
import sys
sys.path.append('.')
import logging
logging.basicConfig(level=logging.DEBUG)

from agents.actuary import Actuary
from core.models import TradeSignal
import time

print("=" * 60)
print("Testing Actuary with detailed logging...")
print("=" * 60)

actuary = Actuary(max_allowed_tax=0.25)

# Test 1: Real token (PEPE on Ethereum)
signal = TradeSignal(
    token_address='0x6982508145454Ce325dDbE47a25d4ec3d2311933',
    chain='1',
    narrative_score=85,
    reasoning='Test',
    discovered_at=time.time()
)
print(f"\nTesting with PEPE token...")
result = actuary.assess_risk(signal)
print(f'\nResult: {result.risk_level} | Max alloc: ${result.max_allocation_usd}')
print(f'Warnings: {result.warnings}')

# Clear cache and test again
actuary._cache = {}
print(f"\n\nTesting again with cleared cache...")
result2 = actuary.assess_risk(signal)
print(f'\nResult2: {result2.risk_level} | Max alloc: ${result2.max_allocation_usd}')
print(f'Warnings2: {result2.warnings}')