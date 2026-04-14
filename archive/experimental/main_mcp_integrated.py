"""
Asymmetric Strike Team — MCP Integrated Edition
===============================================
Enhanced pipeline with MCP architecture integration:

Traditional Pipeline:
  Whisperer → Actuary → Slinger → Reaper

MCP-Enhanced Pipeline:
  PULSE/SWEEP (sentiment) → ORACLE (on-chain intel) → PHANTOM (MCP execution) → FORGE (risk mgmt)

This version integrates the PHANTOM MCP agent for CEX execution while maintaining
backward compatibility with the existing DEX execution via Slinger.

Run modes:
  python main_mcp_integrated.py                              # Paper mode, degen strategy
  python main_mcp_integrated.py --strategy sniper            # Different strategy
  python main_mcp_integrated.py --loop                       # Continuous scanning
  python main_mcp_integrated.py --mcp-only                   # Use only MCP agents (no Slinger)
  python main_mcp_integrated.py --hybrid                     # Use both Slinger (DEX) and PHANTOM (CEX)
  USE_REAL_EXECUTION=true python main_mcp_integrated.py      # Live execution
"""

import os
import sys
import time
import logging
import argparse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MainMCP")


def list_strategies():
    from strategy_factory import StrategyFactory
    factory = StrategyFactory()
    print("\n📋 Available Strategies:\n")
    for key, profile in factory.profiles.items():
        agents = []
        if profile.whisperer: agents.append("Whisperer")
        if profile.shadow:    agents.append("Shadow")
        if profile.oracle:    agents.append("Oracle")
        if profile.sentinel:  agents.append("Sentinel")
        if profile.sleuth:    agents.append("Sleuth")
        if profile.pathfinder: agents.append("Pathfinder")
        if profile.alchemist:  agents.append("Alchemist")
        agents += ["Actuary", "Slinger", "Reaper"]

        print(f"  [{key}] {profile.name}")
        print(f"    {profile.description}")
        print(f"    Team   : {' → '.join(agents)}")
        print(f"    TP/SL  : +{profile.reaper.take_profit_pct:.0f}% / {profile.reaper.stop_loss_pct:.0f}%")
        print(f"    Slippage: {profile.slinger.base_slippage_tolerance*100:.0f}% | Gas: {profile.slinger.gas_premium_multiplier}x")
        print()


def build_banner(strategy_name: str, mode: str, mcp_mode: str = "hybrid"):
    print("\n" + "=" * 70)
    print("🚀  ASYMMETRIC STRIKE TEAM - MCP INTEGRATED EDITION")
    print(f"   Strategy : {strategy_name}")
    print(f"   Mode     : {mode}")
    print(f"   MCP Mode : {mcp_mode}")
    print("=" * 70 + "\n")


def initialize_mcp_agents(strategy: str, mcp_mode: str = "hybrid"):
    """Initialize MCP agents based on mode."""
    mcp_agents = {}
    
    if mcp_mode in ["mcp-only", "hybrid"]:
        try:
            from agents.phantom_mcp_agent import PhantomMCPAgent
            phantom = PhantomMCPAgent()
            
            # Configure PHANTOM based on strategy
            if strategy == "sniper":
                phantom.risk_params['min_confidence_score'] = 0.80
                phantom.risk_params['max_position_size_pct'] = 0.005  # 0.5% for sniper
            elif strategy == "degen":
                phantom.risk_params['min_confidence_score'] = 0.65
                phantom.risk_params['max_position_size_pct'] = 0.02   # 2% for degen
            
            mcp_agents['phantom'] = phantom
            logger.info(f"✅ PHANTOM MCP agent initialized for {strategy} strategy")
        except ImportError as e:
            logger.warning(f"⚠️  PHANTOM MCP agent not available: {e}")
    
    return mcp_agents


def convert_signal_to_mcp_format(signal, assessment):
    """Convert traditional signal format to MCP signal format."""
    if not signal or not assessment:
        return None
    
    # Calculate confidence based on Actuary assessment
    confidence_map = {
        'LOW': 0.85,
        'MEDIUM': 0.75,
        'HIGH': 0.65,
        'REJECTED': 0.0
    }
    
    confidence = confidence_map.get(assessment.risk_level.name, 0.7)
    
    # Map chain to exchange
    exchange_map = {
        'ethereum': 'binance',
        'base': 'binance',
        'arbitrum': 'binance',
        'optimism': 'binance',
        'polygon': 'binance',
        'solana': 'binance'  # Most CEXes support SOL
    }
    
    # Create MCP signal
    mcp_signal = {
        'symbol': f"{signal.token_symbol}/USDT" if signal.token_symbol else "UNKNOWN/USDT",
        'direction': 'buy',  # Always buy for now (we're long-only)
        'confidence': confidence,
        'signal_type': 'hybrid',  # Combined traditional + MCP
        'timestamp': time.time(),
        'metadata': {
            'source': 'AsymmetricStrikeTeam',
            'original_signal': signal.__dict__ if hasattr(signal, '__dict__') else str(signal),
            'assessment': assessment.__dict__ if hasattr(assessment, '__dict__') else str(assessment),
            'exchange': exchange_map.get(signal.chain.lower(), 'binance'),
            'chain': signal.chain,
            'narrative_score': signal.narrative_score if hasattr(signal, 'narrative_score') else 0
        }
    }
    
    return mcp_signal


