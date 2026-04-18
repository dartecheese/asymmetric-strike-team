#!/usr/bin/env python3
"""
Test MCP Integration for Asymmetric Strike Team

This script demonstrates how the MCP integration works with the existing
trading system. It shows the PHANTOM agent receiving signals and executing
trades via MCP servers.
"""

import os
import sys
import json
import time
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.phantom_mcp_agent import PhantomMCPAgent

def test_phantom_agent():
    """Test the PHANTOM MCP agent."""
    print("=" * 60)
    print("MCP INTEGRATION TEST - PHANTOM AGENT")
    print("=" * 60)
    
    # Initialize agent
    agent = PhantomMCPAgent()
    
    print(f"\n✅ Agent initialized: {agent.agent_name} v{agent.version}")
    print(f"📊 Risk parameters: {agent.risk_params}")
    
    # Test 1: Market scanning
    print("\n" + "=" * 40)
    print("TEST 1: Market Scanning (CoinGecko MCP)")
    print("=" * 40)
    
    opportunities = agent.scan_market()
    print(f"\n📈 Found {len(opportunities)} market opportunities:")
    for opp in opportunities:
        print(f"  • {opp['symbol']}: {opp['name']} (Rank: {opp['market_cap_rank']})")
    
    # Test 2: Signal reception and validation
    print("\n" + "=" * 40)
    print("TEST 2: Signal Processing")
    print("=" * 40)
    
    test_signals = [
        {
            'symbol': 'BTC/USDT',
            'direction': 'buy',
            'confidence': 0.85,
            'signal_type': 'sentiment',
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': {
                'source': 'PULSE',
                'sentiment_score': 0.8,
                'funding_rate': -0.0001
            }
        },
        {
            'symbol': 'ETH/USDT',
            'direction': 'sell',
            'confidence': 0.45,  # Too low - should be rejected
            'signal_type': 'technical',
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': {
                'source': 'COMPASS',
                'rsi': 75,
                'regime': 'greed'
            }
        },
        {
            'symbol': 'SOL/USDT',
            'direction': 'buy',
            'confidence': 0.72,
            'signal_type': 'trending',
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': {
                'source': 'SWEEP',
                'volume_spike': 2.5,
                'social_trending': True
            }
        }
    ]
    
    for i, signal in enumerate(test_signals, 1):
        print(f"\n📡 Processing Signal {i}:")
        print(f"  Symbol: {signal['symbol']}")
        print(f"  Direction: {signal['direction'].upper()}")
        print(f"  Confidence: {signal['confidence']:.2f}")
        print(f"  Type: {signal['signal_type']}")
        
        result = agent.receive_signal(signal)
        print(f"  Result: {'✅ ACCEPTED' if result else '❌ REJECTED'}")
    
    # Test 3: Check execution logs
    print("\n" + "=" * 40)
    print("TEST 3: Execution Logs")
    print("=" * 40)
    
    log_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'data', 'phantom_executions.json'
    )
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = json.load(f)
        
        print(f"\n📝 Found {len(logs)} execution logs:")
        for log in logs[-3:]:  # Show last 3 executions
            print(f"\n  Order ID: {log['order']['id']}")
            print(f"  Symbol: {log['order']['symbol']}")
            print(f"  Side: {log['order']['side'].upper()}")
            print(f"  Price: ${log['market_data']['price']:,.2f}")
            print(f"  Amount: {log['order']['amount']}")
            print(f"  Time: {log['timestamp']}")
    else:
        print("\n📝 No execution logs found yet")
    
    # Test 4: Integration with existing system
    print("\n" + "=" * 40)
    print("TEST 4: Integration with Asymmetric Strike Team")
    print("=" * 40)
    
    # Check if we can import existing components
    try:
        # Try to import core components
        from core.config import Config
        print("✅ Core config module available")
        
        # Check for existing agents
        agents_dir = os.path.join(os.path.dirname(__file__), 'agents')
        if os.path.exists(agents_dir):
            agent_files = [f for f in os.listdir(agents_dir) if f.endswith('.py') and f != '__init__.py']
            print(f"✅ Found {len(agent_files)} existing agent files")
            
            # List compatible agents from MCP handover
            mcp_agents = [
                'PHANTOM (execution)',
                'PULSE (sentiment aggregation)',
                'ORACLE (trust scoring)',
                'SONAR (whale monitoring)',
                'SWEEP (market scanning)',
                'COMPASS (regime detection)',
                'RIFT (arbitrage detection)',
                'HERALD (news monitoring)',
                'FORGE (strategy management)'
            ]
            
            print("\n🎯 MCP Agent Architecture:")
            for agent in mcp_agents:
                print(f"  • {agent}")
        
    except ImportError as e:
        print(f"⚠️  Some imports failed: {e}")
        print("  (This is expected if running in isolation)")
    
    print("\n" + "=" * 60)
    print("MCP INTEGRATION TEST COMPLETE")
    print("=" * 60)
    
    print("\n📋 Next Steps for Full MCP Integration:")
    print("  1. Get Binance Testnet API keys")
    print("  2. Configure .env file with API keys")
    print("  3. Install TradingView MCP server")
    print("  4. Implement PULSE agent (sentiment aggregation)")
    print("  5. Implement ORACLE agent (trust scoring)")
    print("  6. Set up signal pipeline between agents")
    print("  7. Test with paper trading")
    print("  8. Deploy to production with small positions")
    
    return True

