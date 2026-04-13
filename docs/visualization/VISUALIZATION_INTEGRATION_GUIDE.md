# QWNT VISUALIZATION INTEGRATION GUIDE
## How to Add Charts & Dashboards Using TradingView MCP
### Generated: 2026-04-12 00:45 GMT+4

## 🎯 OVERVIEW

This guide shows how to integrate **real-time charts and dashboards** into the QWNT trading system using the **TradingView MCP** server we've already installed and configured.

## 📊 AVAILABLE VISUALIZATION MODULES

### **1. TradingViewVisualizer** (`visualization/tradingview_visualizer.py`)
- **Purpose**: Generate charts from TradingView data
- **Chart Types**: Market regime, screening results, performance comparison, real-time monitors
- **Output Formats**: HTML (interactive), PNG (static), JSON (data), TXT (text reports)
- **Dependencies**: Plotly, Pandas, Matplotlib (optional)

### **2. QWNTDashboard** (`visualization/qwnt_dashboard.py`)
- **Purpose**: QWNT-specific dashboards and reports
- **Features**: Performance dashboards, trade analysis, daily reports, continuous monitoring
- **Integration**: Direct integration with QWNT trading system

### **3. TradingViewChartGenerator** (`visualization/tradingview_chart_generator.py`)
- **Purpose**: Direct integration with TradingView MCP CLI
- **Features**: Live data fetching, screening visualization, market regime inference
- **CLI Access**: Uses `tradingview-cli` command-line tool

### **4. Test Suite** (`visualization/test_visualization.py`)
- **Purpose**: Test all visualization components
- **Usage**: Run to verify installation and generate sample charts

## 🚀 QUICK START: GENERATE YOUR FIRST CHART

### **Option 1: Generate Sample Charts (No Data Required)**
```bash
cd /Users/colto/.openclaw/workspace/codex/asymmetric_trading
python visualization/test_visualization.py
```
This will generate 5 sample charts in `visualization/test_output/`

### **Option 2: Generate Live TradingView Charts**
```bash
# Generate stock screening chart with live data
python visualization/tradingview_chart_generator.py --chart-type screening --asset-type stocks

# Generate market regime chart
python visualization/tradingview_chart_generator.py --chart-type regime

# Generate comprehensive dashboard
python visualization/tradingview_chart_generator.py --chart-type dashboard
```

### **Option 3: Generate QWNT Performance Dashboard**
```bash
# Generate sample QWNT dashboard (mock data)
python visualization/qwnt_dashboard.py

# Generate with your data
python visualization/qwnt_dashboard.py --data-file your_data.json --mode performance
```

## 🔧 INTEGRATION POINTS IN QWNT SYSTEM

### **1. Enhanced Whisperer Integration**
**File**: `agents/qwnt_enhanced_whisperer.py`

**Add visualization to signal scanning**:
```python
# Add import at top
from visualization.tradingview_visualizer import TradingViewVisualizer

class QWNTEnhancedWhisperer:
    def __init__(self):
        # Add visualizer
        self.visualizer = TradingViewVisualizer(output_dir="visualization/whisperer")
    
    def scan_with_strategy(self, strategy_name: str):
        # Existing scanning logic...
        signals = self._scan_strategy(strategy_name)
        
        # Generate visualization
        if signals:
            # Create signal strength chart
            chart_data = [
                {
                    'token': s.token_address[:10],
                    'score': s.narrative_score,
                    'chain': s.chain
                }
                for s in signals[:10]
            ]
            
            chart_path = self.visualizer.create_screening_results_chart(
                chart_data, asset_type='crypto', output_format='html'
            )
            
            logger.info(f"📈 Signal visualization: {chart_path}")
        
        return signals
```

### **2. Trading System Integration**
**File**: `qwnt_trading_system.py`

**Add dashboard generation after each trading cycle**:
```python
# Add import
from visualization.qwnt_dashboard import QWNTDashboard

class QWNTTradingSystem:
    def __init__(self, use_mock_tv=True):
        # Add dashboard
        self.dashboard = QWNTDashboard(output_dir="visualization/system")
        
    def run_trading_cycle(self):
        # Existing trading cycle logic...
        success = self._execute_trading_cycle()
        
        # Generate performance dashboard
        if success:
            system_data = self.dashboard.update_from_trading_system(self)
            dashboard_path = self.dashboard.generate_performance_dashboard(
                system_data, output_format='html'
            )
            
            print(f"📊 Performance dashboard: {dashboard_path}")
        
        return success
    
    def generate_daily_report(self):
        """Generate end-of-day report"""
        day_data = self._collect_daily_data()
        report_path = self.dashboard.generate_daily_report(day_data, 'html')
        return report_path
```

