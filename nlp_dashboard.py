from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

from flask import Flask, jsonify, render_template_string, request

from agents.actuary import Actuary
from agents.phantom_mcp_agent import PhantomMCPAgent
from agents.reaper import Reaper
from agents.unified_slinger import UnifiedSlinger
from agents.whisperer import Whisperer
from core.models import RiskAssessment, RiskLevel, TradeSignal
from pricing import get_token_info
from team_commands import TeamCommands
from v2_engine import AdvancedPaperTrader


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NLPDashboard")

app = Flask(__name__)
state_lock = threading.Lock()

trader = AdvancedPaperTrader()
team = TeamCommands(trader)

whisperer = Whisperer(min_velocity_score=30)
actuary = Actuary(max_allowed_tax=0.20)
unified_slinger = UnifiedSlinger()
reaper = Reaper(
    take_profit_pct=100.0,
    stop_loss_pct=-30.0,
    trailing_stop_pct=15.0,
    poll_interval_sec=10.0,
    paper_mode=True,
)
phantom = PhantomMCPAgent()
reaper.start_monitoring()


@dataclass
class AgentCard:
    id: str
    name: str
    role: str
    status: str
    summary: str
    last_action: str
    tone: str


agents: dict[str, AgentCard] = {
    "whisperer": AgentCard("whisperer", "Whisperer", "Signal discovery", "idle", "Scans DexScreener and surfaces momentum names.", "Waiting for scan instruction.", "fast, speculative, opportunistic"),
    "actuary": AgentCard("actuary", "Actuary", "Risk assessment", "idle", "Scores tokens for honeypots, taxes, and trade viability.", "Waiting for target.", "skeptical, defensive, conservative"),
    "slinger": AgentCard("slinger", "Unified Slinger", "Execution routing", "idle", "Routes approved trades to DEX or CEX paths.", "No order queued.", "decisive, execution-first"),
    "reaper": AgentCard("reaper", "Reaper", "Position defense", "active", "Tracks exits, free-rides, stops, and trailing behavior.", "Monitoring open positions.", "ruthless, disciplined"),
    "phantom": AgentCard("phantom", "PHANTOM", "MCP / CEX execution", "standby", "Handles MCP-style CEX execution and market lookups.", "Standing by for market intel or CEX routing.", "systematic, cross-venue"),
}

activity_log: list[dict[str, Any]] = []
chat_history: list[dict[str, str]] = []
watchlist: list[dict[str, Any]] = []
analysis_cache: dict[str, dict[str, Any]] = {}
last_signal: Optional[TradeSignal] = None
last_assessment: Optional[RiskAssessment] = None


def add_log(kind: str, message: str):
    activity_log.insert(0, {"time": time.strftime("%H:%M:%S"), "type": kind, "message": message})
    del activity_log[150:]


def set_agent(agent_id: str, status: str, action: str):
    if agent_id in agents:
        agents[agent_id].status = status
        agents[agent_id].last_action = action


def signal_to_dict(signal: TradeSignal) -> dict[str, Any]:
    return {
        "token_address": signal.token_address,
        "chain": signal.chain,
        "narrative_score": signal.narrative_score,
        "reasoning": signal.reasoning,
        "discovered_at": signal.discovered_at,
    }


def assessment_to_dict(assessment: RiskAssessment) -> dict[str, Any]:
    return {
        "token_address": assessment.token_address,
        "risk_level": assessment.risk_level.value,
        "is_honeypot": assessment.is_honeypot,
        "buy_tax": assessment.buy_tax,
        "sell_tax": assessment.sell_tax,
        "liquidity_locked": assessment.liquidity_locked,
        "max_allocation_usd": assessment.max_allocation_usd,
        "warnings": assessment.warnings,
    }


def build_watch_item(signal: TradeSignal, assessment: RiskAssessment | None = None) -> dict[str, Any]:
    token_info = get_token_info(signal.token_address) or {}
    return {
        "token_address": signal.token_address,
        "chain": signal.chain,
        "symbol": token_info.get("symbol", signal.token_address[:8]),
        "price": token_info.get("price"),
        "score": signal.narrative_score,
        "reasoning": signal.reasoning,
        "risk_level": assessment.risk_level.value if assessment else None,
        "max_allocation_usd": assessment.max_allocation_usd if assessment else None,
        "warnings": assessment.warnings if assessment else [],
        "discovered_at": signal.discovered_at,
    }


