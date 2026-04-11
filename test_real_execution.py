#!/usr/bin/env python3
"""
Test script for real execution mode.
Run this to verify your Web3.py setup.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

def test_environment():
    """Test if environment is properly configured."""
    print("🔧 Testing Real Execution Environment")
    print("=" * 50)
    
    # Check .env file
    env_path = Path(".env")
    if env_path.exists():
        print(f"✅ .env file found: {env_path}")
    else:
        print("❌ .env file not found")
        print("   Copy .env.example to .env and fill in your values")
        return False
    
    # Check variables
    use_real = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
    rpc_url = os.getenv("ETH_RPC_URL")
    private_key = os.getenv("PRIVATE_KEY")
    
    print(f"USE_REAL_EXECUTION: {'✅ true' if use_real else '📝 false (paper mode)'}")
    print(f"ETH_RPC_URL: {'✅ configured' if rpc_url else '❌ not configured'}")
    print(f"PRIVATE_KEY: {'✅ configured' if private_key else '❌ not configured'}")
    
    if not use_real:
        print("
📝 Running in paper trading mode.")
        print("   Set USE_REAL_EXECUTION=true in .env for real execution")
        return True
    
    if not rpc_url or not private_key:
        print("
❌ Real execution enabled but missing required configuration")
        return False
    
    # Test Web3 connection
    try:
        from web3 import Web3
        print("
🔗 Testing Web3 connection...")
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        if w3.is_connected():
            print(f"✅ Connected to chain ID: {w3.eth.chain_id}")
            print(f"   Latest block: {w3.eth.block_number}")
            
            # Test account
            from eth_account import Account
            account = Account.from_key(private_key)
            print(f"✅ Wallet address: {account.address}")
            
            # Check balance (if on a real network)
            try:
                balance = w3.eth.get_balance(account.address)
                print(f"   Balance: {w3.from_wei(balance, 'ether')} ETH")
            except:
                print("   ⚠️  Could not fetch balance (might be testnet or simulation)")
            
            return True
        else:
            print("❌ Failed to connect to RPC endpoint")
            return False
            
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Run: pip install web3 eth-account python-dotenv")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def test_real_slinger():
    """Test the RealSlingerAgent."""
    print("
" + "=" * 50)
    print("Testing RealSlingerAgent")
    print("=" * 50)
    
    try:
        from execution.real_slinger import RealSlingerAgent
        from strategy_factory import StrategyFactory
        from core.models import ExecutionOrder
        
        factory = StrategyFactory()
        degen_config = factory.get_profile("degen").slinger
        
        rpc_url = os.getenv("ETH_RPC_URL")
        private_key = os.getenv("PRIVATE_KEY")
        
        if not rpc_url or not private_key:
            print("❌ Missing RPC_URL or PRIVATE_KEY")
            return False
        
        print("Initializing RealSlingerAgent...")
        slinger = RealSlingerAgent(degen_config, rpc_url, private_key)
        print("✅ RealSlingerAgent initialized")
        
        # Create a test order (using a well-known token)
        order = ExecutionOrder(
            token_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",  # UNI token
            action="BUY",
            amount_usd=100.0,
            slippage_tolerance=0.30,
            gas_premium_gwei=50.0
        )
        
        print(f"
Test order:")
        print(f"  Token: {order.token_address}")
        print(f"  Action: {order.action}")
        print(f"  Amount: ${order.amount_usd}")
        print(f"  Slippage: {order.slippage_tolerance*100}%")
        
        # Note: We won't actually execute unless explicitly enabled
        print("
⚠️  Execution is disabled in test mode")
        print("   To test real execution, modify the test script")
        
        return True
        
    except Exception as e:
        print(f"❌ RealSlingerAgent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🧪 Asymmetric Strike Team - Real Execution Test Suite")
    print("=" * 60)
    
    # Test 1: Environment
    if not test_environment():
        print("
❌ Environment test failed")
        return
    
    # Test 2: Real slinger (only if real execution is enabled)
    use_real = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
    if use_real:
        test_real_slinger()
    
    print("
" + "=" * 60)
    print("✅ Test suite completed")
    print("=" * 60)
    
    # Next steps
    print("
📋 Next steps:")
    print("1. For paper trading: Run `python cli.py`")
    print("2. For real execution: Ensure .env has real RPC and private key")
    print("3. Test with small amounts on testnet first")
    print("4. Use the unified slinger for automatic mode switching")

if __name__ == "__main__":
    main()
