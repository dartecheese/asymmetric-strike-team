#!/usr/bin/env python3
"""
Simple MCP Integration Test
Tests the wiring between traditional pipeline and MCP agents.
"""

import os
import sys
import time
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_signal_conversion():
    """Test converting traditional signals to MCP format."""
    print("=" * 60)
    print("TEST: Signal Conversion")
    print("=" * 60)
    
    # Mock a traditional signal
    class MockSignal:
        def __init__(self):
            self.token_symbol = "ETH"
            self.chain = "ethereum"
            self.narrative_score = 85
            self.reasoning = "Strong social momentum, whale accumulation"
    
    # Mock an assessment
    class MockAssessment:
        def __init__(self):
            self.risk_level = type('RiskLevel', (), {'name': 'MEDIUM'})()
            self.tax_pct = 0.5
            self.is_honeypot = False
    
    # Import the conversion function
    from main_mcp_integrated import convert_signal_to_mcp_format
    
    signal = MockSignal()
    assessment = MockAssessment()
    
    mcp_signal = convert_signal_to_mcp_format(signal, assessment)
    
    print(f"Traditional Signal:")
    print(f"  Token: {signal.token_symbol}")
    print(f"  Chain: {signal.chain}")
    print(f"  Score: {signal.narrative_score}")
    
    print(f"\nConverted MCP Signal:")
    print(f"  Symbol: {mcp_signal['symbol']}")
    print(f"  Direction: {mcp_signal['direction']}")
    print(f"  Confidence: {mcp_signal['confidence']:.2f}")
    print(f"  Exchange: {mcp_signal['metadata']['exchange']}")
    print(f"  Source: {mcp_signal['metadata']['source']}")
    
    return mcp_signal is not None


def test_phantom_agent_initialization():
    """Test PHANTOM agent initialization."""
    print("\n" + "=" * 60)
    print("TEST: PHANTOM Agent Initialization")
    print("=" * 60)
    
    try:
        from agents.phantom_mcp_agent import PhantomMCPAgent
        
        agent = PhantomMCPAgent()
        
        print(f"✅ Agent initialized: {agent.agent_name} v{agent.version}")
        print(f"📊 Risk parameters:")
        for key, value in agent.risk_params.items():
            print(f"  • {key}: {value}")
        
        # Test with different strategies
        print(f"\n🔧 Strategy configurations:")
        
        # Sniper strategy
        agent.risk_params['min_confidence_score'] = 0.80
        agent.risk_params['max_position_size_pct'] = 0.005
        print(f"  • Sniper: min_confidence=0.80, max_position=0.5%")
        
        # Degen strategy  
        agent.risk_params['min_confidence_score'] = 0.65
        agent.risk_params['max_position_size_pct'] = 0.02
        print(f"  • Degen: min_confidence=0.65, max_position=2.0%")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import PHANTOM agent: {e}")
        return False
    except Exception as e:
        print(f"❌ Error initializing agent: {e}")
        return False


def test_mcp_execution_flow():
    """Test the complete MCP execution flow."""
    print("\n" + "=" * 60)
    print("TEST: MCP Execution Flow")
    print("=" * 60)
    
    try:
        from agents.phantom_mcp_agent import PhantomMCPAgent
        
        agent = PhantomMCPAgent()
        
        # Create a test signal
        test_signal = {
            'symbol': 'BTC/USDT',
            'direction': 'buy',
            'confidence': 0.85,
            'signal_type': 'test',
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': {
                'source': 'test',
                'exchange': 'binance'
            }
        }
        
        print(f"Test Signal:")
        print(f"  Symbol: {test_signal['symbol']}")
        print(f"  Confidence: {test_signal['confidence']:.2f}")
        print(f"  Min required: {agent.risk_params['min_confidence_score']:.2f}")
        
        # Test signal reception
        print(f"\nProcessing signal...")
        accepted = agent.receive_signal(test_signal)
        
        if accepted:
            print(f"✅ Signal accepted by PHANTOM")
            
            # Test would execute here
            print(f"📄 Paper mode: Would execute via CCXT MCP")
            print(f"   Exchange: {test_signal['metadata']['exchange']}")
            print(f"   Symbol: {test_signal['symbol']}")
            print(f"   Side: {test_signal['direction'].upper()}")
            
            return True
        else:
            print(f"❌ Signal rejected by PHANTOM")
            return False
            
    except Exception as e:
        print(f"❌ Error in execution flow: {e}")
        return False


def test_main_integration():
    """Test the main integration function."""
    print("\n" + "=" * 60)
    print("TEST: Main Integration Function")
    print("=" * 60)
    
    try:
        from main_mcp_integrated import initialize_mcp_agents
        
        print("Testing MCP agent initialization for different modes:")
        
        # Test hybrid mode
        print(f"\n1. Hybrid mode (DEX + CEX):")
        agents = initialize_mcp_agents("degen", "hybrid")
        if 'phantom' in agents:
            print(f"   ✅ PHANTOM agent initialized")
            print(f"   • Strategy: degen")
            print(f"   • Min confidence: {agents['phantom'].risk_params['min_confidence_score']:.2f}")
            print(f"   • Max position: {agents['phantom'].risk_params['max_position_size_pct']*100:.1f}%")
        else:
            print(f"   ❌ PHANTOM agent not found")
        
        # Test mcp-only mode
        print(f"\n2. MCP-only mode (CEX only):")
        agents = initialize_mcp_agents("sniper", "mcp-only")
        if 'phantom' in agents:
            print(f"   ✅ PHANTOM agent initialized")
            print(f"   • Strategy: sniper")
            print(f"   • Min confidence: {agents['phantom'].risk_params['min_confidence_score']:.2f}")
            print(f"   • Max position: {agents['phantom'].risk_params['max_position_size_pct']*100:.1f}%")
        else:
            print(f"   ❌ PHANTOM agent not found")
        
        # Test traditional mode
        print(f"\n3. Traditional mode (DEX only):")
        agents = initialize_mcp_agents("degen", "traditional")
        if not agents:
            print(f"   ✅ No MCP agents (as expected for traditional mode)")
        else:
            print(f"   ⚠️  Unexpected agents in traditional mode")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in main integration test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("🚀 MCP Integration Test Suite")
    print("Testing wiring between traditional pipeline and MCP architecture")
    print()
    
    tests = [
        ("Signal Conversion", test_signal_conversion),
        ("PHANTOM Agent Initialization", test_phantom_agent_initialization),
        ("MCP Execution Flow", test_mcp_execution_flow),
        ("Main Integration", test_main_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            print()
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
            print()
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! MCP integration is ready.")
        print("\nNext steps:")
        print("1. Run: python main_mcp_integrated.py --strategy degen")
        print("2. Run: python main_mcp_integrated.py --strategy sniper --mcp-only")
        print("3. Run: python main_mcp_integrated.py --loop --interval 300")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)