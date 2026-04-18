import threading
import time
import os
import json
from flask import Flask, jsonify, render_template_string, request

from v2_engine import AdvancedPaperTrader
from team_commands import TeamCommands

app = Flask(__name__)
trader = AdvancedPaperTrader()
team = TeamCommands(trader)
chat_history = []

def clean_symbol(symbol):
    if not symbol: return "TOKEN"
    cleaned = ''.join(char for char in symbol if not ('\u4e00' <= char <= '\u9fff'))
    return cleaned.strip() or "TOKEN"

def process_chat_message(message):
    message_lower = message.lower()
    
    # First check for team commands
    response = team.execute(message)
    if not response.startswith("❌"):
        return response
    
    # Then check for agent-specific queries
    if "whisperer" in message_lower:
        return "🗣️ Whisperer: Scanning live feeds. Stand by."
    elif "reaper" in message_lower:
        return f"💀 Reaper: Monitoring {len(trader.active_positions)} positions."
    elif "balance" in message_lower:
        return f"💰 System: Paper balance: ${trader.paper_balance:,.2f}."
    else:
        return f"🤖 System: I heard '{message}'. Try a team command (panic, nuke, yolo, stealth, stats, help) or mention an agent."

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Asymmetric Strike Team V2 - Institutional Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .log-container { font-family: 'Courier New', monospace; background: #1e1e1e; color: #00ff00; }
        .chat-container { max-height: 250px; overflow-y: auto; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .modal { display: none; position: fixed; z-index: 50; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.8); }
        .modal-content { background-color: #111827; margin: 5% auto; padding: 20px; border: 1px solid #374151; width: 80%; height: 80%; border-radius: 8px;}
        iframe { width: 100%; height: 90%; border: none; }
        .command-btn { transition: all 0.2s; }
        .command-btn:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(255,255,255,0.2); }
    </style>
</head>
<body class="bg-gray-900 text-white p-6 font-sans text-sm">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center mb-6 border-b border-gray-700 pb-4">
            <h1 class="text-2xl font-bold text-red-500">Asymmetric Strike Team <span class="text-xs text-gray-500 ml-2">V2 ENGINE</span></h1>
            <div class="flex items-center space-x-6">
                <!-- Ape Input -->
                <div class="flex space-x-2">
                    <input type="text" id="ape-input" placeholder="0x..." class="bg-gray-800 border border-gray-700 rounded px-3 py-1 text-white text-xs w-48">
                    <button onclick="manualApe()" class="bg-purple-600 hover:bg-purple-700 text-xs font-bold py-1 px-3 rounded shadow-[0_0_10px_rgba(147,51,234,0.5)]">🦍 APE IN</button>
                </div>
                <div class="text-right">
                    <p class="text-gray-400 text-xs">Status: <span class="text-green-500 animate-pulse font-bold">● LIVE</span></p>
                    <p class="text-xl font-mono text-green-400 font-bold" id="paper-balance">Loading...</p>
                </div>
            </div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
            
            <!-- Left Column: Config & Team Commands -->
            <div class="space-y-6">
                <!-- Config Panel -->
                <div class="bg-gray-800 rounded-lg p-4 shadow-lg border border-gray-700">
                    <h2 class="font-bold mb-4 text-blue-400">⚙️ Live Configuration</h2>
                    <div class="space-y-4 text-xs">
                        <div>
                            <label class="text-gray-400 flex justify-between">Trade Size ($)<span id="val-size">250</span></label>
                            <input type="range" id="conf-size" min="50" max="1000" step="50" class="w-full" oninput="document.getElementById('val-size').innerText=this.value">
                        </div>
                        <div>
                            <label class="text-gray-400 flex justify-between">Take Profit (%)<span id="val-tp">100</span></label>
                            <input type="range" id="conf-tp" min="50" max="500" step="10" class="w-full" oninput="document.getElementById('val-tp').innerText=this.value">
                        </div>
                        <div>
                            <label class="text-gray-400 flex justify-between">Stop Loss (%)<span id="val-sl">-30</span></label>
                            <input type="range" id="conf-sl" min="-80" max="-5" step="5" class="w-full" oninput="document.getElementById('val-sl').innerText=this.value">
                        </div>
                        <div>
                            <label class="text-gray-400 flex justify-between">Trailing Stop (%)<span id="val-ts">15</span></label>
                            <input type="range" id="conf-ts" min="5" max="30" step="1" class="w-full" oninput="document.getElementById('val-ts').innerText=this.value">
                        </div>
                        <button onclick="updateConfig()" class="w-full bg-blue-600 hover:bg-blue-700 py-2 rounded mt-2 font-bold">Update Engine</button>
                    </div>
                </div>

                <!-- Team Commands Panel -->
                <div class="bg-gray-800 rounded-lg p-4 shadow-lg border border-gray-700">
                    <h2 class="font-bold mb-4 text-yellow-400">🎮 Team Commands</h2>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <button onclick="sendCommand('panic')" class="command-btn bg-red-700 hover:bg-red-800 py-2 rounded font-bold">🚨 PANIC</button>
                        <button onclick="sendCommand('nuke')" class="command-btn bg-red-900 hover:bg-red-950 py-2 rounded font-bold">💣 NUKE</button>
                        <button onclick="sendCommand('yolo')" class="command-btn bg-green-700 hover:bg-green-800 py-2 rounded font-bold">🤑 YOLO</button>
                        <button onclick="sendCommand('stealth')" class="command-btn bg-gray-700 hover:bg-gray-800 py-2 rounded font-bold">🕵️ STEALTH</button>
                        <button onclick="sendCommand('stats')" class="command-btn bg-blue-700 hover:bg-blue-800 py-2 rounded font-bold col-span-2">📊 STATS</button>
                    </div>
                    <p class="text-gray-400 text-xs mt-3">One-click tactical overrides. Use with caution.</p>
                </div>
            </div>

            <!-- Main Column: Positions & Graveyard -->
            <div class="col-span-3 bg-gray-800 rounded-lg shadow-lg border border-gray-700 overflow-hidden flex flex-col">
                <div class="flex border-b border-gray-700 bg-gray-900">
                    <button onclick="switchTab('positions')" id="tab-btn-positions" class="px-6 py-3 font-bold text-blue-400 border-b-2 border-blue-500">🎯 Active Watchlist</button>
                    <button onclick="switchTab('graveyard')" id="tab-btn-graveyard" class="px-6 py-3 font-bold text-gray-500 hover:text-white">🪦 The Graveyard</button>
                </div>
                
                <div class="p-0 flex-grow overflow-x-auto relative">
                    <!-- Positions Tab -->
                    <div id="tab-positions" class="tab-content active h-[300px] overflow-y-auto">
                        <table class="w-full text-left border-collapse text-xs">
                            <thead class="sticky top-0 bg-gray-800 border-b border-gray-700 text-gray-400">
                                <tr>
                                    <th class="py-2 pl-4">Token (Click for Chart)</th>
                                    <th class="py-2">PnL</th>
                                    <th class="py-2">Amount</th>
                                    <th class="py-2">Entry</th>
                                    <th class="py-2 text-right pr-4">Action</th>
                                </tr>
                            </thead>
                            <tbody id="positions-body"></tbody>
                        </table>
                    </div>
                    
                    <!-- Graveyard Tab -->
                    <div id="tab-graveyard" class="tab-content h-[300px] overflow-y-auto">
                        <table class="w-full text-left border-collapse text-xs">
                            <thead class="sticky top-0 bg-gray-800 border-b border-gray-700 text-gray-400">
                                <tr>
                                    <th class="py-2 pl-4">Time</th>
                                    <th class="py-2">Token</th>
                                    <th class="py-2">Reason</th>
                                    <th class="py-2">Invested</th>
                                    <th class="py-2">Returned</th>
                                    <th class="py-2 text-right pr-4">PnL %</th>
                                </tr>
                            </thead>
                            <tbody id="graveyard-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <!-- Chat -->
            <div class="bg-gray-800 rounded-lg shadow-lg border border-gray-700 flex flex-col h-64">
                <div class="bg-gray-900 px-4 py-2 border-b border-gray-700 text-xs font-bold">Team Comm Link</div>
                <div id="chat-messages" class="chat-container flex-grow p-3 space-y-2"></div>
                <div class="p-2 border-t border-gray-700 flex">
                    <input type="text" id="chat-input" class="flex-grow bg-gray-700 rounded px-2 py-1 text-xs" placeholder="Type a command or talk to the team...">
                    <button onclick="sendChat()" class="ml-2 bg-blue-600 px-3 py-1 rounded text-xs font-bold">Send</button>
                </div>
            </div>
            
            <!-- Terminal -->
            <div class="bg-black rounded-lg shadow-lg border border-gray-700 flex flex-col h-64">
                <div class="bg-gray-800 px-4 py-2 border-b border-gray-700 text-xs font-bold text-gray-400 flex justify-between">
                    <span>Terminal output</span>
                    <span class="text-green-500">v2_engine.py</span>
                </div>
                <div id="logs" class="log-container flex-grow overflow-y-auto p-3 text-xs whitespace-pre"></div>
            </div>
        </div>
    </div>

    <!-- Chart Modal -->
    <div id="chartModal" class="modal">
        <div class="modal-content relative">
            <span onclick="document.getElementById('chartModal').style.display='none'" class="absolute top-2 right-4 text-gray-400 text-2xl hover:text-white cursor-pointer">&times;</span>
            <h2 id="chartTitle" class="text-xl font-bold mb-4">Chart</h2>
            <iframe id="chartFrame" src=""></iframe>
        </div>
    </div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            
            document.querySelectorAll('button[id^="tab-btn-"]').forEach(btn => {
                btn.classList.remove('text-blue-400', 'border-b-2', 'border-blue-500');
                btn.classList.add('text-gray-500');
            });
            const activeBtn = document.getElementById('tab-btn-' + tabId);
            activeBtn.classList.remove('text-gray-500');
            activeBtn.classList.add('text-blue-400', 'border-b-2', 'border-blue-500');
        }

        function openChart(address, symbol) {
            document.getElementById('chartTitle').innerText = symbol + " - TradingView";
            document.getElementById('chartFrame').src = `https://dexscreener.com/ethereum/${address}?embed=1&theme=dark&info=0`;
            document.getElementById('chartModal').style.display = "block";
        }

        async function fetchState() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                
                document.getElementById('paper-balance').innerText = `$${data.paper_balance.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                
                // Update Config if untouched
                if(!document.getElementById('conf-size').dataset.touched) {
                    document.getElementById('conf-size').value = data.config.trade_size;
                    document.getElementById('val-size').innerText = data.config.trade_size;
                    document.getElementById('conf-tp').value = data.config.take_profit;
                    document.getElementById('val-tp').innerText = data.config.take_profit;
                    document.getElementById('conf-sl').value = data.config.stop_loss;
                    document.getElementById('val-sl').innerText = data.config.stop_loss;
                    document.getElementById('conf-ts').value = data.config.trailing_stop;
                    document.getElementById('val-ts').innerText = data.config.trailing_stop;
                    document.getElementById('conf-size').dataset.touched = 'true';
                }

                // Positions
                const tbody = document.getElementById('positions-body');
                tbody.innerHTML = '';
                for (const [address, pos] of Object.entries(data.active_positions)) {
                    let cleanSym = pos.symbol.replace(/[\\u4e00-\\u9fff]/g, '').trim() || 'TOKEN';
                    const tr = document.createElement('tr');
                    tr.className = "border-b border-gray-700/50 hover:bg-gray-700/30";
                    tr.innerHTML = `
                        <td class="py-2 pl-4 font-bold text-blue-400 cursor-pointer" onclick="openChart('${address}', '${cleanSym}')">📈 ${cleanSym}</td>
                        <td class="py-2 font-mono text-yellow-400">Tracking...</td>
                        <td class="py-2 font-mono text-gray-400">${pos.amount_tokens.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                        <td class="py-2 font-mono text-gray-400">$${pos.entry_price.toLocaleString()}</td>
                        <td class="py-2 text-right pr-4">
                            <button onclick="forceSell('${address}')" class="bg-red-500 hover:bg-red-600 text-white px-2 py-1 rounded">DUMP</button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                }
                
                // Graveyard
                const gbody = document.getElementById('graveyard-body');
                gbody.innerHTML = '';
                data.graveyard.forEach(trade => {
                    let cleanSym = trade.symbol.replace(/[\\u4e00-\\u9fff]/g, '').trim() || 'TOKEN';
                    const isProfit = trade.pnl_pct >= 0;
                    const pnlColor = isProfit ? 'text-green-500' : 'text-red-500';
                    const tr = document.createElement('tr');
                    tr.className = "border-b border-gray-700/50 hover:bg-gray-700/30 text-gray-300";
                    tr.innerHTML = `
                        <td class="py-2 pl-4">${trade.time}</td>
                        <td class="py-2 font-bold cursor-pointer hover:text-white" onclick="openChart('${trade.address}', '${cleanSym}')">${cleanSym}</td>
                        <td class="py-2 text-[10px] uppercase">${trade.reason}</td>
                        <td class="py-2 font-mono text-gray-400">$${trade.invested.toLocaleString(undefined,{maximumFractionDigits:2})}</td>
                        <td class="py-2 font-mono ${pnlColor}">$${trade.returned.toLocaleString(undefined,{maximumFractionDigits:2})}</td>
                        <td class="py-2 font-mono ${pnlColor} font-bold text-right pr-4">${trade.pnl_pct > 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%</td>
                    `;
                    gbody.appendChild(tr);
                });

            } catch (err) {}
        }

        async function updateConfig() {
            const cfg = {
                trade_size: parseFloat(document.getElementById('conf-size').value),
                take_profit: parseFloat(document.getElementById('conf-tp').value),
                stop_loss: parseFloat(document.getElementById('conf-sl').value),
                trailing_stop: parseFloat(document.getElementById('conf-ts').value)
            };
            await fetch('/api/config', {
                method: 'POST', 
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(cfg)
            });
            });
"""