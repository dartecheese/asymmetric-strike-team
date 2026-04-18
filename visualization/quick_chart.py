#!/usr/bin/env python3
"""
Quick chart generation from TradingView MCP
Simple, robust chart generation that works now.
"""

import subprocess
import json
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import os
from datetime import datetime
import numpy as np

def get_tradingview_data(asset_type='stocks', preset='quality_stocks', limit=10):
    """Get data from TradingView MCP CLI"""
    cmd = ['tradingview-cli', 'screen', asset_type, '--format', 'json', 
           '--limit', str(limit)]
    if preset:
        cmd.extend(['--preset', preset])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return None
        
        data = json.loads(result.stdout)
        
        # Extract the list
        if asset_type == 'stocks' and 'stocks' in data:
            return data['stocks']
        elif asset_type == 'crypto' and 'cryptos' in data:
            return data['cryptos']
        elif asset_type == 'forex' and 'forex' in data:
            return data['forex']
        elif asset_type == 'etf' and 'etfs' in data:
            return data['etfs']
        else:
            # Try to find any list
            for key, value in data.items():
                if isinstance(value, list) and value:
                    return value
            return data
    except Exception as e:
        print(f"Failed to get data: {e}")
        return None

def create_stock_bar_chart(stock_data, output_file='stock_chart.png'):
    """Create simple bar chart of stock performance"""
    if not stock_data or not isinstance(stock_data, list):
        print("No valid stock data")
        return None
    
    # Extract names and changes
    names = []
    changes = []
    
    for item in stock_data[:15]:  # Limit to 15
        if isinstance(item, dict):
            name = item.get('symbol', item.get('name', 'Unknown'))
            change = item.get('change', 0)
            
            # Truncate long names
            if len(name) > 15:
                name = name[:12] + '...'
            
            names.append(name)
            changes.append(change)
    
    if not names:
        print("No data to plot")
        return None
    
    # Create figure
    plt.figure(figsize=(12, 6))
    
    # Color bars based on change
    colors = ['#2ecc71' if c >= 0 else '#e74c3c' for c in changes]
    
    bars = plt.bar(range(len(names)), changes, color=colors)
    
    # Add value labels on bars
    for i, (bar, change) in enumerate(zip(bars, changes)):
        height = bar.get_height()
        label_x = bar.get_x() + bar.get_width() / 2
        label_y = height + (0.01 * max(changes) if height >= 0 else -0.01 * min(changes))
        plt.text(label_x, label_y, f'{change:+.1f}%', 
                ha='center', va='bottom' if height >= 0 else 'top', fontsize=9)
    
    # Customize chart
    plt.title(f'Stock Performance - {datetime.now().strftime("%Y-%m-%d %H:%M")}', fontsize=14)
    plt.xlabel('Stocks', fontsize=12)
    plt.ylabel('Change (%)', fontsize=12)
    plt.xticks(range(len(names)), names, rotation=45, ha='right')
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # Save figure
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Chart saved to: {output_file}")
    return output_file

