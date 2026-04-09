import time
import logging
import random
from typing import Optional, Dict, List
from pydantic import BaseModel
from enum import Enum

from core.models import TradeSignal
from strategy_factory import AlchemistConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Alchemist")

class ProtocolRisk(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class YieldOpportunity:
    """Represents a yield farming opportunity."""
    def __init__(self, protocol: str, apr: float, tvl: float, risk: ProtocolRisk):
        self.protocol = protocol
        self.apr = apr
        self.tvl = tvl
        self.risk = risk
        self.score = self._calculate_score()
    
    def _calculate_score(self) -> float:
        """Calculate a unified score for comparison."""
        # Weight APR more than TVL, penalize risk
        apr_score = min(self.apr / 50.0, 1.0)  # Cap at 50% APR = 1.0
        tvl_score = min(self.tvl / 1000000000, 1.0)  # Cap at $1B TVL = 1.0
        
        risk_multiplier = {
            ProtocolRisk.LOW: 1.0,
            ProtocolRisk.MEDIUM: 0.7,
            ProtocolRisk.HIGH: 0.4
        }
        
        return (apr_score * 0.6 + tvl_score * 0.4) * risk_multiplier[self.risk]

class AlchemistAgent:
    """
    The Alchemist - Optimizes yield across DeFi protocols.
    Automatically rotates capital to highest risk-adjusted returns.
    """
    def __init__(self, config: AlchemistConfig):
        self.config = config
        self.current_positions: Dict[str, float] = {}  # protocol -> amount_usd
        self.yield_history: List[Dict] = []
        logger.info(f"⚗️  Alchemist initialized.")
        logger.info(f"   Target protocols: {', '.join(config.target_protocols)}")
        logger.info(f"   Min APR threshold: {config.min_apr_threshold}%")
    
    def scan_yield_opportunities(self) -> List[YieldOpportunity]:
        """Scan all target protocols for current yield opportunities."""
        logger.info(f"[Alchemist] Scanning yield opportunities...")
        time.sleep(0.5)
        
        opportunities = []
        
        # Mock data - in reality: DeFi Llama, Yearn, etc.
        yield_data = {
            "aave": {
                "stablecoin_pool": {"apr": 8.5, "tvl": 4500000000, "risk": ProtocolRisk.LOW},
                "eth_pool": {"apr": 3.2, "tvl": 2800000000, "risk": ProtocolRisk.LOW},
            },
            "compound": {
                "usdc_pool": {"apr": 7.8, "tvl": 3200000000, "risk": ProtocolRisk.LOW},
                "eth_pool": {"apr": 2.9, "tvl": 1900000000, "risk": ProtocolRisk.LOW},
            },
            "curve": {
                "3pool": {"apr": 5.2, "tvl": 8500000000, "risk": ProtocolRisk.LOW},
                "frax_pool": {"apr": 12.7, "tvl": 1200000000, "risk": ProtocolRisk.MEDIUM},
            },
            "yearn": {
                "usdc_vault": {"apr": 9.3, "tvl": 950000000, "risk": ProtocolRisk.LOW},
                "eth_vault": {"apr": 4.1, "tvl": 780000000, "risk": ProtocolRisk.LOW},
            },
            "balancer": {
                "eth_80_bal_20": {"apr": 15.2, "tvl": 450000000, "risk": ProtocolRisk.MEDIUM},
                "stable_pool": {"apr": 6.8, "tvl": 320000000, "risk": ProtocolRisk.LOW},
            }
        }
        
        # Filter to target protocols and create opportunities
        for protocol in self.config.target_protocols:
            if protocol in yield_data:
                for pool_name, pool_data in yield_data[protocol].items():
                    if pool_data["apr"] >= self.config.min_apr_threshold:
                        opp = YieldOpportunity(
                            protocol=f"{protocol}_{pool_name}",
                            apr=pool_data["apr"],
                            tvl=pool_data["tvl"],
                            risk=pool_data["risk"]
                        )
                        opportunities.append(opp)
        
        # Sort by score (highest first)
        opportunities.sort(key=lambda x: x.score, reverse=True)
        
        return opportunities
    
    def calculate_optimal_allocation(self, capital_usd: float) -> Dict[str, float]:
        """Calculate optimal capital allocation across opportunities."""
        opportunities = self.scan_yield_opportunities()
        
        if not opportunities:
            return {}
        
        allocations = {}
        remaining_capital = capital_usd
        
        # Simple allocation: top 3 opportunities, weighted by score
        top_opportunities = opportunities[:3]
        total_score = sum(opp.score for opp in top_opportunities)
        
        for opp in top_opportunities:
            # Allocate proportionally to score
            allocation_pct = opp.score / total_score if total_score > 0 else 1/3
            
            # Adjust for risk
            risk_adjustment = {
                ProtocolRisk.LOW: 1.0,
                ProtocolRisk.MEDIUM: 0.8 * self.config.risk_adjustment_speed,
                ProtocolRisk.HIGH: 0.5 * self.config.risk_adjustment_speed
            }
            
            final_pct = allocation_pct * risk_adjustment[opp.risk]
            allocation_usd = capital_usd * final_pct
            
            allocations[opp.protocol] = allocation_usd
            remaining_capital -= allocation_usd
        
        # If auto-compounding is enabled, note that
        if self.config.auto_compound:
            logger.info("[Alchemist] Auto-compounding enabled - rewards will be reinvested")
        
        return allocations
    
    def assess_protocol_health(self, protocol: str) -> Dict[str, any]:
        """Assess the health and safety of a protocol."""
        logger.info(f"[Alchemist] Assessing health of {protocol}...")
        time.sleep(0.3)
        
        # Mock health checks - in reality: security audits, bug bounties, etc.
        health_metrics = {
            "audit_score": random.uniform(0.7, 1.0),  # 0-1
            "time_since_last_audit_days": random.randint(30, 180),
            "bug_bounty_active": random.choice([True, False]),
            "team_doxxed": random.choice([True, False]),
            "governance_token": random.choice([True, False]),
            "insurance_available": random.choice([True, False]),
            "historical_slashes": 0,  # Number of historical exploits
            "community_sentiment": random.uniform(0.5, 0.95)  # 0-1
        }
        
        # Calculate overall health score
        weights = {
            "audit_score": 0.3,
            "time_since_last_audit_days": -0.1,  # Negative - older audits are worse
            "bug_bounty_active": 0.15,
            "team_doxxed": 0.1,
            "insurance_available": 0.15,
            "historical_slashes": -0.2,
            "community_sentiment": 0.2
        }
        
        health_score = 0.5  # Base
        
        for metric, weight in weights.items():
            value = health_metrics[metric]
            if metric == "time_since_last_audit_days":
                # Normalize: < 90 days = good, > 180 days = bad
                normalized = max(0, 1 - (value / 365))
                health_score += normalized * weight
            elif metric == "historical_slashes":
                health_score += (1 - min(value / 10, 1)) * weight  # 0 slashes = 1, 10+ = 0
            elif isinstance(value, bool):
                health_score += (1 if value else 0) * weight
            else:
                health_score += value * weight
        
        health_metrics["overall_health_score"] = max(0, min(1, health_score))
        
        return health_metrics
    
    def generate_rebalance_signal(self, current_positions: Dict[str, float]) -> Optional[TradeSignal]:
        """Generate signal to rebalance portfolio based on new opportunities."""
        logger.info("[Alchemist] Analyzing rebalance opportunities...")
        
        # Calculate total portfolio value
        total_portfolio = sum(current_positions.values())
        if total_portfolio == 0:
            total_portfolio = 10000  # Default for new portfolio
        
        # Find optimal allocation
        optimal_allocation = self.calculate_optimal_allocation(total_portfolio)
        
        if not optimal_allocation:
            return None
        
        # Compare with current positions
        rebalance_needed = False
        reasoning_parts = []
        
        for protocol, optimal_amount in optimal_allocation.items():
            current_amount = current_positions.get(protocol, 0)
            
            # Check if rebalance needed (>20% difference)
            if abs(optimal_amount - current_amount) / max(optimal_amount, 1) > 0.2:
                rebalance_needed = True
                
                if optimal_amount > current_amount:
                    action = f"Add ${optimal_amount - current_amount:.0f} to {protocol}"
                else:
                    action = f"Remove ${current_amount - optimal_amount:.0f} from {protocol}"
                
                reasoning_parts.append(action)
        
        if rebalance_needed:
            # Get top opportunity for signal focus
            opportunities = self.scan_yield_opportunities()
            if opportunities:
                top_opp = opportunities[0]
                
                # Assess protocol health
                health = self.assess_protocol_health(top_opp.protocol.split("_")[0])
                
                if health["overall_health_score"] > 0.7:  # Only if healthy
                    reasoning = "Rebalance: " + "; ".join(reasoning_parts[:3])  # Limit to top 3
                    
                    return TradeSignal(
                        token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC for yield
                        chain="ethereum",
                        narrative_score=int(top_opp.score * 100),
                        reasoning=f"{reasoning} | Top yield: {top_opp.protocol} ({top_opp.apr:.1f}% APR)",
                        discovered_at=time.time()
                    )
        
        return None
    
    def generate_signal(self) -> Optional[TradeSignal]:
        """Generate yield farming signal."""
        return self.generate_rebalance_signal(self.current_positions)

if __name__ == "__main__":
    from strategy_factory import StrategyFactory
    
    factory = StrategyFactory()
    alchemist_config = factory.get_profile("yield_alchemist").alchemist
    
    alchemist = AlchemistAgent(alchemist_config)
    
    print("Testing Alchemist Agent:")
    print("-" * 40)
    
    # Scan opportunities
    opportunities = alchemist.scan_yield_opportunities()
    print(f"Yield Opportunities Found: {len(opportunities)}")
    
    for i, opp in enumerate(opportunities[:3]):
        print(f"  {i+1}. {opp.protocol}: {opp.apr:.1f}% APR, Score: {opp.score:.3f}")
    
    # Calculate allocation
    allocation = alchemist.calculate_optimal_allocation(10000)
    print(f"\nOptimal Allocation for $10k:")
    for protocol, amount in allocation.items():
        print(f"  {protocol}: ${amount:.2f}")
    
    # Assess protocol health
    if opportunities:
        health = alchemist.assess_protocol_health(opportunities[0].protocol.split("_")[0])
        print(f"\nProtocol Health ({opportunities[0].protocol.split('_')[0]}):")
        print(f"  Overall Score: {health['overall_health_score']:.3f}")
        print(f"  Audit Score: {health['audit_score']:.3f}")
        print(f"  Community Sentiment: {health['community_sentiment']:.3f}")
    
    # Generate signal
    signal = alchemist.generate_signal()
    if signal:
        print(f"\n✅ Signal Generated:")
        print(f"   Token: {signal.token_address[:20]}...")
        print(f"   Score: {signal.narrative_score}/100")
        print(f"   Reason: {signal.reasoning}")
    else:
        print("\n⏸️  No rebalance signal (portfolio already optimal)")