def find_address(text: str) -> Optional[str]:
    match = re.search(r"0x[a-fA-F0-9]{40}", text)
    return match.group(0) if match else None


def find_symbol(text: str) -> Optional[str]:
    for candidate in ["BTC", "ETH", "SOL", "BNB", "PEPE", "WETH", "WBTC"]:
        if candidate.lower() in text.lower():
            return candidate
    return None


def make_manual_signal(address: str, chain: str = "1") -> TradeSignal:
    return TradeSignal(
        token_address=address,
        chain=chain,
        narrative_score=55,
        reasoning="Manual dashboard target",
        discovered_at=time.time(),
    )


def run_whisperer_scan(top_n: int = 5) -> tuple[str, list[dict[str, Any]]]:
    global last_signal
    set_agent("whisperer", "active", f"Scanning top {top_n} signals")
    try:
        signals = whisperer.scan_top_n(top_n)
        items: list[dict[str, Any]] = []
        for signal in signals:
            if not last_signal:
                last_signal = signal
            items.append(build_watch_item(signal))
        if signals:
            last_signal = signals[0]
            add_log("scan", f"Whisperer found {len(signals)} signals")
            set_agent("whisperer", "idle", f"Found {len(signals)} signal(s)")
            return f"Whisperer found {len(signals)} signal(s). Top candidate score {signals[0].narrative_score}.", items
        add_log("scan", "Whisperer found no qualifying signals")
        set_agent("whisperer", "idle", "No qualifying signals found")
        return "Whisperer found no qualifying signals this pass.", []
    except Exception as e:
        logger.exception("Whisperer scan failed")
        set_agent("whisperer", "error", f"Scan failed: {e}")
        add_log("error", f"Whisperer failed: {e}")
        return f"Whisperer scan failed: {e}", []


def run_actuary_assess(signal: TradeSignal) -> tuple[str, Optional[dict[str, Any]]]:
    global last_assessment
    set_agent("actuary", "active", f"Assessing {signal.token_address[:10]}...")
    try:
        assessment = actuary.assess_risk(signal)
        last_assessment = assessment
        analysis_cache[signal.token_address.lower()] = {
            "signal": signal_to_dict(signal),
            "assessment": assessment_to_dict(assessment),
        }
        set_agent("actuary", "idle", f"{assessment.risk_level.value} on {signal.token_address[:10]}...")
        add_log("risk", f"Actuary rated {signal.token_address[:10]}... as {assessment.risk_level.value}")
        return (
            f"Actuary rated this {assessment.risk_level.value}. Max allocation ${assessment.max_allocation_usd:.2f}. "
            f"Buy tax {assessment.buy_tax*100:.1f}%, sell tax {assessment.sell_tax*100:.1f}%.",
            assessment_to_dict(assessment),
        )
    except Exception as e:
        logger.exception("Actuary assessment failed")
        set_agent("actuary", "error", f"Assessment failed: {e}")
        add_log("error", f"Actuary failed: {e}")
        return f"Actuary failed: {e}", None


def sync_reaper_position(order):
    if order:
        try:
            reaper.take_position(order)
        except Exception as e:
            add_log("error", f"Reaper could not take position: {e}")


def run_slinger_execute(assessment: RiskAssessment, chain_id: str = "1", symbol: str | None = None) -> tuple[str, Optional[dict[str, Any]]]:
    set_agent("slinger", "active", f"Executing {assessment.token_address[:10]}...")
    try:
        order = unified_slinger.execute_order(assessment, chain_id=chain_id, symbol=symbol)
        if not order:
            set_agent("slinger", "idle", "Execution rejected or unavailable")
            add_log("trade", "Unified Slinger did not place an order")
            return "Slinger stood down. Order was rejected or could not be generated.", None
        sync_reaper_position(order)
        set_agent("slinger", "idle", f"Queued BUY ${order.amount_usd:.2f}")
        add_log("trade", f"Unified Slinger created {order.action} order for ${order.amount_usd:.2f}")
        return (
            f"Slinger generated a {order.action} order for ${order.amount_usd:.2f} on chain {order.chain}. "
            f"Slippage {order.slippage_tolerance*100:.1f}%, gas {order.gas_premium_gwei:.1f} gwei.",
            {
                "token_address": order.token_address,
                "chain": order.chain,
                "action": order.action,
                "amount_usd": order.amount_usd,
                "slippage_tolerance": order.slippage_tolerance,
                "gas_premium_gwei": order.gas_premium_gwei,
                "entry_price_usd": order.entry_price_usd,
                "tx_hash": order.tx_hash,
            },
        )
    except Exception as e:
        logger.exception("Slinger execution failed")
        set_agent("slinger", "error", f"Execution failed: {e}")
        add_log("error", f"Slinger failed: {e}")
        return f"Slinger failed: {e}", None


