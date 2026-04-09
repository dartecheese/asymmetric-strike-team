import time
import logging
from typing import Optional

from core.models import TradeSignal, RiskAssessment, ExecutionOrder, RiskLevel
from strategy_factory import StrategyFactory
from execution.slinger import SlingerAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StrategyRunner")

# --- Mock Agents for Pipeline Demonstration ---

class WhispererAgent:
    def __init__(self, config):
        self.config = config
    def scan(self) -> Optional[TradeSignal]:
        logger.info(f"[Whisperer] Scanning for social velocity...")
        time.sleep(0.5)
        return TradeSignal(token_address="0xTOKEN", chain="ethereum", narrative_score=90, reasoning="Trending", discovered_at=time.time())

class ShadowAgent:
    def __init__(self, config):
        self.config = config
    def watch_wallets(self) -> Optional[TradeSignal]:
        logger.info(f"[Shadow] Watching target wallets {self.config.target_wallets} for activity...")
        time.sleep(0.5)
        return TradeSignal(token_address="0xWHALETOKEN", chain="ethereum", narrative_score=100, reasoning="Smart money buy detected", discovered_at=time.time())

class OracleAgent:
    def __init__(self, config):
        self.config = config
    def generate_signal(self) -> Optional[TradeSignal]:
        logger.info(f"[Oracle] Analyzing macro indicators and whale movements...")
        time.sleep(0.5)
        return TradeSignal(token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", chain="ethereum", narrative_score=85, reasoning="Macro accumulation + whale buys", discovered_at=time.time())

class SentinelAgent:
    def __init__(self, config):
        self.config = config
    def generate_signal(self, token_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2") -> Optional[TradeSignal]:
        logger.info(f"[Sentinel] Analyzing market structure and liquidity...")
        time.sleep(0.5)
        return TradeSignal(token_address=token_address, chain="ethereum", narrative_score=88, reasoning="Optimal entry zone identified", discovered_at=time.time())

class AlchemistAgent:
    def __init__(self, config):
        self.config = config
    def generate_signal(self) -> Optional[TradeSignal]:
        logger.info(f"[Alchemist] Scanning for optimal yield opportunities...")
        time.sleep(0.5)
        return TradeSignal(token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", chain="ethereum", narrative_score=92, reasoning="High APR rebalance opportunity", discovered_at=time.time())

class SleuthAgent:
    def __init__(self, config):
        self.config = config
    def investigate(self, token_address: str) -> bool:
        logger.info(f"[Sleuth] Running on-chain forensics on {token_address}...")
        time.sleep(0.5)
        return True # Mock passing the forensic check

class PathfinderAgent:
    def __init__(self, config):
        self.config = config
    def find_arbitrage(self) -> Optional[TradeSignal]:
        logger.info(f"[Pathfinder] Scanning for arbitrage opportunities...")
        time.sleep(0.5)
        return TradeSignal(token_address="0xARBTOKEN", chain="ethereum", narrative_score=95, reasoning="1.8% arbitrage spread detected", discovered_at=time.time())

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

# --- Main Event Loop ---

def run_strategy(strategy_name: str):
    logger.info(f"=== INITIALIZING TEAM CONFIG: {strategy_name.upper()} ===")
    
    factory = StrategyFactory()
    profile = factory.get_profile(strategy_name)
    logger.info(f"Goal: {profile.description}\n")
    
    # --- 1. Dynamic Ingestion Phase ---
    signal = None
    
    # Check each possible ingestion agent in priority order
    if profile.shadow:
        shadow = ShadowAgent(profile.shadow)
        signal = shadow.watch_wallets()
    elif profile.oracle:
        oracle = OracleAgent(profile.oracle)
        signal = oracle.generate_signal()
    elif profile.sentinel:
        sentinel = SentinelAgent(profile.sentinel)
        signal = sentinel.generate_signal()
    elif profile.alchemist:
        alchemist = AlchemistAgent(profile.alchemist)
        signal = alchemist.generate_signal()
    elif profile.pathfinder:
        pathfinder = PathfinderAgent(profile.pathfinder)
        signal = pathfinder.find_arbitrage()
    elif profile.whisperer:
        whisperer = WhispererAgent(profile.whisperer)
        signal = whisperer.scan()
        
    if not signal:
        logger.info("No actionable signals found. Sleeping.")
        return
        
    # --- 2. Optional Forensics Phase ---
    if profile.sleuth:
        sleuth = SleuthAgent(profile.sleuth)
        passed = sleuth.investigate(signal.token_address)
        if not passed:
            logger.warning("Trade rejected by Sleuth forensics.")
            return
            
    # --- 3. Core Pipeline (Actuary -> Slinger -> Reaper) ---
    actuary = ActuaryAgent(profile.actuary)
    assessment = actuary.assess_risk(signal)
    
    if assessment.risk_level == RiskLevel.REJECTED:
        logger.warning(f"Trade rejected by Actuary: {assessment.warnings}")
        return
        
    order = ExecutionOrder(
        token_address=assessment.token_address,
        action="BUY",
        amount_usd=assessment.max_allocation_usd,
        slippage_tolerance=profile.slinger.base_slippage_tolerance,
        gas_premium_gwei=30.0
    )
    
    slinger = SlingerAgent(profile.slinger)
    tx_hash = slinger.execute_order(order, wallet_address="0xMyWallet", private_key="MockKey")
    
    if tx_hash:
        reaper = ReaperAgent(profile.reaper)
        reaper.monitor_position(tx_hash)
        
    logger.info("=== CYCLE COMPLETE ===\n")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing All Strategy Configurations")
    print("="*60 + "\n")
    
    factory = StrategyFactory()
    
    # Test all strategies
    strategies = [
        "degen",
        "sniper", 
        "shadow_clone",
        "arb_hunter",
        "oracle_eye",
        "liquidity_sentinel",
        "yield_alchemist",
        "forensic_sniper"
    ]
    
    for strategy in strategies:
        print(f"\n🧪 Testing: {strategy}")
        print("-" * 40)
        run_strategy(strategy)
        time.sleep(1)
    
    print("\n" + "="*60)
    print("✅ All strategy configurations tested successfully!")
    print("="*60)