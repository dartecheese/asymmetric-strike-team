#!/usr/bin/env python3
import os
import sys
sys.path.append('.')

# Mock environment
os.environ['USE_REAL_EXECUTION'] = 'false'

import time
from strategy_factory import StrategyFactory
from agents.whisperer import Whisperer
from agents.actuary import Actuary
from agents.slinger import Slinger
from agents.reaper import Reaper
from core.models import RiskLevel

print("Testing Asymmetric Strike Team pipeline...")

factory = StrategyFactory()
try:
    profile = factory.get_profile("degen")
    print(f"✓ Loaded strategy: {profile.name}")
except ValueError as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# Build agents
whisperer_cfg = profile.whisperer
min_score = whisperer_cfg.min_velocity_score if whisperer_cfg else 50
whisperer = Whisperer(min_velocity_score=min_score)

actuary_cfg = profile.actuary
actuary = Actuary(
    max_allowed_tax=actuary_cfg.max_tax_allowed / 100,
)

slinger = Slinger()
reaper = Reaper(
    take_profit_pct=profile.reaper.take_profit_pct,
    stop_loss_pct=profile.reaper.stop_loss_pct,
    trailing_stop_pct=profile.reaper.trailing_stop_pct,
    poll_interval_sec=5.0,
    paper_mode=True,
)

print("\n1. Whisperer scanning...")
signal = whisperer.scan_firehose()
if not signal:
    print("✗ No signal from Whisperer")
    sys.exit(0)

print(f"✓ Signal: {signal.token_address} on chain {signal.chain}")
print(f"  Score: {signal.narrative_score} | {signal.reasoning[:80]}...")

print("\n2. Actuary assessing risk...")
assessment = actuary.assess_risk(signal)

if assessment.risk_level == RiskLevel.REJECTED:
    print(f"✗ Token REJECTED by Actuary")
    sys.exit(0)

if actuary_cfg.strict_mode and assessment.risk_level == RiskLevel.HIGH:
    print(f"✗ Strict mode: HIGH risk token rejected")
    sys.exit(0)

print(f"✓ Approved: {assessment.risk_level.value} | Max alloc: ${assessment.max_allocation_usd}")

print("\n3. Slinger executing...")
order = slinger.execute_order(assessment, chain_id=signal.chain)

if not order:
    print("✗ Slinger returned no order")
    sys.exit(0)

print(f"✓ Order generated: ${order.amount_usd} USD")
print(f"  Slippage: {order.slippage_tolerance*100:.1f}% | Gas: {order.gas_premium_gwei:.1f} Gwei")

print("\n4. Reaper monitoring (simulated)...")
reaper.take_position(order)
print(f"✓ Position taken at ${order.entry_price_usd if order.entry_price_usd else 'N/A'}")

print("\n✅ Pipeline test complete!")