def run_phantom_market(symbol: str = "BTC/USDT") -> tuple[str, Optional[dict[str, Any]]]:
    set_agent("phantom", "active", f"Fetching market data for {symbol}")
    try:
        result = phantom._call_mcp_server("ccxt", "fetch_ticker", {"symbol": symbol})
        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown MCP error"))
        ticker = result["data"]
        set_agent("phantom", "standby", f"Fetched {symbol} ticker")
        add_log("mcp", f"PHANTOM fetched market data for {symbol}")
        return (
            f"PHANTOM market read for {symbol}: last {ticker['last']:.4f}, bid {ticker['bid']:.4f}, ask {ticker['ask']:.4f}, volume {ticker['quoteVolume']:.0f}.",
            ticker,
        )
    except Exception as e:
        logger.exception("PHANTOM market fetch failed")
        set_agent("phantom", "error", f"Market fetch failed: {e}")
        add_log("error", f"PHANTOM failed: {e}")
        return f"PHANTOM failed: {e}", None


def positions_snapshot() -> list[dict[str, Any]]:
    rows = []
    for address, pos in trader.active_positions.items():
        info = get_token_info(address) or {}
        current_price = info.get("price", pos["entry_price"])
        current_value = pos["amount_tokens"] * current_price
        pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100 if pos["entry_price"] else 0
        rows.append({
            "token_address": address,
            "symbol": pos["symbol"],
            "entry_price": pos["entry_price"],
            "current_price": current_price,
            "invested_usd": pos["invested_usd"],
            "amount_tokens": pos["amount_tokens"],
            "current_value": current_value,
            "pnl_pct": pnl_pct,
            "principal_secured": pos.get("principal_secured", False),
        })
    return rows


def reaper_snapshot() -> list[dict[str, Any]]:
    rows = []
    for pos in reaper.positions.values():
        rows.append({
            "token_address": pos.token_address,
            "chain": pos.chain,
            "status": pos.status,
            "entry_value": pos.entry_value,
            "current_value": pos.current_value,
            "peak_value": pos.peak_value,
            "pnl_pct": pos.pnl_pct,
            "last_price_usd": pos.last_price_usd,
        })
    return rows


def current_system_summary() -> dict[str, Any]:
    return {
        "paper_balance": trader.paper_balance,
        "active_count": len(trader.active_positions),
        "graveyard_count": len(trader.graveyard),
        "config": dict(trader.config),
        "reaper": reaper.get_portfolio_summary(),
    }


