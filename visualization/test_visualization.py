#!/usr/bin/env python3
"""
Test visualization system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visualization.tradingview_visualizer import TradingViewVisualizer

def test_market_regime_chart():
    """Test market regime chart generation"""
    print("Testing market regime chart...")
    
    visualizer = TradingViewVisualizer(output_dir="visualization/test_output")
    
    # Sample market regime data
    sample_data = {
        'overall_regime': 'bull',
        'confidence': 0.75,
        'regime_strength': {'bull': 0.8, 'bear': 0.1, 'correction': 0.1},
        'recommendations': [
            {'sector': 'Technology', 'action': 'buy', 'strength': 0.9},
            {'sector': 'Healthcare', 'action': 'buy', 'strength': 0.7},
            {'sector': 'Energy', 'action': 'sell', 'strength': 0.6},
            {'sector': 'Finance', 'action': 'hold', 'strength': 0.5},
        ]
    }
    
    # Generate HTML chart
    chart_path = visualizer.create_market_regime_chart(sample_data, output_format='html')
    print(f"✅ Market regime chart: {chart_path}")
    
    # Generate JSON data
    json_path = visualizer.create_market_regime_chart(sample_data, output_format='json')
    print(f"✅ Market regime data: {json_path}")
    
    return chart_path

def test_screening_chart():
    """Test screening results chart generation"""
    print("\nTesting screening results chart...")
    
    visualizer = TradingViewVisualizer(output_dir="visualization/test_output")
    
    # Sample screening data
    sample_data = [
        {'name': 'Apple Inc.', 'symbol': 'AAPL', 'change': 2.5, 'market_cap_basic': 2500000000000},
        {'name': 'Microsoft', 'symbol': 'MSFT', 'change': 1.8, 'market_cap_basic': 2000000000000},
        {'name': 'Amazon', 'symbol': 'AMZN', 'change': -0.5, 'market_cap_basic': 1800000000000},
        {'name': 'Google', 'symbol': 'GOOGL', 'change': 3.2, 'market_cap_basic': 1500000000000},
        {'name': 'Tesla', 'symbol': 'TSLA', 'change': -2.1, 'market_cap_basic': 600000000000},
        {'name': 'NVIDIA', 'symbol': 'NVDA', 'change': 5.7, 'market_cap_basic': 800000000000},
        {'name': 'Meta', 'symbol': 'META', 'change': 1.2, 'market_cap_basic': 900000000000},
        {'name': 'Netflix', 'symbol': 'NFLX', 'change': -1.5, 'market_cap_basic': 250000000000},
    ]
    
    # Generate HTML chart
    chart_path = visualizer.create_screening_results_chart(sample_data, asset_type='stocks', output_format='html')
    print(f"✅ Screening results chart: {chart_path}")
    
    return chart_path

def test_dashboard():
    """Test comprehensive dashboard generation"""
    print("\nTesting comprehensive dashboard...")
    
    visualizer = TradingViewVisualizer(output_dir="visualization/test_output")
    
    # Sample data for all visualizations
    all_data = {
        'market_regime': {
            'overall_regime': 'bull',
            'confidence': 0.75,
            'recommendations': [
                {'sector': 'Tech', 'action': 'buy', 'strength': 0.9},
                {'sector': 'Health', 'action': 'buy', 'strength': 0.7},
            ]
        },
        'screening_stocks': [
            {'name': 'AAPL', 'change': 2.5, 'market_cap_basic': 2500000000000},
            {'name': 'MSFT', 'change': 1.8, 'market_cap_basic': 2000000000000},
        ],
        'strategy_performance': {
            'degen': {'total_return': 25.5, 'win_rate': 0.65, 'sharpe_ratio': 1.2},
            'sniper': {'total_return': 18.2, 'win_rate': 0.75, 'sharpe_ratio': 2.1},
            'oracle_eye': {'total_return': 32.7, 'win_rate': 0.8, 'sharpe_ratio': 2.5},
        },
        'realtime_monitor': {
            'active_signals': 5,
            'today_pnl': 1250.50,
            'success_rate': 0.75,
            'performance_history': {
                'timestamps': ['2024-01-01', '2024-01-02', '2024-01-03'],
                'values': [1000, 1200, 1250]
            }
        }
    }
    
    # Generate dashboard
    dashboard_path = visualizer.generate_dashboard(all_data, output_format='html')
    print(f"✅ Comprehensive dashboard: {dashboard_path}")
    
    return dashboard_path

def test_qwnt_dashboard():
    """Test QWNT dashboard integration"""
    print("\nTesting QWNT dashboard integration...")
    
    from visualization.qwnt_dashboard import QWNTDashboard
    
    dashboard = QWNTDashboard(output_dir="visualization/test_output")
    
    # Sample QWNT system data
    sample_system_data = {
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
            'max_drawdown': -5.2,
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
        ],
        'screening_stocks': [
            {'name': 'AAPL', 'change': 2.5, 'market_cap_basic': 2500000000000},
            {'name': 'MSFT', 'change': 1.8, 'market_cap_basic': 2000000000000},
        ]
    }
    
    # Generate performance dashboard
    perf_dashboard = dashboard.generate_performance_dashboard(sample_system_data, 'html')
    print(f"✅ QWNT performance dashboard: {perf_dashboard}")
    
    # Generate trade analysis dashboard
    sample_trades = [
        {'symbol': 'AAPL', 'entry_price': 150, 'exit_price': 165, 'pnl': 1500, 'pnl_percent': 10.0, 'duration_hours': 24, 'strategy': 'oracle_eye'},
        {'symbol': 'MSFT', 'entry_price': 300, 'exit_price': 285, 'pnl': -1500, 'pnl_percent': -5.0, 'duration_hours': 48, 'strategy': 'sniper'},
        {'symbol': 'GOOGL', 'entry_price': 120, 'exit_price': 132, 'pnl': 1200, 'pnl_percent': 10.0, 'duration_hours': 12, 'strategy': 'oracle_eye'},
        {'symbol': 'TSLA', 'entry_price': 200, 'exit_price': 220, 'pnl': 2000, 'pnl_percent': 10.0, 'duration_hours': 72, 'strategy': 'degen'},
    ]
    
    trade_dashboard = dashboard.generate_trade_analysis_dashboard(sample_trades, 'html')
    print(f"✅ QWNT trade analysis dashboard: {trade_dashboard}")
    
    return perf_dashboard, trade_dashboard

def main():
    """Run all tests"""
    print("=" * 60)
    print("QWNT VISUALIZATION SYSTEM TEST")
    print("=" * 60)
    
    try:
        # Test 1: Market regime chart
        chart1 = test_market_regime_chart()
        
        # Test 2: Screening chart
        chart2 = test_screening_chart()
        
        # Test 3: Comprehensive dashboard
        chart3 = test_dashboard()
        
        # Test 4: QWNT dashboard integration
        chart4, chart5 = test_qwnt_dashboard()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("\nGenerated charts:")
        print(f"  1. Market regime: {chart1}")
        print(f"  2. Screening results: {chart2}")
        print(f"  3. Comprehensive dashboard: {chart3}")
        print(f"  4. QWNT performance dashboard: {chart4}")
        print(f"  5. QWNT trade analysis: {chart5}")
        print("\nOpen the HTML files in a browser to view the charts.")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())