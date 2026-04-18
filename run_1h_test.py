#!/usr/bin/env python3
"""
1-Hour Quick Test
=================
Quick test to verify the system works before running 48-hour test.
"""
import os
import sys
import time
import logging
from datetime import datetime, timedelta

# Add current directory to path
sys.path.append('.')

from simple_config import SimpleConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("1h_test")


def run_quick_test():
    """Run a quick 1-hour test."""
    # Configuration
    config = SimpleConfig()
    config.default_strategy = "conservative"
    config.loop_interval_seconds = 120  # 2 minutes between scans
    config.enable_sentiment = True
    
    print("\n" + "=" * 70)
    print("🚀 ASYMMETRIC STRIKE TEAM - 1-HOUR QUICK TEST")
    print("=" * 70)
    print(f"Strategy: {config.default_strategy}")
    print(f"Scan Interval: {config.loop_interval_seconds} seconds")
    print(f"Duration: 1 hour")
    print("=" * 70)
    print("\nThis test will verify the system works correctly.")
    print("Press Ctrl+C to stop early.\n")
    
    # Import here to catch import errors
    try:
        from main_simple import run_simple_cycle
        print("✅ All imports successful")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Test duration
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=1)
    
    cycle_count = 0
    successful_cycles = 0
    
    try:
        while datetime.now() < end_time:
            cycle_count += 1
            
            print(f"\n{'='*50}")
            print(f"CYCLE #{cycle_count}")
            print(f"{'='*50}")
            
            try:
                success = run_simple_cycle(config)
                
                if success:
                    successful_cycles += 1
                    print(f"✅ Cycle {cycle_count} successful")
                else:
                    print(f"⚠️  Cycle {cycle_count} completed without trade (normal)")
                
            except Exception as e:
                print(f"❌ Cycle {cycle_count} failed: {e}")
                # Continue with test despite errors
            
            # Calculate time remaining
            remaining = (end_time - datetime.now()).total_seconds()
            if remaining > 0:
                print(f"\n⏳ Next cycle in {config.loop_interval_seconds}s...")
                time.sleep(min(config.loop_interval_seconds, remaining))
        
        # Test complete
        print("\n" + "=" * 70)
        print("🎉 1-HOUR TEST COMPLETE")
        print("=" * 70)
        
        if cycle_count > 0:
            success_rate = (successful_cycles / cycle_count) * 100
            print(f"Total Cycles: {cycle_count}")
            print(f"Successful: {successful_cycles}")
            print(f"Success Rate: {success_rate:.1f}%")
            
            if success_rate > 70:
                print("\n✅ SYSTEM READY for 48-hour test")
                print("   The system is working correctly.")
            elif success_rate > 40:
                print("\n⚠️  SYSTEM PARTIALLY WORKING")
                print("   Some cycles failed. Check logs for errors.")
            else:
                print("\n❌ SYSTEM NEEDS FIXING")
                print("   Too many failures. Investigate before 48h test.")
        else:
            print("No cycles completed")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
        print(f"Completed {cycle_count} cycles, {successful_cycles} successful")
        return True
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    success = run_quick_test()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ Quick test completed")
        print("\nNext steps:")
        print("1. Review the output above")
        print("2. If system is working, run: ./start_48h_test.sh")
        print("3. Or run: python run_48h_test.py")
    else:
        print("❌ Quick test failed")
        print("\nTroubleshooting:")
        print("1. Check Python dependencies: pip install -r requirements.txt")
        print("2. Check for syntax errors in Python files")
        print("3. Verify all agent files exist in agents/ directory")
    print("=" * 70)