def route_command(message: str) -> dict[str, Any]:
    global watchlist, last_signal, last_assessment
    text = message.strip()
    lowered = text.lower()

    if not text:
        return {"reply": "Say something and I’ll route it.", "agent": "system"}

    if lowered in {"panic", "nuke", "yolo", "stealth", "stats", "help"}:
        reply = team.execute(lowered)
        add_log("command", f"Team command executed: {lowered}")
        return {"reply": reply, "agent": "system"}

    address = find_address(text)

    if "scan" in lowered or "watchlist" in lowered or "momentum" in lowered or "whisperer" in lowered:
        top_n = 5
        num_match = re.search(r"top\s+(\d+)", lowered)
        if num_match:
            top_n = max(1, min(20, int(num_match.group(1))))
        reply, items = run_whisperer_scan(top_n=top_n)
        if items:
            watchlist = items
        return {"reply": reply, "agent": "whisperer", "watchlist": items}

    if "assess" in lowered or "risk" in lowered or "honeypot" in lowered or "tax" in lowered or "actuary" in lowered:
        signal = None
        if address:
            signal = make_manual_signal(address)
        elif last_signal:
            signal = last_signal
        elif watchlist:
            top = watchlist[0]
            signal = make_manual_signal(top["token_address"], top["chain"])
            signal.narrative_score = top["score"]
            signal.reasoning = top["reasoning"]
        if not signal:
            return {"reply": "Give me a token address or scan first so Actuary has something real to assess.", "agent": "actuary"}
        reply, assessment = run_actuary_assess(signal)
        if assessment and watchlist:
            for item in watchlist:
                if item["token_address"].lower() == signal.token_address.lower():
                    item.update({
                        "risk_level": assessment["risk_level"],
                        "max_allocation_usd": assessment["max_allocation_usd"],
                        "warnings": assessment["warnings"],
                    })
        return {"reply": reply, "agent": "actuary", "assessment": assessment}

    if any(word in lowered for word in ["buy", "execute", "route", "order", "slinger", "ape into"]):
        if address and lowered.startswith("ape into"):
            ok = trader.manual_ape(address)
            msg = f"Manual ape queued through the paper trader for {address}." if ok else f"Could not queue manual ape for {address}."
            add_log("trade", msg)
            return {"reply": msg, "agent": "slinger"}

        assessment = last_assessment
        if address and address.lower() in analysis_cache:
            cached = analysis_cache[address.lower()].get("assessment")
            if cached:
                assessment = RiskAssessment(
                    token_address=cached["token_address"],
                    is_honeypot=cached["is_honeypot"],
                    buy_tax=cached["buy_tax"],
                    sell_tax=cached["sell_tax"],
                    liquidity_locked=cached["liquidity_locked"],
                    risk_level=RiskLevel(cached["risk_level"]),
                    max_allocation_usd=cached["max_allocation_usd"],
                    warnings=cached["warnings"],
                )
        if not assessment:
            return {"reply": "I need an Actuary approval first. Scan or assess a token before telling Slinger to execute.", "agent": "slinger"}

        chain_id = "cex" if any(word in lowered for word in ["cex", "exchange", "binance", "phantom"]) else "1"
        symbol = None
        token_symbol = find_symbol(text)
        if chain_id == "cex" and token_symbol:
            symbol = f"{token_symbol}/USDT"
        reply, order = run_slinger_execute(assessment, chain_id=chain_id, symbol=symbol)
        return {"reply": reply, "agent": "slinger", "order": order}

    if any(word in lowered for word in ["phantom", "mcp", "cex", "ticker", "market"]):
        symbol = find_symbol(text) or "BTC"
        reply, ticker = run_phantom_market(f"{symbol}/USDT")
        return {"reply": reply, "agent": "phantom", "ticker": ticker}

    if any(word in lowered for word in ["reaper", "positions", "stop", "tp", "sl", "portfolio", "summary"]):
        summary = reaper.get_portfolio_summary()
        set_agent("reaper", "active", "Reported portfolio summary")
        add_log("reaper", f"Reported portfolio summary with {summary['total_positions']} tracked positions")
        return {
            "reply": (
                f"Reaper is tracking {summary['total_positions']} position(s). "
                f"Active {summary['active']}, free-ride {summary['free_ride']}, closed {summary['closed']}, total tracked value ${summary['total_value_usd']:.2f}."
            ),
            "agent": "reaper",
            "portfolio": summary,
        }

    return {
        "reply": "Be more direct. Try: 'scan top 5', 'assess 0x...', 'execute on cex', 'PHANTOM BTC ticker', 'positions', or 'stats'.",
        "agent": "system",
    }


