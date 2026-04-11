"""
Integration script to bridge the Asymmetric Strike Team with real Web3.py execution.

This script:
1. Updates the main.py to use real execution when enabled
2. Creates a unified Slinger that switches between real/paper modes
3. Provides test utilities for real execution
"""

import os
import sys
from pathlib import Path

def update_main_py():
    """Update main.py to support real execution mode."""
    main_py_path = Path("main.py")
    
    if not main_py_path.exists():
        print("❌ main.py not found")
        return False
    
    with open(main_py_path, 'r') as f:
        content = f.read()
    
    # Check if real execution is already integrated
    if "USE_REAL_EXECUTION" in content:
        print("✅ main.py already has real execution support")
        return True
    
    # Find the Slinger initialization
    if "slinger = Slinger()" in content:
        new_content = content.replace(
            "    # Initialize Team\n    whisperer = Whisperer()\n    actuary = Actuary(max_allowed_tax=0.25) # Give it 25% tolerance for degen plays\n    slinger = Slinger()\n    reaper = Reaper()",
            """    # Initialize Team
    whisperer = Whisperer()
    actuary = Actuary(max_allowed_tax=0.25) # Give it 25% tolerance for degen plays
    
    # Real execution mode check
    USE_REAL_EXECUTION = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
    RPC_URL = os.getenv("ETH_RPC_URL")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    
    if USE_REAL_EXECUTION and RPC_URL and PRIVATE_KEY:
        print("🚀 REAL EXECUTION MODE ENABLED")
        from execution.real_slinger import RealSlingerAgent
        from strategy_factory import StrategyFactory
        factory = StrategyFactory()
        degen_config = factory.get_profile("degen").slinger
        slinger = RealSlingerAgent(degen_config, RPC_URL, PRIVATE_KEY)
    else:
        print("📝 PAPER TRADING MODE")
        slinger = Slinger()
    
    reaper = Reaper()"""
        )
        
        with open(main_py_path, 'w') as f:
            f.write(new_content)
        
        print("✅ Updated main.py with real execution support")
        return True
    
    print("❌ Could not find Slinger initialization in main.py")
    return False

def create_unified_slinger():
    """Create a unified Slinger class that switches between real/paper modes."""
    unified_slinger_path = Path("execution/unified_slinger.py")
    
    unified_code = '''"""
Unified Slinger Agent - Switches between real and paper execution based on environment.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

from core.models import ExecutionOrder
from strategy_factory import SlingerConfig

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnifiedSlinger")

class UnifiedSlingerAgent:
    """
    Unified execution agent that automatically switches between:
    - Real Web3.py execution (when USE_REAL_EXECUTION=true)
    - Paper trading simulation (default)
    """
    def __init__(self, config: SlingerConfig):
        self.config = config
        self.use_real = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
        self.rpc_url = os.getenv("ETH_RPC_URL")
        self.private_key = os.getenv("PRIVATE_KEY")
        
        if self.use_real and self.rpc_url and self.private_key:
            logger.info("🚀 Initializing REAL execution mode")
            try:
                from execution.real_slinger import RealSlingerAgent
                self.real_slinger = RealSlingerAgent(config, self.rpc_url, self.private_key)
                self.mode = "REAL"
            except ImportError as e:
                logger.error(f"Failed to load RealSlingerAgent: {e}")
                self.mode = "PAPER"
                self._init_paper_slinger()
        else:
            logger.info("📝 Initializing PAPER trading mode")
            self.mode = "PAPER"
            self._init_paper_slinger()
    
    def _init_paper_slinger(self):
        """Initialize the paper trading slinger."""
        from execution.slinger import SlingerAgent
        self.paper_slinger = SlingerAgent(self.config, rpc_url="http://localhost:8545")
    
    def execute_order(self, order: ExecutionOrder, wallet_address: str = None, private_key: str = None):
        """Execute order in appropriate mode."""
        logger.info(f"Executing {order.action} for {order.token_address} (${order.amount_usd}) in {self.mode} mode")
        
        if self.mode == "REAL":
            # Real execution - wallet address and private key come from env
            return self.real_slinger.execute_order(order)
        else:
            # Paper execution - use provided or mock credentials
            wallet = wallet_address or "0xMockWalletAddress"
            key = private_key or "MockPrivateKey"
            return self.paper_slinger.execute_order(order, wallet, key)
    
    def get_mode(self):
        """Get current execution mode."""
        return self.mode
    
    def test_connection(self):
        """Test the connection (real mode) or simulation (paper mode)."""
        if self.mode == "REAL":
            try:
                # Test Web3 connection
                from web3 import Web3
                w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                if w3.is_connected():
                    return f"✅ Connected to chain ID: {w3.eth.chain_id}"
                else:
                    return "❌ Failed to connect to RPC"
            except Exception as e:
                return f"❌ Connection test failed: {e}"
        else:
            return "📝 Paper trading mode - no blockchain connection needed"

if __name__ == "__main__":
    # Test the unified slinger
    from strategy_factory import StrategyFactory
    
    factory = StrategyFactory()
    degen_config = factory.get_profile("degen").slinger
    
    slinger = UnifiedSlingerAgent(degen_config)
    print(f"Mode: {slinger.get_mode()}")
    print(f"Connection test: {slinger.test_connection()}")
    
    # Test with a mock order
    order = ExecutionOrder(
        token_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",  # UNI token
        action="BUY",
        amount_usd=100.0,
        slippage_tolerance=0.30,
        gas_premium_gwei=50.0
    )
    
    try:
        tx_hash = slinger.execute_order(order)
        print(f"Transaction result: {tx_hash}")
    except Exception as e:
        print(f"Execution test failed: {e}")
'''
    
    with open(unified_slinger_path, 'w') as f:
        f.write(unified_code)
    
    print(f"✅ Created unified slinger at {unified_slinger_path}")
    return True

