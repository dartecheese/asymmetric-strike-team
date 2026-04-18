import time
import logging
from typing import Optional, List
from pydantic import BaseModel

from core.models import TradeSignal
from strategy_factory import OracleConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Oracle")

class OracleAgent:
    """
    The Oracle - Monitors macro indicators and whale movements.
    Tracks CEX flows, whale wallets, and market sentiment.
    """
    def __init__(self, config: OracleConfig):
        self.config = config
        logger.info(f"🔮 Oracle initialized. Tracking {len(self.config.track_whale_wallets)} whale wallets.")
        logger.info(f"   Monitoring: {', '.join(self.config.macro_indicators)}")
    
    def check_cex_flows(self) -> dict:
        """Monitor CEX inflows/outflows for unusual activity."""
        if not self.config.monitor_cex_flows:
            return {}
        
        logger.info("[Oracle] Checking CEX flows...")
        time.sleep(0.3)  # Simulate API call
        
        # Mock data - in reality: Glassnode, CryptoQuant, etc.
        return {
            "binance_net_flow": 2500.5,  # ETH
            "coinbase_net_flow": -1200.3,
            "kraken_net_flow": 450.7,
            "total_net_flow": 1750.9,
            "trend": "accumulation"  # accumulation/distribution/neutral
        }
    
    def track_whale_movements(self) -> List[dict]:
        """Monitor specified whale wallets for large transactions."""
        alerts = []
        
        for wallet in self.config.track_whale_wallets:
            logger.info(f"[Oracle] Scanning whale wallet: {wallet[:10]}...")
            time.sleep(0.2)
            
            # Mock: 30% chance of a whale move
            import random
            if random.random() < 0.3:
                amount = random.uniform(self.config.alert_threshold_eth, self.config.alert_threshold_eth * 5)
                direction = random.choice(["buy", "sell", "transfer"])
                
                alert = {
                    "wallet": wallet,
                    "amount_eth": amount,
                    "direction": direction,
                    "timestamp": time.time(),
                    "message": f"Whale {direction.upper()} of {amount:.1f} ETH detected"
                }
                alerts.append(alert)
        
        return alerts
    
    def get_macro_indicators(self) -> dict:
        """Fetch current macro indicators."""
        logger.info(f"[Oracle] Fetching macro indicators: {', '.join(self.config.macro_indicators)}")
        time.sleep(0.4)
        
        indicators = {}
        
        if "fear_greed" in self.config.macro_indicators:
            indicators["fear_greed"] = {
                "value": 65,  # 0-100
                "sentiment": "greed",
                "change_24h": +5
            }
        
        if "funding_rates" in self.config.macro_indicators:
            indicators["funding_rates"] = {
                "btc_perpetual": 0.01,  # %
                "eth_perpetual": 0.008,
                "trend": "slightly_positive"
            }
        
        if "oi_change" in self.config.macro_indicators:
            indicators["oi_change"] = {
                "btc_24h_change": +3.2,  # %
                "eth_24h_change": +5.7,
                "total_oi_usd": 28500000000
            }
        
        if "volatility_index" in self.config.macro_indicators:
            indicators["volatility_index"] = {
                "btc_30d_vol": 58.3,
                "eth_30d_vol": 72.1,
                "trend": "decreasing"
            }
        
        if "stablecoin_flows" in self.config.macro_indicators:
            indicators["stablecoin_flows"] = {
                "usdt_supply_change": +1200000000,
                "usdc_supply_change": -450000000,
                "dai_supply_change": +230000000
            }
        
        return indicators
    
    def generate_signal(self) -> Optional[TradeSignal]:
        """Generate trade signal based on macro + whale analysis."""
        logger.info("[Oracle] Analyzing macro/whale data for signals...")
        
        # Get all data
        cex_flows = self.check_cex_flows()
        whale_alerts = self.track_whale_movements()
        macro = self.get_macro_indicators()
        
        # Analyze for signals
        score = 50  # Base score
        
        # CEX flow analysis
        if cex_flows.get("trend") == "accumulation":
            score += 15
            reasoning = "CEX net inflows detected (accumulation phase)"
        elif cex_flows.get("trend") == "distribution":
            score -= 20
            reasoning = "CEX net outflows detected (distribution phase)"
        else:
            reasoning = "CEX flows neutral"
        
        # Whale activity
        if whale_alerts:
            buy_alerts = [a for a in whale_alerts if a["direction"] == "buy"]
            if len(buy_alerts) > 0:
                score += len(buy_alerts) * 10
                reasoning += f" | {len(buy_alerts)} whale buy(s) detected"
        
        # Fear & Greed
        if "fear_greed" in macro:
            fg = macro["fear_greed"]["value"]
            if fg < 25:  # Extreme fear
                score += 25
                reasoning += " | Extreme fear (contrarian buy signal)"
            elif fg > 75:  # Extreme greed
                score -= 20
                reasoning += " | Extreme greed (caution advised)"
        
        # Only generate signal if score is significant
        if score >= 70:
            # In reality, Oracle would suggest specific assets based on analysis
            # For now, mock a blue-chip signal
            return TradeSignal(
                token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
                chain="ethereum",
                narrative_score=min(score, 100),
                reasoning=reasoning,
                discovered_at=time.time()
            )
        
        return None

if __name__ == "__main__":
    from strategy_factory import StrategyFactory
    
    factory = StrategyFactory()
    oracle_config = factory.get_profile("oracle_eye").oracle
    
    oracle = OracleAgent(oracle_config)
    
    print("Testing Oracle Agent:")
    print("-" * 40)
    
    cex_flows = oracle.check_cex_flows()
    print(f"CEX Flows: {cex_flows.get('trend', 'N/A')}")
    
    whale_alerts = oracle.track_whale_movements()
    print(f"Whale Alerts: {len(whale_alerts)}")
    
    macro = oracle.get_macro_indicators()
    print(f"Macro Indicators: {len(macro)}")
    
    signal = oracle.generate_signal()
    if signal:
        print(f"\n✅ Signal Generated:")
        print(f"   Token: {signal.token_address[:20]}...")
        print(f"   Score: {signal.narrative_score}/100")
        print(f"   Reason: {signal.reasoning}")
    else:
        print("\n⏸️  No signal generated (insufficient conviction)")