HTML = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Asymmetric Strike Team, NLP Dashboard</title>
  <script src=\"https://cdn.tailwindcss.com\"></script>
  <style>
    body { background: #0a0f1c; }
    .panel { background: linear-gradient(180deg, rgba(17,24,39,.96), rgba(10,15,28,.98)); border: 1px solid rgba(71,85,105,.45); }
    .scroll { scrollbar-width: thin; }
    .glow { box-shadow: 0 0 0 1px rgba(59,130,246,.15), 0 0 30px rgba(37,99,235,.08); }
    table td, table th { vertical-align: top; }
  </style>
</head>
<body class=\"text-slate-100 min-h-screen\">
  <div class=\"max-w-7xl mx-auto p-6 space-y-6\">
    <header class=\"flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4\">
      <div>
        <p class=\"text-xs uppercase tracking-[0.35em] text-sky-400\">Asymmetric Strike Team</p>
        <h1 class=\"text-3xl font-semibold\">Real Agent NLP Dashboard</h1>
        <p class=\"text-slate-400 mt-2 max-w-3xl\">Talk to the actual agents, inspect live watchlists and positions, and drive the pipeline without bouncing between scripts.</p>
      </div>
      <div class=\"panel rounded-2xl px-4 py-3 glow\">
        <div class=\"text-xs text-slate-400\">Live paper balance</div>
        <div id=\"paper-balance\" class=\"text-2xl font-bold text-emerald-400\">$0.00</div>
      </div>
    </header>

    <section class=\"grid grid-cols-1 xl:grid-cols-3 gap-6\">
      <div class=\"xl:col-span-2 space-y-6\">
        <div class=\"panel rounded-2xl p-5 glow\">
          <h2 class=\"text-lg font-semibold\">Natural-language command bar</h2>
          <p class=\"text-sm text-slate-400 mt-1\">Examples: “scan top 5”, “assess 0x...”, “execute on cex”, “PHANTOM BTC ticker”, “positions”, “stats”.</p>
          <div class=\"flex gap-3 mt-4\">
            <input id=\"command-input\" class=\"flex-1 bg-slate-950/70 border border-slate-700 rounded-xl px-4 py-3 outline-none focus:border-sky-500\" placeholder=\"Type a command in plain English...\" />
            <button onclick=\"sendCommand()\" class=\"bg-sky-600 hover:bg-sky-500 rounded-xl px-5 py-3 font-semibold\">Send</button>
          </div>
          <div class=\"mt-3 flex flex-wrap gap-2 text-sm\">
            <button class=\"rounded-full px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-700\" onclick=\"quick('scan top 5')\">scan top 5</button>
            <button class=\"rounded-full px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-700\" onclick=\"quick('assess risk')\">assess</button>
            <button class=\"rounded-full px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-700\" onclick=\"quick('execute')\">execute</button>
            <button class=\"rounded-full px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-700\" onclick=\"quick('PHANTOM BTC ticker')\">btc ticker</button>
            <button class=\"rounded-full px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-700\" onclick=\"quick('positions')\">positions</button>
            <button class=\"rounded-full px-3 py-1 bg-rose-950 hover:bg-rose-900 border border-rose-700\" onclick=\"quick('panic')\">panic</button>
          </div>
        </div>

        <div class=\"grid grid-cols-1 2xl:grid-cols-2 gap-6\">
          <div class=\"panel rounded-2xl p-5 glow\">
            <div class=\"flex items-center justify-between mb-4\">
              <h2 class=\"text-lg font-semibold\">Conversation</h2>
              <span class=\"text-xs text-slate-400\">Routed replies</span>
            </div>
            <div id=\"chat-history\" class=\"space-y-3 max-h-[360px] overflow-y-auto scroll\"></div>
          </div>

          <div class=\"panel rounded-2xl p-5 glow\">
            <div class=\"flex items-center justify-between mb-4\">
              <h2 class=\"text-lg font-semibold\">Activity log</h2>
              <button onclick=\"refresh()\" class=\"text-sm text-sky-400 hover:text-sky-300\">Refresh</button>
            </div>
            <div id=\"activity-log\" class=\"space-y-2 max-h-[360px] overflow-y-auto scroll text-sm\"></div>
          </div>
        </div>

        <div class=\"panel rounded-2xl p-5 glow\">
          <div class=\"flex items-center justify-between mb-4\">
            <h2 class=\"text-lg font-semibold\">Watchlist</h2>
            <span class=\"text-xs text-slate-400\">Whisperer + Actuary output</span>
          </div>
          <div class=\"overflow-x-auto\">
            <table class=\"w-full text-sm\">
              <thead class=\"text-slate-400 border-b border-slate-800\">
                <tr>
                  <th class=\"text-left py-2\">Token</th>
                  <th class=\"text-left py-2\">Chain</th>
                  <th class=\"text-left py-2\">Price</th>
                  <th class=\"text-left py-2\">Score</th>
                  <th class=\"text-left py-2\">Risk</th>
                  <th class=\"text-left py-2\">Max Alloc</th>
                </tr>
              </thead>
              <tbody id=\"watchlist-body\"></tbody>
            </table>
          </div>
        </div>

        <div class=\"grid grid-cols-1 2xl:grid-cols-2 gap-6\">
          <div class=\"panel rounded-2xl p-5 glow\">
            <div class=\"flex items-center justify-between mb-4\">
              <h2 class=\"text-lg font-semibold\">Paper trader positions</h2>
              <span class=\"text-xs text-slate-400\">AdvancedPaperTrader state</span>
            </div>
            <div class=\"overflow-x-auto\">
              <table class=\"w-full text-sm\">
                <thead class=\"text-slate-400 border-b border-slate-800\">
                  <tr>
                    <th class=\"text-left py-2\">Token</th>
                    <th class=\"text-left py-2\">Entry</th>
                    <th class=\"text-left py-2\">Current</th>
                    <th class=\"text-left py-2\">PnL</th>
                  </tr>
                </thead>
                <tbody id=\"positions-body\"></tbody>
              </table>
            </div>
          </div>

          <div class=\"panel rounded-2xl p-5 glow\">
            <div class=\"flex items-center justify-between mb-4\">
              <h2 class=\"text-lg font-semibold\">Reaper book</h2>
              <span class=\"text-xs text-slate-400\">Tracked execution orders</span>
            </div>
            <div class=\"overflow-x-auto\">
              <table class=\"w-full text-sm\">
                <thead class=\"text-slate-400 border-b border-slate-800\">
                  <tr>
                    <th class=\"text-left py-2\">Token</th>
                    <th class=\"text-left py-2\">Status</th>
                    <th class=\"text-left py-2\">Value</th>
                    <th class=\"text-left py-2\">PnL</th>
                  </tr>
                </thead>
                <tbody id=\"reaper-body\"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div class=\"space-y-6\">
        <div class=\"panel rounded-2xl p-5 glow\">
          <h2 class=\"text-lg font-semibold mb-4\">Agent roster</h2>
          <div id=\"agent-cards\" class=\"space-y-3\"></div>
        </div>

        <div class=\"panel rounded-2xl p-5 glow\">
          <h2 class=\"text-lg font-semibold mb-4\">Engine controls</h2>
          <div class=\"space-y-4 text-sm\">
            <label class=\"block\">
              <div class=\"flex justify-between text-slate-400 mb-1\"><span>Trade size</span><span id=\"trade-size-val\"></span></div>
              <input id=\"trade-size\" type=\"range\" min=\"50\" max=\"1000\" step=\"50\" class=\"w-full\" />
            </label>
            <label class=\"block\">
              <div class=\"flex justify-between text-slate-400 mb-1\"><span>Take profit %</span><span id=\"tp-val\"></span></div>
              <input id=\"take-profit\" type=\"range\" min=\"20\" max=\"300\" step=\"5\" class=\"w-full\" />
            </label>
            <label class=\"block\">
              <div class=\"flex justify-between text-slate-400 mb-1\"><span>Stop loss %</span><span id=\"sl-val\"></span></div>
              <input id=\"stop-loss\" type=\"range\" min=\"-80\" max=\"-5\" step=\"5\" class=\"w-full\" />
            </label>
            <label class=\"block\">
              <div class=\"flex justify-between text-slate-400 mb-1\"><span>Trailing stop %</span><span id=\"trail-val\"></span></div>
              <input id=\"trailing-stop\" type=\"range\" min=\"3\" max=\"30\" step=\"1\" class=\"w-full\" />
            </label>
            <button onclick=\"saveConfig()\" class=\"w-full bg-emerald-600 hover:bg-emerald-500 rounded-xl py-3 font-semibold\">Save config</button>
          </div>
        </div>

        <div class=\"panel rounded-2xl p-5 glow\">
          <h2 class=\"text-lg font-semibold mb-4\">System snapshot</h2>
          <div id=\"snapshot\" class=\"text-sm text-slate-300 space-y-2\"></div>
        </div>
      </div>
    </section>
  </div>

<script>
async function api(path, options={}) {
  const res = await fetch(path, options);
  return await res.json();
}

function badge(status) {
  const colors = { idle:'bg-slate-700 text-slate-200', active:'bg-emerald-700 text-emerald-100', standby:'bg-amber-700 text-amber-100', error:'bg-rose-700 text-rose-100' };
  return colors[status] || colors.idle;
}

function renderChat(items) {
  const el = document.getElementById('chat-history');
  el.innerHTML = '';
  items.forEach(item => {
    const wrap = document.createElement('div');
    wrap.className = 'space-y-2';
    wrap.innerHTML = `
      <div class=\"bg-slate-950/60 border border-slate-800 rounded-xl p-3\"><div class=\"text-xs text-slate-500 mb-1\">You</div><div>${item.user}</div></div>
      <div class=\"bg-sky-950/30 border border-sky-900 rounded-xl p-3\"><div class=\"text-xs text-sky-400 mb-1\">${item.agent}</div><div>${item.reply}</div></div>
    `;
    el.appendChild(wrap);
  });
}

function renderAgents(items) {
  const el = document.getElementById('agent-cards');
  el.innerHTML = '';
  items.forEach(agent => {
    const card = document.createElement('div');
    card.className = 'bg-slate-950/50 border border-slate-800 rounded-xl p-4';
    card.innerHTML = `
      <div class=\"flex items-start justify-between gap-3\">
        <div><div class=\"font-semibold\">${agent.name}</div><div class=\"text-xs text-slate-400\">${agent.role}</div></div>
        <span class=\"text-xs px-2 py-1 rounded-full ${badge(agent.status)}\">${agent.status}</span>
      </div>
      <div class=\"text-sm text-slate-300 mt-3\">${agent.summary}</div>
      <div class=\"text-xs text-slate-500 mt-3\">Tone: ${agent.tone}</div>
      <div class=\"text-xs text-slate-400 mt-2\">Last action: ${agent.last_action}</div>
    `;
    el.appendChild(card);
  });
}

function renderLog(items) {
  const el = document.getElementById('activity-log');
  el.innerHTML = '';
  items.forEach(item => {
    const row = document.createElement('div');
    row.className = 'bg-slate-950/45 border border-slate-800 rounded-lg px-3 py-2';
    row.innerHTML = `<span class=\"text-slate-500 text-xs mr-2\">${item.time}</span><span class=\"text-sky-400 text-xs uppercase mr-2\">${item.type}</span>${item.message}`;
    el.appendChild(row);
  });
}

function renderWatchlist(items) {
  const body = document.getElementById('watchlist-body');
  body.innerHTML = '';
  items.forEach(item => {
    const tr = document.createElement('tr');
    tr.className = 'border-b border-slate-800';
    tr.innerHTML = `
      <td class=\"py-2\"><div class=\"font-semibold\">${item.symbol}</div><div class=\"text-xs text-slate-500\">${item.token_address.slice(0,12)}...</div></td>
      <td class=\"py-2\">${item.chain}</td>
      <td class=\"py-2\">${item.price ? '$' + Number(item.price).toFixed(8) : 'n/a'}</td>
      <td class=\"py-2\">${item.score}</td>
      <td class=\"py-2\">${item.risk_level || 'unassessed'}</td>
      <td class=\"py-2\">${item.max_allocation_usd ? '$' + Number(item.max_allocation_usd).toFixed(2) : 'n/a'}</td>
    `;
    body.appendChild(tr);
  });
}

function renderPositions(items, targetId) {
  const body = document.getElementById(targetId);
  body.innerHTML = '';
  items.forEach(item => {
    const tr = document.createElement('tr');
    tr.className = 'border-b border-slate-800';
    if (targetId === 'positions-body') {
      tr.innerHTML = `
        <td class=\"py-2\"><div class=\"font-semibold\">${item.symbol}</div><div class=\"text-xs text-slate-500\">${item.token_address.slice(0,12)}...</div></td>
        <td class=\"py-2\">$${Number(item.entry_price).toFixed(8)}</td>
        <td class=\"py-2\">$${Number(item.current_price).toFixed(8)}</td>
        <td class=\"py-2 ${item.pnl_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}\">${Number(item.pnl_pct).toFixed(2)}%</td>
      `;
    } else {
      tr.innerHTML = `
        <td class=\"py-2\"><div class=\"font-semibold\">${item.token_address.slice(0,12)}...</div><div class=\"text-xs text-slate-500\">${item.chain}</div></td>
        <td class=\"py-2\">${item.status}</td>
        <td class=\"py-2\">$${Number(item.current_value).toFixed(2)}</td>
        <td class=\"py-2 ${item.pnl_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}\">${Number(item.pnl_pct).toFixed(2)}%</td>
      `;
    }
    body.appendChild(tr);
  });
}

function renderSnapshot(state) {
  document.getElementById('paper-balance').innerText = `$${Number(state.paper_balance).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}`;
  document.getElementById('snapshot').innerHTML = `
    <div>Active positions: <span class=\"text-white font-semibold\">${state.active_count}</span></div>
    <div>Closed trades: <span class=\"text-white font-semibold\">${state.graveyard_count}</span></div>
    <div>Trade size: <span class=\"text-white font-semibold\">$${state.config.trade_size}</span></div>
    <div>TP / SL: <span class=\"text-white font-semibold\">${state.config.take_profit}% / ${state.config.stop_loss}%</span></div>
    <div>Trailing stop: <span class=\"text-white font-semibold\">${state.config.trailing_stop}%</span></div>
    <div>Reaper tracked value: <span class=\"text-white font-semibold\">$${Number(state.reaper.total_value_usd).toFixed(2)}</span></div>
  `;

  document.getElementById('trade-size').value = state.config.trade_size;
  document.getElementById('take-profit').value = state.config.take_profit;
  document.getElementById('stop-loss').value = state.config.stop_loss;
  document.getElementById('trailing-stop').value = state.config.trailing_stop;
  document.getElementById('trade-size-val').innerText = `$${state.config.trade_size}`;
  document.getElementById('tp-val').innerText = `${state.config.take_profit}%`;
  document.getElementById('sl-val').innerText = `${state.config.stop_loss}%`;
  document.getElementById('trail-val').innerText = `${state.config.trailing_stop}%`;
}

async function refresh() {
  const data = await api('/api/dashboard_state');
  renderChat(data.chat_history);
  renderAgents(data.agents);
  renderLog(data.activity_log);
  renderWatchlist(data.watchlist);
  renderPositions(data.positions, 'positions-body');
  renderPositions(data.reaper_positions, 'reaper-body');
  renderSnapshot(data.system);
}

async function sendCommand() {
  const input = document.getElementById('command-input');
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  await api('/api/nlp', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message}) });
  await refresh();
}

