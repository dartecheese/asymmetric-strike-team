"""
Enhanced Whisperer Agent with TradingView MCP Integration
Combines social/smart money scanning with quantitative market data
"""

import time
import random
from typing import Dict, List, Optional
from datetime import datetime
import logging

from core.models import TradeSignal
from enum import Enum

class Chain(Enum):
    ETHEREUM = "ethereum"
    SOLANA = "solana"
    AVALANCHE = "avalanche"
    BASE = "base"
    ARBITRUM = "arbitrum"
from tradingview_integration import get_tradingview_integration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QWNTEnhancedWhisperer")

class QWNTEnhancedWhisperer:
    """
    Enhanced version of Whisperer that integrates TradingView MCP data
    Provides quantitative market context for trading decisions
    """
    
    def __init__(self, use_mock_tv: bool = False):
        self.tradingview = get_tradingview_integration(use_mock=use_mock_tv)
        self.last_market_analysis = None
        self.last_analysis_time = None
        self.market_regime = "unknown"
        
    def scan_firehose(self) -> TradeSignal:
        """
        Enhanced scanning that combines social signals with quantitative data
        """
        logger.info("🔍 QWNT Enhanced Whisperer scanning...")
        
        # Get market context first
        market_context = self._get_market_context()
        
        # Generate signal based on market regime
        signal = self._generate_signal_for_regime(market_context)
        
        # Enhance signal with quantitative data
        signal = self._enhance_signal_with_quantitative_data(signal, market_context)
        
        logger.info(f"📡 Generated signal: {signal.action} {signal.token_symbol} "
                   f"on {signal.chain.value} (Confidence: {signal.confidence:.1%})")
        
        return signal
    
    def _get_market_context(self) -> Dict:
        """Get current market context from TradingView"""
        # Refresh analysis every 5 minutes
        if (self.last_analysis_time is None or 
            (datetime.now() - self.last_analysis_time).seconds > 300):
            
            logger.info("📊 Refreshing market analysis from TradingView")
            self.last_market_analysis = self.tradingview.get_market_regime()
            self.last_analysis_time = datetime.now()
            self.market_regime = self.last_market_analysis.get("overall_regime", "unknown")
        
        return self.last_market_analysis
    
    def _generate_signal_for_regime(self, market_context: Dict) -> TradeSignal:
        """Generate trading signal appropriate for current market regime"""
        regime = market_context.get("overall_regime", "unknown")
        
        # Mock token pool (in production, this would come from actual data)
        token_pool = [
            {"symbol": "ETH", "name": "Ethereum", "chain": Chain.ETHEREUM},
            {"symbol": "UNI", "name": "Uniswap", "chain": Chain.ETHEREUM},
            {"symbol": "AAVE", "name": "Aave", "chain": Chain.ETHEREUM},
            {"symbol": "SOL", "name": "Solana", "chain": Chain.SOLANA},
            {"symbol": "AVAX", "name": "Avalanche", "chain": Chain.AVALANCHE},
        ]
        
        # Select token based on regime
        if regime == "bull":
            # In bull markets, focus on high-beta tokens
            token = random.choice([t for t in token_pool if t["symbol"] in ["ETH", "SOL", "AVAX"]])
            action = "BUY"
            confidence = random.uniform(0.7, 0.9)
            
        elif regime == "bear":
            # In bear markets, focus on defensive/blue-chip tokens
            token = random.choice([t for t in token_pool if t["symbol"] in ["ETH", "UNI"]])
            action = random.choice(["BUY", "SELL"])  # More cautious
            confidence = random.uniform(0.4, 0.7)
            
        else:  # correction or unknown
            # Balanced approach
            token = random.choice(token_pool)
            action = random.choice(["BUY", "SELL", "HOLD"])
            confidence = random.uniform(0.5, 0.8)
        
        # Create signal
        import time
        signal = TradeSignal(
            token_address=f"0xMock{token['symbol']}",
            chain=token["chain"].value,
            narrative_score=int(confidence * 100),
            reasoning=f"Market regime: {regime.upper()} | Token: {token['symbol']} | Action: {action}",
            discovered_at=time.time()
        )
        # Add custom attributes
        signal.token_symbol = token["symbol"]
        signal.token_name = token["name"]
        signal.action = action
        signal.confidence = confidence
        signal.narrative = f"Market regime: {regime.upper()}"
        signal.velocity_score = int(confidence * 100)
        signal.source = "QWNT_Enhanced_Whisperer"
        
        return signal
    
    def _enhance_signal_with_quantitative_data(self, signal: TradeSignal, market_context: Dict) -> TradeSignal:
        """Enhance signal with quantitative data from TradingView"""
        
        # Get technical analysis for the token (if it's a stock/crypto with symbol)
        try:
            # For crypto tokens, we might need to map to TradingView symbols
            tv_symbol = self._map_to_tradingview_symbol(signal.token_symbol)
            if tv_symbol:
                ta_data = self.tradingview.get_technical_analysis(tv_symbol)
                
                # Enhance signal metadata with technical data
                if "technical_signals" in ta_data:
                    signals = ta_data["technical_signals"]
                    
                    # Adjust confidence based on technical signals
                    if signals.get("overall", {}).get("signal") == "bullish":
                        signal.confidence = min(signal.confidence * 1.2, 0.95)
                        signal.narrative += " | Technicals: BULLISH"
                    elif signals.get("overall", {}).get("signal") == "bearish":
                        signal.confidence = max(signal.confidence * 0.8, 0.1)
                        signal.narrative += " | Technicals: BEARISH"
                    
                    # Add RSI info
                    rsi_signal = signals.get("rsi", {}).get("signal", "neutral")
                    signal.narrative += f" | RSI: {rsi_signal.upper()}"
                    
        except Exception as e:
            logger.warning(f"Could not enhance signal with TradingView data: {e}")
        
        # Add market regime context
        regime = market_context.get("overall_regime", "unknown")
        signal.narrative += f" | Market: {regime.upper()}"
        
        # Add recommendations from market analysis
        recommendations = market_context.get("recommendations", [])
        if recommendations:
            signal.narrative += f" | Rec: {recommendations[0][:50]}..."
        
        return signal
    
    def _map_to_tradingview_symbol(self, token_symbol: str) -> Optional[str]:
        """Map our token symbols to TradingView symbols"""
        mapping = {
            "ETH": "COINBASE:ETH-USD",
            "BTC": "COINBASE:BTC-USD",
            "SOL": "COINBASE:SOL-USD",
            "AVAX": "COINBASE:AVAX-USD",
            "UNI": "COINBASE:UNI-USD",
            "AAVE": "COINBASE:AAVE-USD",
            "AAPL": "NASDAQ:AAPL",
            "MSFT": "NASDAQ:MSFT",
            "GOOGL": "NASDAQ:GOOGL",
            "TSLA": "NASDAQ:TSLA",
            "NVDA": "NASDAQ:NVDA",
        }
        return mapping.get(token_symbol.upper())
    
    def get_market_insights(self) -> Dict:
        """Get comprehensive market insights for dashboard/reporting"""
        insights = {
            "timestamp": datetime.now().isoformat(),
            "market_regime": self.market_regime,
            "recommendations": [],
            "quantitative_metrics": {},
            "screening_opportunities": []
        }
        
        # Get fresh market analysis
        market_context = self._get_market_context()
        insights.update(market_context)
        
        # Get screening opportunities based on regime
        regime = market_context.get("overall_regime", "unknown")
        
        if regime == "bull":
            # Screen for momentum opportunities
            opportunities = self.tradingview.screen_stocks("momentum_stocks", limit=5)
            insights["screening_opportunities"] = opportunities
            insights["recommendations"].append("Bull market: Focus on momentum stocks with strong technicals")
            
        elif regime == "bear":
            # Screen for defensive/value opportunities
            opportunities = self.tradingview.screen_stocks("value_stocks", limit=5)
            insights["screening_opportunities"] = opportunities
            insights["recommendations"].append("Bear market: Focus on value stocks with strong fundamentals")
            
        else:
            # Screen for quality opportunities
            opportunities = self.tradingview.screen_stocks("quality_stocks", limit=5)
            insights["screening_opportunities"] = opportunities
            insights["recommendations"].append("Correction: Focus on high-quality stocks")
        
        # Add quantitative metrics from major indices
        if "indices" in market_context:
            for index, data in market_context["indices"].items():
                insights["quantitative_metrics"][index] = {
                    "drawdown": f"{data.get('drawdown_pct', 0):.1f}%",
                    "rsi": data.get("rsi", 50),
                    "regime": data.get("regime", "unknown")
                }
        
        return insights
    
    def scan_with_strategy(self, strategy_name: str) -> List[TradeSignal]:
        """
        Scan for opportunities specific to a trading strategy
        """
        logger.info(f"🎯 Strategy-specific scanning for: {strategy_name}")
        
        # Get strategy integration from TradingView
        integration = self.tradingview.integrate_with_qwnt_strategy(strategy_name)
        
        signals = []
        
        # Convert screening results to trade signals
        for opportunity in integration.get("screening_results", [])[:3]:  # Top 3
            signal = self._convert_opportunity_to_signal(opportunity, strategy_name)
            if signal:
                signals.append(signal)
        
        # If no opportunities from screening, generate generic signal
        if not signals:
            generic_signal = self.scan_firehose()
            generic_signal.narrative += f" | Strategy: {strategy_name}"
            signals.append(generic_signal)
        
        return signals
    
    def _convert_opportunity_to_signal(self, opportunity: Dict, strategy_name: str) -> Optional[TradeSignal]:
        """Convert TradingView screening result to TradeSignal"""
        symbol = opportunity.get("symbol", "")
        if not symbol:
            return None
        
        # Map symbol to token (simplified - in production would have proper mapping)
        token_symbol = symbol.split(":")[-1] if ":" in symbol else symbol
        
        # Determine action based on strategy and metrics
        action = "BUY"
        confidence = 0.7
        
        # Adjust based on RSI
        rsi = opportunity.get("RSI", 50)
        if rsi > 70:
            confidence *= 0.8
        elif rsi < 30:
            confidence *= 1.2
        
        # Adjust based on momentum
        perf_1m = opportunity.get("Perf.1M", 0)
        if perf_1m > 10:
            confidence *= 1.1
        elif perf_1m < -5:
            confidence *= 0.9
        
        import time
        signal = TradeSignal(
            token_address=f"0xTV{token_symbol}",
            chain="ethereum",  # Default chain
            narrative_score=int(confidence * 100),
            reasoning=f"TradingView screening | Strategy: {strategy_name} | RSI: {rsi:.1f} | Symbol: {token_symbol}",
            discovered_at=time.time()
        )
        # Add custom attributes not in base model
        signal.token_symbol = token_symbol
        signal.token_name = opportunity.get("name", token_symbol)
        signal.action = action
        signal.confidence = min(confidence, 0.95)
        signal.narrative = f"TradingView screening | Strategy: {strategy_name} | RSI: {rsi:.1f}"
        signal.velocity_score = int(confidence * 100)
        signal.source = f"TradingView_{strategy_name}"
        
        return signal