def create_test_script():
    """Create a test script for real execution."""
    test_script_path = Path("test_real_execution.py")
    
    test_code = '''#!/usr/bin/env python3
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
        print("\n📝 Running in paper trading mode.")
        print("   Set USE_REAL_EXECUTION=true in .env for real execution")
        return True
    
    if not rpc_url or not private_key:
        print("\n❌ Real execution enabled but missing required configuration")
        return False
    
    # Test Web3 connection
    try:
        from web3 import Web3
        print("\n🔗 Testing Web3 connection...")
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
    print("\n" + "=" * 50)
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
        
        print(f"\nTest order:")
        print(f"  Token: {order.token_address}")
        print(f"  Action: {order.action}")
        print(f"  Amount: ${order.amount_usd}")
        print(f"  Slippage: {order.slippage_tolerance*100}%")
        
        # Note: We won't actually execute unless explicitly enabled
        print("\n⚠️  Execution is disabled in test mode")
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
        print("\n❌ Environment test failed")
        return
    
    # Test 2: Real slinger (only if real execution is enabled)
    use_real = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
    if use_real:
        test_real_slinger()
    
    print("\n" + "=" * 60)
    print("✅ Test suite completed")
    print("=" * 60)
    
    # Next steps
    print("\n📋 Next steps:")
    print("1. For paper trading: Run `python cli.py`")
    print("2. For real execution: Ensure .env has real RPC and private key")
    print("3. Test with small amounts on testnet first")
    print("4. Use the unified slinger for automatic mode switching")

if __name__ == "__main__":
    main()
'''
    
    with open(test_script_path, 'w') as f:
        f.write(test_code)
    
    # Make it executable
    test_script_path.chmod(0o755)
    
    print(f"✅ Created test script at {test_script_path}")
    return True

def main():
    """Main integration function."""
    print("🔧 Integrating Real Execution into Asymmetric Strike Team")
    print("=" * 60)
    
    # We're already in the asymmetric_trading directory
    original_dir = os.getcwd()
    target_dir = Path(original_dir)
    
    try:
        os.chdir(target_dir)
        print(f"Working in: {os.getcwd()}")
        
        # 1. Update main.py
        print("\n1. Updating main.py...")
        update_main_py()
        
        # 2. Create unified slinger
        print("\n2. Creating unified slinger...")
        create_unified_slinger()
        
        # 3. Create test script
        print("\n3. Creating test script...")
        create_test_script()
        
        print("\n" + "=" * 60)
        print("✅ Integration complete!")
        print("\n📋 Next steps:")
        print("1. Configure your .env file:")
        print("   cp .env.example .env")
        print("   # Edit .env with your RPC URL and private key")
        print("2. Test the setup:")
        print("   python test_real_execution.py")
        print("3. Run the system:")
        print("   python cli.py")
        print("\n⚠️  WARNING: Real execution spends real ETH.")
        print("   Test on Sepolia testnet first with test ETH!")
        
    except Exception as e:
        print(f"❌ Integration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    main()