### **3. CLI Integration**
**File**: `cli.py`

**Add visualization commands to CLI**:
```python
@click.command()
@click.option('--asset-type', default='stocks', help='Asset type')
@click.option('--preset', default='quality_stocks', help='Screening preset')
def chart(asset_type, preset):
    """Generate TradingView charts"""
    from visualization.tradingview_chart_generator import TradingViewChartGenerator
    
    generator = TradingViewChartGenerator()
    chart_path = generator.generate_screening_chart(asset_type, preset)
    
    click.echo(f"Chart generated: {chart_path}")
    click.echo(f"Open file://{os.path.abspath(chart_path)} in your browser")

@click.command()
def dashboard():
    """Generate QWNT performance dashboard"""
    from visualization.qwnt_dashboard import QWNTDashboard
    
    dashboard = QWNTDashboard()
    
    # Get data from running system or file
    data = load_system_data()
    dashboard_path = dashboard.generate_performance_dashboard(data)
    
    click.echo(f"Dashboard generated: {dashboard_path}")

# Add to main CLI group
cli.add_command(chart)
cli.add_command(dashboard)
```

### **4. Real-Time Monitoring Integration**
**File**: `monitoring/realtime_monitor.py` (new)

**Create continuous monitoring dashboard**:
```python
from visualization.qwnt_dashboard import QWNTDashboard
import time
import threading

class RealtimeMonitor:
    def __init__(self, trading_system, interval_seconds=300):
        self.system = trading_system
        self.interval = interval_seconds
        self.dashboard = QWNTDashboard()
        
    def start(self):
        """Start continuous monitoring"""
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        print(f"📊 Real-time monitor started (updates every {self.interval}s)")
        
    def _monitor_loop(self):
        while True:
            try:
                # Update dashboard
                data = self.dashboard.update_from_trading_system(self.system)
                dashboard_path = self.dashboard.generate_performance_dashboard(data)
                
                print(f"Monitor update: {dashboard_path}")
                
                time.sleep(self.interval)
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(self.interval)

# Usage in main.py
monitor = RealtimeMonitor(trading_system, interval_seconds=300)
monitor.start()
```

## 📈 SPECIFIC VISUALIZATION SCENARIOS

### **Scenario 1: Signal Discovery Visualization**
```python
# Visualize top signals from whisperer
def visualize_signals(signals, output_dir="visualization/signals"):
    visualizer = TradingViewVisualizer(output_dir)
    
    # Convert signals to chart data
    chart_data = []
    for signal in signals[:20]:
        chart_data.append({
            'name': signal.token_address[:10] + '...',
            'score': signal.narrative_score,
            'chain': signal.chain,
            'velocity': getattr(signal, 'velocity', 0),
        })
    
    # Create bubble chart
    chart_path = visualizer.create_screening_results_chart(
        chart_data, asset_type='crypto', output_format='html'
    )
    
    return chart_path
```

### **Scenario 2: Risk Assessment Visualization**
```python
# Visualize risk assessment results
def visualize_risk_assessment(assessments):
    visualizer = TradingViewVisualizer(output_dir="visualization/risk")
    
    # Prepare data
    risk_data = []
    for assessment in assessments:
        risk_data.append({
            'token': assessment.token_address[:10],
            'risk_level': assessment.risk_level,
            'honeypot': assessment.is_honeypot,
            'buy_tax': assessment.buy_tax * 100,
            'sell_tax': assessment.sell_tax * 100,
        })
    
    # Create risk heatmap
    chart_path = visualizer.create_screening_results_chart(
        risk_data, asset_type='crypto', output_format='html'
    )
    
    return chart_path
```

### **Scenario 3: Execution Performance Visualization**
```python
# Visualize execution quality
def visualize_execution_quality(executions):
    visualizer = TradingViewVisualizer(output_dir="visualization/execution")
    
    # Prepare data
    exec_data = []
    for exec in executions:
        exec_data.append({
            'symbol': exec.symbol,
            'slippage': exec.slippage_percent,
            'latency': exec.latency_ms,
            'success': exec.success,
            'gas_used': exec.gas_used,
        })
    
    # Create execution dashboard
    chart_path = visualizer.create_realtime_monitor({
        'executions': exec_data,
        'avg_slippage': np.mean([e['slippage'] for e in exec_data]),
        'success_rate': sum(1 for e in exec_data if e['success']) / len(exec_data),
    }, output_format='html')
    
    return chart_path
```