def run_mcp_execution(phantom_agent, mcp_signal, strategy_profile, paper_mode=True):
    """Execute trade via PHANTOM MCP agent."""
    if not phantom_agent or not mcp_signal:
        return None
    
    print("\n" + "=" * 60)
    print("🎭 PHANTOM MCP EXECUTION")
    print("=" * 60)
    
    # Validate signal meets minimum confidence
    min_confidence = phantom_agent.risk_params['min_confidence_score']
    if mcp_signal['confidence'] < min_confidence:
        print(f"❌ Signal confidence {mcp_signal['confidence']:.2f} < minimum {min_confidence:.2f}")
        return None
    
    # Process signal through PHANTOM
    print(f"📡 Processing signal: {mcp_signal['symbol']}")
    print(f"   Direction: {mcp_signal['direction'].upper()}")
    print(f"   Confidence: {mcp_signal['confidence']:.2f}")
    print(f"   Source: {mcp_signal['metadata']['source']}")
    
    accepted = phantom_agent.receive_signal(mcp_signal)
    if not accepted:
        print("❌ Signal rejected by PHANTOM")
        return None
    
    # Calculate position size based on strategy
    position_size_pct = phantom_agent.risk_params['max_position_size_pct']
    
    # Adjust for strategy
    if strategy_profile.name.lower() == 'sniper':
        position_size_pct *= 0.5  # Half size for sniper
    elif strategy_profile.name.lower() == 'degen':
        position_size_pct *= 1.5  # Larger for degen
    
    print(f"✅ Signal accepted by PHANTOM")
    print(f"   Position size: {position_size_pct*100:.2f}% of portfolio")
    
    # Simulate execution (in real implementation, this would call MCP)
    if paper_mode:
        print("📄 PAPER MODE: Simulating CEX execution via CCXT MCP")
        # In paper mode, just log what would happen
        execution_result = {
            'status': 'paper_simulated',
            'symbol': mcp_signal['symbol'],
            'side': mcp_signal['direction'],
            'amount_pct': position_size_pct,
            'timestamp': time.time(),
            'exchange': mcp_signal['metadata']['exchange'],
            'paper_mode': True
        }
    else:
        print("🚨 LIVE MODE: Would execute via CCXT MCP")
        # TODO: Implement actual MCP execution
        execution_result = {
            'status': 'live_execution_pending',
            'symbol': mcp_signal['symbol'],
            'side': mcp_signal['direction'],
            'amount_pct': position_size_pct,
            'timestamp': time.time(),
            'exchange': mcp_signal['metadata']['exchange'],
            'paper_mode': False,
            'note': 'Real MCP execution not yet implemented'
        }
    
    return execution_result