def create_crypto_heatmap(crypto_data, output_file='crypto_heatmap.png'):
    """Create heatmap of crypto performance"""
    if not crypto_data or not isinstance(crypto_data, list):
        print("No valid crypto data")
        return None
    
    # Extract data
    cryptos = []
    changes = []
    volumes = []
    
    for item in crypto_data[:10]:
        if isinstance(item, dict):
            name = item.get('symbol', item.get('name', 'Unknown'))
            change = item.get('change', 0)
            volume = item.get('volume', 0) or item.get('market_cap_basic', 0)
            
            cryptos.append(name)
            changes.append(change)
            volumes.append(volume)
    
    if not cryptos:
        return None
    
    # Normalize volumes for bubble sizes
    if max(volumes) > min(volumes):
        sizes = [(v - min(volumes)) / (max(volumes) - min(volumes)) * 1000 + 100 for v in volumes]
    else:
        sizes = [300] * len(volumes)
    
    # Create scatter plot
    plt.figure(figsize=(10, 6))
    
    scatter = plt.scatter(range(len(cryptos)), changes, s=sizes, 
                         c=changes, cmap='RdYlGn', alpha=0.6, edgecolors='black')
    
    # Add labels
    for i, (crypto, change, size) in enumerate(zip(cryptos, changes, sizes)):
        plt.text(i, change, crypto, ha='center', va='center' if change >= 0 else 'top', 
                fontsize=9, fontweight='bold')
    
    plt.colorbar(scatter, label='Change (%)')
    plt.title(f'Crypto Performance Heatmap - {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    plt.xlabel('Cryptocurrencies')
    plt.ylabel('Change (%)')
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Heatmap saved to: {output_file}")
    return output_file

def create_performance_dashboard(stock_data, crypto_data, output_file='dashboard.png'):
    """Create multi-panel dashboard"""
    if not stock_data and not crypto_data:
        print("No data for dashboard")
        return None
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Stock bar chart
    if stock_data:
        stock_names = []
        stock_changes = []
        for item in stock_data[:8]:
            if isinstance(item, dict):
                name = item.get('symbol', item.get('name', 'Unknown'))
                change = item.get('change', 0)
                stock_names.append(name[:10])
                stock_changes.append(change)
        
        colors = ['#2ecc71' if c >= 0 else '#e74c3c' for c in stock_changes]
        axes[0, 0].bar(stock_names, stock_changes, color=colors)
        axes[0, 0].set_title('Top Stock Performance')
        axes[0, 0].set_ylabel('Change (%)')
        axes[0, 0].tick_params(axis='x', rotation=45)
        axes[0, 0].axhline(y=0, color='black', linewidth=0.5)
    
    # 2. Crypto scatter
    if crypto_data:
        crypto_names = []
        crypto_changes = []
        for item in crypto_data[:8]:
            if isinstance(item, dict):
                name = item.get('symbol', item.get('name', 'Unknown'))
                change = item.get('change', 0)
                crypto_names.append(name[:10])
                crypto_changes.append(change)
        
        scatter = axes[0, 1].scatter(range(len(crypto_names)), crypto_changes, 
                                    s=200, c=crypto_changes, cmap='RdYlGn', alpha=0.7)
        axes[0, 1].set_title('Crypto Performance')
        axes[0, 1].set_ylabel('Change (%)')
        axes[0, 1].set_xticks(range(len(crypto_names)))
        axes[0, 1].set_xticklabels(crypto_names, rotation=45)
        plt.colorbar(scatter, ax=axes[0, 1])
    
    # 3. Summary statistics
    all_changes = []
    if stock_data:
        for item in stock_data:
            if isinstance(item, dict):
                all_changes.append(item.get('change', 0))
    if crypto_data:
        for item in crypto_data:
            if isinstance(item, dict):
                all_changes.append(item.get('change', 0))
    
    if all_changes:
        stats_text = [
            f"Total Assets: {len(all_changes)}",
            f"Average Change: {np.mean(all_changes):.2f}%",
            f"Positive: {sum(1 for c in all_changes if c >= 0)}",
            f"Negative: {sum(1 for c in all_changes if c < 0)}",
            f"Max Gain: {max(all_changes):.2f}%",
            f"Max Loss: {min(all_changes):.2f}%",
        ]
        
        axes[1, 0].text(0.1, 0.9, '\n'.join(stats_text), fontsize=12,
                       verticalalignment='top', transform=axes[1, 0].transAxes)
        axes[1, 0].set_title('Performance Summary')
        axes[1, 0].axis('off')
    
    # 4. Distribution histogram
    if all_changes:
        axes[1, 1].hist(all_changes, bins=15, color='#3498db', edgecolor='black', alpha=0.7)
        axes[1, 1].axvline(x=0, color='red', linestyle='--', linewidth=1)
        axes[1, 1].set_title('Change Distribution')
        axes[1, 1].set_xlabel('Change (%)')
        axes[1, 1].set_ylabel('Frequency')
        axes[1, 1].grid(True, alpha=0.3)
    
    plt.suptitle(f'TradingView MCP Dashboard - {datetime.now().strftime("%Y-%m-%d %H:%M")}', 
                fontsize=16, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Dashboard saved to: {output_file}")
    return output_file

def main():
    """Generate sample charts"""
    print("📊 Generating TradingView MCP Charts...")
    
    # Create output directory
    os.makedirs('visualization/quick_charts', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get data
    print("Fetching stock data...")
    stock_data = get_tradingview_data('stocks', 'quality_stocks', 15)
    
    print("Fetching crypto data...")
    crypto_data = get_tradingview_data('crypto', None, 10)
    
    # Generate charts
    charts = []
    
    if stock_data:
        stock_chart = create_stock_bar_chart(
            stock_data, 
            f'visualization/quick_charts/stocks_{timestamp}.png'
        )
        if stock_chart:
            charts.append(('Stock Performance', stock_chart))
    
    if crypto_data:
        try:
            crypto_chart = create_crypto_heatmap(
                crypto_data,
                f'visualization/quick_charts/crypto_{timestamp}.png'
            )
            if crypto_chart:
                charts.append(('Crypto Heatmap', crypto_chart))
        except Exception as e:
            print(f"Skipping crypto chart due to error: {e}")
    
    if stock_data or crypto_data:
        dashboard = create_performance_dashboard(
            stock_data, crypto_data,
            f'visualization/quick_charts/dashboard_{timestamp}.png'
        )
        if dashboard:
            charts.append(('Dashboard', dashboard))
    
    # Print results
    print("\n" + "="*60)
    print("✅ CHARTS GENERATED SUCCESSFULLY")
    print("="*60)
    
    for title, path in charts:
        print(f"{title}: {os.path.abspath(path)}")
    
    # Create HTML viewer
    html_path = f'visualization/quick_charts/viewer_{timestamp}.html'
    with open(html_path, 'w') as f:
        f.write(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TradingView Charts - {timestamp}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .chart {{ margin: 20px 0; text-align: center; }}
                img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>TradingView MCP Charts</h1>
                <p>Generated: {datetime.now().isoformat()}</p>
            </div>
        """)
        
        for title, path in charts:
            f.write(f"""
            <div class="chart">
                <h2>{title}</h2>
                <img src="{os.path.basename(path)}" alt="{title}">
            </div>
            """)
        
        f.write("</body></html>")
    
    print(f"\n📁 HTML Viewer: {os.path.abspath(html_path)}")
    print(f"📁 Open in browser: file://{os.path.abspath(html_path)}")

if __name__ == "__main__":
    main()