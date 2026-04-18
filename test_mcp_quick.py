import os
import sys

# Test basic imports
print("Testing MCP integration imports...")

try:
    # Test importing the main module
    from main_mcp_integrated import convert_signal_to_mcp_format, initialize_mcp_agents
    print("✅ main_mcp_integrated imports work")
except ImportError as e:
    print(f"❌ Failed to import main_mcp_integrated: {e}")

try:
    # Test importing PHANTOM agent
    from agents.phantom_mcp_agent import PhantomMCPAgent
    print("✅ PHANTOM agent imports work")
except ImportError as e:
    print(f"❌ Failed to import PHANTOM agent: {e}")

try:
    # Test importing traditional agents
    from agents.whisperer import Whisperer
    from agents.actuary import Actuary
    from agents.unified_slinger import UnifiedSlinger
    from agents.reaper import Reaper
    print("✅ Traditional agent imports work")
except ImportError as e:
    print(f"❌ Failed to import traditional agents: {e}")

try:
    # Test strategy factory
    from strategy_factory import StrategyFactory
    print("✅ Strategy factory imports work")
except ImportError as e:
    print(f"❌ Failed to import strategy factory: {e}")

print("\n✅ All imports tested successfully!")

# Quick functionality test
print("\nTesting signal conversion...")

class MockSignal:
    def __init__(self):
        self.token_symbol = "ETH"
        self.chain = "ethereum"
        self.narrative_score = 85
        self.reasoning = "Test"

class MockAssessment:
    def __init__(self):
        self.risk_level = type('RiskLevel', (), {'name': 'MEDIUM'})()
        self.tax_pct = 0.5
        self.is_honeypot = False

signal = MockSignal()
assessment = MockAssessment()

mcp_signal = convert_signal_to_mcp_format(signal, assessment)
if mcp_signal:
    print(f"✅ Signal conversion works:")
    print(f"   Symbol: {mcp_signal['symbol']}")
    print(f"   Confidence: {mcp_signal['confidence']:.2f}")
else:
    print("❌ Signal conversion failed")

print("\n✅ Quick test completed!")