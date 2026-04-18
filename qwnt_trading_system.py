#!/usr/bin/env python3
"""
QWNT Trading System with TradingView MCP Integration
Quantitative trading with real-time market data and enhanced decision making
"""

import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import logging

from agents.qwnt_enhanced_whisperer import QWNTEnhancedWhisperer
from agents.actuary import Actuary
from execution.unified_slinger import UnifiedSlingerAgent
from strategy_factory import StrategyFactory, SlingerConfig
from core.models import ExecutionOrder
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('qwnt_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("QWNT_Trading_System")

class QWNTTradingSystem:
    """
    Complete QWNT trading system with TradingView MCP integration
    Combines quantitative market data with autonomous trading execution
    """
    
    def __init__(self, use_mock_tv: bool = False):
        load_dotenv()
        
        # Configuration
        self.strategy_name = os.getenv("STRATEGY_PROFILE", "oracle_eye")
        self.use_real_execution = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
        self.rpc_url = os.getenv("ETH_RPC_URL")
        self.private_key = os.getenv("PRIVATE_KEY")
        self.scan_interval = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))
        
        # Initialize components
        self.whisperer = QWNTEnhancedWhisperer(use_mock_tv=use_mock_tv)
        self.actuary = Actuary(max_allowed_tax=0.25)
        
        # Initialize execution
        self._init_execution()
        
        # Performance tracking
        self.trades_executed = 0
        self.start_time = datetime.now()
        
        logger.info(f"🚀 QWNT Trading System Initialized")
        logger.info(f"  Strategy: {self.strategy_name}")
        logger.info(f"  Execution Mode: {'REAL' if self.use_real_execution else 'PAPER'}")
        logger.info(f"  TradingView Integration: {'MOCK' if use_mock_tv else 'LIVE'}")
    
    def _init_execution(self):
        """Initialize execution layer"""
        factory = StrategyFactory()
        
        try:
            strategy_profile = factory.get_profile(self.strategy_name)
            slinger_config = strategy_profile.slinger
        except:
            # Default config if strategy not found
            slinger_config = SlingerConfig(
                use_private_mempool=False,
                base_slippage_tolerance=0.15,
                gas_premium_multiplier=2.0
            )
        
        self.slinger = UnifiedSlingerAgent(slinger_config)
        
        if self.slinger.mode == "REAL":
            logger.warning("⚠️  REAL EXECUTION MODE ENABLED - Transactions will use real funds!")
        else:
            logger.info("📝 Paper trading mode - no real transactions")
    
    def get_market_report(self) -> Dict:
        """Get comprehensive market report from TradingView"""
        logger.info("📈 Generating market report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "system": "QWNT Trading System",
            "strategy": self.strategy_name,
            "market_analysis": {},
            "trading_opportunities": [],
            "recommendations": []
        }
        
        # Get market insights
        insights = self.whisperer.get_market_insights()
        report["market_analysis"] = insights
        
        # Get strategy-specific opportunities
        signals = self.whisperer.scan_with_strategy(self.strategy_name)
        report["trading_opportunities"] = [
            {
                "symbol": s.token_symbol,
                "action": s.action,
                "confidence": f"{s.confidence:.1%}",
                "narrative": s.narrative,
                "chain": s.chain.value
            }
            for s in signals
        ]
        
        # Generate recommendations
        regime = insights.get("market_regime", "unknown")
        
        if regime == "bull":
            report["recommendations"].extend([
                "Increase position sizes for momentum strategies",
                "Focus on high-beta assets",
                "Consider trailing stops to capture upside"
            ])
        elif regime == "bear":
            report["recommendations"].extend([
                "Reduce position sizes by 50%",
                "Focus on defensive/blue-chip assets",
                "Use tight stop losses",
                "Consider short opportunities"
            ])
        else:
            report["recommendations"].extend([
                "Maintain balanced portfolio",
                "Use medium position sizes",
                "Monitor for regime change"
            ])
        
        # Add execution mode recommendation
        if self.slinger.mode == "PAPER":
            report["recommendations"].append("⚠️ Currently in PAPER trading mode - no real funds at risk")
        else:
            report["recommendations"].append("🚨 REAL EXECUTION MODE - Real funds at risk!")
        
        return report
    
    def run_trading_cycle(self) -> bool:
        """Run a complete trading cycle"""
        logger.info(f"\n🔄 Starting trading cycle for {self.strategy_name}")
        logger.info("-" * 50)
        
        try:
            # 1. Get market insights
            market_report = self.get_market_report()
            regime = market_report["market_analysis"].get("market_regime", "unknown")
            logger.info(f"📊 Market Regime: {regime.upper()}")
            
            # 2. Generate trading signals
            signals = self.whisperer.scan_with_strategy(self.strategy_name)
            
            if not signals:
                logger.warning("No trading signals generated")
                return False
            
            # 3. Process each signal
            successful_trades = 0
            
            for signal in signals[:2]:  # Limit to 2 signals per cycle
                logger.info(f"\n📡 Processing signal: {signal.action} {signal.token_symbol}")
                logger.info(f"  Confidence: {signal.confidence:.1%}")
                logger.info(f"  Narrative: {signal.narrative}")
                
                # 4. Risk assessment
                assessment = self.actuary.assess_risk(signal)
                
                if not assessment.approved:
                    logger.warning(f"  ❌ Risk assessment failed: {assessment.rejection_reason}")
                    continue
                
                logger.info(f"  ✅ Risk assessment passed")
                
                # 5. Create execution order
                order = ExecutionOrder(
                    token_address=signal.token_address,
                    action=signal.action,
                    amount_usd=100.0,  # Fixed amount for demo
                    slippage_tolerance=0.15,
                    gas_premium_gwei=2.0
                )
                
                # 6. Execute trade
                logger.info(f"  🚀 Executing {order.action} order for ${order.amount_usd}")
                
                try:
                    result = self.slinger.execute_order(order)
                    
                    if result and hasattr(result, 'success') and result.success:
                        logger.info(f"  ✅ Trade executed successfully")
                        if hasattr(result, 'tx_hash'):
                            logger.info(f"  Transaction: {result.tx_hash}")
                        successful_trades += 1
                        self.trades_executed += 1
                    else:
                        logger.warning(f"  ❌ Trade execution failed")
                        
                except Exception as e:
                    logger.error(f"  💥 Execution error: {e}")
            
            # 7. Print cycle summary
            logger.info(f"\n📈 Cycle complete: {successful_trades} trades executed")
            
            # Update performance metrics
            self._update_performance_metrics()
            
            return successful_trades > 0
            
        except Exception as e:
            logger.error(f"💥 Trading cycle failed: {e}")
            return False
    
    def _update_performance_metrics(self):
        """Update and log performance metrics"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        metrics = {
            "uptime_seconds": int(elapsed),
            "trades_executed": self.trades_executed,
            "trades_per_hour": self.trades_executed / (elapsed / 3600) if elapsed > 0 else 0,
            "execution_mode": self.slinger.mode,
            "strategy": self.strategy_name,
            "last_update": datetime.now().isoformat()
        }
        
        # Save metrics to file
        with open("qwnt_performance.json", "w") as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"📊 Performance: {self.trades_executed} trades in {int(elapsed)}s "
                   f"({metrics['trades_per_hour']:.1f}/hour)")
    
    def run_continuous(self, max_cycles: int = None):
        """Run continuous trading"""
        logger.info(f"\n🔍 Starting continuous trading")
        logger.info(f"  Strategy: {self.strategy_name}")
        logger.info(f"  Scan Interval: {self.scan_interval}s")
        logger.info(f"  Max Cycles: {max_cycles or 'unlimited'}")
        logger.info("  Press Ctrl+C to stop\n")
        
        cycle_count = 0
        
        try:
            while max_cycles is None or cycle_count < max_cycles:
                cycle_count += 1
                logger.info(f"\n📈 CYCLE {cycle_count}")
                logger.info("=" * 40)
                
                success = self.run_trading_cycle()
                
                if not success and cycle_count > 3:
                    logger.warning("Multiple failed cycles - checking market conditions...")
                    report = self.get_market_report()
                    regime = report["market_analysis"].get("market_regime", "unknown")
                    
                    if regime == "bear":
                        logger.info("Bear market detected - increasing scan interval")
                        self.scan_interval = min(self.scan_interval * 2, 300)  # Max 5 minutes
                
                # Wait for next cycle
                logger.info(f"\n⏳ Waiting {self.scan_interval}s for next cycle...")
                time.sleep(self.scan_interval)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down...")
        finally:
            self.shutdown()
    
    def run_single_cycle(self):
        """Run a single trading cycle and shutdown"""
        logger.info("\n🧪 Running single trading cycle")
        self.run_trading_cycle()
        self.shutdown()
    
    def shutdown(self):
        """Shutdown the system"""
        logger.info("\n🛑 Shutting down QWNT Trading System")
        
        # Print final performance
        elapsed = (datetime.now() - self.start_time).total_seconds()
        logger.info(f"\n📈 FINAL PERFORMANCE:")
        logger.info(f"  Total runtime: {int(elapsed)}s")
        logger.info(f"  Trades executed: {self.trades_executed}")
        logger.info(f"  Avg trades/hour: {self.trades_executed / (elapsed / 3600):.1f}" if elapsed > 0 else "N/A")
        
        # Save final report
        final_report = self.get_market_report()
        final_report["performance"] = {
            "total_trades": self.trades_executed,
            "total_runtime_seconds": int(elapsed),
            "shutdown_time": datetime.now().isoformat()
        }
        
        with open("qwnt_final_report.json", "w") as f:
            json.dump(final_report, f, indent=2)
        
        logger.info(f"✅ Final report saved to qwnt_final_report.json")
        logger.info("\n🎯 QWNT Trading System shutdown complete")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="QWNT Trading System with TradingView Integration")
    parser.add_argument("--mode", choices=["continuous", "single", "report"], 
                       default="single", help="Operation mode")
    parser.add_argument("--strategy", default="oracle_eye", 
                       help="Strategy profile to use")
    parser.add_argument("--interval", type=int, default=30,
                       help="Scan interval in seconds (continuous mode only)")
    parser.add_argument("--max-cycles", type=int,
                       help="Maximum number of cycles (continuous mode only)")
    parser.add_argument("--mock-tv", action="store_true",
                       help="Use mock TradingView data (for development)")
    
    args = parser.parse_args()
    
    # Create and run system
    system = QWNTTradingSystem(use_mock_tv=args.mock_tv)
    
    # Override config from args
    if args.strategy:
        os.environ["STRATEGY_PROFILE"] = args.strategy
    if args.interval:
        os.environ["SCAN_INTERVAL_SECONDS"] = str(args.interval)
    
    # Run in selected mode
    if args.mode == "continuous":
        system.run_continuous(max_cycles=args.max_cycles)
    elif args.mode == "single":
        system.run_single_cycle()
    elif args.mode == "report":
        report = system.get_market_report()
        print(json.dumps(report, indent=2))
        system.shutdown()

if __name__ == "__main__":
    main()