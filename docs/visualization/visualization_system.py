#!/usr/bin/env python3
"""
QWNT Visualization System
Creates charts, dashboards, and data visualizations for trading insights
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path

# Try to import visualization libraries (optional)
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib not installed. Install with: pip install matplotlib")

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("⚠️  plotly not installed. Install with: pip install plotly")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QWNT_Visualization")

class QWNTVisualizer:
    """
    Creates visualizations for QWNT trading system
    Supports multiple output formats: PNG, HTML, JSON
    """
    
    def __init__(self, output_dir: str = "visualizations"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Color schemes
        self.colors = {
            'bull': '#2ecc71',  # Green
            'bear': '#e74c3c',  # Red
            'correction': '#f39c12',  # Orange
            'buy': '#27ae60',  # Dark green
            'sell': '#c0392b',  # Dark red
            'neutral': '#7f8c8d',  # Gray
            'profit': '#16a085',  # Teal
            'loss': '#d35400',  # Pumpkin
        }
        
        logger.info(f"📊 QWNT Visualizer initialized. Output directory: {self.output_dir}")
    
    def create_performance_dashboard(self, performance_data: Dict) -> str:
        """
        Create comprehensive performance dashboard
        Returns path to generated HTML file
        """
        logger.info("Creating performance dashboard...")
        
        if not PLOTLY_AVAILABLE:
            return self._create_text_performance_report(performance_data)
        
        # Create subplots
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                'Portfolio Value Over Time',
                'Daily Returns Distribution',
                'Trade Win/Loss Ratio',
                'Strategy Performance Comparison',
                'Risk Metrics',
                'Market Exposure'
            ),
            specs=[
                [{"type": "scatter"}, {"type": "bar"}],
                [{"type": "pie"}, {"type": "scatter"}],
                [{"type": "indicator"}, {"type": "bar"}]
            ]
        )
        
        # 1. Portfolio value over time
        if 'portfolio_history' in performance_data:
            dates = performance_data['portfolio_history'].get('dates', [])
            values = performance_data['portfolio_history'].get('values', [])
            
            fig.add_trace(
                go.Scatter(
                    x=dates, y=values,
                    mode='lines+markers',
                    name='Portfolio Value',
                    line=dict(color=self.colors['bull'], width=2),
                    fill='tozeroy',
                    fillcolor='rgba(46, 204, 113, 0.1)'
                ),
                row=1, col=1
            )
        
        # 2. Daily returns distribution
        if 'daily_returns' in performance_data:
            returns = performance_data['daily_returns']
            
            fig.add_trace(
                go.Histogram(
                    x=returns,
                    name='Daily Returns',
                    marker_color=self.colors['neutral'],
                    nbinsx=20,
                    opacity=0.7
                ),
                row=1, col=2
            )
        
        # 3. Trade win/loss ratio
        if 'trade_stats' in performance_data:
            wins = performance_data['trade_stats'].get('wins', 0)
            losses = performance_data['trade_stats'].get('losses', 0)
            total = wins + losses
            
            if total > 0:
                fig.add_trace(
                    go.Pie(
                        labels=['Wins', 'Losses'],
                        values=[wins, losses],
                        marker=dict(colors=[self.colors['profit'], self.colors['loss']]),
                        hole=0.4,
                        name='Win/Loss Ratio'
                    ),
                    row=2, col=1
                )
        
        # 4. Strategy performance
        if 'strategy_performance' in performance_data:
            strategies = list(performance_data['strategy_performance'].keys())
            returns = list(performance_data['strategy_performance'].values())
            
            fig.add_trace(
                go.Bar(
                    x=strategies,
                    y=returns,
                    name='Strategy Returns',
                    marker_color=[self.colors['bull'] if r > 0 else self.colors['bear'] for r in returns]
                ),
                row=2, col=2
            )
        
        # 5. Risk metrics gauge
        if 'risk_metrics' in performance_data:
            sharpe = performance_data['risk_metrics'].get('sharpe_ratio', 0)
            max_dd = performance_data['risk_metrics'].get('max_drawdown', 0)
            
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=sharpe,
                    title={'text': "Sharpe Ratio"},
                    gauge={
                        'axis': {'range': [-1, 3]},
                        'bar': {'color': self.colors['bull'] if sharpe > 1 else self.colors['bear']},
                        'steps': [
                            {'range': [-1, 0], 'color': "lightgray"},
                            {'range': [0, 1], 'color': "lightyellow"},
                            {'range': [1, 3], 'color': "lightgreen"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': 1.0
                        }
                    }
                ),
                row=3, col=1
            )
        
        # 6. Market exposure
        if 'market_exposure' in performance_data:
            markets = list(performance_data['market_exposure'].keys())
            exposures = list(performance_data['market_exposure'].values())
            
            fig.add_trace(
                go.Bar(
                    x=markets,
                    y=exposures,
                    name='Market Exposure',
                    marker_color=self.colors['neutral']
                ),
                row=3, col=2
            )
        
        # Update layout
        fig.update_layout(
            title_text="QWNT Trading Performance Dashboard",
            height=1200,
            showlegend=True,
            template="plotly_white"
        )
        
        # Save as HTML
        output_path = self.output_dir / "performance_dashboard.html"
        fig.write_html(str(output_path))
        
        logger.info(f"✅ Dashboard saved to: {output_path}")
        return str(output_path)
    
    def create_market_regime_chart(self, regime_data: Dict) -> str:
        """
        Create market regime visualization
        """
        logger.info("Creating market regime chart...")
        
        if not PLOTLY_AVAILABLE:
            return self._create_text_regime_report(regime_data)
        
        fig = go.Figure()
        
        # Add regime areas
        if 'regime_history' in regime_data:
            dates = regime_data['regime_history'].get('dates', [])
            regimes = regime_data['regime_history'].get('regimes', [])
            values = regime_data['regime_history'].get('values', [])
            
            # Create colored background based on regime
            prev_regime = None
            start_idx = 0
            
            for i, regime in enumerate(regimes):
                if regime != prev_regime:
                    if prev_regime is not None:
                        # Add background for previous regime
                        fig.add_vrect(
                            x0=dates[start_idx], x1=dates[i-1],
                            fillcolor=self.colors.get(prev_regime, '#ecf0f1'),
                            opacity=0.3,
                            layer="below",
                            line_width=0,
                        )
                    start_idx = i
                    prev_regime = regime
            
            # Add line chart
            fig.add_trace(
                go.Scatter(
                    x=dates, y=values,
                    mode='lines',
                    name='Market Index',
                    line=dict(color='#2c3e50', width=2)
                )
            )
        
        # Add current regime indicator
        current_regime = regime_data.get('current_regime', 'unknown')
        fig.add_annotation(
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            text=f"Current Regime: <b>{current_regime.upper()}</b>",
            showarrow=False,
            font=dict(
                size=16,
                color=self.colors.get(current_regime, '#000000')
            ),
            bgcolor="white",
            bordercolor=self.colors.get(current_regime, '#000000'),
            borderwidth=2,
            borderpad=4
        )
        
        # Update layout
        fig.update_layout(
            title_text="Market Regime Analysis",
            xaxis_title="Date",
            yaxis_title="Index Value",
            template="plotly_white",
            hovermode="x unified"
        )
        
        output_path = self.output_dir / "market_regime.html"
        fig.write_html(str(output_path))
        
        logger.info(f"✅ Market regime chart saved to: {output_path}")
        return str(output_path)
    
    def create_trade_analysis_chart(self, trades_data: List[Dict]) -> str:
        """
        Create trade analysis visualization
        """
        logger.info(f"Creating trade analysis chart for {len(trades_data)} trades...")
        
        if not trades_data:
            return "No trade data available"
        
        if not PLOTLY_AVAILABLE:
            return self._create_text_trade_report(trades_data)
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(trades_data)
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Trade P&L Distribution',
                'Entry vs Exit Prices',
                'Trade Duration Analysis',
                'Strategy Performance'
            )
        )
        
        # 1. P&L Distribution
        if 'pnl_percent' in df.columns:
            fig.add_trace(
                go.Histogram(
                    x=df['pnl_percent'],
                    name='P&L Distribution',
                    marker_color=df['pnl_percent'].apply(
                        lambda x: self.colors['profit'] if x > 0 else self.colors['loss']
                    ),
                    nbinsx=20
                ),
                row=1, col=1
            )
        
        # 2. Entry vs Exit Prices
        if all(col in df.columns for col in ['entry_price', 'exit_price']):
            fig.add_trace(
                go.Scatter(
                    x=df['entry_price'],
                    y=df['exit_price'],
                    mode='markers',
                    marker=dict(
                        size=10,
                        color=df['pnl_percent'] if 'pnl_percent' in df.columns else self.colors['neutral'],
                        colorscale='RdYlGn',
                        showscale=True,
                        colorbar=dict(title="P&L %")
                    ),
                    text=df.get('symbol', ''),
                    name='Entry vs Exit'
                ),
                row=1, col=2
            )
            
            # Add diagonal line (break-even)
            min_price = min(df['entry_price'].min(), df['exit_price'].min())
            max_price = max(df['entry_price'].max(), df['exit_price'].max())
            fig.add_trace(
                go.Scatter(
                    x=[min_price, max_price],
                    y=[min_price, max_price],
                    mode='lines',
                    line=dict(color='gray', dash='dash'),
                    name='Break-even'
                ),
                row=1, col=2
            )
        
        # 3. Trade Duration Analysis
        if 'duration_hours' in df.columns:
            fig.add_trace(
                go.Box(
                    y=df['duration_hours'],
                    name='Trade Duration',
                    marker_color=self.colors['neutral'],
                    boxpoints='all'
                ),
                row=2, col=1
            )
        
        # 4. Strategy Performance
        if 'strategy' in df.columns:
            strategy_stats = df.groupby('strategy').agg({
                'pnl_percent': 'mean',
                'symbol': 'count'
            }).rename(columns={'symbol': 'trade_count'})
            
            fig.add_trace(
                go.Bar(
                    x=strategy_stats.index,
                    y=strategy_stats['pnl_percent'],
                    name='Avg P&L by Strategy',
                    marker_color=self.colors['bull'],
                    text=strategy_stats['trade_count'],
                    textposition='auto'
                ),
                row=2, col=2
            )
        
        # Update layout
        fig.update_layout(
            title_text="Trade Analysis Dashboard",
            height=800,
            template="plotly_white",
            showlegend=True
        )
        
        output_path = self.output_dir / "trade_analysis.html"
        fig.write_html(str(output_path))
        
        logger.info(f"✅ Trade analysis chart saved to: {output_path}")
        return str(output_path)
    
    def create_realtime_monitor(self, realtime_data: Dict) -> str:
        """
        Create real-time monitoring dashboard
        """
        logger.info("Creating real-time monitor...")
        
        if not PLOTLY_AVAILABLE:
            return self._create_text_realtime_report(realtime_data)
        
        fig = make_subplots(
            rows=2, cols=3,
            specs=[
                [{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}],
                [{"type": "scatter", "colspan": 3}, None, None]
            ],
            subplot_titles=(
                'Active Positions',
                'Today\'s P&L',
                'Win Rate',
                'Price Movements'
            )
        )
        
        # 1. Active Positions
        active_positions = realtime_data.get('active_positions', 0)
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=active_positions,
                title={"text": "Active Positions"},
                number={"font": {"size": 40}},
                domain={'row': 0, 'column': 0}
            ),
            row=1, col=1
        )
        
        # 2. Today's P&L
        today_pnl = realtime_data.get('today_pnl', 0)
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
        
        # 3. Win Rate
        win_rate = realtime_data.get('win_rate', 0) * 100
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=win_rate,
                title={"text": "Win Rate"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': self.colors['profit'] if win_rate > 50 else self.colors['loss']},
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
        
        # 4. Price Movements
        if 'price_history' in realtime_data:
            times = realtime_data['price_history'].get('times', [])
            prices = realtime_data['price_history'].get('prices', [])
            
            fig.add_trace(
                go.Scatter(
                    x=times,
                    y=prices,
                    mode='lines',
                    name='Price',
                    line=dict(color=self.colors['bull'], width=2),
                    fill='tozeroy',
                    fillcolor='rgba(46, 204, 113, 0.1)'
                ),
                row=2, col=1
            )
        
        # Update layout
        fig.update_layout(
            title_text="QWNT Real-Time Monitor",
            height=600,
            template="plotly_dark",  # Dark theme for monitoring
            paper_bgcolor='#1e1e1e',
            plot_bgcolor='#1e1e1e',
            font_color='white'
        )
        
        output_path = self.output_dir / "realtime_monitor.html"
        fig.write_html(str(output_path))
        
        logger.info(f"✅ Real-time monitor saved to: {output_path}")
        return str(output_path)
    
    def create_tradingview_style_chart(self, symbol: str, data: Dict) -> str:
        """
        Create TradingView-style chart for a specific symbol
        """
        logger.info(f"Creating TradingView-style chart for {symbol}...")
        
        if not PLOTLY_AVAILABLE:
            return f"Chart for {symbol}: {json.dumps(data, indent=2)}"
        
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.6, 0.