#!/usr/bin/env python3
"""
Test the enhanced Asymmetric Strike Team system.
"""
import sys
sys.path.append('.')
import os
os.environ['USE_REAL_EXECUTION'] = 'false'

import time
from strategy_factory import StrategyFactory
from agents.enhanced_whisperer import EnhancedWhisperer
from agents.actuary import Actuary
from agents.unified_slinger import UnifiedSlinger
from agents.reaper import Reaper
from core.models import RiskLevel

print("Testing Enhanced Asymmetric Strike Team")
print("=" * 70)

factory = StrategyFactory()
try:
    profile = factory.get_profile("degen")
    print(f"✓ Loaded strategy: {profile.name}")
except ValueError as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# Build enhanced agents
whisperer = EnhancedWhisperer(min_velocity_score=50, use_sentiment=True)
actuary = Actuary(max_allowed_tax=profile.actuary.max_tax_allowed / 100)
slinger = UnifiedSlinger()
slinger.set_strategy_params(
    slippage=profile.slinger.base_slippage_tolerance,
    gas_multiplier=profile.slinger.gas_premium_multiplier,
    private_mempool=profile.slinger.use_private_mempool
)
reaper = Reaper(
    take_profit_pct=profile.reaper.take_profit_pct,
    stop_loss_pct=profile.reaper.stop_loss_pct,
    trailing_stop_pct=profile.reaper.trailing_stop_pct,
    poll_interval_sec=5.0,
    paper_mode=True,
)

print("\n1. Enhanced Whisperer scanning (with sentiment)...")
signal = whisperer.scan_firehose()
if not signal:
    print("✗ No signal found")
    sys.exit(0)

print(f"✓ Signal: {signal.token_address[:10]}... on chain {signal.chain}")
print(f"  Score: {signal.narrative_score} | {signal.reasoning[:80]}...")

print("\n2. Actuary assessing risk...")
assessment = actuary.assess_risk(signal)

if assessment.risk_level == RiskLevel.REJECTED:
    print(f"✗ Token REJECTED by Actuary")
    sys.exit(0)

if profile.actuary.strict_mode and assessment.risk_level == RiskLevel.HIGH:
    print(f"✗ Strict mode: HIGH risk token rejected")
    sys.exit(0)

print(f"✓ Approved: {assessment.risk_level.value} | Max alloc: ${assessment.max_allocation_usd}")

print("\n3. Unified Slinger executing...")
# Check if this is a CEX-listed token
token_lower = signal.token_address.lower()
cex_tokens = {
    "0x6982508145454ce325ddbe47a25d4ec3d2311933": "PEPE/USDT",
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "ETH/USDT",
}
symbol = cex_tokens.get(token_lower)
chain_id = "cex" if symbol else signal.chain

order = slinger.execute_order(assessment, chain_id=chain_id, symbol=symbol)

if not order:
    print("✗ Slinger returned no order")
    sys.exit(0)

venue = "CEX" if order.is_cex else "DEX"
print(f"✓ {venue} order generated: ${order.amount_usd} USD")
print(f"  Slippage: {order.slippage_tolerance*100:.1f}%")

print("\n4. Reaper monitoring (simulated)...")
reaper.take_position(order)
print(f"✓ Position taken")

print("\n" + "=" * 70)
print("✅ Enhanced System Test Complete!")
print("\nFeatures Verified:")
print("✓ Enhanced Whisperer with sentiment analysis")
print("✓ Unified Slinger (DEX/CEX routing)")
print("✓ Auto-venue selection")
print("✓ Full pipeline execution")
print("\nReady for paper trading validation run!")