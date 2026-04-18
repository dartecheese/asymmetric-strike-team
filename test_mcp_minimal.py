#!/usr/bin/env python3
"""
Minimal MCP Integration Test
Tests core functionality without external dependencies.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔧 Testing MCP Integration Core Components")
print("=" * 50)

# Test 1: Check if we can import the conversion function
print("\n1. Testing signal conversion function...")
try:
    # Import just the function we need
    import main_mcp_integrated
    
    # Check if function exists
    if hasattr(main_mcp_integrated, 'convert_signal_to_mcp_format'):
        print("✅ Function exists in module")
        
        # Create mock classes
        class MockSignal:
            def __init__(self):
                self.token_symbol = "BTC"
                self.chain = "ethereum"
                self.narrative_score = 80
        
        class MockAssessment:
            def __init__(self):
                # Create a simple risk level class
                class RiskLevel:
                    name = "MEDIUM"
                self.risk_level = RiskLevel()
                self.tax_pct = 0.3
                self.is_honeypot = False
        
        # Test the function
        signal = MockSignal()
        assessment = MockAssessment()
        
        # Call the function
        result = main_mcp_integrated.convert_signal_to_mcp_format(signal, assessment)
        
        if result:
            print(f"✅ Signal conversion successful!")
            print(f"   Symbol: {result.get('symbol', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 0):.2f}")
            print(f"   Direction: {result.get('direction', 'N/A')}")
        else:
            print("❌ Signal conversion returned None")
            
    else:
        print("❌ Function not found in module")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check PHANTOM agent
print("\n2. Testing PHANTOM agent...")
try:
    from agents.phantom_mcp_agent import PhantomMCPAgent
    print("✅ PHANTOM agent can be imported")
    
    # Try to create an instance
    agent = PhantomMCPAgent()
    print(f"✅ Agent created: {agent.agent_name} v{agent.version}")
    print(f"   Risk params: {len(agent.risk_params)} parameters")
    
except ImportError as e:
    print(f"⚠️  PHANTOM agent import failed (may need dependencies): {e}")
except Exception as e:
    print(f"❌ Error creating agent: {e}")

# Test 3: Check traditional agents
print("\n3. Testing traditional agents...")
agents_to_test = ['Whisperer', 'Actuary', 'UnifiedSlinger', 'Reaper']
all_good = True

for agent_name in agents_to_test:
    try:
        module = __import__('agents.' + agent_name.lower(), fromlist=[agent_name])
        agent_class = getattr(module, agent_name)
        print(f"✅ {agent_name} can be imported")
    except ImportError as e:
        print(f"⚠️  {agent_name} import failed: {e}")
        all_good = False
    except AttributeError as e:
        print(f"⚠️  {agent_name} class not found: {e}")
        all_good = False
    except Exception as e:
        print(f"❌ Error with {agent_name}: {e}")
        all_good = False

# Test 4: Check strategy factory
print("\n4. Testing strategy factory...")
try:
    from strategy_factory import StrategyFactory
    print("✅ StrategyFactory can be imported")
    
    factory = StrategyFactory()
    print(f"✅ Factory created with {len(factory.profiles)} strategies")
    
    # Try to get a profile
    profile = factory.get_profile('degen')
    print(f"✅ 'degen' profile loaded: {profile.name}")
    
except ImportError as e:
    print(f"⚠️  StrategyFactory import failed: {e}")
except Exception as e:
    print(f"❌ Error with StrategyFactory: {e}")

print("\n" + "=" * 50)
print("📊 Test Summary")
print("=" * 50)

if all_good:
    print("🎉 All core components are available!")
    print("\nNext steps:")
    print("1. Install missing dependencies: pip install python-dotenv")
    print("2. Run the integrated system: python main_mcp_integrated.py --strategy degen")
    print("3. Try hybrid mode: python main_mcp_integrated.py --strategy sniper --mcp-mode hybrid")
else:
    print("⚠️  Some components failed to import")
    print("\nCheck:")
    print("1. Are you in the asymmetric_trading directory?")
    print("2. Are dependencies installed? (pip install -r requirements.txt)")
    print("3. Check the errors above for specific issues")

print("\n✅ Minimal test completed!")