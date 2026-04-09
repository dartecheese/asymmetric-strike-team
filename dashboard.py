import threading
import time
import os
from flask import Flask, jsonify, render_template_string, request

# Import the PaperTrader
from paper_trader import PaperTrader

app = Flask(__name__)
trader = PaperTrader()

# HTML Template with Tailwind CSS
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Asymmetric Strike Team - Paper Trading Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .log-container {
            font-family: 'Courier New', Courier, monospace;
            background: #1e1e1e;
            color: #00ff00;
        }
    </style>
</head>
<body class="bg-gray-900 text-white p-8 font-sans">
    <div class="max-w-6xl mx-auto">
        <header class="flex justify-between items-center mb-8 border-b border-gray-700 pb-4">
            <h1 class="text-3xl font-bold text-red-500">Asymmetric Strike Team Dashboard</h1>
            <div class="text-right">
                <p class="text-gray-400 text-sm">Status: <span class="text-green-500 animate-pulse">● LIVE (MOCK)</span></p>
                <p class="text-2xl font-mono text-green-400" id="paper-balance">Loading...</p>
            </div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Active Positions Panel -->
            <div class="col-span-2 bg-gray-800 rounded-lg p-6 shadow-lg border border-gray-700">
                <h2 class="text-xl font-bold mb-4 flex items-center">
                    <span class="mr-2">🔫</span> Active Positions (Reaper Watchlist)
                </h2>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="border-b border-gray-700 text-gray-400">
                                <th class="py-2">Token</th>
                                <th class="py-2">Amount</th>
                                <th class="py-2">Entry Price</th>
                                <th class="py-2">Invested</th>
                                <th class="py-2 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody id="positions-body">
                            <!-- Populated by JS -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Global Controls -->
            <div class="bg-gray-800 rounded-lg p-6 shadow-lg border border-gray-700 flex flex-col justify-between">
                <div>
                    <h2 class="text-xl font-bold mb-4">Command & Control</h2>
                    <p class="text-sm text-gray-400 mb-4">The Whisperer is continuously scanning DexScreener's Latest feed for newly marketed tokens on EVM chains. The Actuary will automatically reject honeypots.</p>
                </div>
                <div class="space-y-4">
                    <button onclick="alert('Currently strictly enforcing Paper Trading rules.')" class="w-full bg-blue-600 hover:bg-blue-700 font-bold py-2 px-4 rounded transition">
                        Toggle Live Trading (Disabled)
                    </button>
                    <button onclick="fetch('/api/shutdown', {method: 'POST'}); alert('Initiating graceful shutdown...')" class="w-full bg-red-600 hover:bg-red-700 font-bold py-2 px-4 rounded transition">
                        Kill All Systems
                    </button>
                </div>
            </div>
        </div>

        <!-- Live Terminal -->
        <div class="mt-8 bg-black rounded-lg shadow-lg border border-gray-700 overflow-hidden">
            <div class="bg-gray-800 px-4 py-2 border-b border-gray-700 flex justify-between items-center">
                <span class="font-bold text-sm">Terminal Logs</span>
                <span class="text-xs text-gray-500">paper_trading.log</span>
            </div>
            <div id="logs" class="log-container h-64 overflow-y-auto p-4 text-sm whitespace-pre">
                Loading logs...
            </div>
        </div>
    </div>

    <script>
        async function fetchState() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                
                // Update Balance
                document.getElementById('paper-balance').innerText = `$${data.paper_balance.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                
                // Update Positions
                const tbody = document.getElementById('positions-body');
                tbody.innerHTML = '';
                
                for (const [address, pos] of Object.entries(data.active_positions)) {
                    const tr = document.createElement('tr');
                    tr.className = "border-b border-gray-700/50 hover:bg-gray-700/30 transition";
                    tr.innerHTML = `
                        <td class="py-3 font-bold text-blue-400">
                            <a href="https://dexscreener.com/ethereum/${address}" target="_blank" class="hover:underline">${pos.symbol}</a>
                        </td>
                        <td class="py-3 font-mono text-sm">${pos.amount_tokens.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                        <td class="py-3 font-mono text-sm">$${pos.entry_price.toLocaleString()}</td>
                        <td class="py-3 font-mono text-sm text-green-400">$${pos.invested_usd.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                        <td class="py-3 text-right">
                            <button onclick="forceSell('${address}')" class="bg-red-500 hover:bg-red-600 text-white text-xs font-bold py-1 px-3 rounded">
                                FORCE SELL
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                }
                
                if (Object.keys(data.active_positions).length === 0) {
                    tbody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-gray-500">No active positions. Whisperer is scanning...</td></tr>`;
                }

            } catch (err) {
                console.error("Failed to fetch state:", err);
            }
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                const text = await res.text();
                const logContainer = document.getElementById('logs');
                const isScrolledToBottom = logContainer.scrollHeight - logContainer.clientHeight <= logContainer.scrollTop + 10;
                
                logContainer.innerText = text;
                
                if (isScrolledToBottom) {
                    logContainer.scrollTop = logContainer.scrollHeight;
                }
            } catch (err) {
                console.error("Failed to fetch logs:", err);
            }
        }

        async function forceSell(address) {
            if(confirm("Are you sure you want to force dump this token at current market value?")) {
                await fetch(`/api/sell/${address}`, { method: 'POST' });
                fetchState(); // instant refresh
            }
        }

        // Poll every 2 seconds
        setInterval(fetchState, 2000);
        setInterval(fetchLogs, 2000);
        
        // Initial fetch
        fetchState();
        fetchLogs();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/state")
def get_state():
    return jsonify({
        "paper_balance": trader.paper_balance,
        "active_positions": trader.active_positions
    })

@app.route("/api/logs")
def get_logs():
    try:
        # Get the last 50 lines of the log file
        with open("paper_trading.log", "r") as f:
            lines = f.readlines()
            return "".join(lines[-50:])
    except FileNotFoundError:
        return "Log file not found."

@app.route("/api/sell/<address>", methods=["POST"])
def force_sell(address):
    success = trader.force_sell(address)
    return jsonify({"success": success})

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    trader.is_running = False
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        os._exit(0)
    func()
    return "Shutting down..."

def start_background_trader():
    # Start the trader loop in a background thread
    t = threading.Thread(target=trader.loop, daemon=True)
    t.start()

if __name__ == "__main__":
    print("Starting background trader thread...")
    start_background_trader()
    print("Starting Flask dashboard on http://127.0.0.1:5000")
    # Turn off reloader to prevent the background thread from running twice
    app.run(host="0.0.0.0", port=5002, debug=False, use_reloader=False)
