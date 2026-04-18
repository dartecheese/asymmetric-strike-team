#!/usr/bin/env python3
import sys
sys.path.append('.')
from core.models import ExecutionOrder

print("Testing validation errors...")

# Test 1: Valid order
try:
    order = ExecutionOrder(
        token_address="0x123...",
        chain="1",
        action="BUY",
        amount_usd=100.0,
        slippage_tolerance=0.15,
        gas_premium_gwei=45.0,
        entry_price_usd=1.0
    )
    print("✓ Valid order created")
except Exception as e:
    print(f"✗ Error creating valid order: {e}")

# Test 2: Invalid action
try:
    order = ExecutionOrder(
        token_address="0x123...",
        chain="1",
        action="INVALID",  # Should fail pattern="^(BUY|SELL)$"
        amount_usd=100.0,
        slippage_tolerance=0.15,
        gas_premium_gwei=45.0,
        entry_price_usd=1.0
    )
    print("✗ Invalid action should have failed")
except Exception as e:
    print(f"✓ Invalid action correctly rejected: {type(e).__name__}")

# Test 3: Invalid narrative_score in TradeSignal
from core.models import TradeSignal
import time

try:
    signal = TradeSignal(
        token_address="0x123...",
        chain="1",
        narrative_score=150,  # Should fail ge=0, le=100
        reasoning="Test",
        discovered_at=time.time()
    )
    print("✗ Invalid narrative_score should have failed")
except Exception as e:
    print(f"✓ Invalid narrative_score correctly rejected: {type(e).__name__}")

# Test 4: Negative amount
try:
    order = ExecutionOrder(
        token_address="0x123...",
        chain="1",
        action="BUY",
        amount_usd=-100.0,  # Negative amount
        slippage_tolerance=0.15,
        gas_premium_gwei=45.0,
        entry_price_usd=1.0
    )
    print("✗ Negative amount should have failed")
except Exception as e:
    print(f"✓ Negative amount correctly rejected: {type(e).__name__}")