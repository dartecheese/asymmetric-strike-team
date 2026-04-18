#!/usr/bin/env python3
"""
TradingView MCP Visualizer
Generate charts and dashboards from TradingView MCP data
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
from datetime import datetime

# Optional imports for visualization
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logging.warning("Plotly not available. Install with: pip install plotly")

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.warning("Matplotlib not available. Install with: pip install matplotlib")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logging.warning("Pandas not available. Install with: pip install pandas")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingViewVisualizer")

class TradingViewVisualizer:
    """
    Generate visualizations from TradingView MCP data
    """
    
    def __init__(self, output_dir: str = "visualization/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Color schemes for market regimes
        self.regime_colors = {
            'bull': '#2ecc71',  # Green
            'bear': '#e74c3c',  # Red
            'correction': '#f39c12',  # Orange
            'unknown': '#95a5a6',  # Gray
        }
        
        # Color schemes for performance
        self.performance_colors = {
            'positive': '#27ae60',  # Dark green
            'negative': '#c0392b',  # Dark red
            'neutral': '#7f8c8d',  # Gray
        }
        
        logger.info(f"TradingView Visualizer initialized. Output directory: {self.output_dir}")
    
    def create_market_regime_chart(self, regime_data: Dict, output_format: str = 'html') -> str:
        """
        Create market regime visualization
        
        Args:
            regime_data: Dictionary with regime information from TradingView
            output_format: 'html', 'png', or 'json'
            
        Returns:
            Path to generated chart file
        """
        logger.info("Creating market regime chart...")
        
        if not PLOTLY_AVAILABLE:
            return self._create_text_regime_report(regime_data)
        
        # Extract data
        overall_regime = regime_data.get('overall_regime', 'unknown')
        regime_strength = regime_data.get('regime_strength', {})
        recommendations = regime_data.get('recommendations', [])
        
        # Create gauge chart for regime strength
        fig = make_subplots(
            rows=2, cols=2,
            specs=[
                [{"type": "indicator"}, {"type": "indicator"}],
                [{"type": "bar", "colspan": 2}, None]
            ],
            subplot_titles=(
                'Market Regime',
                'Regime Confidence',
                'Sector Recommendations'
            )
        )
        
        # 1. Market Regime Gauge
        regime_values = {'bull': 100, 'bear': 0, 'correction': 50, 'unknown': 25}
        regime_value = regime_values.get(overall_regime, 25)
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=regime_value,
                title={"text": "Market Regime"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': self.regime_colors.get(overall_regime, '#95a5a6')},
                    'steps': [
                        {'range': [0, 33], 'color': self.regime_colors['bear']},
                        {'range': [33, 66], 'color': self.regime_colors['correction']},
                        {'range': [66, 100], 'color': self.regime_colors['bull']}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': regime_value
                    }
                }
            ),
            row=1, col=1
        )
        
        # 2. Regime Confidence
        confidence = regime_data.get('confidence', 0.5) * 100
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=confidence,
                title={"text": "Confidence %"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': '#3498db'},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgray"},
                        {'range': [50, 80], 'color': "lightyellow"},
                        {'range': [80, 100], 'color': "lightgreen"}
                    ]
                }
            ),
            row=1, col=2
        )
        
        # 3. Sector Recommendations
        if recommendations and PANDAS_AVAILABLE:
            # Parse recommendations
            sectors = []
            actions = []
            strengths = []
            
            for rec in recommendations[:10]:  # Top 10
                if isinstance(rec, dict):
                    sectors.append(rec.get('sector', 'Unknown'))
                    actions.append(rec.get('action', 'neutral'))
                    strengths.append(rec.get('strength', 0))
                elif isinstance(rec, str):
                    sectors.append(rec)
                    actions.append('neutral')
                    strengths.append(1)
            
            # Create color mapping for actions
            action_colors = {
                'buy': self.performance_colors['positive'],
                'sell': self.performance_colors['negative'],
                'neutral': self.performance_colors['neutral']
            }
            
            colors = [action_colors.get(action, '#95a5a6') for action in actions]
            
            fig.add_trace(
                go.Bar(
                    x=sectors,
                    y=strengths,
                    name='Recommendation Strength',
                    marker_color=colors,
                    text=actions,
                    textposition='auto'
                ),
                row=2, col=1
            )
        
        # Update layout
        fig.update_layout(
            title_text=f"Market Regime Analysis - {overall_regime.upper()} Market",
            height=800,
            template="plotly_white",
            showlegend=False
        )
        
        # Save chart
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"market_regime_{timestamp}"
        
        if output_format == 'html':
            output_path = self.output_dir / f"{filename}.html"
            fig.write_html(str(output_path))
        elif output_format == 'png' and PLOTLY_AVAILABLE:
            output_path = self.output_dir / f"{filename}.png"
            fig.write_image(str(output_path))
        else:
            output_path = self.output_dir / f"{filename}.json"
            with open(output_path, 'w') as f:
                json.dump(regime_data, f, indent=2)
        
        logger.info(f"Market regime chart saved to: {output_path}")
        return str(output_path)
    
    def create_screening_results_chart(self, screening_data: List[Dict], 
                                      asset_type: str = 'stocks',
                                      output_format: str = 'html') -> str:
        """
        Create visualization for screening results
        
        Args:
            screening_data: List of screening results from TradingView
            asset_type: 'stocks', 'crypto', 'forex', or 'etf'
            output_format: 'html', 'png', or 'json'
            
        Returns:
            Path to generated chart file
        """
        logger.info(f"Creating screening results chart for {asset_type}...")
        
        if not screening_data:
            logger.warning("No screening data provided")
            return ""
        
        if not PLOTLY_AVAILABLE or not PANDAS_AVAILABLE:
            return self._create_text_screening_report(screening_data, asset_type)
        
        # Convert to DataFrame
        df = pd.DataFrame(screening_data)
        
        # Determine key columns based on asset type
        if asset_type == 'stocks':
            value_col = 'market_cap_basic'
            change_col = 'change'
            name_col = 'name'
        elif asset_type == 'crypto':
            value_col = 'market_cap_basic'
            change_col = 'change'
            name_col = 'name'
        elif asset_type == 'forex':
            value_col = 'volume'
            change_col = 'change'
            name_col = 'description'
        else:  # ETF
            value_col = 'market_cap_basic'
            change_col = 'change'
            name_col = 'name'
        
        # Ensure columns exist
        available_cols = df.columns.tolist()
        if value_col not in available_cols:
            value_col = available_cols[0] if available_cols else 'value'
        if change_col not in available_cols:
            change_col = available_cols[1] if len(available_cols) > 1 else 'change'
        if name_col not in available_cols:
            name_col = available_cols[2] if len(available_cols) > 2 else 'name'
        
        # Create bubble chart
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=(
                f'Top {asset_type.capitalize()} Screening Results',
                'Performance Distribution'
            ),
            specs=[[{"type": "scatter"}, {"type": "box"}]]
        )
        
        # 1. Bubble chart: Size by market cap, color by change
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[value_col] if value_col in df.columns else df.iloc[:, 0],
                mode='markers+text',
                marker=dict(
                    size=df[value_col] / df[value_col].max() * 50 + 10 if value_col in df.columns else 20,
                    color=df[change_col] if change_col in df.columns else 0,
                    colorscale='RdYlGn',
                    showscale=True,
                    colorbar=dict(title="Change %"),
                    line=dict(width=1, color='DarkSlateGrey')
                ),
                text=df[name_col] if name_col in df.columns else df.index,
                textposition="top center",
                name=asset_type.capitalize()
            ),
            row=1, col=1
        )
        
        # 2. Box plot of changes
        if change_col in df.columns:
            fig.add_trace(
                go.Box(
                    y=df[change_col],
                    name='Change Distribution',
                    marker_color='#3498db',
                    boxpoints='all'
                ),
                row=1, col=2
            )
        
        # Update layout
        fig.update_layout(
            title_text=f"{asset_type.capitalize()} Screening Results",
            xaxis_title="Rank",
            yaxis_title=value_col.replace('_', ' ').title(),
            height=600,
            template="plotly_white",
            showlegend=False
        )
        
        # Save chart
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screening_{asset_type}_{timestamp}"
        
        if output_format == 'html':
            output_path = self.output_dir / f"{filename}.html"
            fig.write_html(str(output_path))
        elif output_format == 'png' and PLOTLY_AVAILABLE:
            output_path = self.output_dir / f"{filename}.png"
            fig.write_image(str(output_path))
        else:
            output_path = self.output_dir / f"{filename}.json"
            with open(output_path, 'w') as f:
                json.dump(screening_data, f, indent=2)
        
        logger.info(f"Screening results chart saved to: {output_path}")
        return str(output_path)
    
    def create_performance_comparison_chart(self, strategies_data: Dict, output_format: str = 'html') -> str:
        """
        Create strategy performance comparison chart
        
        Args:
            strategies_data: Dictionary with strategy performance data
            output_format: 'html', 'png', or 'json'
            
        Returns:
            Path to generated chart file
        """
        logger.info("Creating strategy performance comparison chart...")
        
        if not strategies_data:
            logger.warning("No strategy data provided")
            return ""
        
        if not PLOTLY_AVAILABLE:
            return self._create_text_strategy_report(strategies_data)
        
        # Prepare data
        strategies = list(strategies_data.keys())
        
        # Extract metrics (handle missing gracefully)
        returns = []
        win_rates = []
        sharpe_ratios = []
        
        for strategy in strategies:
            data = strategies_data[strategy]
            returns.append(data.get('total_return', 0))
            win_rates.append(data.get('win_rate', 0) * 100)  # Convert to percentage
            sharpe_ratios.append(data.get('sharpe_ratio', 0))
        
        # Create radar chart for multi-dimensional comparison
        fig = go.Figure()
        
        # Normalize values for radar chart (0-1 range)
        def normalize(values):
            if not values:
                return []
            min_val = min(values)
            max_val = max(values)
            if max_val == min_val:
                return [0.5] * len(values)
            return [(v - min_val) / (max_val - min_val) for v in values]
        
        norm_returns = normalize(returns)
        norm_win_rates = normalize(win_rates)
        norm_sharpe = normalize(sharpe_ratios)
        
        # Create radar chart
        for i, strategy in enumerate(strategies):
            fig.add_trace(go.Scatterpolar(
                r=[norm_returns[i], norm_win_rates[i], norm_sharpe[i], norm_returns[i]],  # Close the shape
                theta=['Returns', 'Win Rate', 'Sharpe Ratio', 'Returns'],
                name=strategy,
                fill='toself',
                line=dict(color=plt.cm.tab20(i) if MATPLOTLIB_AVAILABLE else f'hsl({i*40}, 70%, 50%)')
            ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1]
                )
            ),
            title_text="Strategy Performance Comparison",
            height=600,
            template="plotly_white",
            showlegend=True
        )
        
        # Also create bar chart for absolute values
        fig2 = make_subplots(
            rows=1, cols=3,
            subplot_titles=('Total Returns %', 'Win Rate %', 'Sharpe Ratio')
        )
        
        # Colors based on performance
        return_colors = ['#2ecc71' if r >= 0 else '#e74c3c' for r in returns]
        win_rate_colors = ['#2ecc71' if wr >= 50 else '#e74c3c' for wr in win_rates]
        sharpe_colors = ['#2ecc71' if sr >= 1 else '#f39c12' if sr >= 0 else '#e74c3c' for sr in sharpe_ratios]
        
        fig2.add_trace(
            go.Bar(x=strategies, y=returns, name='Returns', marker_color=return_colors),
            row=1, col=1
        )
        
        fig2.add_trace(
            go.Bar(x=strategies, y=win_rates, name='Win Rate', marker_color=win_rate_colors),
            row=1, col=2
        )
        
        fig2.add_trace(
            go.Bar(x=strategies, y=sharpe_ratios, name='Sharpe Ratio', marker_color=sharpe_colors),
            row=1, col=3
        )
        
        fig2.update_layout(
            title_text="Strategy Performance Metrics",
            height=500,
            template="plotly_white",
            showlegend=False
        )
        
        # Save charts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_format == 'html':
            # Combine charts into single HTML
            from plotly.io import to_html
            combined_html = to_html(fig, full_html=False) + to_html(fig2, full_html=False)
            
            output_path = self.output_dir / f"strategy_comparison_{timestamp}.html"
            with open(output_path, 'w') as f:
                f.write(f"<html><head><title>Strategy Comparison</title></head><body>")
                f.write(combined_html)
                f.write("</body></html>")
        elif output_format == 'png' and PLOTLY_AVAILABLE:
            output_path = self.output_dir / f"strategy_comparison_{timestamp}.png"
            fig.write_image(str(output_path))
        else:
            output_path = self.output_dir / f"strategy_comparison_{timestamp}.json"
            with open(output_path, 'w') as f:
                json.dump(strategies_data, f, indent=2)
        
        logger.info(f"Strategy comparison chart saved to: {output_path}")
        return str(output_path)
    
    def create_realtime_monitor(self, monitor_data: Dict, output_format: str = 'html') -> str:
        """
        Create real-time monitoring dashboard
        
        Args:
            monitor_data: Dictionary with real-time monitoring data
            output_format: 'html', 'png', or 'json'
            
        Returns:
            Path to generated dashboard file
        """
        logger.info("Creating real-time monitor dashboard...")
        
        if not PLOTLY_AVAILABLE:
            return self._create_text_monitor_report(monitor_data)
        
        # Create dashboard with multiple indicators
        fig = make_subplots(
            rows=2, cols=3,
            specs=[
                [{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}],
                [{"type": "scatter", "colspan": 3}, None, None]
            ],
            subplot_titles=(
                'Active Signals',
                'Today\'s P&L',
                'Success Rate',
                'Recent Performance'
            )
        )
        
        # 1. Active Signals
        active_signals = monitor_data.get('active_signals', 0)
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=active_signals,
                title={"text": "Active Signals"},
                number={"font": {"size": 40}},
                domain={'row': 0, 'column': 0}
            ),
            row=1, col=1
        )
        
        # 2. Today's P&L
        today_pnl = monitor_data.get('today_pnl', 0)
        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=today_pnl,
                title={"text": "Today's P&L"},
                number={"prefix": "$", "font": {"size": 40}},
                delta={'reference': 0, 'relative': False},
                domain={'row': 0, 'column': 1}
            ),
            row=1, col=2
        )
        
        # 3. Success Rate
        success_rate = monitor_data.get('success_rate', 0) * 100
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=success_rate,
                title={"text": "Success Rate"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': '#2ecc71' if success_rate > 50 else '#e74c3c'},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgray"},
                        {'range': [50, 75], 'color': "lightyellow"},
                        {'range': [75, 100], 'color': "lightgreen"}
                    ]
                },
                domain={'row': 0, 'column': 2}
            ),
            row=1, col=3
        )
        
        # 4. Recent Performance
        if 'performance_history' in monitor_data:
            history = monitor_data['performance_history']
            timestamps = history.get('timestamps', [])
            values = history.get('values', [])
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=values,
                    mode='lines+markers',
                    name='Performance',
                    line=dict(color='#3498db', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(52, 152, 219, 0.1)'
                ),
                row=2, col=1
            )
        
        # Update layout
        fig.update_layout(
            title_text="QWNT Real-Time Monitor",
            height=700,
            template="plotly_dark",
            paper_bgcolor='#1e1e1e',
            plot_bgcolor='#1e1e1e',
            font_color='white'
        )
        
        # Save dashboard
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_format == 'html':
            output_path = self.output_dir / f"realtime_monitor_{timestamp}.html"
            fig.write_html(str(output_path))
        elif output_format == 'png' and PLOTLY_AVAILABLE:
            output_path = self.output_dir / f"realtime_monitor_{timestamp}.png"
            fig.write_image(str(output_path))
        else:
            output_path = self.output_dir / f"realtime_monitor_{timestamp}.json"
            with open(output_path, 'w') as f:
                json.dump(monitor_data, f, indent=2)
        
        logger.info(f"Real-time monitor saved to: {output_path}")
        return str(output_path)
    
    def _create_text_regime_report(self, regime_data: Dict) -> str:
        """Create text report when visualization libraries not available"""
        output = []
        output.append("=" * 60)
        output.append("MARKET REGIME ANALYSIS")
        output.append("=" * 60)
        output.append(f"Overall Regime: {regime_data.get('overall_regime', 'unknown').upper()}")
        output.append(f"Confidence: {regime_data.get('confidence', 0) * 100:.1f}%")
        
        recommendations = regime_data.get('recommendations', [])
        if recommendations:
            output.append("\nRecommendations:")
            for rec in recommendations[:5]:
                if isinstance(rec, dict):
                    output.append(f"  - {rec.get('sector', 'Unknown')}: {rec.get('action', 'neutral')} "
                                 f"(strength: {rec.get('strength', 0)})")
                else:
                    output.append(f"  - {rec}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"market_regime_{timestamp}.txt"
        
        with open(output_path, 'w') as f:
            f.write("\n".join(output))
        
        return str(output_path)
    
    def _create_text_screening_report(self, screening_data: List[Dict], asset_type: str) -> str:
        """Create text report for screening results"""
        output = []
        output.append("=" * 60)
        output.append(f"{asset_type.upper()} SCREENING RESULTS")
        output.append("=" * 60)
        
        for i, item in enumerate(screening_data[:10], 1):
            if isinstance(item, dict):
                name = item.get('name', item.get('description', f'Item {i}'))
                change = item.get('change', 0)
                output.append(f"{i:2d}. {name[:40]:40s} Change: {change:+.2f}%")
            else:
                output.append(f"{i:2d}. {str(item)}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"screening_{asset_type}_{timestamp}.txt"
        
        with open(output_path, 'w') as f:
            f.write("\n".join(output))
        
        return str(output_path)
    
    def _create_text_strategy_report(self, strategies_data: Dict) -> str:
        """Create text report for strategy performance"""
        output = []
        output.append("=" * 60)
        output.append("STRATEGY PERFORMANCE COMPARISON")
        output.append("=" * 60)
        
        for strategy, data in strategies_data.items():
            returns = data.get('total_return', 0)
            win_rate = data.get('win_rate', 0) * 100
            sharpe = data.get('sharpe_ratio', 0)
            
            output.append(f"\n{strategy.upper()}:")
            output.append(f"  Total Return: {returns:+.2f}%")
            output.append(f"  Win Rate: {win_rate:.1f}%")
            output.append(f"  Sharpe Ratio: {sharpe:.2f}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"strategy_comparison_{timestamp}.txt"
        
        with open(output_path, 'w') as f:
            f.write("\n".join(output))
        
        return str(output_path)
    
    def _create_text_monitor_report(self, monitor_data: Dict) -> str:
        """Create text report for real-time monitor"""
        output = []
        output.append("=" * 60)
        output.append("REAL-TIME MONITOR")
        output.append("=" * 60)
        output.append(f"Timestamp: {datetime.now().isoformat()}")
        output.append(f"Active Signals: {monitor_data.get('active_signals', 0)}")
        output.append(f"Today's P&L: ${monitor_data.get('today_pnl', 0):.2f}")
        output.append(f"Success Rate: {monitor_data.get('success_rate', 0) * 100:.1f}%")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"realtime_monitor_{timestamp}.txt"
        
        with open(output_path, 'w') as f:
            f.write("\n".join(output))
        
        return str(output_path)
    
    def generate_dashboard(self, all_data: Dict, output_format: str = 'html') -> str:
        """
        Generate comprehensive dashboard with all visualizations
        
        Args:
            all_data: Dictionary containing all visualization data
            output_format: 'html', 'png', or 'json'
            
        Returns:
            Path to generated dashboard file
        """
        logger.info("Generating comprehensive dashboard...")
        
        # Collect all visualizations
        charts = []
        
        # Market regime chart
        if 'market_regime' in all_data:
            chart_path = self.create_market_regime_chart(
                all_data['market_regime'], 
                output_format='html' if output_format == 'html' else 'json'
            )
            charts.append(('Market Regime', chart_path))
        
        # Screening results charts
        for asset_type in ['stocks', 'crypto', 'forex', 'etf']:
            key = f'screening_{asset_type}'
            if key in all_data:
                chart_path = self.create_screening_results_chart(
                    all_data[key],
                    asset_type,
                    output_format='html' if output_format == 'html' else 'json'
                )
                charts.append((f'{asset_type.capitalize()} Screening', chart_path))
        
        # Strategy performance
        if 'strategy_performance' in all_data:
            chart_path = self.create_performance_comparison_chart(
                all_data['strategy_performance'],
                output_format='html' if output_format == 'html' else 'json'
            )
            charts.append(('Strategy Performance', chart_path))
        
        # Real-time monitor
        if 'realtime_monitor' in all_data:
            chart_path = self.create_realtime_monitor(
                all_data['realtime_monitor'],
                output_format='html' if output_format == 'html' else 'json'
            )
            charts.append(('Real-Time Monitor', chart_path))
        
        # Create dashboard HTML if requested
        if output_format == 'html' and charts:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dashboard_path = self.output_dir / f"dashboard_{timestamp}.html"
            
            with open(dashboard_path, 'w') as f:
                f.write("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>QWNT Trading Dashboard</title>
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
                        <h1>QWNT Trading Dashboard</h1>
                        <p>Generated: """ + datetime.now().isoformat() + """</p>
                    </div>
                """)
                
                for title, chart_path in charts:
                    if chart_path.endswith('.html'):
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
            
            logger.info(f"Dashboard saved to: {dashboard_path}")
            return str(dashboard_path)
        
        # Return first chart path or JSON summary
        if charts:
            return charts[0][1]
        else:
            # Save data as JSON
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"dashboard_data_{timestamp}.json"
            with open(output_path, 'w') as f:
                json.dump(all_data, f, indent=2)
            return str(output_path)


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate TradingView visualizations")
    parser.add_argument('--data-file', help='JSON file with visualization data')
    parser.add_argument('--output-format', default='html', choices=['html', 'png', 'json', 'txt'])
    parser.add_argument('--dashboard', action='store_true', help='Generate full dashboard')
    
    args = parser.parse_args()
    
    visualizer = TradingViewVisualizer()
    
    if args.data_file:
        with open(args.data_file, 'r') as f:
            data = json.load(f)
        
        if args.dashboard:
            output_path = visualizer.generate_dashboard(data, args.output_format)
        else:
            # Generate individual charts based on data keys
            if 'market_regime' in data:
                output_path = visualizer.create_market_regime_chart(data['market_regime'], args.output_format)
            elif any(key.startswith('screening_') for key in data.keys()):
                for key in data.keys():
                    if key.startswith('screening_'):
                        asset_type = key.replace('screening_', '')
                        output_path = visualizer.create_screening_results_chart(
                            data[key], asset_type, args.output_format
                        )
                        break
            elif 'strategy_performance' in data:
                output_path = visualizer.create_performance_comparison_chart(
                    data['strategy_performance'], args.output_format
                )
            else:
                output_path = visualizer.generate_dashboard(data, args.output_format)
        
        print(f"Visualization generated: {output_path}")
    else:
        print("No data file provided. Generating sample visualizations...")
        
        # Generate sample data for demonstration
        sample_regime_data = {
            'overall_regime': 'bull',
            'confidence': 0.75,
            'regime_strength': {'bull': 0.8, 'bear': 0.1, 'correction': 0.1},
            'recommendations': [
                {'sector': 'Technology', 'action': 'buy', 'strength': 0.9},
                {'sector': 'Healthcare', 'action': 'buy', 'strength': 0.7},
                {'sector': 'Energy', 'action': 'sell', 'strength': 0.6},
            ]
        }
        
        output_path = visualizer.create_market_regime_chart(sample_regime_data, args.output_format)
        print(f"Sample market regime chart: {output_path}")