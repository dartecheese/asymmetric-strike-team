import time
import logging
import random
from typing import Optional, Dict, List
from pydantic import BaseModel

from core.models import TradeSignal
from strategy_factory import SentinelConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Sentinel")

class MarketStructure:
    """Represents current market structure analysis."""
    def __init__(self):
        self.support_levels: List[float] = []
        self.resistance_levels: List[float] = []
        self.liquidity_clusters: Dict[str, float] = {}  # price -> liquidity
        self.volatility_5min: float = 0.0

class SentinelAgent:
    """
    The Sentinel - Monitors market structure, liquidity, and volatility.
    Identifies optimal entry/exit points and warns of potential liquidations.
    """
    def __init__(self, config: SentinelConfig):
        self.config = config
        self.market_structure = MarketStructure()
        logger.info(f"🛡️  Sentinel initialized.")
        logger.info(f"   Liquidity monitoring: {config.monitor_liquidity_pools}")
        logger.info(f"   Volatility alert: {config.volatility_alert_threshold}%")
    
    def scan_liquidity_pools(self, token_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2") -> Dict[str, float]:
        """Scan DEX liquidity pools for the token."""
        if not self.config.monitor_liquidity_pools:
            return {}
        
        logger.info(f"[Sentinel] Scanning liquidity pools for {token_address[:10]}...")
        time.sleep(0.3)
        
        # Mock data - in reality: The Graph, DEX subgraphs, etc.
        pools = {
            "uniswap_v3_0.3%": {
                "liquidity_usd": 12500000,
                "current_price": 3050.25,
                "price_range_low": 2900.50,
                "price_range_high": 3200.75,
                "depth_score": 0.85  # 0-1
            },
            "uniswap_v2": {
                "liquidity_usd": 8500000,
                "current_price": 3048.90,
                "slippage_1%": 0.15,  # % price impact for 1% of pool
                "depth_score": 0.72
            },
            "sushiswap": {
                "liquidity_usd": 3200000,
                "current_price": 3051.10,
                "slippage_1%": 0.28,
                "depth_score": 0.61
            }
        }
        
        # Update market structure with liquidity clusters
        for pool_name, data in pools.items():
            price = data["current_price"]
            liquidity = data["liquidity_usd"]
            self.market_structure.liquidity_clusters[pool_name] = liquidity
            
            # Identify support/resistance from liquidity concentrations
            if liquidity > 5000000:  # Major liquidity pool
                if price < data.get("price_range_low", price * 0.95):
                    self.market_structure.support_levels.append(price * 0.97)
                elif price > data.get("price_range_high", price * 1.05):
                    self.market_structure.resistance_levels.append(price * 1.03)
        
        return pools
    
    def check_volatility(self, token_address: str) -> Dict[str, float]:
        """Monitor 5-minute volatility and check against threshold."""
        logger.info(f"[Sentinel] Checking volatility for {token_address[:10]}...")
        time.sleep(0.2)
        
        # Mock volatility calculation
        current_price = 3050.0
        price_5min_ago = current_price * (1 + random.uniform(-0.1, 0.1))  # ±10%
        
        volatility_pct = abs((current_price - price_5min_ago) / price_5min_ago) * 100
        self.market_structure.volatility_5min = volatility_pct
        
        alert = volatility_pct >= self.config.volatility_alert_threshold
        
        return {
            "volatility_5min_pct": volatility_pct,
            "alert_triggered": alert,
            "current_price": current_price,
            "price_5min_ago": price_5min_ago
        }
    
    def monitor_liquidations(self) -> Optional[Dict[str, float]]:
        """Monitor for potential liquidation cascades."""
        if not self.config.liquidation_watch:
            return None
        
        logger.info("[Sentinel] Monitoring liquidation levels...")
        time.sleep(0.4)
        
        # Mock liquidation data
        liquidation_levels = {
            "eth_longs_liquidation_price": 2850.0,  # Price where many longs get liquidated
            "eth_shorts_liquidation_price": 3250.0,
            "estimated_liquidation_size_usd": 45000000,
            "distance_to_long_liquidation_pct": 6.5,  # Current price is 6.5% above liquidation
            "distance_to_short_liquidation_pct": 6.2,
            "risk_level": "moderate"  # low/moderate/high/critical
        }
        
        # Check if we're approaching dangerous levels
        if liquidation_levels["distance_to_long_liquidation_pct"] < 3.0:
            logger.warning(f"⚠️  Approaching long liquidation cascade! ({liquidation_levels['distance_to_long_liquidation_pct']}% away)")
        
        return liquidation_levels
    
    def identify_optimal_entry(self, token_address: str) -> Optional[Dict[str, float]]:
        """Identify optimal entry points based on market structure."""
        if not self.config.track_support_resistance:
            return None
        
        logger.info(f"[Sentinel] Identifying optimal entry for {token_address[:10]}...")
        time.sleep(0.3)
        
        # Use market structure analysis
        if not self.market_structure.support_levels:
            self.scan_liquidity_pools(token_address)
        
        if self.market_structure.support_levels:
            # Find strongest support (most liquidity)
            strongest_support = max(self.market_structure.support_levels)
            
            # Calculate entry zones
            entry_zone = {
                "optimal_entry": strongest_support * 1.02,  # 2% above support
                "aggressive_entry": strongest_support * 1.00,  # At support
                "conservative_entry": strongest_support * 0.98,  # Below support (if breaks)
                "stop_loss": strongest_support * 0.95,
                "take_profit_1": strongest_support * 1.08,
                "take_profit_2": strongest_support * 1.15,
                "confidence_score": 0.75  # 0-1
            }
            
            return entry_zone
        
        return None
    
    def generate_signal(self, token_address: str) -> Optional[TradeSignal]:
        """Generate trade signal based on market structure analysis."""
        logger.info(f"[Sentinel] Analyzing market structure for {token_address[:10]}...")
        
        # Run all analyses
        liquidity_data = self.scan_liquidity_pools(token_address)
        volatility_data = self.check_volatility(token_address)
        liquidation_data = self.monitor_liquidations()
        entry_zone = self.identify_optimal_entry(token_address)
        
        # Calculate signal score
        score = 50
        
        reasoning_parts = []
        
        # Volatility analysis
        if volatility_data["alert_triggered"]:
            score -= 25
            reasoning_parts.append(f"High volatility ({volatility_data['volatility_5min_pct']:.1f}%)")
        else:
            score += 10
            reasoning_parts.append(f"Stable volatility ({volatility_data['volatility_5min_pct']:.1f}%)")
        
        # Liquidity analysis
        if liquidity_data:
            total_liquidity = sum(pool["liquidity_usd"] for pool in liquidity_data.values())
            if total_liquidity > 10000000:  # > $10M liquidity
                score += 15
                reasoning_parts.append(f"Deep liquidity (${total_liquidity/1e6:.1f}M)")
            else:
                score -= 10
                reasoning_parts.append(f"Thin liquidity (${total_liquidity/1e6:.1f}M)")
        
        # Entry zone analysis
        if entry_zone and entry_zone["confidence_score"] > 0.7:
            score += 20
            reasoning_parts.append(f"Clear entry zone identified (confidence: {entry_zone['confidence_score']:.2f})")
        
        # Liquidation risk
        if liquidation_data and liquidation_data["risk_level"] in ["high", "critical"]:
            score -= 30
            reasoning_parts.append(f"High liquidation risk ({liquidation_data['risk_level']})")
        
        # Generate signal if conditions are favorable
        if score >= 70 and entry_zone:
            reasoning = " | ".join(reasoning_parts)
            
            return TradeSignal(
                token_address=token_address,
                chain="ethereum",
                narrative_score=min(score, 100),
                reasoning=reasoning,
                discovered_at=time.time()
            )
        
        return None

if __name__ == "__main__":
    from strategy_factory import StrategyFactory
    
    factory = StrategyFactory()
    sentinel_config = factory.get_profile("liquidity_sentinel").sentinel
    
    sentinel = SentinelAgent(sentinel_config)
    
    print("Testing Sentinel Agent:")
    print("-" * 40)
    
    # Test with WETH
    test_token = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    
    liquidity = sentinel.scan_liquidity_pools(test_token)
    print(f"Liquidity Pools: {len(liquidity)}")
    
    volatility = sentinel.check_volatility(test_token)
    print(f"5-min Volatility: {volatility['volatility_5min_pct']:.2f}%")
    
    liquidations = sentinel.monitor_liquidations()
    if liquidations:
        print(f"Liquidation Risk: {liquidations['risk_level']}")
    
    entry_zone = sentinel.identify_optimal_entry(test_token)
    if entry_zone:
        print(f"Optimal Entry: ${entry_zone['optimal_entry']:.2f}")
    
    signal = sentinel.generate_signal(test_token)
    if signal:
        print(f"\n✅ Signal Generated:")
        print(f"   Score: {signal.narrative_score}/100")
        print(f"   Reason: {signal.reasoning}")
    else:
        print("\n⏸️  No signal generated (market conditions not optimal)")