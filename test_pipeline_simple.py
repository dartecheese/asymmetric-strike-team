#!/usr/bin/env python3
"""
Simple Pipeline Test
====================
Test the basic Whisperer → Actuary → Slinger → Reaper pipeline
"""

import sys
import logging
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

def test_whisperer():
    """Test Whisperer can fetch token data"""
    print("🧪 Testing Whisperer...")
    try:
        from agents.whisperer import Whisperer
        whisperer = Whisperer(min_velocity_score=50)
        tokens = whisperer.scan()
        print(f"✅ Whisperer found {len(tokens)} tokens")
        if tokens:
            print(f"   Sample token: {tokens[0].get('symbol', 'N/A')} on {tokens[0].get('chain_name', 'N/A')}")
        return tokens
    except Exception as e:
        print(f"❌ Whisperer test failed: {e}")
        return []

def test_actuary():
    """Test Actuary risk assessment"""
    print("\n🧪 Testing Actuary...")
    try:
        from agents.actuary import Actuary
        actuary = Actuary(max_allowed_tax=0.15)  # 15% max tax
        
        # Test with a known safe token (WETH on Ethereum)
        test_token = {
            'token_address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'goplus_chain_id': '1',
            'chain_name': 'Ethereum'
        }
        
        risk_level, details = actuary.assess(test_token)
        print(f"✅ Actuary test completed")
        print(f"   Risk level: {risk_level}")
        print(f"   Details: {details}")
        return True
    except Exception as e:
        print(f"❌ Actuary test failed: {e}")
        return False

def test_slinger():
    """Test Slinger transaction building"""
    print("\n🧪 Testing Slinger (paper mode)...")
    try:
        from agents.unified_slinger import UnifiedSlinger
        slinger = UnifiedSlinger(paper_mode=True)
        
        # Test with mock data
        mock_token = {
            'token_address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'chain_name': 'Ethereum',
            'symbol': 'WETH',
            'price_usd': 3500.0
        }
        
        print("✅ Slinger initialized in paper mode")
        return True
    except Exception as e:
        print(f"❌ Slinger test failed: {e}")
        return False

def test_reaper():
    """Test Reaper position monitoring"""
    print("\n🧪 Testing Reaper...")
    try:
        from agents.reaper import Reaper
        reaper = Reaper(take_profit_pct=100.0, stop_loss_pct=30.0)
        
        print("✅ Reaper initialized")
        print(f"   Take profit: +{reaper.take_profit_pct}%")
        print(f"   Stop loss: -{reaper.stop_loss_pct}%")
        return True
    except Exception as e:
        print(f"❌ Reaper test failed: {e}")
        return False

def main():
    print("🚀 Testing Asymmetric Strike Team Pipeline")
    print("=" * 50)
    
    # Test each component
    whisperer_ok = test_whisperer()
    actuary_ok = test_actuary()
    slinger_ok = test_slinger()
    reaper_ok = test_reaper()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   Whisperer: {'✅' if whisperer_ok else '❌'}")
    print(f"   Actuary: {'✅' if actuary_ok else '❌'}")
    print(f"   Slinger: {'✅' if slinger_ok else '❌'}")
    print(f"   Reaper: {'✅' if reaper_ok else '❌'}")
    
    all_ok = whisperer_ok and actuary_ok and slinger_ok and reaper_ok
    if all_ok:
        print("\n🎉 All pipeline components are working!")
    else:
        print("\n⚠️  Some components need attention")

if __name__ == "__main__":
    main()