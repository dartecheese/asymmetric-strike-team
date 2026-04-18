#!/usr/bin/env python3
"""
Test One Cycle
==============
Test just one cycle to verify the system works.
"""
import sys
sys.path.append('.')

from simple_config import SimpleConfig
from main_simple import run_simple_cycle

print("Testing one cycle...")
config = SimpleConfig()
config.default_strategy = "conservative"
config.enable_sentiment = True

try:
    success = run_simple_cycle(config)
    if success:
        print("✅ Cycle completed successfully!")
    else:
        print("⚠️  Cycle completed without trade (this is normal)")
except Exception as e:
    print(f"❌ Cycle failed: {e}")
    import traceback
    traceback.print_exc()