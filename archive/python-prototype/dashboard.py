import threading
import time
import os
from flask import Flask, jsonify, render_template_string, request
from strategy_factory import StrategyFactory
import os
from dotenv import load_dotenv

# Import the PaperTrader
from paper_trader import PaperTrader

load_dotenv()
app = Flask(__name__)
trader = PaperTrader()
factory = StrategyFactory()
current_strategy = "degen" # Default
strategy_thread = None
is_running = False

# Real Execution Mode (toggle via env)
USE_REAL_EXECUTION = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
if USE_REAL_EXECUTION:
    from execution.real_slinger import RealSlingerAgent
    RPC_URL = os.getenv("ETH_RPC_URL")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    if not RPC_URL or not PRIVATE_KEY:
        print("⚠️  Real execution enabled but missing ETH_RPC_URL or PRIVATE_KEY in .env")
        USE_REAL_EXECUTION = False

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
            <h1 class="text-3xl font-bold text-red-500">Asymmetric Strike Team</h1>
            <div class="text-right">
                <p class="text-gray-400 text-sm">Status: <span id="status-badge" class="text-green-500 animate-pulse">● LIVE</span></p>
                <p class="text-2xl font-mono text-green-400" id="paper-balance">Loading...</p>
            </div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Active Positions Panel -->
            <div class="col-span-2 space-y-6">
                <!-- Strategy Selection -->
                <div class="bg-gray-800 rounded-lg p-6 shadow-lg border border-gray-700">
                    <h2 class="text-xl font-bold mb-4 flex items-center">
                        <span class="mr-2">🧠</span> Strategy Configuration
                    </h2>
                    <div class="flex gap-4">
                        <select id="strategy-select" class="bg-gray-700 border border-gray-600 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5">
                            <option value="degen">Degen Ape (High Risk / Speed)</option>
                            <option value="sniper">Safe Sniper (MEV Protected / Strict)</option>
                            <option value="shadow_clone">Shadow Clone (Copy Trade Smart Money)</option>
                            <option value="arb_hunter">Arb Hunter (DEX Arbitrage)</option>
                            <option value="oracle_eye">Oracle's Eye (Macro + Whale Tracking)</option>
                            <option value="liquidity_sentinel">Liquidity Sentinel (Market Structure)</option>
                            <option value="yield_alchemist">Yield Alchemist (DeFi Optimization)</option>
                            <option value="forensic_sniper">Forensic Sniper (Deep Due Diligence)</option>
                        </select>
                        <button onclick="changeStrategy()" class="bg-blue-600 hover:bg-blue-700 font-bold py-2 px-6 rounded transition whitespace-nowrap">
                            Deploy Team
                        </button>
                    </div>
                    <p id="current-strategy-info" class="mt-3 text-sm text-gray-400">Current Strategy: <span class="text-blue-400 font-bold" id="strategy-name">Degen Ape</span></p>
                </div>

                <!-- Table -->
                <div class="bg-gray-800 rounded-lg p-6 shadow-lg border border-gray-700">
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
                    <p class="text-sm text-gray-400 mb-4" id="strategy-desc">The Whisperer is continuously scanning social channels. The Slinger is operating with high gas limits.</p>
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-xs text-gray-500">Execution Mode:</span>
                        <span id="exec-mode" class="text-xs font-bold px-2 py-1 rounded bg-gray-700">PAPER</span>
                    </div>
                </div>
                <div class="space-y-4">
                    <button onclick="toggleEngine()" id="engine-btn" class="w-full bg-red-600 hover:bg-red-700 font-bold py-2 px-4 rounded transition">
                        Stop Engine
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
                
                // Update Strategy Info
                document.getElementById('strategy-name').innerText = data.strategy_name;
                document.getElementById('strategy-desc').innerText = data.strategy_desc;
                document.getElementById('strategy-select').value = data.strategy_id;
                
                // Engine Status
                const btn = document.getElementById('engine-btn');
                const badge = document.getElementById('status-badge');
                const execMode = document.getElementById('exec-mode');
                if (data.is_running) {
                    btn.innerText = "Stop Engine";
                    btn.className = "w-full bg-red-600 hover:bg-red-700 font-bold py-2 px-4 rounded transition";
                    badge.innerText = "● LIVE";
                    badge.className = "text-green-500 animate-pulse";
                } else {
                    btn.innerText = "Start Engine";
                    btn.className = "w-full bg-green-600 hover:bg-green-700 font-bold py-2 px-4 rounded transition";
                    badge.innerText = "○ PAUSED";
                    badge.className = "text-yellow-500";
                }
                execMode.innerText = data.execution_mode;
                execMode.className = data.execution_mode === "REAL" ? 
                    "text-xs font-bold px-2 py-1 rounded bg-red-900 text-red-300" : 
                    "text-xs font-bold px-2 py-1 rounded bg-gray-700";
                
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

        async function toggleEngine() {
            await fetch('/api/toggle', { method: 'POST' });
            fetchState();
        }
        
        async function changeStrategy() {
            const select = document.getElementById('strategy-select');
            const newStrategy = select.value;
            await fetch(`/api/strategy/${newStrategy}`, { method: 'POST' });
            alert(`Deploying ${newStrategy} team configuration!`);
            fetchState();
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
    profile = factory.get_profile(current_strategy)
    return jsonify({
        "paper_balance": trader.paper_balance,
        "active_positions": trader.active_positions,
        "strategy_id": current_strategy,
        "strategy_name": profile.name,
        "strategy_desc": profile.description,
        "is_running": is_running,
        "execution_mode": "REAL" if USE_REAL_EXECUTION else "PAPER"
    })

@app.route("/api/toggle", methods=["POST"])
def toggle_engine():
    global is_running
    is_running = not is_running
    return jsonify({"success": True, "is_running": is_running})

@app.route("/api/strategy/<name>", methods=["POST"])
def set_strategy(name):
    global current_strategy
    if name in factory.profiles:
        current_strategy = name
        # Log the change to the paper trading log so it shows in the terminal UI
        with open("paper_trading.log", "a") as f:
            f.write(f"\n[SYSTEM] Strategy changed to: {name.upper()}\n\n")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Strategy not found"}), 404

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

def run_strategy_loop():
    from strategy_runner import run_strategy
    global is_running, current_strategy, USE_REAL_EXECUTION
    
    # If real execution is enabled, we need to inject the RealSlinger into the runner
    if USE_REAL_EXECUTION:
        from execution.real_slinger import RealSlingerAgent
        from strategy_factory import StrategyFactory
        import os
        
        RPC_URL = os.getenv("ETH_RPC_URL")
        PRIVATE_KEY = os.getenv("PRIVATE_KEY")
        factory = StrategyFactory()
        
        def real_execution_override(strategy_name):
            """Custom runner that uses RealSlinger instead of mock."""
            from core.models import TradeSignal, RiskAssessment, ExecutionOrder, RiskLevel
            import logging
            import time
            
            logger = logging.getLogger("RealStrategyRunner")
            profile = factory.get_profile(strategy_name)
            logger.info(f"=== REAL EXECUTION: {profile.name} ===")
            
            # Initialize Real Slinger
            slinger = RealSlingerAgent(profile.slinger, RPC_URL, PRIVATE_KEY)
            
            # Mock the other agents for now (they would be real in production)
            logger.info("[Whisperer] Scanning... (mock)")
            signal = TradeSignal(
                token_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
                chain="ethereum",
                narrative_score=90,
                reasoning="Real execution test",
                discovered_at=time.time()
            )
            
            assessment = RiskAssessment(
                token_address=signal.token_address,
                is_honeypot=False,
                buy_tax=2.0,
                sell_tax=2.0,
                liquidity_locked=True,
                risk_level=RiskLevel.MEDIUM,
                max_allocation_usd=100.0,
                warnings=[]
            )
            
            order = ExecutionOrder(
                token_address=assessment.token_address,
                action="BUY",
                amount_usd=assessment.max_allocation_usd,
                slippage_tolerance=profile.slinger.base_slippage_tolerance,
                gas_premium_gwei=30.0
            )
            
            # REAL EXECUTION
            tx_hash = slinger.execute_order(order)
            logger.info(f"✅ Real transaction sent: {tx_hash}")
            
            # Log to paper_trading.log for dashboard display
            with open("paper_trading.log", "a") as f:
                f.write(f"\n[REAL] {profile.name}: Tx {tx_hash}\n")
            
            logger.info("=== CYCLE COMPLETE ===\n")
    
    while True:
        if is_running:
            try:
                if USE_REAL_EXECUTION:
                    real_execution_override(current_strategy)
                else:
                    run_strategy(current_strategy)
            except Exception as e:
                with open("paper_trading.log", "a") as f:
                    f.write(f"[ERROR] Strategy execution failed: {e}\n")
            time.sleep(3)
        else:
            time.sleep(1)

def start_background_trader():
    global is_running
    is_running = True
    # We replaced the paper_trader loop with our new strategy runner loop
    t = threading.Thread(target=run_strategy_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    print("Starting background trader thread...")
    start_background_trader()
    print("Starting Flask dashboard on http://127.0.0.1:5000")
    # Turn off reloader to prevent the background thread from running twice
    app.run(host="0.0.0.0", port=5002, debug=False, use_reloader=False)