# Test the enhanced whisperer
if __name__ == "__main__":
    print("🧪 Testing QWNT Enhanced Whisperer with TradingView Integration")
    print("=" * 60)
    
    whisperer = QWNTEnhancedWhisperer(use_mock_tv=True)
    
    # Test market insights
    print("\n📊 Market Insights:")
    insights = whisperer.get_market_insights()
    print(f"  Regime: {insights['market_regime'].upper()}")
    for rec in insights.get("recommendations", [])[:2]:
        print(f"  • {rec}")
    
    # Test strategy-specific scanning
    print("\n🎯 Strategy Scanning:")
    for strategy in ["degen", "sniper", "oracle_eye"]:
        signals = whisperer.scan_with_strategy(strategy)
        if signals:
            print(f"  {strategy}: {len(signals)} signals generated")
            for signal in signals[:1]:  # Show first signal
                print(f"    → {signal.action} {signal.token_symbol} ({signal.confidence:.1%})")
    
    # Test regular scanning
    print("\n🔍 Regular Scanning:")
    signal = whisperer.scan_firehose()
    print(f"  Signal: {signal.action} {signal.token_symbol}")
    print(f"  Confidence: {signal.confidence:.1%}")
    print(f"  Narrative: {signal.narrative}")
    
    print("\n✅ QWNT Enhanced Whisperer Test Complete")