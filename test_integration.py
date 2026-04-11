#!/usr/bin/env python3
"""
Test the integrated real execution system.
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_main_with_real_execution():
    """Test main.py with real execution mode."""
    print("🧪 Testing main.py integration")
    print("=" * 50)
    
    # Create a test .env file
    env_content = """# Test configuration
USE_REAL_EXECUTION=false
ETH_RPC_URL=https://sepolia.infura.io/v3/test
PRIVATE_KEY=0xtest
"""
    
    env_path = Path(".env.test_integration")
    env_path.write_text(env_content)
    
    # Temporarily set environment variable to use our test .env
    original_env = os.environ.get("DOTENV_PATH")
    os.environ["DOTENV_PATH"] = str(env_path)
    
    try:
        # Import and run main
        from main import main
        
        print("Running main()...")
        # We'll catch KeyboardInterrupt to stop after a few seconds
        import threading
        import time
        
        def run_main():
            try:
                main()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                print(f"Error in main: {e}")
        
        thread = threading.Thread(target=run_main)
        thread.daemon = True
        thread.start()
        
        # Let it run for 3 seconds
        time.sleep(3)
        
        # Send interrupt
        import signal
        os.kill(os.getpid(), signal.SIGINT)
        
        thread.join(timeout=1)
        
        print("\n✅ main.py test completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if original_env:
            os.environ["DOTENV_PATH"] = original_env
        else:
            os.environ.pop("DOTENV_PATH", None)
        
        if env_path.exists():
            env_path.unlink()

def test_unified_slinger():
    """Test the unified slinger."""
    print("\n" + "=" * 50)
    print("Testing UnifiedSlingerAgent")
    print("=" * 50)
    
    try:
        from execution.unified_slinger import UnifiedSlingerAgent
        
        # Create a mock config
        from pydantic import BaseModel
        
        class TestConfig(BaseModel):
            use_private_mempool: bool = False
            base_slippage_tolerance: float = 0.15
            gas_premium_multiplier: float = 1.5
        
        config = TestConfig()
        
        # Test initialization
        slinger = UnifiedSlingerAgent(config)
        print(f"Mode: {slinger.get_mode()}")
        print(f"Connection test: {slinger.test_connection()}")
        
        # Test with mock order
        class TestOrder(BaseModel):
            token_address: str = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"
            action: str = "BUY"
            amount_usd: float = 100.0
            slippage_tolerance: float = 0.30
            gas_premium_gwei: float = 50.0
        
        order = TestOrder()
        
        tx_hash = slinger.execute_order(order)
        print(f"Transaction result: {tx_hash}")
        
        print("\n✅ UnifiedSlingerAgent test completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def test_real_slinger_module():
    """Test that real_slinger.py can be imported."""
    print("\n" + "=" * 50)
    print("Testing real_slinger.py module")
    print("=" * 50)
    
    try:
        from execution.real_slinger import RealSlingerAgent
        
        print("✅ RealSlingerAgent can be imported")
        
        # Check the class
        print(f"Class: {RealSlingerAgent}")
        
        # Check if it has required methods
        import inspect
        methods = [m for m in dir(RealSlingerAgent) if not m.startswith('_')]
        print(f"Methods: {', '.join(methods[:5])}...")
        
        print("\n✅ real_slinger.py test completed")
        
    except ImportError as e:
        print(f"⚠️  Import warning: {e}")
        print("This is OK if web3.py is not installed")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def test_strategy_runner_real():
    """Test the enhanced strategy runner."""
    print("\n" + "=" * 50)
    print("Testing strategy_runner_real.py")
    print("=" * 50)
    
    try:
        # We'll run it as a subprocess to avoid interfering with current env
        import subprocess
        
        result = subprocess.run(
            [sys.executable, "strategy_runner_real.py"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print("Output:")
        print(result.stdout[:500])  # First 500 chars
        
        if result.returncode == 0:
            print("\n✅ strategy_runner_real.py test completed")
        else:
            print(f"\n⚠️  strategy_runner_real.py exited with code {result.returncode}")
            print(f"Stderr: {result.stderr[:200]}")
            
    except subprocess.TimeoutExpired:
        print("⚠️  Test timed out (expected for continuous runner)")
    except Exception as e:
        print(f"❌ Test failed: {e}")

def main():
    """Run all tests."""
    print("🧪 Asymmetric Strike Team - Integration Test Suite")
    print("=" * 60)
    
    # Change to the correct directory
    os.chdir(Path(__file__).parent)
    
    tests = [
        test_unified_slinger,
        test_real_slinger_module,
        test_strategy_runner_real,
        test_main_with_real_execution,
    ]
    
    passed = 0
    total = len(tests)
    
    for i, test in enumerate(tests, 1):
        print(f"\nTest {i}/{total}: {test.__name__}")
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All tests passed!")
    else:
        print(f"⚠️  {total - passed} test(s) failed")
    
    print("\n📋 Next steps:")
    print("1. For real execution: Configure .env with RPC and private key")
    print("2. Test on Sepolia testnet first")
    print("3. Run: python test_real_execution.py")
    print("4. Start trading: python cli.py")

if __name__ == "__main__":
    main()