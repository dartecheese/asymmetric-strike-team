#!/usr/bin/env python3
"""
Generate charts directly from TradingView MCP CLI
"""

import subprocess
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visualization.tradingview_visualizer import TradingViewVisualizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingViewChartGenerator")

class TradingViewChartGenerator:
    """
    Generate charts by calling TradingView MCP CLI
    """
    
    def __init__(self, output_dir: str = "visualization/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.visualizer = TradingViewVisualizer(output_dir=output_dir)
        
        # Check if tradingview-cli is available
        self.cli_available = self._check_cli_available()
        
        if not self.cli_available:
            logger.warning("tradingview-cli not found in PATH. Using mock data.")
    
    def _check_cli_available(self) -> bool:
        """Check if tradingview-cli is available"""
        try:
            result = subprocess.run(
                ['tradingview-cli', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def run_screening(self, asset_type: str = 'stocks', 
                     preset: Optional[str] = None,
                     filters: Optional[List[Dict]] = None,
                     limit: int = 20,
                     markets: List[str] = None) -> Optional[Dict]:
        """
        Run screening via tradingview-cli
        
        Args:
            asset_type: 'stocks', 'crypto', 'forex', or 'etf'
            preset: Preset name (e.g., 'quality_stocks')
            filters: List of filter dictionaries
            limit: Number of results
            markets: List of markets (for stocks/etf)
            
        Returns:
            Dictionary with screening results or None if failed
        """
        if not self.cli_available:
            logger.error("tradingview-cli not available")
            return None
        
        # Build command
        cmd = ['tradingview-cli', 'screen', asset_type, '--format', 'json', '--limit', str(limit)]
        
        if preset:
            cmd.extend(['--preset', preset])
        
        if markets and asset_type in ['stocks', 'etf']:
            markets_str = ','.join(markets)
            cmd.extend(['--markets', markets_str])
        
        # TODO: Add filters support (would need to pass as JSON)
        
        logger.info(f"Running screening command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Screening failed: {result.stderr}")
                return None
            
            # Parse JSON output
            data = json.loads(result.stdout)
            
            # Extract stocks/crypto/etc from response
            if asset_type == 'stocks' and 'stocks' in data:
                return data['stocks']
            elif asset_type == 'crypto' and 'cryptos' in data:
                return data['cryptos']
            elif asset_type == 'forex' and 'forex' in data:
                return data['forex']
            elif asset_type == 'etf' and 'etfs' in data:
                return data['etfs']
            else:
                # Try to find any list in the response
                for key, value in data.items():
                    if isinstance(value, list) and value:
                        return value
                
                return data
            
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.error(f"Screening error: {e}")
            return None
    
    def generate_screening_chart(self, asset_type: str = 'stocks', 
                                preset: str = 'quality_stocks',
                                output_format: str = 'html') -> str:
        """
        Generate screening chart directly from TradingView
        
        Args:
            asset_type: Type of asset to screen
            preset: Preset screening strategy
            output_format: Output format ('html', 'png', 'json')
            
        Returns:
            Path to generated chart
        """
        logger.info(f"Generating {asset_type} screening chart with preset '{preset}'...")
        
        # Run screening
        screening_data = self.run_screening(asset_type, preset=preset, limit=20)
        
        if not screening_data:
            logger.warning(f"No screening data for {asset_type}. Using mock data.")
            
            # Generate mock data
            screening_data = self._generate_mock_screening_data(asset_type, preset)
            
            if not screening_data:
                return ""
        
        # Generate chart
        chart_path = self.visualizer.create_screening_results_chart(
            screening_data, asset_type, output_format
        )
        
        logger.info(f"Screening chart generated: {chart_path}")
        return chart_path
    
    def generate_market_regime_chart(self, output_format: str = 'html') -> str:
        """
        Generate market regime chart
        
        Note: TradingView MCP doesn't have direct market regime endpoint,
        so we use screening data to infer regime or use mock data.
        
        Args:
            output_format: Output format ('html', 'png', 'json')
            
        Returns:
            Path to generated chart
        """
        logger.info("Generating market regime chart...")
        
        # Get stock screening data to infer market regime
        stocks_data = self.run_screening('stocks', preset='quality_stocks', limit=50)
        
        regime_data = {}
        
        if stocks_data and isinstance(stocks_data, list) and len(stocks_data) > 0:
            # Analyze stock data to infer regime
            changes = []
            for stock in stocks_data[:20]:
                if isinstance(stock, dict) and 'change' in stock:
                    changes.append(stock['change'])
            
            if changes:
                avg_change = sum(changes) / len(changes)
                
                # Simple regime inference
                if avg_change > 1.0:
                    regime = 'bull'
                    confidence = min(0.3 + avg_change / 10, 0.9)
                elif avg_change < -1.0:
                    regime = 'bear'
                    confidence = min(0.3 + abs(avg_change) / 10, 0.9)
                else:
                    regime = 'correction'
                    confidence = 0.5
                
                # Get top sectors (mock for now)
                recommendations = [
                    {'sector': 'Technology', 'action': 'buy', 'strength': 0.8},
                    {'sector': 'Healthcare', 'action': 'hold', 'strength': 0.6},
                    {'sector': 'Energy', 'action': 'sell' if regime == 'bear' else 'hold', 'strength': 0.4},
                ]
                
                regime_data = {
                    'overall_regime': regime,
                    'confidence': confidence,
                    'regime_strength': {
                        'bull': 0.6 if regime == 'bull' else 0.2,
                        'bear': 0.6 if regime == 'bear' else 0.2,
                        'correction': 0.6 if regime == 'correction' else 0.2,
                    },
                    'recommendations': recommendations,
                    'avg_change': avg_change,
                }
        
        if not regime_data:
            # Use mock regime data
            regime_data = {
                'overall_regime': 'bull',
                'confidence': 0.75,
                'regime_strength': {'bull': 0.8, 'bear': 0.1, 'correction': 0.1},
                'recommendations': [
                    {'sector': 'Technology', 'action': 'buy', 'strength': 0.9},
                    {'sector': 'Healthcare', 'action': 'buy', 'strength': 0.7},
                    {'sector': 'Energy', 'action': 'sell', 'strength': 0.6},
                ]
            }
        
        # Generate chart
        chart_path = self.visualizer.create_market_regime_chart(regime_data, output_format)
        
        logger.info(f"Market regime chart generated: {chart_path}")
        return chart_path
    
    def generate_comprehensive_dashboard(self, output_format: str = 'html') -> str:
        """
        Generate comprehensive dashboard with multiple charts
        
        Args:
            output_format: Output format ('html', 'png', 'json')
            
        Returns:
            Path to generated dashboard
        """
        logger.info("Generating comprehensive dashboard...")
        
        all_data = {}
        
        # 1. Market regime
        regime_chart = self.generate_market_regime_chart('html' if output_format == 'html' else 'json')
        if regime_chart:
            all_data['market_regime_chart'] = regime_chart
        
        # 2. Stock screening
        stock_chart = self.generate_screening_chart('stocks', 'quality_stocks', 
                                                   'html' if output_format == 'html' else 'json')
        if stock_chart:
            all_data['screening_stocks_chart'] = stock_chart
        
        # 3. Crypto screening
        crypto_chart = self.generate_screening_chart('crypto', None,
                                                    'html' if output_format == 'html' else 'json')
        if crypto_chart:
            all_data['screening_crypto_chart'] = crypto_chart
        
        # 4. Generate dashboard HTML
        if output_format == 'html' and any(key.endswith('_chart') for key in all_data.keys()):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dashboard_path = self.output_dir / f"tradingview_dashboard_{timestamp}.html"
            
            with open(dashboard_path, 'w') as f:
                f.write("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>TradingView MCP Dashboard</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 20px; }
                        .header { text-align: center; margin-bottom: 30px; }
                        .chart-container { margin: 20px 0; border: 1px solid #ddd; padding: 10px; }
                        iframe { width: 100%; height: 600px; border: none; }
                        .chart-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>TradingView MCP Dashboard</h1>
                        <p>Generated: """ + datetime.now().isoformat() + """</p>
                    </div>
                """)
                
                for key, chart_path in all_data.items():
                    if chart_path.endswith('.html'):
                        title = key.replace('_chart', '').replace('_', ' ').title()
                        f.write(f"""
                        <div class="chart-container">
                            <div class="chart-title">{title}</div>
                            <iframe src="{chart_path}"></iframe>
                        </div>
                        """)
                
                f.write("""
                </body>
                </html>
                """)
            
            logger.info(f"Comprehensive dashboard generated: {dashboard_path}")
            return str(dashboard_path)
        
        # Fallback: return first chart or save data as JSON
        if all_data:
            first_chart = next(iter(all_data.values()))
            return first_chart
        else:
            # Save empty data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"dashboard_data_{timestamp}.json"
            with open(output_path, 'w') as f:
                json.dump({'message': 'No data generated'}, f, indent=2)
            return str(output_path)
    
    def _generate_mock_screening_data(self, asset_type: str, preset: str) -> List[Dict]:
        """Generate mock screening data for testing"""
        
        if asset_type == 'stocks':
            return [
                {'name': 'Apple Inc.', 'symbol': 'AAPL', 'change': 2.5, 'market_cap_basic': 2500000000000},
                {'name': 'Microsoft', 'symbol': 'MSFT', 'change': 1.8, 'market_cap_basic': 2000000000000},
                {'name': 'Amazon', 'symbol': 'AMZN', 'change': -0.5, 'market_cap_basic': 1800000000000},
                {'name': 'Google', 'symbol': 'GOOGL', 'change': 3.2, 'market_cap_basic': 1500000000000},
                {'name': 'Tesla', 'symbol': 'TSLA', 'change': -2.1, 'market_cap_basic': 600000000000},
                {'name': 'NVIDIA', 'symbol': 'NVDA', 'change': 5.7, 'market_cap_basic': 800000000000},
                {'name': 'Meta', 'symbol': 'META', 'change': 1.2, 'market_cap_basic': 900000000000},
                {'name': 'Netflix', 'symbol': 'NFLX', 'change': -1.5, 'market_cap_basic': 250000000000},
            ]
        
        elif asset_type == 'crypto':
            return [
                {'name': 'Bitcoin', 'symbol': 'BTCUSD', 'change': 3.2, 'market_cap_basic': 1200000000000},
                {'name': 'Ethereum', 'symbol': 'ETHUSD', 'change': 5.7, 'market_cap_basic': 400000000000},
                {'name': 'Solana', 'symbol': 'SOLUSD', 'change': 12.5, 'market_cap_basic': 80000000000},
                {'name': 'Cardano', 'symbol': 'ADAUSD', 'change': -1.2, 'market_cap_basic': 25000000000},
                {'name': 'Polkadot', 'symbol': 'DOTUSD', 'change': 2.3, 'market_cap_basic': 15000000000},
            ]
        
        elif asset_type == 'forex':
            return [
                {'name': 'EUR/USD', 'symbol': 'EURUSD', 'change': 0.12, 'volume': 1500000},
                {'name': 'GBP/USD', 'symbol': 'GBPUSD', 'change': -0.08, 'volume': 800000},
                {'name': 'USD/JPY', 'symbol': 'USDJPY', 'change': 0.25, 'volume': 1200000},
                {'name': 'AUD/USD', 'symbol': 'AUDUSD', 'change': -0.15, 'volume': 500000},
            ]
        
        else:  # ETF
            return [
                {'name': 'SPDR S&P 500', 'symbol': 'SPY', 'change': 1.5, 'market_cap_basic': 400000000000},
                {'name': 'Invesco QQQ', 'symbol': 'QQQ', 'change': 2.2, 'market_cap_basic': 200000000000},
                {'name': 'iShares Core S&P 500', 'symbol': 'IVV', 'change': 1.4, 'market_cap_basic': 350000000000},
                {'name': 'Vanguard Total Stock Market', 'symbol': 'VTI', 'change': 1.3, 'market_cap_basic': 300000000000},
            ]


# CLI interface
if __name__ == "__main__":
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="Generate TradingView charts from MCP CLI")
    parser.add_argument('--chart-type', default='screening',
                       choices=['screening', 'regime', 'dashboard', 'all'],
                       help='Type of chart to generate')
    parser.add_argument('--asset-type', default='stocks',
                       choices=['stocks', 'crypto', 'forex', 'etf'],
                       help='Asset type for screening')
    parser.add_argument('--preset', default='quality_stocks',
                       help='Screening preset name')
    parser.add_argument('--output-format', default='html',
                       choices=['html', 'png', 'json', 'txt'])
    parser.add_argument('--output-dir', default='visualization/charts',
                       help='Output directory')
    
    args = parser.parse_args()
    
    generator = TradingViewChartGenerator(args.output_dir)
    
    if args.chart_type == 'screening':
        chart_path = generator.generate_screening_chart(
            args.asset_type, args.preset, args.output_format
        )
        
    elif args.chart_type == 'regime':
        chart_path = generator.generate_market_regime_chart(args.output_format)
        
    elif args.chart_type == 'dashboard':
        chart_path = generator.generate_comprehensive_dashboard(args.output_format)
        
    elif args.chart_type == 'all':
        # Generate all charts
        charts = []
        
        regime_path = generator.generate_market_regime_chart('html' if args.output_format == 'html' else 'json')
        if regime_path:
            charts.append(('Market Regime', regime_path))
        
        for asset in ['stocks', 'crypto', 'forex', 'etf']:
            screening_path = generator.generate_screening_chart(asset, None, 
                                                              'html' if args.output_format == 'html' else 'json')
            if screening_path:
                charts.append((f'{asset.capitalize()} Screening', screening_path))
        
        if args.output_format == 'html' and charts:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dashboard_path = Path(args.output_dir) / f"all_charts_{timestamp}.html"
            
            with open(dashboard_path, 'w') as f:
                f.write(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>TradingView All Charts</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        .header {{ text-align: center; margin-bottom: 30px; }}
                        .chart-container {{ margin: 20px 0; }}
                        iframe {{ width: 100%; height: 600px; border: none; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>TradingView MCP Charts</h1>
                        <p>Generated: {datetime.now().isoformat()}</p>
                    </div>
                """)
                
                for title, path in charts:
                    if path.endswith('.html'):
                        f.write(f"""
                        <div class="chart-container">
                            <h2>{title}</h2>
                            <iframe src="{path}"></iframe>
                        </div>
                        """)
                
                f.write("</body></html>")
            
            chart_path = str(dashboard_path)
        else:
            chart_path = charts[0][1] if charts else ""
    
    if chart_path:
        print(f"✅ Chart generated: {chart_path}")
    else:
        print("❌ Failed to generate chart")
        sys.exit(1)