def create_integration_plan():
    """Create a detailed integration plan based on the MCP handover."""
    print("\n" + "=" * 60)
    print("MCP INTEGRATION PLAN FOR ASYMMETRIC STRIKE TEAM")
    print("=" * 60)
    
    plan = {
        'week_1': {
            'title': 'Foundation',
            'tasks': [
                'Set up MCP directory structure',
                'Install CCXT MCP server ✅',
                'Configure exchange API keys (Testnet)',
                'Test CCXT: fetch BTC/USDT price',
                'Install CoinGecko MCP',
                'Create unified mcp_config.json ✅',
                'Implement PHANTOM agent ✅'
            ]
        },
        'week_2': {
            'title': 'Intelligence Layer',
            'tasks': [
                'Get Santiment API key',
                'Clone and install crypto-sentiment-mcp',
                'Clone and install crypto-feargreed-mcp',
                'Clone and install crypto-indicators-mcp',
                'Test sentiment pipeline',
                'Build sentiment-stack.js',
                'Implement PULSE agent',
                'Wire sentiment output to dashboard'
            ]
        },
        'week_3': {
            'title': 'On-Chain Intelligence',
            'tasks': [
                'Get Dune API key',
                'Configure Dune MCP server',
                'Build trust scoring query library',
                'Test trust scoring on known projects',
                'Create trust-scores.db schema',
                'Implement ORACLE agent',
                'Wire trust gate into signal pipeline'
            ]
        },
        'week_4': {
            'title': 'Execution Integration',
            'tasks': [
                'Install TradingView MCP server',
                'Test confluence analysis',
                'Install Hyperliquid MCP',
                'Test DEX vs CEX price comparison',
                'Wire PHANTOM to multiple venues',
                'Implement RIFT agent (arbitrage)',
                'Set up cross-venue execution'
            ]
        },
        'week_5': {
            'title': 'Full Pipeline Test',
            'tasks': [
                'Run end-to-end pipeline test',
                'Dry run with paper trading',
                'Monitor for 48 hours',
                'Adjust signal weights',
                'Deploy with minimum positions',
                'Set up kill switch',
                'Document operational procedures'
            ]
        }
    }
    
    for week, details in plan.items():
        print(f"\n{week.upper()}: {details['title']}")
        print("-" * 40)
        for i, task in enumerate(details['tasks'], 1):
            status = "✅" if "✅" in task else "□"
            task_clean = task.replace("✅", "").strip()
            print(f"  {status} {i:2d}. {task_clean}")
    
    print("\n" + "=" * 60)
    print("AGENT-TO-MCP ROUTING MAP")
    print("=" * 60)
    
    routing_map = {
        'PHANTOM': ['ccxt', 'hyperliquid'],
        'PULSE': ['crypto-sentiment', 'fear-greed', 'crypto-indicators'],
        'ORACLE': ['dune', 'coingecko', 'cryptoapis-data'],
        'SONAR': ['dune', 'coingecko'],
        'SWEEP': ['coingecko', 'crypto-indicators'],
        'COMPASS': ['fear-greed', 'crypto-sentiment', 'tradingview'],
        'RIFT': ['ccxt', 'hyperliquid'],
        'HERALD': ['cryptopanic', 'tradingview'],
        'FORGE': ['freqtrade', 'tradingview']
    }
    
    for agent, servers in routing_map.items():
        print(f"\n{agent}:")
        for server in servers:
            print(f"  • {server}")
    
    return plan

if __name__ == "__main__":
    print("\n🚀 Starting MCP Integration Test Suite")
    print("   (Based on OpenClaw MCP Integration Handover)\n")
    
    try:
        # Run tests
        test_phantom_agent()
        
        # Show integration plan
        create_integration_plan()
        
        print("\n" + "=" * 60)
        print("✅ MCP INTEGRATION READY FOR IMPLEMENTATION")
        print("=" * 60)
        print("\nThe Asymmetric Strike Team is now equipped with MCP architecture.")
        print("Next: Begin Week 1 implementation with real API keys.")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)