function quick(text) {
  document.getElementById('command-input').value = text;
  sendCommand();
}

async function saveConfig() {
  const payload = {
    trade_size: Number(document.getElementById('trade-size').value),
    take_profit: Number(document.getElementById('take-profit').value),
    stop_loss: Number(document.getElementById('stop-loss').value),
    trailing_stop: Number(document.getElementById('trailing-stop').value),
  };
  await api('/api/config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
  await refresh();
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('command-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendCommand();
  });

  ['trade-size','take-profit','stop-loss','trailing-stop'].forEach(id => {
    document.getElementById(id).addEventListener('input', () => {
      document.getElementById('trade-size-val').innerText = `$${document.getElementById('trade-size').value}`;
      document.getElementById('tp-val').innerText = `${document.getElementById('take-profit').value}%`;
      document.getElementById('sl-val').innerText = `${document.getElementById('stop-loss').value}%`;
      document.getElementById('trail-val').innerText = `${document.getElementById('trailing-stop').value}%`;
    });
  });

  refresh();
  setInterval(refresh, 7000);
});
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/dashboard_state")
def dashboard_state():
    return jsonify({
        "agents": [asdict(agent) for agent in agents.values()],
        "activity_log": activity_log,
        "chat_history": chat_history[-30:],
        "watchlist": watchlist,
        "positions": positions_snapshot(),
        "reaper_positions": reaper_snapshot(),
        "system": current_system_summary(),
    })


@app.route("/api/nlp", methods=["POST"])
def api_nlp():
    payload = request.get_json(force=True) or {}
    message = str(payload.get("message", "")).strip()
    result = route_command(message)
    chat_history.append({"user": message, "agent": result["agent"].upper(), "reply": result["reply"]})
    add_log("nlp", f"Routed command to {result['agent']}: {message}")
    return jsonify(result)


@app.route("/api/config", methods=["POST"])
def api_config():
    payload = request.get_json(force=True) or {}
    for key in ["trade_size", "take_profit", "stop_loss", "trailing_stop"]:
        if key in payload:
            trader.config[key] = float(payload[key])

    reaper.take_profit_pct = trader.config["take_profit"]
    reaper.stop_loss_pct = trader.config["stop_loss"]
    reaper.trailing_stop_pct = trader.config["trailing_stop"]

    add_log("config", f"Updated config: {json.dumps(trader.config)}")
    return jsonify({"ok": True, "config": trader.config})


if __name__ == "__main__":
    add_log("system", "Real-agent NLP dashboard initialized")
    app.run(host="127.0.0.1", port=5055, debug=True)