def run_cycle(strategy: str = "degen", paper_mode: bool = True, 
              mcp_mode: str = "hybrid", use_mcp: bool = True) -> dict:
    """
    Run a single scan → assess → execute cycle with MCP integration.
    
    Returns dict with results from both traditional and MCP pipelines.
    """
    from strategy_factory import StrategyFactory
    from agents.whisperer import Whisperer
    from agents.actuary import Actuary
    from agents.unified_slinger import UnifiedSlinger
    from agents.reaper import Reaper
    from core.models import RiskLevel
    
    results = {
        'traditional': {'trade_placed': False, 'order': None},
        'mcp': {'trade_placed': False, 'execution': None},
        'strategy': strategy,
        'mcp_mode': mcp_mode,
        'timestamp': time.time()
    }
    
    # Initialize MCP agents if requested
    mcp_agents = {}
    if use_mcp and mcp_mode in ["mcp-only", "hybrid"]:
        mcp_agents = initialize_mcp_agents(strategy, mcp_mode)
    
    factory = StrategyFactory()
    try:
        profile = factory.get_profile(strategy)
    except ValueError as e:
        logger.error(str(e))
        return results
    
    # --- Build traditional agents from strategy profile ---
    whisperer_cfg = profile.whisperer
    min_score = whisperer_cfg.min_velocity_score if whisperer_cfg else 50
    whisperer = Whisperer(min_velocity_score=min_score)
    
    actuary_cfg = profile.actuary
    actuary = Actuary(
        max_allowed_tax=actuary_cfg.max_tax_allowed / 100,
    )
    
    slinger_cfg = profile.slinger
    slinger = UnifiedSlinger()
    slinger.set_strategy_params(
        slippage=slinger_cfg.base_slippage_tolerance,
        gas_multiplier=slinger_cfg.gas_premium_multiplier,
        private_mempool=slinger_cfg.use_private_mempool
    )
    
    reaper_cfg = profile.reaper
    reaper = Reaper(
        take_profit_pct=reaper_cfg.take_profit_pct,
        stop_loss_pct=reaper_cfg.stop_loss_pct,
        trailing_stop_pct=reaper_cfg.trailing_stop_pct,
        poll_interval_sec=5.0,
        paper_mode=paper_mode,
    )
    
    print(f"📐 Profile loaded: {profile.name}")
    print(f"   MCP Mode : {mcp_mode}")
    
    # --- Step 1: Whisperer scans for signals ---
    print("\n" + "-" * 60)
    print("🔍 STEP 1: SIGNAL SCANNING")
    print("-" * 60)
    signal = whisperer.scan_firehose()
    if not signal:
        logger.warning("Whisperer returned no signal this cycle.")
        return results
    
    print(f"   Token: {signal.token_symbol or 'Unknown'}")
    print(f"   Score: {signal.narrative_score} | Chain: {signal.chain}")
    print(f"   {signal.reasoning[:120]}...")
    
    # --- Step 2: Actuary assesses risk ---
    print("\n" + "-" * 60)
    print("🛡️  STEP 2: RISK ASSESSMENT")
    print("-" * 60)
    assessment = actuary.assess_risk(signal)
    
    if assessment.risk_level == RiskLevel.REJECTED:
        print(f"❌ Token REJECTED by Actuary. Standing down.")
        return results
    
    if actuary_cfg.strict_mode and assessment.risk_level == RiskLevel.HIGH:
        print(f"❌ Strict mode: HIGH risk token rejected.")
        return results
    
    print(f"✅ Risk assessment: {assessment.risk_level.name}")
    print(f"   Tax: {assessment.tax_pct:.2f}% | Honeypot: {assessment.is_honeypot}")
    
    # --- Step 3: Traditional DEX Execution (if hybrid or traditional) ---
    if mcp_mode in ["traditional", "hybrid"]:
        print("\n" + "-" * 60)
        print("⚡ STEP 3A: DEX EXECUTION (Slinger)")
        print("-" * 60)
        order = slinger.execute_order(assessment, chain_id=signal.chain)
        
        if order:
            results['traditional']['trade_placed'] = True
            results['traditional']['order'] = order
            
            # Pass to Reaper for monitoring
            print(f"💀 [Reaper] Entry price @ ${order.entry_price_usd:.8f}" if order.entry_price_usd else "(no price feed)")
            reaper.take_position(order)
            reaper.start_monitoring()
            
            # Monitor for a bit
            monitor_duration = 30
            try:
                time.sleep(monitor_duration)
            except KeyboardInterrupt:
                print("\nInterrupted.")
            
            reaper.stop_monitoring()
            summary = reaper.get_portfolio_summary()
            print(f"\n💀 [Reaper] Summary: {summary}")
        else:
            print("❌ Slinger returned no order.")
    
    # --- Step 4: MCP CEX Execution (if mcp-only or hybrid) ---
    if mcp_mode in ["mcp-only", "hybrid"] and 'phantom' in mcp_agents:
        print("\n" + "-" * 60)
        print("🎭 STEP 3B/4: CEX EXECUTION (PHANTOM MCP)")
        print("-" * 60)
        
        # Convert signal to MCP format
        mcp_signal = convert_signal_to_mcp_format(signal, assessment)
        if mcp_signal:
            # Execute via PHANTOM
            execution_result = run_mcp_execution(
                mcp_agents['phantom'], 
                mcp_signal, 
                profile, 
                paper_mode
            )
            
            if execution_result:
                results['mcp']['trade_placed'] = True
                results['mcp']['execution'] = execution_result
                
                print(f"✅ MCP execution result: {execution_result['status']}")
                if execution_result.get('paper_mode', True):
                    print("📄 Paper trade simulated successfully")
                else:
                    print("🚨 Live execution initiated via MCP")
            else:
                print("❌ MCP execution failed or was rejected")
        else:
            print("❌ Could not convert signal to MCP format")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Asymmetric Strike Team - MCP Integrated")
    parser.add_argument("--strategy", default="degen",
                        help="Strategy profile (default: degen)")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuous scanning loop")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between scans in loop mode (default: 60)")
    parser.add_argument("--list", action="store_true",
                        help="List all available strategy profiles and exit")
    parser.add_argument("--mcp-mode", choices=["traditional", "mcp-only", "hybrid"], 
                        default="hybrid", help="Execution mode (default: hybrid)")
    parser.add_argument("--no-mcp", action="store_true",
                        help="Disable MCP integration (force traditional mode)")
    args = parser.parse_args()
    
    if args.list:
        list_strategies()
        return
    
    use_real = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
    rpc_url  = os.getenv("ETH_RPC_URL")
    priv_key = os.getenv("PRIVATE_KEY")
    
    paper_mode = True
    if use_real and rpc_url and priv_key:
        paper_mode = False
        logger.warning("⚠️  REAL EXECUTION MODE — live transactions will broadcast!")
    elif use_real:
        logger.warning("USE_REAL_EXECUTION=true but RPC_URL or PRIVATE_KEY missing — defaulting to paper.")
    
    # Determine MCP mode
    mcp_mode = "traditional" if args.no_mcp else args.mcp_mode
    use_mcp = not args.no_mcp
    
    build_banner(args.strategy, "LIVE" if not paper_mode else "PAPER", mcp_mode)
    
    if mcp_mode != "traditional":
        print("🔗 MCP Integration Status:")
        print(f"   • PHANTOM Agent: {"✅ Available" if use_mcp else "❌ Disabled"}")
        print(f"   • Mode: {mcp_mode}")
        print(f"   • Execution: {"CEX via CCXT MCP" if mcp_mode == "mcp-only" else "DEX + CEX Hybrid"}")
        print()
    
    cycle_count = 0
    trade_count = 0
    
    def run_cycle_wrapper():
        nonlocal cycle_count, trade_count
        cycle_count += 1
        print(f"\n🔄 CYCLE #{cycle_count} - {time.strftime('%H:%M:%S')}")
        
        results = run_cycle(
            strategy=args.strategy,
            paper_mode=paper_mode,
            mcp_mode=mcp_mode,
            use_mcp=use_mcp
        )
        
        # Count trades
        if results['traditional']['trade_placed']:
            trade_count += 1
        if results['mcp']['trade_placed']:
            trade_count += 1
        
        return results
    
    if args.loop:
        print(f"🔁 Continuous scanning mode - interval: {args.interval}s")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                run_cycle_wrapper()
                print(f"\n⏰ Next scan in {args.interval} seconds...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print(f"\n\n📊 Session Summary:")
            print(f"   Cycles: {cycle_count}")
            print(f"   Trades: {trade_count}")
            print(f"   Strategy: {args.strategy}")
            print(f"   MCP Mode: {mcp_mode}")
            print("\n👋 Session ended by user.")
    else:
        # Single cycle
        results = run_cycle_wrapper()
        
        print("\n" + "=" * 60)
        print("📊 CYCLE SUMMARY")
        print("=" * 60)
        
        if results['traditional']['trade_placed']:
            order = results['traditional']['order']
            print(f"✅ DEX Trade (Slinger):")
            print(f"   Token: {order.token_symbol}")
            print(f"   Chain: {order.chain_id}")
            print(f"   Amount: {order.amount_eth:.6f} ETH" if order.amount_eth else "Amount: N/A")
            print(f"   Entry: ${order.entry_price_usd:.8f}" if order.entry_price_usd else "Entry: N/A")
        else:
            print("❌ No DEX trade placed")
        
        if results['mcp']['trade_placed']:
            exec_result = results['mcp']['execution']
            print(f"\n✅ CEX Trade (PHANTOM MCP):")
            print(f"   Symbol: {exec_result['symbol']}")
            print(f"   Side: {exec_result['side'].upper()}")
            print(f"   Size: {exec_result['amount_pct']*100:.2f}%")
            print(f"   Exchange: {exec_result['exchange']}")
            print(f"   Mode: {"📄 PAPER" if exec_result.get('paper_mode', True) else "🚨 LIVE"}")
        else:
            print("\n❌ No CEX trade placed via MCP")
        
        print(f"\n🎯 Strategy: {results['strategy']}")
        print(f"🔗 MCP Mode: {results['mcp_mode']}")
        
        # Save results to log
        log_entry = {
            'timestamp': time.time(),
            'strategy': args.strategy,
            'mcp_mode': mcp_mode,
            'paper_mode': paper_mode,
            'results': results
        }
        
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"mcp_integration_{int(time.time())}.json")
        
        import json
        with open(log_file, 'w') as f:
            json.dump(log_entry, f, indent=2, default=str)
        
        print(f"\n📝 Results logged to: {log_file}")


if __name__ == "__main__":
    main()