### **Scenario 4: Portfolio Performance Visualization**
```python
# Visualize portfolio performance
def visualize_portfolio_performance(portfolio_history):
    from visualization.qwnt_dashboard import QWNTDashboard
    
    dashboard = QWNTDashboard()
    
    # Prepare performance data
    perf_data = {
        'performance': {
            'total_pnl': portfolio_history['total_pnl'],
            'win_rate': portfolio_history['win_rate'],
            'sharpe_ratio': portfolio_history['sharpe_ratio'],
            'max_drawdown': portfolio_history['max_drawdown'],
        },
        'portfolio_history': {
            'dates': portfolio_history['dates'],
            'values': portfolio_history['values'],
        }
    }
    
    # Generate dashboard
    dashboard_path = dashboard.generate_performance_dashboard(perf_data)
    
    return dashboard_path
```

## 🎨 CUSTOMIZING VISUALIZATIONS

### **Color Schemes**
```python
# Custom color schemes in TradingViewVisualizer
visualizer = TradingViewVisualizer()
visualizer.regime_colors = {
    'bull': '#00ff00',  # Bright green
    'bear': '#ff0000',  # Bright red
    'correction': '#ffff00',  # Yellow
}

visualizer.performance_colors = {
    'positive': '#00cc00',
    'negative': '#cc0000',
    'neutral': '#cccccc',
}
```

### **Chart Layouts**
```python
# Custom chart layouts
fig = make_subplots(
    rows=2, cols=2,
    specs=[
        [{"type": "scatter"}, {"type": "indicator"}],
        [{"type": "bar", "colspan": 2}, None]
    ],
    subplot_titles=('Price', 'Indicator', 'Volume')
)
```

### **Output Formats**
```python
# Multiple output formats
chart_path = visualizer.create_market_regime_chart(
    data,
    output_format='html'  # Options: 'html', 'png', 'json', 'txt'
)

# Generate all formats
for fmt in ['html', 'png', 'json']:
    visualizer.create_market_regime_chart(data, output_format=fmt)
```

## 🔌 INTEGRATION WITH EXTERNAL SYSTEMS

### **Telegram Bot Integration**
```python
# Send charts to Telegram
def send_chart_to_telegram(chat_id, chart_path):
    import requests
    
    if chart_path.endswith('.png'):
        with open(chart_path, 'rb') as photo:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                data={'chat_id': chat_id},
                files={'photo': photo}
            )
    elif chart_path.endswith('.html'):
        # Convert HTML to PNG first
        import imgkit
        imgkit.from_file(chart_path, '/tmp/chart.png')
        send_chart_to_telegram(chat_id, '/tmp/chart.png')
```

### **Discord Webhook Integration**
```python
# Send charts to Discord
def send_chart_to_discord(webhook_url, chart_path, title="Trading Chart"):
    from discord_webhook import DiscordWebhook, DiscordEmbed
    
    webhook = DiscordWebhook(url=webhook_url)
    
    if chart_path.endswith('.png'):
        with open(chart_path, 'rb') as f:
            webhook.add_file(file=f.read(), filename='chart.png')
    
    embed = DiscordEmbed(title=title, description="Latest trading chart")
    embed.set_image(url='attachment://chart.png')
    
    webhook.add_embed(embed)
    webhook.execute()
```

### **Email Report Integration**
```python
# Send charts via email
def send_chart_via_email(to_email, chart_path, subject="Daily Trading Report"):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage
    
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['To'] = to_email
    
    # Attach chart
    with open(chart_path, 'rb') as f:
        img = MIMEImage(f.read())
        img.add_header('Content-ID', '<chart1>')
        msg.attach(img)
    
    # HTML content with embedded chart
    html = f"""
    <html>
        <body>
            <h1>Daily Trading Report</h1>
            <img src="cid:chart1">
        </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html'))
    
    # Send email
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL, PASSWORD)
    server.send_message(msg)
    server.quit()
```

## 🧪 TESTING YOUR INTEGRATION

