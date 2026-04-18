#!/usr/bin/env python3
"""
QWNT Dashboard Integration
Generate visualizations for QWNT trading system
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visualization.tradingview_visualizer import TradingViewVisualizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QWNTDashboard")

class QWNTDashboard:
    """
    Main dashboard generator for QWNT trading system
    """
    
    def __init__(self, output_dir: str = "visualization/dashboards"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.visualizer = TradingViewVisualizer()
        
        # Performance tracking
        self.performance_history = []
        self.trade_history = []
        
        logger.info(f"QWNT Dashboard initialized. Output directory: {self.output_dir}")
    
    def update_from_trading_system(self, trading_system) -> Dict:
        """
        Extract data from trading system for visualization
        
        Args:
            trading_system: QWNTTradingSystem instance
            
        Returns:
            Dictionary with extracted data
        """
        logger.info("Extracting data from trading system...")
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'strategy': getattr(trading_system, 'strategy_name', 'unknown'),
                'mode': getattr(trading_system, 'execution_mode', 'paper'),
                'cycle_count': getattr(trading_system, 'cycle_count', 0),
            }
        }
        
        # Extract agent data if available
        if hasattr(trading_system, 'whisperer'):
            whisperer = trading_system.whisperer
            if hasattr(whisperer, 'last_signals'):
                data['signals'] = [
                    {
                        'token_address': s.token_address[:10] + '...' if hasattr(s, 'token_address') else 'unknown',
                        'narrative_score': getattr(s, 'narrative_score', 0),
                        'chain': getattr(s, 'chain', 'unknown'),
                        'reasoning': getattr(s, 'reasoning', '')[:100] + '...' if hasattr(s, 'reasoning') else '',
                    }
                    for s in getattr(whisperer, 'last_signals', [])[:5]
                ]
        
        # Extract performance data
        if hasattr(trading_system, 'performance_tracker'):
            tracker = trading_system.performance_tracker
            data['performance'] = {
                'total_pnl': getattr(tracker, 'total_pnl', 0),
                'win_rate': getattr(tracker, 'win_rate', 0),
                'trades_executed': getattr(tracker, 'trades_executed', 0),
                'sharpe_ratio': getattr(tracker, 'sharpe_ratio', 0),
            }
        
        # Extract TradingView data if available
        if hasattr(trading_system, 'tradingview'):
            tv = trading_system.tradingview
            if hasattr(tv, 'last_regime'):
                data['market_regime'] = getattr(tv, 'last_regime', {})
            
            if hasattr(tv, 'last_screening_results'):
                results = getattr(tv, 'last_screening_results', {})
                for asset_type, result in results.items():
                    data[f'screening_{asset_type}'] = result
        
        return data
    
    def generate_performance_dashboard(self, performance_data: Dict, output_format: str = 'html') -> str:
        """
        Generate performance dashboard
        
        Args:
            performance_data: Performance data dictionary
            output_format: Output format ('html', 'png', 'json')
            
        Returns:
            Path to generated dashboard
        """
        logger.info("Generating performance dashboard...")
        
        # Prepare data for visualization
        viz_data = {}
        
        # Add market regime if available
        if 'market_regime' in performance_data:
            viz_data['market_regime'] = performance_data['market_regime']
        
        # Add screening results if available
        for key in performance_data:
            if key.startswith('screening_'):
                viz_data[key] = performance_data[key]
        
        # Add strategy performance
        if 'system_info' in performance_data:
            strategy = performance_data['system_info'].get('strategy', 'unknown')
            perf = performance_data.get('performance', {})
            
            viz_data['strategy_performance'] = {
                strategy: {
                    'total_return': perf.get('total_pnl', 0),
                    'win_rate': perf.get('win_rate', 0),
                    'sharpe_ratio': perf.get('sharpe_ratio', 0),
                    'trades': perf.get('trades_executed', 0),
                }
            }
        
        # Add real-time monitor data
        viz_data['realtime_monitor'] = {
            'active_signals': len(performance_data.get('signals', [])),
            'today_pnl': performance_data.get('performance', {}).get('total_pnl', 0),
            'success_rate': performance_data.get('performance', {}).get('win_rate', 0),
            'performance_history': {
                'timestamps': [datetime.now().isoformat()],
                'values': [performance_data.get('performance', {}).get('total_pnl', 0)]
            }
        }
        
        # Generate dashboard
        dashboard_path = self.visualizer.generate_dashboard(viz_data, output_format)
        
        # Also save raw data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_path = self.output_dir / f"performance_data_{timestamp}.json"
        with open(data_path, 'w') as f:
            json.dump(performance_data, f, indent=2)
        
        logger.info(f"Performance dashboard generated: {dashboard_path}")
        return dashboard_path
    
    def generate_trade_analysis_dashboard(self, trades: List[Dict], output_format: str = 'html') -> str:
        """
        Generate trade analysis dashboard
        
        Args:
            trades: List of trade dictionaries
            output_format: Output format ('html', 'png', 'json')
            
        Returns:
            Path to generated dashboard
        """
        logger.info(f"Generating trade analysis dashboard for {len(trades)} trades...")
        
        if not trades:
            logger.warning("No trade data provided")
            return ""
        
        # Prepare data for visualization
        viz_data = {}
        
        # Convert trades to DataFrame-like structure
        trade_summary = []
        for trade in trades:
            summary = {
                'symbol': trade.get('symbol', 'Unknown'),
                'entry_price': trade.get('entry_price', 0),
                'exit_price': trade.get('exit_price', 0),
                'pnl': trade.get('pnl', 0),
                'pnl_percent': trade.get('pnl_percent', 0),
                'duration_hours': trade.get('duration_hours', 0),
                'strategy': trade.get('strategy', 'unknown'),
                'timestamp': trade.get('timestamp', datetime.now().isoformat()),
            }
            trade_summary.append(summary)
        
        # Create custom visualization for trades
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            # Create trade analysis dashboard
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=(
                    'Trade P&L Distribution',
                    'Win/Loss by Strategy',
                    'Trade Duration vs P&L',
                    'Cumulative P&L'
                )
            )
            
            # 1. P&L Distribution
            pnl_values = [t['pnl'] for t in trade_summary]
            fig.add_trace(
                go.Histogram(
                    x=pnl_values,
                    name='P&L Distribution',
                    marker_color=['#2ecc71' if x >= 0 else '#e74c3c' for x in pnl_values],
                    nbinsx=20
                ),
                row=1, col=1
            )
            
            # 2. Win/Loss by Strategy
            if len(trade_summary) > 0:
                strategies = {}
                for trade in trade_summary:
                    strategy = trade['strategy']
                    if strategy not in strategies:
                        strategies[strategy] = {'wins': 0, 'losses': 0}
                    
                    if trade['pnl'] >= 0:
                        strategies[strategy]['wins'] += 1
                    else:
                        strategies[strategy]['losses'] += 1
                
                strategy_names = list(strategies.keys())
                win_counts = [strategies[s]['wins'] for s in strategy_names]
                loss_counts = [strategies[s]['losses'] for s in strategy_names]
                
                fig.add_trace(
                    go.Bar(
                        x=strategy_names,
                        y=win_counts,
                        name='Wins',
                        marker_color='#2ecc71'
                    ),
                    row=1, col=2
                )
                
                fig.add_trace(
                    go.Bar(
                        x=strategy_names,
                        y=loss_counts,
                        name='Losses',
                        marker_color='#e74c3c'
                    ),
                    row=1, col=2
                )
            
            # 3. Trade Duration vs P&L
            durations = [t['duration_hours'] for t in trade_summary]
            pnl_percents = [t['pnl_percent'] for t in trade_summary]
            
            fig.add_trace(
                go.Scatter(
                    x=durations,
                    y=pnl_percents,
                    mode='markers',
                    marker=dict(
                        size=10,
                        color=pnl_percents,
                        colorscale='RdYlGn',
                        showscale=True,
                        colorbar=dict(title="P&L %")
                    ),
                    text=[t['symbol'] for t in trade_summary],
                    name='Duration vs P&L'
                ),
                row=2, col=1
            )
            
            # 4. Cumulative P&L
            cumulative_pnl = []
            running_total = 0
            for trade in trade_summary:
                running_total += trade['pnl']
                cumulative_pnl.append(running_total)
            
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(cumulative_pnl))),
                    y=cumulative_pnl,
                    mode='lines+markers',
                    name='Cumulative P&L',
                    line=dict(color='#3498db', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(52, 152, 219, 0.1)'
                ),
                row=2, col=2
            )
            
            # Update layout
            fig.update_layout(
                title_text=f"Trade Analysis Dashboard ({len(trades)} trades)",
                height=800,
                template="plotly_white",
                showlegend=True
            )
            
            # Save dashboard
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if output_format == 'html':
                output_path = self.output_dir / f"trade_analysis_{timestamp}.html"
                fig.write_html(str(output_path))
            elif output_format == 'png':
                output_path = self.output_dir / f"trade_analysis_{timestamp}.png"
                fig.write_image(str(output_path))
            else:
                output_path = self.output_dir / f"trade_analysis_{timestamp}.json"
                with open(output_path, 'w') as f:
                    json.dump(trades, f, indent=2)
            
            logger.info(f"Trade analysis dashboard generated: {output_path}")
            return str(output_path)
            
        except ImportError:
            logger.warning("Plotly not available for trade analysis")
            
            # Fall back to text report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"trade_analysis_{timestamp}.txt"
            
            with open(output_path, 'w') as f:
                f.write("=" * 60 + "\n")
                f.write("TRADE ANALYSIS REPORT\n")
                f.write("=" * 60 + "\n\n")
                
                total_pnl = sum(t.get('pnl', 0) for t in trades)
                winning_trades = sum(1 for t in trades if t.get('pnl', 0) >= 0)
                
                f.write(f"Total Trades: {len(trades)}\n")
                f.write(f"Winning Trades: {winning_trades} ({winning_trades/len(trades)*100:.1f}%)\n")
                f.write(f"Total P&L: ${total_pnl:.2f}\n\n")
                
                f.write("Recent Trades:\n")
                for i, trade in enumerate(trades[:10], 1):
                    f.write(f"{i:2d}. {trade.get('symbol', 'Unknown'):10s} "
                           f"P&L: ${trade.get('pnl', 0):+.2f} "
                           f"({trade.get('pnl_percent', 0):+.1f}%)\n")
            
            return str(output_path)
    
    def generate_daily_report(self, day_data: Dict, output_format: str = 'html') -> str:
        """
        Generate daily trading report
        
        Args:
            day_data: Dictionary with daily trading data
            output_format: Output format ('html', 'png', 'json')
            
        Returns:
            Path to generated report
        """
        logger.info("Generating daily trading report...")
        
        # Collect all visualizations for the day
        all_viz_data = {}
        
        # Add market regime
        if 'market_regime' in day_data:
            all_viz_data['market_regime'] = day_data['market_regime']
        
        # Add screening results
        for key in day_data:
            if key.startswith('screening_'):
                all_viz_data[key] = day_data[key]
        
        # Add trading performance
        if 'performance' in day_data:
            # Create strategy performance data
            strategy = day_data.get('strategy', 'daily')
            perf = day_data['performance']
            
            all_viz_data['strategy_performance'] = {
                strategy: {
                    'total_return': perf.get('total_pnl', 0),
                    'win_rate': perf.get('win_rate', 0),
                    'sharpe_ratio': perf.get('sharpe_ratio', 0),
                    'max_drawdown': perf.get('max_drawdown', 0),
                }
            }
        
        # Add trades if available
        if 'trades' in day_data and day_data['trades']:
            trade_dashboard = self.generate_trade_analysis_dashboard(
                day_data['trades'], 
                output_format='html' if output_format == 'html' else 'json'
            )
            all_viz_data['trade_analysis'] = trade_dashboard
        
        # Generate comprehensive dashboard
        timestamp = datetime.now().strftime("%Y%m%d")
        if output_format == 'html':
            # Create daily report HTML
            report_path = self.output_dir / f"daily_report_{timestamp}.html"
            
            with open(report_path, 'w') as f:
                f.write(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>QWNT Daily Trading Report - {timestamp}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        .header {{ text-align: center; margin-bottom: 30px; }}
                        .summary {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                        .metric {{ display: inline-block; margin: 0 20px; text-align: center; }}
                        .metric-value {{ font-size: 24px; font-weight: bold; }}
                        .metric-label {{ font-size: 14px; color: #666; }}
                        .positive {{ color: #2ecc71; }}
                        .negative {{ color: #e74c3c; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>QWNT Daily Trading Report</h1>
                        <h2>{timestamp}</h2>
                    </div>
                    
                    <div class="summary">
                        <h3>Daily Summary</h3>
                        <div class="metric">
                            <div class="metric-value {'positive' if day_data.get('performance', {}).get('total_pnl', 0) >= 0 else 'negative'}">
                                ${day_data.get('performance', {}).get('total_pnl', 0):+.2f}
                            </div>
                            <div class="metric-label">Total P&L</div>
                        </div>
                        
                        <div class="metric">
                            <div class="metric-value">
                                {day_data.get('performance', {}).get('trades_executed', 0)}
                            </div>
                            <div class="metric-label">Trades</div>
                        </div>
                        
                        <div class="metric">
                            <div class="metric-value {'positive' if day_data.get('performance', {}).get('win_rate', 0) >= 0.5 else 'negative'}">
                                {day_data.get('performance', {}).get('win_rate', 0)*100:.1f}%
                            </div>
                            <div class="metric-label">Win Rate</div>
                        </div>
                        
                        <div class="metric">
                            <div class="metric-value">
                                {day_data.get('strategy', 'unknown')}
                            </div>
                            <div class="metric-label">Strategy</div>
                        </div>
                    </div>
                """)
                
                # Add embedded visualizations
                for key, viz_path in all_viz_data.items():
                    if isinstance(viz_path, str) and viz_path.endswith('.html'):
                        f.write(f"""
                        <div style="margin: 30px 0;">
                            <h3>{key.replace('_', ' ').title()}</h3>
                            <iframe src="{viz_path}" width="100%" height="600" frameborder="0"></iframe>
                        </div>
                        """)
                
                f.write("""
                </body>
                </html>
                """)
            
            logger.info(f"Daily report generated: {report_path}")
            return str(report_path)
        
        else:
            # Save as JSON
            report_path = self.output_dir / f"daily_report_{timestamp}.json"
            with open(report_path, 'w') as f:
                json.dump(day_data, f, indent=2)
            
            logger.info(f"Daily report generated: {report_path}")
            return str(report_path)
    
    def run_continuous_monitor(self, trading_system, interval_seconds: int = 300):
        """
        Run continuous monitoring dashboard
        
        Args:
            trading_system: QWNTTradingSystem instance
            interval_seconds: Update interval in seconds
        """
        logger.info(f"Starting continuous monitor (interval: {interval_seconds}s)")
        
        try:
            import time
            import threading
            
            def monitor_loop():
                while True:
                    try:
                        # Extract data
                        data = self.update_from_trading_system(trading_system)
                        
                        # Generate dashboard
                        dashboard_path = self.generate_performance_dashboard(data, 'html')
                        
                        logger.info(f"Monitor update: {dashboard_path}")
                        
                        # Wait for next update
                        time.sleep(interval_seconds)
                        
                    except Exception as e:
                        logger.error(f"Monitor error: {e}")
                        time.sleep(interval_seconds)
            
            # Start monitor in background thread
            monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
            monitor_thread.start()
            
            logger.info("Continuous monitor started in background")
            
        except ImportError:
            logger.error("Threading not available for continuous monitor")


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="QWNT Dashboard Generator")
    parser.add_argument('--mode', default='performance', 
                       choices=['performance', 'trades', 'daily', 'monitor'],
                       help='Dashboard mode')
    parser.add_argument('--data-file', help='JSON file with data')
    parser.add_argument('--output-format', default='html', 
                       choices=['html', 'png', 'json', 'txt'])
    parser.add_argument('--output-dir', default='visualization/dashboards',
                       help='Output directory')
    
    args = parser.parse_args()
    
    dashboard = QWNTDashboard(args.output_dir)
    
    if args.data_file:
        with open(args.data_file, 'r') as f:
            data = json.load(f)
        
        if args.mode == 'performance':
            output_path = dashboard.generate_performance_dashboard(data, args.output_format)
        elif args.mode == 'trades':
            output_path = dashboard.generate_trade_analysis_dashboard(
                data.get('trades', []), args.output_format
            )
        elif args.mode == 'daily':
            output_path = dashboard.generate_daily_report(data, args.output_format)
        else:
            output_path = dashboard.generate_performance_dashboard(data, args.output_format)
        
        print(f"Dashboard generated: {output_path}")
    
    else:
        print("No data file provided. Generating sample dashboard...")
        
        # Generate sample data
        sample_data = {
            'system_info': {
                'strategy': 'oracle_eye',
                'mode': 'paper',
                'cycle_count': 42,
            },
            'performance': {
                'total_pnl': 1250.50,
                'win_rate': 0.75,
                'trades_executed': 12,
                'sharpe_ratio': 1.85,
            },
            'market_regime': {
                'overall_regime': 'bull',
                'confidence': 0.8,
                'recommendations': [
                    {'sector': 'Technology', 'action': 'buy', 'strength': 0.9},
                    {'sector': 'Finance', 'action': 'buy', 'strength': 0.7},
                ]
            },
            'signals': [
                {
                    'token_address': '0x1234...',
                    'narrative_score': 85,
                    'chain': 'ethereum',
                    'reasoning': 'High social velocity...',
                }
            ]
        }
        
        output_path = dashboard.generate_performance_dashboard(sample_data, args.output_format)
        print(f"Sample dashboard: {output_path}")