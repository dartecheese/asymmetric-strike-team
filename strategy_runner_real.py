"""
Enhanced Strategy Runner with Real Execution Support
Integrates RealSlingerAgent for live Web3.py transactions when USE_REAL_EXECUTION=true
"""

import os
import time
import logging
from typing import Optional
from dotenv import load_dotenv

from core.models import TradeSignal, RiskAssessment, ExecutionOrder, RiskLevel
from strategy_factory import StrategyFactory

# Load environment variables
load_dotenv()

# Check for real execution mode
USE_REAL_EXECUTION = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
RPC_URL = os.getenv("ETH_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StrategyRunnerReal")

# --- Mock Agents for Pipeline Demonstration ---
# (Same as original for non-execution parts)

class WhispererAgent:
    def __init__(self, config):
        self.config = config
    def scan(self) -> Optional[TradeSignal]:
        logger.info(f"[Whisperer] Scanning for social velocity...")
        time.sleep(0.5)
        return TradeSignal(token_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", chain="ethereum", narrative_score=90, reasoning="Trending", discovered_at=time.time())

class ShadowAgent:
    def __init__(self, config):
        self.config = config
    def watch_wallets(self) -> Optional[TradeSignal]:
        logger.info(f"[Shadow] Watching target wallets {self.config.target_wallets} for activity...")
        time.sleep(0.5)
        return TradeSignal(token_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", chain="ethereum", narrative_score=100, reasoning="Smart money buy detected", discovered_at=time.time())

class ActuaryAgent:
    def __init__(self, config):
        self.config = config
    def assess_risk(self, signal: TradeSignal) -> RiskAssessment:
        logger.info(f"[Actuary] Auditing contract & taxes for {signal.token_address}...")
        time.sleep(0.5)
        return RiskAssessment(
            token_address=signal.token_address, is_honeypot=False, buy_tax=2.0, sell_tax=2.0,
            liquidity_locked=True, risk_level=RiskLevel.MEDIUM, max_allocation_usd=500.0, warnings=[]
        )

class ReaperAgent:
    def __init__(self, config):
        self.config = config
    def monitor_position(self, tx_hash: str):
        logger.info(f"[Reaper] Monitoring position {tx_hash} (TP: {self.config.take_profit_pct}%, SL: {self.config.stop_loss_pct}%)")

# --- Main Event Loop with Real Execution Support ---

def run_strategy_real(strategy_name: str):
    """Run strategy with real execution support."""
    logger.info(f"=== INITIALIZING TEAM CONFIG: {strategy_name.upper()} ===")
    
    factory = StrategyFactory()
    profile = factory.get_profile(strategy_name)
    logger.info(f"Goal: {profile.description}")
    logger.info(f"Execution Mode: {'REAL' if USE_REAL_EXECUTION else 'PAPER'}\n")
    
    # --- 1. Signal Generation Phase ---
    signal = None
    
    # Check each possible ingestion agent in priority order
    if profile.shadow:
        shadow = ShadowAgent(profile.shadow)
        signal = shadow.watch_wallets()
    elif profile.whisperer:
        whisperer = WhispererAgent(profile.whisperer)
        signal = whisperer.scan()
        
    if not signal:
        logger.info("No actionable signals found. Sleeping.")
        return
        
    # --- 2. Risk Assessment Phase ---
    actuary = ActuaryAgent(profile.actuary)
    assessment = actuary.assess_risk(signal)
    
    if assessment.risk_level == RiskLevel.REJECTED:
        logger.warning(f"Trade rejected by Actuary: {assessment.warnings}")
        return
        
    # --- 3. Execution Phase ---
    order = ExecutionOrder(
        token_address=assessment.token_address,
        action="BUY",
        amount_usd=assessment.max_allocation_usd,
        slippage_tolerance=profile.slinger.base_slippage_tolerance,
        gas_premium_gwei=30.0
    )
    
    tx_hash = None
    
    if USE_REAL_EXECUTION:
        # Real Web3.py execution
        if not RPC_URL or not PRIVATE_KEY:
            logger.error("Real execution enabled but missing RPC_URL or PRIVATE_KEY in .env")
            return
            
        try:
            from execution.real_slinger import RealSlingerAgent
            logger.info("🚀 Initializing RealSlingerAgent for live execution...")
            
            slinger = RealSlingerAgent(profile.slinger, RPC_URL, PRIVATE_KEY)
            tx_hash = slinger.execute_order(order)
            
            if tx_hash:
                logger.info(f"✅ Real transaction sent! Hash: {tx_hash}")
            else:
                logger.error("❌ Real execution failed")
                
        except ImportError as e:
            logger.error(f"Failed to import RealSlingerAgent: {e}")
            return
        except Exception as e:
            logger.error(f"Real execution error: {e}")
            return
    else:
        # Paper trading / simulation
        from execution.slinger import SlingerAgent
        logger.info("📝 Paper trading mode - simulating execution")
        
        # Use a mock RPC for simulation
        slinger = SlingerAgent(profile.slinger, rpc_url="http://localhost:8545")
        tx_hash = slinger.execute_order(order, wallet_address="0xMockWallet", private_key="MockKey")
        
        if tx_hash:
            logger.info(f"📝 Simulated transaction: {tx_hash}")
    
    # --- 4. Position Monitoring Phase ---
    if tx_hash:
        reaper = ReaperAgent(profile.reaper)
        reaper.monitor_position(tx_hash)
        
    logger.info("=== CYCLE COMPLETE ===\n")

def test_real_execution_setup():
    """Test if real execution is properly configured."""
    print("\n" + "="*60)
    print("Testing Real Execution Setup")
    print("="*60)
    
    if USE_REAL_EXECUTION:
        print("✅ USE_REAL_EXECUTION=true")
        
        if RPC_URL:
            print(f"✅ RPC_URL configured: {RPC_URL[:30]}...")
        else:
            print("❌ RPC_URL not configured")
            
        if PRIVATE_KEY:
            print(f"✅ PRIVATE_KEY configured: {PRIVATE_KEY[:10]}...")
        else:
            print("❌ PRIVATE_KEY not configured")
            
        # Test Web3 connection
        try:
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider(RPC_URL))
            if w3.is_connected():
                print(f"✅ Connected to chain ID: {w3.eth.chain_id}")
                print(f"   Latest block: {w3.eth.block_number}")
            else:
                print("❌ Failed to connect to RPC")
        except Exception as e:
            print(f"❌ Web3 connection test failed: {e}")
    else:
        print("📝 Paper trading mode (USE_REAL_EXECUTION=false)")
        
    print("="*60)

if __name__ == "__main__":
    # Test the setup
    test_real_execution_setup()
    
    print("\n" + "="*60)
    print("Testing Strategy Execution")
    print("="*60 + "\n")
    
    # Test with degen strategy
    run_strategy_real("degen")
    
    print("\n" + "="*60)
    print("✅ Strategy execution test complete!")
    print("="*60)