### **Test Script**
```bash
# Run comprehensive tests
cd /Users/colto/.openclaw/workspace/codex/asymmetric_trading
python visualization/test_visualization.py

# Test individual components
python -c "from visualization.tradingview_visualizer import TradingViewVisualizer; tv = TradingViewVisualizer(); print('✅ Visualizer OK')"

# Test CLI integration
python visualization/tradingview_chart_generator.py --chart-type screening --asset-type stocks --output-format html
```

### **Verification Checklist**
- [ ] Charts generate without errors
- [ ] HTML files open in browser
- [ ] Data is accurate and up-to-date
- [ ] Colors and layouts are readable
- [ ] Performance is acceptable (< 5 seconds per chart)
- [ ] Error handling works (missing data, API failures)

## 🚀 PRODUCTION DEPLOYMENT

### **Scheduled Chart Generation** (Cron Jobs)
```bash
# Generate daily report at 6 PM
0 18 * * * cd /path/to/qwnt && python visualization/tradingview_chart_generator.py --chart-type dashboard >> /var/log/qwnt_charts.log

# Generate hourly market update
0 * * * * cd /path/to/qwnt && python visualization/tradingview_chart_generator.py --chart-type regime >> /var/log/qwnt_regime.log

# Generate performance dashboard after each trading cycle
# Add to qwnt_trading_system.py in run_trading_cycle()
```

### **Web Dashboard Deployment**
```python
# Simple Flask dashboard server
from flask import Flask, send_file
import os

app = Flask(__name__)

@app.route('/dashboard')
def serve_dashboard():
    # Generate fresh dashboard
    from visualization.tradingview_chart_generator import TradingViewChartGenerator
    generator = TradingViewChartGenerator()
    dashboard_path = generator.generate_comprehensive_dashboard()
    
    return send_file(dashboard_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### **Monitoring and Alerting**
```python
# Monitor chart generation failures
import logging
from logging.handlers import SMTPHandler

logger = logging.getLogger('Visualization')
handler = SMTPHandler(
    mailhost=('smtp.gmail.com', 587),
    fromaddr='alerts@qwnt.com',
    toaddrs=['admin@qwnt.com'],
    subject='Visualization Failure',
    credentials=('user', 'pass'),
    secure=()
)
logger.addHandler(handler)

try:
    generate_charts()
except Exception as e:
    logger.error(f"Chart generation failed: {e}")
```

## 📚 NEXT STEPS

### **Immediate Actions (Today)**
1. ✅ Install visualization dependencies (`pip install plotly pandas matplotlib kaleido`)
2. ✅ Run test suite to verify installation
3. ✅ Integrate into whisperer for signal visualization
4. ✅ Add dashboard generation to trading system
5. ✅ Test with real TradingView data

### **Short-term Improvements (This Week)**
1. Add real-time monitoring dashboard
2. Create automated daily reports
3. Integrate with Telegram/Discord for alerts
4. Optimize chart performance for large datasets
5. Add user-configurable chart templates

### **Long-term Vision (Next Month)**
1. Deploy web-based dashboard with authentication
2. Implement predictive analytics visualizations
3. Add multi-user collaboration features
4. Create mobile-responsive dashboards
5. Integrate with other data sources (Chainalysis, Dune Analytics, etc.)

## 🆘 TROUBLESHOOTING

### **Common Issues**

1. **"ModuleNotFoundError: No module named 'plotly'"**
   ```bash
   pip install plotly pandas matplotlib kaleido
   ```

2. **"tradingview-cli not found"**
   ```bash
   npm install -g tradingview-mcp-server
   ```

3. **Charts are empty or missing data**
   - Check TradingView MCP server is running
   - Verify API keys/credentials (if required)
   - Test with `tradingview-cli screen stocks --limit 5`

4. **HTML charts don't display in browser**
   - Open with `open chart.html` (macOS) or `xdg-open chart.html` (Linux)
   - Ensure JavaScript is enabled in browser
   - Check browser console for errors

5. **Performance issues with large datasets**
   - Reduce `--limit` parameter
   - Use `output_format='png'` for static images
   - Implement data sampling or aggregation

### **Getting Help**
- **TradingView MCP Docs**: `npm home tradingview-mcp-server`
- **Plotly Documentation**: https://plotly.com/python/
- **QWNT Issues**: Check GitHub repository
- **Community Support**: OpenClaw Discord

---

**Status**: VISUALIZATION SYSTEM READY FOR INTEGRATION
**Last Updated**: 2026-04-12 00:45 GMT+4
**Primary Contact**: OpenClaw Control UI

**Ready to proceed?** Run `python visualization/test_visualization.py` to generate your first charts!