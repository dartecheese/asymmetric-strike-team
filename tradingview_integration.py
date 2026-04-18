#!/usr/bin/env python3
"""
TradingView MCP Integration for QWNT Trading Agents
Provides market data, screening, and technical analysis integration
"""

import json
import subprocess
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingViewIntegration")

class TradingViewMCP:
    """
    Integration with TradingView MCP server for market data and screening
    """
    
    def __init__(self, mcp_server_path: str = "tradingview-mcp-server"):
        self.mcp_server_path = mcp_server_path
        self._test_connection()
    
    def _test_connection(self):
        """Test if TradingView MCP server is available"""
        try:
            result = subprocess.run(
                [self.mcp_server_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.info(f"✅ TradingView MCP server available: {result.stdout.strip()}")
            return True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.warning(f"⚠️ TradingView MCP server not available: {e}")
            logger.info("Using mock data for development")
            return False
    
    def _run_cli_command(self, args: List[str]) -> Dict:
        """Run TradingView CLI command and return JSON result"""
        try:
            cmd = ["tradingview-cli"] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"CLI command failed: {result.stderr}")
                return {"error": result.stderr}
            
            return json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.error(f"Error running CLI command: {e}")
            return {"error": str(e)}
    
    def screen_stocks(self, preset: str = "quality_stocks", limit: int = 20) -> List[Dict]:
        """
        Screen stocks using TradingView presets
        Available presets: quality_stocks, value_stocks, dividend_stocks, momentum_stocks,
                          growth_stocks, garp, deep_value, breakout_scanner, etc.
        """
        logger.info(f"📊 Screening stocks with preset: {preset}")
        
        result = self._run_cli_command([
            "screen", "stocks",
            "--preset", preset,
            "--limit", str(limit)
        ])
        
        if "error" in result:
            return []
        
        return result.get("stocks", [])
    
    def get_market_regime(self) -> Dict:
        """
        Get current market regime analysis
        Returns bull/correction/bear status for major indices
        """
        logger.info("📈 Analyzing market regime")
        
        # Get major indices
        indices = ["NASDAQ:COMP", "NYSEARCA:SPY", "TVC:DXY", "TVC:VIX"]
        
        market_data = {}
        for index in indices:
            result = self._run_cli_command(["lookup", index])
            if "error" not in result and result.get("symbols"):
                market_data[index] = result["symbols"][0]
        
        # Analyze regime
        regime_analysis = self._analyze_market_regime(market_data)
        return regime_analysis
    
    def _analyze_market_regime(self, market_data: Dict) -> Dict:
        """Analyze market regime based on index data"""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "overall_regime": "unknown",
            "indices": {},
            "recommendations": []
        }
        
        for index, data in market_data.items():
            close = data.get("close", 0)
            ath = data.get("all_time_high", close)
            rsi = data.get("RSI", 50)
            
            # Calculate drawdown from ATH
            drawdown_pct = ((ath - close) / ath) * 100 if ath > 0 else 0
            
            # Determine regime for this index
            if drawdown_pct < 5:
                regime = "bull"
            elif drawdown_pct < 20:
                regime = "correction"
            else:
                regime = "bear"
            
            # RSI analysis
            rsi_signal = "neutral"
            if rsi > 70:
                rsi_signal = "overbought"
            elif rsi < 30:
                rsi_signal = "oversold"
            
            analysis["indices"][index] = {
                "close": close,
                "ath": ath,
                "drawdown_pct": drawdown_pct,
                "rsi": rsi,
                "rsi_signal": rsi_signal,
                "regime": regime
            }
        
        # Overall regime (weighted by importance)
        regimes = [data["regime"] for data in analysis["indices"].values()]
        bull_count = regimes.count("bull")
        bear_count = regimes.count("bear")
        
        if bull_count >= 2:
            analysis["overall_regime"] = "bull"
            analysis["recommendations"].append("Market in bull regime - consider aggressive strategies")
        elif bear_count >= 2:
            analysis["overall_regime"] = "bear"
            analysis["recommendations"].append("Market in bear regime - consider defensive strategies")
        else:
            analysis["overall_regime"] = "correction"
            analysis["recommendations"].append("Market in correction - consider balanced strategies")
        
        return analysis
    
    def get_technical_analysis(self, symbol: str) -> Dict:
        """
        Get technical analysis for a symbol
        """
        logger.info(f"📉 Getting technical analysis for {symbol}")
        
        result = self._run_cli_command(["lookup", symbol])
        if "error" in result or not result.get("symbols"):
            return {"error": f"Symbol {symbol} not found"}
        
        data = result["symbols"][0]
        
        # Generate technical signals
        signals = self._generate_technical_signals(data)
        
        return {
            "symbol": symbol,
            "data": data,
            "technical_signals": signals,
            "timestamp": datetime.now().isoformat()
        }
    
    def _generate_technical_signals(self, data: Dict) -> Dict:
        """Generate technical trading signals from data"""
        signals = {}
        
        # RSI signals
        rsi = data.get("RSI", 50)
        if rsi > 70:
            signals["rsi"] = {"signal": "overbought", "action": "sell/avoid"}
        elif rsi < 30:
            signals["rsi"] = {"signal": "oversold", "action": "buy/accumulate"}
        else:
            signals["rsi"] = {"signal": "neutral", "action": "hold"}
        
        # Moving average signals
        sma50 = data.get("SMA50", 0)
        sma200 = data.get("SMA200", 0)
        close = data.get("close", 0)
        
        if sma50 > sma200 and close > sma50:
            signals["moving_averages"] = {"signal": "golden_cross", "action": "bullish"}
        elif sma50 < sma200 and close < sma50:
            signals["moving_averages"] = {"signal": "death_cross", "action": "bearish"}
        else:
            signals["moving_averages"] = {"signal": "neutral", "action": "wait"}
        
        # Volume analysis
        volume = data.get("volume", 0)
        avg_volume = data.get("average_volume_30d_calc", volume)
        
        if volume > avg_volume * 1.5:
            signals["volume"] = {"signal": "high_volume", "action": "momentum"}
        elif volume < avg_volume * 0.5:
            signals["volume"] = {"signal": "low_volume", "action": "caution"}
        else:
            signals["volume"] = {"signal": "normal_volume", "action": "neutral"}
        
        # Overall signal
        bullish_signals = sum(1 for s in signals.values() if s.get("action") in ["bullish", "buy/accumulate", "momentum"])
        bearish_signals = sum(1 for s in signals.values() if s.get("action") in ["bearish", "sell/avoid", "caution"])
        
        if bullish_signals > bearish_signals:
            signals["overall"] = {"signal": "bullish", "confidence": bullish_signals / len(signals)}
        elif bearish_signals > bullish_signals:
            signals["overall"] = {"signal": "bearish", "confidence": bearish_signals / len(signals)}
        else:
            signals["overall"] = {"signal": "neutral", "confidence": 0.5}
        
        return signals
    
    def get_crypto_screen(self, preset: str = "momentum", limit: int = 10) -> List[Dict]:
        """
        Screen cryptocurrencies
        """
        logger.info(f"₿ Screening cryptocurrencies with preset: {preset}")
        
        # For crypto, we might need custom filters since preset might not exist
        filters = []
        
        if preset == "momentum":
            filters = [
                {"field": "RSI", "operator": "in_range", "value": [40, 70]},
                {"field": "Perf.1M", "operator": "greater", "value": 10}
            ]
        elif preset == "oversold":
            filters = [
                {"field": "RSI", "operator": "less", "value": 35},
                {"field": "market_cap_basic", "operator": "greater", "value": 1000000000}
            ]
        
        if filters:
            filters_json = json.dumps(filters)
            result = self._run_cli_command([
                "screen", "crypto",
                "--filters", filters_json,
                "--limit", str(limit)
            ])
        else:
            result = self._run_cli_command([
                "screen", "crypto",
                "--limit", str(limit)
            ])
        
        if "error" in result:
            return []
        
        return result.get("crypto", [])
    
    def integrate_with_qwnt_strategy(self, strategy_name: str) -> Dict:
        """
        Integrate TradingView data with QWNT trading strategy
        """
        integration = {
            "strategy": strategy_name,
            "market_data": {},
            "screening_results": [],
            "recommendations": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Get market regime first
        market_regime = self.get_market_regime()
        integration["market_data"]["regime"] = market_regime
        
        # Strategy-specific screening
        if strategy_name == "degen":
            # High momentum stocks for degen strategy
            stocks = self.screen_stocks("momentum_stocks", limit=15)
            integration["screening_results"] = stocks
            integration["recommendations"].append("Degen strategy: Focus on high-momentum stocks with RSI 50-70")
            
        elif strategy_name == "sniper":
            # Quality stocks for sniper strategy
            stocks = self.screen_stocks("quality_stocks", limit=10)
            integration["screening_results"] = stocks
            integration["recommendations"].append("Sniper strategy: Focus on high-quality stocks with strong fundamentals")
            
        elif strategy_name == "oracle_eye":
            # Mixed screening for oracle strategy
            quality_stocks = self.screen_stocks("quality_stocks", limit=5)
            momentum_stocks = self.screen_stocks("momentum_stocks", limit=5)
            integration["screening_results"] = quality_stocks + momentum_stocks
            integration["recommendations"].append("Oracle Eye: Balance between quality and momentum")
            
        elif strategy_name == "arb_hunter":
            # Get crypto for arbitrage opportunities
            crypto = self.get_crypto_screen("momentum", limit=10)
            integration["screening_results"] = crypto
            integration["recommendations"].append("Arb Hunter: Monitor high-volume cryptocurrencies for arbitrage")
        
        # Market regime-based recommendations
        if market_regime["overall_regime"] == "bull":
            integration["recommendations"].append("Bull market: Consider aggressive position sizing")
        elif market_regime["overall_regime"] == "bear":
            integration["recommendations"].append("Bear market: Reduce position sizes, focus on shorts/hedges")
        else:
            integration["recommendations"].append("Correction: Use balanced approach with tight stop losses")
        
        return integration

# Mock implementation for development when MCP server is not available
class MockTradingViewMCP:
    """Mock TradingView MCP for development"""
    
    def __init__(self, *args, **kwargs):
        logger.info("⚠️ Using MockTradingViewMCP (development mode)")
    
    def screen_stocks(self, preset: str = "quality_stocks", limit: int = 20) -> List[Dict]:
        """Mock stock screening"""
        mock_stocks = [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "close": 175.50,
                "change": 1.2,
                "RSI": 65.3,
                "SMA50": 170.2,
                "SMA200": 165.8,
                "price_earnings_ttm": 28.5,
                "return_on_equity": 150.2,
                "market_cap": 2800000000000
            },
            {
                "symbol": "MSFT",
                "name": "Microsoft Corporation",
                "close": 415.75,
                "change": 0.8,
                "RSI": 58.7,
                "SMA50": 410.3,
                "SMA200": 395.6,
                "price_earnings_ttm": 35.2,
                "return_on_equity": 89.5,
                "market_cap": 3100000000000
            }
        ]
        return mock_stocks[:limit]
    
    def get_market_regime(self) -> Dict:
        """Mock market regime analysis"""
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_regime": "bull",
            "indices": {
                "NASDAQ:COMP": {
                    "close": 16250.75,
                    "ath": 16500.25,
                    "drawdown_pct": 1.5,
                    "rsi": 62.3,
                    "rsi_signal": "neutral",
                    "regime": "bull"
                }
            },
            "recommendations": ["Market in bull regime - consider aggressive strategies"]
        }
    
    def integrate_with_qwnt_strategy(self, strategy_name: str) -> Dict:
        """Mock integration"""
        return {
            "strategy": strategy_name,
            "market_data": {"regime": self.get_market_regime()},
            "screening_results": self.screen_stocks(limit=5),
            "recommendations": [
                f"Mock data for {strategy_name} strategy",
                "Use real TradingView MCP for production"
            ],
            "timestamp": datetime.now().isoformat()
        }

def get_tradingview_integration(use_mock: bool = False):
    """
    Factory function to get TradingView integration
    Use mock for development when MCP server is not available
    """
    if use_mock:
        return MockTradingViewMCP()
    
    try:
        return TradingViewMCP()
    except Exception as e:
        logger.warning(f"Failed to initialize TradingViewMCP: {e}")
        logger.info("Falling back to mock implementation")
        return MockTradingViewMCP()

if __name__ == "__main__":
    # Test the integration
    tv = get_tradingview_integration()
    
    print("🧪 Testing TradingView MCP Integration")
    print("=" * 60)
    
    # Test market regime
    regime = tv.get_market_regime()
    print(f"📈 Market Regime: {regime['overall_regime'].upper()}")
    for rec in regime["recommendations"]:
        print(f"  • {rec}")
    
    # Test strategy integration
    for strategy in ["degen", "sniper", "oracle_eye"]:
        print(f"\n🎯 Testing {strategy} strategy integration:")
        integration = tv.integrate_with_qwnt_strategy(strategy)
        print(f"  Found {len(integration['screening_results'])} screening results")
        for rec in integration["recommendations"][:2]:
            print(f"  • {rec}")
    
    print("\n✅ TradingView MCP Integration Test Complete")