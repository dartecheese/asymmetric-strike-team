from __future__ import annotations

import json
import logging
import re
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
from strategy_factory import StrategyFactory
from team_commands import TeamCommands
from v2_engine import AdvancedPaperTrader


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NLPDashboard")

app = Flask(__name__)

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
strategy_factory = StrategyFactory()
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
selected_strategy: str = "degen"
selected_mode: str = "traditional"
last_error: Optional[str] = None
conversation_state: dict[str, Any] = {
    "user_profile": {
        "risk": "balanced",
        "speed": "balanced",
        "venue": "dex",
        "goal": "opportunistic upside",
        "needs_guidance": True,
    },
    "last_recommendation": None,
}

STRATEGY_PERSONAS = {
    "degen": {"risk": "high", "speed": "fast", "venue": "dex", "style": "aggressive momentum chasing with loose filters"},
    "sniper": {"risk": "low", "speed": "measured", "venue": "dex", "style": "defensive entries with stricter contract and liquidity requirements"},
    "shadow_clone": {"risk": "medium", "speed": "fast", "venue": "dex", "style": "copy-trading smart money instead of relying on narrative"},
    "arb_hunter": {"risk": "low", "speed": "fast", "venue": "dex", "style": "spread capture and routing efficiency"},
    "oracle_eye": {"risk": "medium", "speed": "measured", "venue": "hybrid", "style": "macro plus whale-tracking for earlier positioning"},
    "liquidity_sentinel": {"risk": "low", "speed": "measured", "venue": "hybrid", "style": "liquidity-aware entries with market structure discipline"},
    "yield_alchemist": {"risk": "low", "speed": "slow", "venue": "dex", "style": "yield and capital rotation over degen speculation"},
    "forensic_sniper": {"risk": "very low", "speed": "slow", "venue": "dex", "style": "deep due diligence before acting"},
}


def add_log(kind: str, message: str):
    activity_log.insert(0, {"time": time.strftime("%H:%M:%S"), "type": kind, "message": message})
    del activity_log[150:]


def set_error(message: Optional[str]):
    global last_error
    last_error = message
    if message:
        add_log("error", message)


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
        "chart_url": f"https://dexscreener.com/ethereum/{signal.token_address}?embed=1&theme=dark&info=0",
    }


def apply_strategy(name: str) -> dict[str, Any]:
    global selected_strategy, whisperer
    profile = strategy_factory.get_profile(name)
    selected_strategy = name
    whisperer_cfg = profile.whisperer
    min_velocity = whisperer_cfg.min_velocity_score if whisperer_cfg else 30
    whisperer = Whisperer(min_velocity_score=min_velocity)
    reaper.take_profit_pct = profile.reaper.take_profit_pct
    reaper.stop_loss_pct = profile.reaper.stop_loss_pct
    reaper.trailing_stop_pct = profile.reaper.trailing_stop_pct
    trader.config["take_profit"] = profile.reaper.take_profit_pct
    trader.config["stop_loss"] = profile.reaper.stop_loss_pct
    trader.config["trailing_stop"] = profile.reaper.trailing_stop_pct
    trader.config["trade_size"] = max(25.0, profile.actuary.max_tax_allowed * 5)
    unified_slinger.set_strategy_params(
        slippage=profile.slinger.base_slippage_tolerance,
        gas_multiplier=profile.slinger.gas_premium_multiplier,
        private_mempool=profile.slinger.use_private_mempool,
    )
    set_agent("whisperer", "idle", f"Configured for strategy {name}")
    set_agent("actuary", "idle", f"Max tax {profile.actuary.max_tax_allowed}%")
    set_agent("slinger", "idle", f"Mode {selected_mode}, strategy {name}")
    add_log("strategy", f"Applied strategy {name}")
    return {
        "name": name,
        "description": profile.description,
        "slippage": profile.slinger.base_slippage_tolerance,
        "gas_multiplier": profile.slinger.gas_premium_multiplier,
        "use_private_mempool": profile.slinger.use_private_mempool,
    }


def set_execution_mode(mode: str) -> str:
    global selected_mode
    selected_mode = mode
    if mode == "traditional":
        unified_slinger.preferred_venue = "dex"
    elif mode == "mcp-only":
        unified_slinger.preferred_venue = "cex"
    else:
        unified_slinger.preferred_venue = "auto"
    set_agent("slinger", "idle", f"Execution mode set to {mode}")
    set_agent("phantom", "standby", f"Mode set to {mode}")
    add_log("mode", f"Execution mode set to {mode}")
    return mode


def find_address(text: str) -> Optional[str]:
    match = re.search(r"0x[a-fA-F0-9]{40}", text)
    return match.group(0) if match else None


def find_symbol(text: str) -> Optional[str]:
    for candidate in ["BTC", "ETH", "SOL", "BNB", "PEPE", "WETH", "WBTC"]:
        if candidate.lower() in text.lower():
            return candidate
    return None


def make_manual_signal(address: str, chain: str = "1") -> TradeSignal:
    return TradeSignal(token_address=address, chain=chain, narrative_score=55, reasoning="Manual dashboard target", discovered_at=time.time())


def infer_user_preferences(text: str) -> dict[str, Any]:
    lowered = text.lower()
    prefs = dict(conversation_state["user_profile"])
    if any(word in lowered for word in ["low risk", "safer", "careful", "defensive", "protect capital"]):
        prefs["risk"] = "low"
    elif any(word in lowered for word in ["high risk", "aggressive", "degen", "ape", "moonshot"]):
        prefs["risk"] = "high"
    elif any(word in lowered for word in ["balanced", "moderate"]):
        prefs["risk"] = "balanced"
    if any(word in lowered for word in ["fast", "quick", "speed"]):
        prefs["speed"] = "fast"
    elif any(word in lowered for word in ["slow", "patient", "careful entries"]):
        prefs["speed"] = "slow"
    if any(word in lowered for word in ["cex", "exchange", "binance"]):
        prefs["venue"] = "cex"
    elif any(word in lowered for word in ["both", "hybrid"]):
        prefs["venue"] = "hybrid"
    elif any(word in lowered for word in ["dex", "onchain", "on-chain"]):
        prefs["venue"] = "dex"
    if any(word in lowered for word in ["walk me through", "explain", "guide me", "help me understand"]):
        prefs["needs_guidance"] = True
    if any(word in lowered for word in ["yield", "apr", "farm"]):
        prefs["goal"] = "yield"
    elif any(word in lowered for word in ["momentum", "runner", "breakout"]):
        prefs["goal"] = "momentum"
    elif any(word in lowered for word in ["whale", "macro", "market context"]):
        prefs["goal"] = "macro"
    elif any(word in lowered for word in ["copy trade", "smart money"]):
        prefs["goal"] = "copy"
    return prefs


def recommend_strategy_from_preferences(prefs: dict[str, Any]) -> tuple[str, str, str]:
    risk = prefs.get("risk", "balanced")
    speed = prefs.get("speed", "balanced")
    venue = prefs.get("venue", "dex")
    goal = prefs.get("goal", "opportunistic upside")
    if goal == "yield":
        return "yield_alchemist", "traditional", "That points toward capital rotation and yield harvesting."
    if goal == "copy":
        return "shadow_clone", "traditional", "If the user wants smart-money following, shadow_clone is the cleanest fit."
    if goal == "macro":
        return "oracle_eye", "hybrid", "Macro plus whale-tracking calls for a broader contextual strategy."
    if risk == "low" and speed in {"slow", "balanced"}:
        return "forensic_sniper", "traditional", "Low risk plus a need for explanation suggests deep due diligence first."
    if risk == "low" and speed == "fast":
        return "sniper", "traditional", "This asks for speed with guardrails, so sniper is the compromise."
    if risk == "balanced" and venue == "hybrid":
        return "liquidity_sentinel", "hybrid", "Hybrid venue plus balanced risk fits liquidity-aware execution."
    if risk == "high" and speed == "fast":
        return "degen", "traditional", "The user is asking for aggressive upside with less friction."
    if venue == "cex":
        return "oracle_eye", "mcp-only", "If they want exchange-driven execution, we should bias toward the MCP path."
    return "oracle_eye", "hybrid", "This sounds like they want context, flexibility, and guided trade selection."


def conversational_strategy_response(text: str) -> Optional[dict[str, Any]]:
    lowered = text.lower().strip()
    if not any(phrase in lowered for phrase in ["strategy", "risk", "safer", "aggressive", "walk me through", "what should", "which mode", "which strategy", "help me decide", "how should", "explain", "guide me", "i want", "i prefer", "i'm looking for"]):
        return None
    prefs = infer_user_preferences(text)
    conversation_state["user_profile"] = prefs
    suggested_strategy, suggested_mode, rationale = recommend_strategy_from_preferences(prefs)
    conversation_state["last_recommendation"] = {"strategy": suggested_strategy, "mode": suggested_mode, "rationale": rationale}
    whisper = STRATEGY_PERSONAS.get(suggested_strategy, {})
    explanation = (
        f"Whisperer: Based on what you're describing, I'd lean {suggested_strategy}. It fits a {whisper.get('style', 'flexible')} approach.\n\n"
        f"Actuary: From a risk angle, you're signaling {prefs.get('risk')} risk tolerance with a {prefs.get('speed')} execution preference. That makes {suggested_strategy} more sensible than blindly staying in {selected_strategy}.\n\n"
        f"PHANTOM: Venue preference looks like {prefs.get('venue')}, so I’d pair that with {suggested_mode} mode.\n\n"
        f"Reaper: Goal is still capital discipline. Even in this setup, exits and drawdown control matter more than hype.\n\n"
        f"My recommendation: switch to {suggested_strategy} with {suggested_mode} mode. {rationale}"
    )
    return {"reply": explanation, "agent": "system", "recommendation": {"strategy": suggested_strategy, "mode": suggested_mode, "preferences": prefs}}


def apply_recommended_setup() -> dict[str, Any]:
    rec = conversation_state.get("last_recommendation")
    if not rec:
        return {"reply": "There is no recent recommendation to apply yet.", "agent": "system"}
    strategy_details = apply_strategy(rec["strategy"])
    mode = set_execution_mode(rec["mode"])
    return {"reply": f"Applied recommended setup: {rec['strategy']} with {mode} mode.", "agent": "system", "strategy": strategy_details, "mode": mode}


def run_whisperer_scan(top_n: int = 5) -> tuple[str, list[dict[str, Any]]]:
    global last_signal
    set_error(None)
    set_agent("whisperer", "active", f"Scanning top {top_n} signals")
    try:
        signals = whisperer.scan_top_n(top_n)
        items = [build_watch_item(signal) for signal in signals]
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
        set_error(f"Whisperer failed: {e}")
        return f"Whisperer scan failed: {e}", []


def run_actuary_assess(signal: TradeSignal) -> tuple[str, Optional[dict[str, Any]]]:
    global last_assessment
    set_error(None)
    set_agent("actuary", "active", f"Assessing {signal.token_address[:10]}...")
    try:
        assessment = actuary.assess_risk(signal)
        last_assessment = assessment
        analysis_cache[signal.token_address.lower()] = {"signal": signal_to_dict(signal), "assessment": assessment_to_dict(assessment)}
        set_agent("actuary", "idle", f"{assessment.risk_level.value} on {signal.token_address[:10]}...")
        add_log("risk", f"Actuary rated {signal.token_address[:10]}... as {assessment.risk_level.value}")
        return (f"Actuary rated this {assessment.risk_level.value}. Max allocation ${assessment.max_allocation_usd:.2f}. Buy tax {assessment.buy_tax*100:.1f}%, sell tax {assessment.sell_tax*100:.1f}%.", assessment_to_dict(assessment))
    except Exception as e:
        logger.exception("Actuary assessment failed")
        set_agent("actuary", "error", f"Assessment failed: {e}")
        set_error(f"Actuary failed: {e}")
        return f"Actuary failed: {e}", None


def run_slinger_execute(assessment: RiskAssessment, chain_id: str = "1", symbol: str | None = None) -> tuple[str, Optional[dict[str, Any]]]:
    set_error(None)
    set_agent("slinger", "active", f"Executing {assessment.token_address[:10]}...")
    try:
        order = unified_slinger.execute_order(assessment, chain_id=chain_id, symbol=symbol)
        if not order:
            set_agent("slinger", "idle", "Execution rejected or unavailable")
            add_log("trade", "Unified Slinger did not place an order")
            return "Slinger stood down. Order was rejected or could not be generated.", None
        reaper.take_position(order)
        set_agent("slinger", "idle", f"Queued BUY ${order.amount_usd:.2f}")
        add_log("trade", f"Unified Slinger created {order.action} order for ${order.amount_usd:.2f}")
        return (f"Slinger generated a {order.action} order for ${order.amount_usd:.2f} on chain {order.chain}. Slippage {order.slippage_tolerance*100:.1f}%, gas {order.gas_premium_gwei:.1f} gwei.", {"token_address": order.token_address, "chain": order.chain, "action": order.action, "amount_usd": order.amount_usd, "slippage_tolerance": order.slippage_tolerance, "gas_premium_gwei": order.gas_premium_gwei, "entry_price_usd": order.entry_price_usd, "tx_hash": order.tx_hash})
    except Exception as e:
        logger.exception("Slinger execution failed")
        set_agent("slinger", "error", f"Execution failed: {e}")
        set_error(f"Slinger failed: {e}")
        return f"Slinger failed: {e}", None


def run_phantom_market(symbol: str = "BTC/USDT") -> tuple[str, Optional[dict[str, Any]]]:
    set_error(None)
    set_agent("phantom", "active", f"Fetching market data for {symbol}")
    try:
        result = phantom._call_mcp_server("ccxt", "fetch_ticker", {"symbol": symbol})
        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown MCP error"))
        ticker = result["data"]
        set_agent("phantom", "standby", f"Fetched {symbol} ticker")
        add_log("mcp", f"PHANTOM fetched market data for {symbol}")
        return (f"PHANTOM market read for {symbol}: last {ticker['last']:.4f}, bid {ticker['bid']:.4f}, ask {ticker['ask']:.4f}, volume {ticker['quoteVolume']:.0f}.", ticker)
    except Exception as e:
        logger.exception("PHANTOM market fetch failed")
        set_agent("phantom", "error", f"Market fetch failed: {e}")
        set_error(f"PHANTOM failed: {e}")
        return f"PHANTOM failed: {e}", None


def positions_snapshot() -> list[dict[str, Any]]:
    rows = []
    for address, pos in trader.active_positions.items():
        info = get_token_info(address) or {}
        current_price = info.get("price", pos["entry_price"])
        pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100 if pos["entry_price"] else 0
        rows.append({"token_address": address, "symbol": pos["symbol"], "entry_price": pos["entry_price"], "current_price": current_price, "pnl_pct": pnl_pct})
    return rows


def reaper_snapshot() -> list[dict[str, Any]]:
    return [{"token_address": pos.token_address, "chain": pos.chain, "status": pos.status, "current_value": pos.current_value, "pnl_pct": pos.pnl_pct} for pos in reaper.positions.values()]


def current_system_summary() -> dict[str, Any]:
    return {
        "paper_balance": trader.paper_balance,
        "active_count": len(trader.active_positions),
        "graveyard_count": len(trader.graveyard),
        "config": dict(trader.config),
        "reaper": reaper.get_portfolio_summary(),
        "selected_strategy": selected_strategy,
        "selected_mode": selected_mode,
        "last_error": last_error,
        "available_strategies": sorted(strategy_factory.profiles.keys()),
        "available_modes": ["traditional", "hybrid", "mcp-only"],
        "conversation_state": conversation_state,
    }


def route_command(message: str) -> dict[str, Any]:
    global watchlist, last_signal, last_assessment
    text = message.strip()
    lowered = text.lower()
    if not text:
        return {"reply": "Say something and I’ll route it.", "agent": "system"}
    if lowered in {"apply recommendation", "use recommendation", "do the recommended setup"}:
        return apply_recommended_setup()
    convo = conversational_strategy_response(text)
    if convo:
        add_log("conversation", f"Generated conversational strategy guidance for: {text[:80]}")
        return convo
    if lowered in {"panic", "nuke", "yolo", "stealth", "stats", "help"}:
        reply = team.execute(lowered)
        add_log("command", f"Team command executed: {lowered}")
        return {"reply": reply, "agent": "system"}
    if lowered.startswith("strategy "):
        name = lowered.split("strategy ", 1)[1].strip()
        if name not in strategy_factory.profiles:
            return {"reply": f"Unknown strategy '{name}'.", "agent": "system"}
        details = apply_strategy(name)
        return {"reply": f"Strategy switched to {name}: {details['description']}", "agent": "system", "strategy": details}
    if lowered.startswith("mode "):
        mode = lowered.split("mode ", 1)[1].strip()
        if mode not in {"traditional", "hybrid", "mcp-only"}:
            return {"reply": f"Unknown mode '{mode}'.", "agent": "system"}
        set_execution_mode(mode)
        return {"reply": f"Execution mode switched to {mode}.", "agent": "system", "mode": mode}
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
        signal = make_manual_signal(address) if address else last_signal
        if not signal and watchlist:
            top = watchlist[0]
            signal = make_manual_signal(top["token_address"], top["chain"])
            signal.narrative_score = top["score"]
            signal.reasoning = top["reasoning"]
        if not signal:
            return {"reply": "Give me a token address or scan first so Actuary has something real to assess.", "agent": "actuary"}
        reply, assessment = run_actuary_assess(signal)
        return {"reply": reply, "agent": "actuary", "assessment": assessment}
    if any(word in lowered for word in ["buy", "execute", "route", "order", "slinger", "ape into"]):
        if not last_assessment:
            return {"reply": "I need an Actuary approval first. Scan or assess a token before telling Slinger to execute.", "agent": "slinger"}
        chain_id = "cex" if selected_mode == "mcp-only" else ("cex" if any(word in lowered for word in ["cex", "exchange", "binance", "phantom"]) else "1")
        if selected_mode == "hybrid":
            chain_id = "1"
        symbol = None
        token_symbol = find_symbol(text)
        if chain_id == "cex" and token_symbol:
            symbol = f"{token_symbol}/USDT"
        reply, order = run_slinger_execute(last_assessment, chain_id=chain_id, symbol=symbol)
        return {"reply": reply, "agent": "slinger", "order": order}
    if any(word in lowered for word in ["phantom", "mcp", "cex", "ticker", "market"]):
        symbol = find_symbol(text) or "BTC"
        reply, ticker = run_phantom_market(f"{symbol}/USDT")
        return {"reply": reply, "agent": "phantom", "ticker": ticker}
    if any(word in lowered for word in ["reaper", "positions", "stop", "tp", "sl", "portfolio", "summary"]):
        summary = reaper.get_portfolio_summary()
        set_agent("reaper", "active", "Reported portfolio summary")
        return {"reply": f"Reaper is tracking {summary['total_positions']} position(s). Active {summary['active']}, free-ride {summary['free_ride']}, closed {summary['closed']}, total tracked value ${summary['total_value_usd']:.2f}.", "agent": "reaper", "portfolio": summary}
    return {"reply": "Try talking naturally about risk, speed, and goals, or use direct commands like 'scan top 5', 'assess 0x...', 'apply recommendation', or 'PHANTOM BTC ticker'.", "agent": "system"}


HTML = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Asymmetric Strike Team NLP Dashboard</title>
  <script src=\"https://cdn.tailwindcss.com\"></script>
  <style>
    body { background: #0a0f1c; }
    .panel { background: linear-gradient(180deg, rgba(17,24,39,.96), rgba(10,15,28,.98)); border: 1px solid rgba(71,85,105,.45); }
    .scroll { scrollbar-width: thin; }
    .glow { box-shadow: 0 0 0 1px rgba(59,130,246,.15), 0 0 30px rgba(37,99,235,.08); }
    iframe { width: 100%; min-height: 320px; border: 0; border-radius: 12px; background: #020617; }
  </style>
</head>
<body class=\"text-slate-100 min-h-screen\">
  <div class=\"max-w-7xl mx-auto p-6 space-y-6\">
    <header class=\"flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4\">
      <div>
        <p class=\"text-xs uppercase tracking-[0.35em] text-sky-400\">Asymmetric Strike Team</p>
        <h1 class=\"text-3xl font-semibold\">Conversational NLP Dashboard</h1>
        <p class=\"text-slate-400 mt-2 max-w-3xl\">Discuss strategy naturally, get agent-style guidance, then move into scan, assess, and execution.</p>
      </div>
      <div class=\"panel rounded-2xl px-4 py-3 glow\">
        <div class=\"text-xs text-slate-400\">Live paper balance</div>
        <div id=\"paper-balance\" class=\"text-2xl font-bold text-emerald-400\">$0.00</div>
      </div>
    </header>

    <section class=\"grid grid-cols-1 xl:grid-cols-3 gap-6\">
      <div class=\"xl:col-span-2 space-y-6\">
        <div class=\"panel rounded-2xl p-5 glow\">
          <h2 class=\"text-lg font-semibold\">Strategy conversation</h2>
          <p class=\"text-sm text-slate-400 mt-1\">Try: “I want lower risk but still decent upside”, “walk me through the best strategy”, “which mode fits exchange execution?”</p>
          <div class=\"flex gap-3 mt-4\">
            <input id=\"command-input\" class=\"flex-1 bg-slate-950/70 border border-slate-700 rounded-xl px-4 py-3 outline-none focus:border-sky-500\" placeholder=\"Talk to the team in plain English...\" />
            <button onclick=\"sendCommand()\" class=\"bg-sky-600 hover:bg-sky-500 rounded-xl px-5 py-3 font-semibold\">Send</button>
          </div>
          <div class=\"mt-3 flex flex-wrap gap-2 text-sm\">
            <button class=\"rounded-full px-3 py-1 bg-slate-900 border border-slate-700\" onclick=\"quick('I want lower risk but still decent upside')\">lower risk, decent upside</button>
            <button class=\"rounded-full px-3 py-1 bg-slate-900 border border-slate-700\" onclick=\"quick('walk me through the best strategy for a cautious user')\">cautious user</button>
            <button class=\"rounded-full px-3 py-1 bg-slate-900 border border-slate-700\" onclick=\"quick('which mode fits exchange execution')\">exchange mode</button>
            <button class=\"rounded-full px-3 py-1 bg-violet-900 border border-violet-700\" onclick=\"quick('apply recommendation')\">apply recommendation</button>
            <button class=\"rounded-full px-3 py-1 bg-slate-900 border border-slate-700\" onclick=\"quick('scan top 5')\">scan top 5</button>
          </div>
        </div>

        <div class=\"grid grid-cols-1 2xl:grid-cols-2 gap-6\">
          <div class=\"panel rounded-2xl p-5 glow\">
            <div class=\"flex items-center justify-between mb-4\"><h2 class=\"text-lg font-semibold\">Conversation</h2><span class=\"text-xs text-slate-400\">Agent-style replies</span></div>
            <div id=\"chat-history\" class=\"space-y-3 max-h-[420px] overflow-y-auto scroll\"></div>
          </div>
          <div class=\"panel rounded-2xl p-5 glow\">
            <div class=\"flex items-center justify-between mb-4\"><h2 class=\"text-lg font-semibold\">Recommendation</h2><span class=\"text-xs text-slate-400\">Current fit</span></div>
            <div id=\"recommendation\" class=\"text-sm text-slate-300 space-y-2\"></div>
            <button onclick=\"quick('apply recommendation')\" class=\"mt-4 w-full bg-violet-600 hover:bg-violet-500 rounded-xl py-3 font-semibold\">Apply recommendation</button>
          </div>
        </div>

        <div class=\"panel rounded-2xl p-5 glow\">
          <div class=\"flex items-center justify-between mb-4\"><h2 class=\"text-lg font-semibold\">Watchlist</h2><span class=\"text-xs text-slate-400\">Signal candidates</span></div>
          <div class=\"overflow-x-auto\">
            <table class=\"w-full text-sm\">
              <thead class=\"text-slate-400 border-b border-slate-800\"><tr><th class=\"text-left py-2\">Token</th><th class=\"text-left py-2\">Price</th><th class=\"text-left py-2\">Score</th><th class=\"text-left py-2\">Risk</th><th class=\"text-left py-2\">Actions</th></tr></thead>
              <tbody id=\"watchlist-body\"></tbody>
            </table>
          </div>
        </div>

        <div class=\"grid grid-cols-1 2xl:grid-cols-2 gap-6\">
          <div class=\"panel rounded-2xl p-5 glow\"><div class=\"flex items-center justify-between mb-4\"><h2 class=\"text-lg font-semibold\">Token detail</h2><span id=\"detail-symbol\" class=\"text-xs text-slate-400\">No token selected</span></div><div id=\"token-detail\" class=\"text-sm text-slate-300 space-y-2\"></div></div>
          <div class=\"panel rounded-2xl p-5 glow\"><div class=\"flex items-center justify-between mb-4\"><h2 class=\"text-lg font-semibold\">Chart</h2><span class=\"text-xs text-slate-400\">DexScreener</span></div><iframe id=\"chart-frame\" src=\"about:blank\"></iframe></div>
        </div>
      </div>

      <div class=\"space-y-6\">
        <div class=\"panel rounded-2xl p-5 glow\"><h2 class=\"text-lg font-semibold mb-4\">Agent roster</h2><div id=\"agent-cards\" class=\"space-y-3\"></div></div>
        <div class=\"panel rounded-2xl p-5 glow\"><h2 class=\"text-lg font-semibold mb-4\">System snapshot</h2><div id=\"snapshot\" class=\"text-sm text-slate-300 space-y-2\"></div><div id=\"error-banner\" class=\"hidden mt-4 rounded-xl border border-rose-800 bg-rose-950/40 text-rose-200 px-3 py-3 text-sm\"></div></div>
        <div class=\"panel rounded-2xl p-5 glow\"><div class=\"flex items-center justify-between mb-4\"><h2 class=\"text-lg font-semibold\">Activity log</h2><button onclick=\"refresh()\" class=\"text-sm text-sky-400\">Refresh</button></div><div id=\"activity-log\" class=\"space-y-2 max-h-[360px] overflow-y-auto scroll text-sm\"></div></div>
      </div>
    </section>
  </div>
<script>
window.__watchlist = [];
async function api(path, options={}) { const res = await fetch(path, options); return await res.json(); }
function badge(status) { const colors = { idle:'bg-slate-700 text-slate-200', active:'bg-emerald-700 text-emerald-100', standby:'bg-amber-700 text-amber-100', error:'bg-rose-700 text-rose-100' }; return colors[status] || colors.idle; }
function renderChat(items) { const el = document.getElementById('chat-history'); el.innerHTML=''; items.forEach(item => { const wrap = document.createElement('div'); wrap.className='space-y-2'; wrap.innerHTML = `<div class=\"bg-slate-950/60 border border-slate-800 rounded-xl p-3\"><div class=\"text-xs text-slate-500 mb-1\">You</div><div>${item.user}</div></div><div class=\"bg-sky-950/30 border border-sky-900 rounded-xl p-3 whitespace-pre-wrap\"><div class=\"text-xs text-sky-400 mb-1\">${item.agent}</div><div>${item.reply}</div></div>`; el.appendChild(wrap); }); }
function renderAgents(items) { const el = document.getElementById('agent-cards'); el.innerHTML=''; items.forEach(agent => { const card = document.createElement('div'); card.className='bg-slate-950/50 border border-slate-800 rounded-xl p-4'; card.innerHTML = `<div class=\"flex items-start justify-between gap-3\"><div><div class=\"font-semibold\">${agent.name}</div><div class=\"text-xs text-slate-400\">${agent.role}</div></div><span class=\"text-xs px-2 py-1 rounded-full ${badge(agent.status)}\">${agent.status}</span></div><div class=\"text-sm text-slate-300 mt-3\">${agent.summary}</div><div class=\"text-xs text-slate-400 mt-2\">Last action: ${agent.last_action}</div>`; el.appendChild(card); }); }
function renderLog(items) { const el = document.getElementById('activity-log'); el.innerHTML=''; items.forEach(item => { const row = document.createElement('div'); row.className='bg-slate-950/45 border border-slate-800 rounded-lg px-3 py-2'; row.innerHTML = `<span class=\"text-slate-500 text-xs mr-2\">${item.time}</span><span class=\"text-sky-400 text-xs uppercase mr-2\">${item.type}</span>${item.message}`; el.appendChild(row); }); }
function selectToken(item) { document.getElementById('detail-symbol').innerText = item.symbol; document.getElementById('token-detail').innerHTML = `<div><span class=\"text-slate-500\">Address:</span> ${item.token_address}</div><div><span class=\"text-slate-500\">Chain:</span> ${item.chain}</div><div><span class=\"text-slate-500\">Price:</span> ${item.price ? '$' + Number(item.price).toFixed(8) : 'n/a'}</div><div><span class=\"text-slate-500\">Score:</span> ${item.score}</div><div><span class=\"text-slate-500\">Risk:</span> ${item.risk_level || 'unassessed'}</div><div><span class=\"text-slate-500\">Reasoning:</span> ${item.reasoning}</div><div><span class=\"text-slate-500\">Warnings:</span> ${(item.warnings && item.warnings.length) ? item.warnings.join(' | ') : 'none'}</div>`; document.getElementById('chart-frame').src = item.chart_url || 'about:blank'; }
async function watchAction(action, address) { const commands = { assess: `assess ${address}`, execute: `execute ${address}` }; await api('/api/nlp', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: commands[action]}) }); await refresh(); }
function renderWatchlist(items) { window.__watchlist = items; const body = document.getElementById('watchlist-body'); body.innerHTML=''; items.forEach((item, index) => { const tr = document.createElement('tr'); tr.className='border-b border-slate-800'; tr.innerHTML = `<td class=\"py-2\"><button class=\"text-left\" onclick=\"selectToken(window.__watchlist[${index}])\"><div class=\"font-semibold text-sky-300\">${item.symbol}</div><div class=\"text-xs text-slate-500\">${item.token_address.slice(0,12)}...</div></button></td><td class=\"py-2\">${item.price ? '$' + Number(item.price).toFixed(8) : 'n/a'}</td><td class=\"py-2\">${item.score}</td><td class=\"py-2\">${item.risk_level || 'unassessed'}</td><td class=\"py-2\"><div class=\"flex flex-wrap gap-2\"><button class=\"px-2 py-1 rounded bg-slate-800 text-xs\" onclick=\"watchAction('assess','${item.token_address}')\">assess</button><button class=\"px-2 py-1 rounded bg-emerald-800 text-xs\" onclick=\"watchAction('execute','${item.token_address}')\">execute</button></div></td>`; body.appendChild(tr); }); if (items.length) selectToken(items[0]); }
function renderRecommendation(system) { const rec = system.conversation_state?.last_recommendation; const prefs = system.conversation_state?.user_profile; const el = document.getElementById('recommendation'); if (!rec) { el.innerHTML = '<div class="text-slate-400">No recommendation yet. Start a strategy conversation.</div>'; return; } el.innerHTML = `<div><span class=\"text-slate-500\">Strategy:</span> <span class=\"font-semibold text-white\">${rec.strategy}</span></div><div><span class=\"text-slate-500\">Mode:</span> <span class=\"font-semibold text-white\">${rec.mode}</span></div><div><span class=\"text-slate-500\">Risk preference:</span> ${prefs.risk}</div><div><span class=\"text-slate-500\">Speed preference:</span> ${prefs.speed}</div><div><span class=\"text-slate-500\">Venue preference:</span> ${prefs.venue}</div><div><span class=\"text-slate-500\">Reason:</span> ${rec.rationale}</div>`; }
function renderSnapshot(state) { document.getElementById('paper-balance').innerText = `$${Number(state.paper_balance).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}`; document.getElementById('snapshot').innerHTML = `<div>Active positions: <span class=\"text-white font-semibold\">${state.active_count}</span></div><div>Closed trades: <span class=\"text-white font-semibold\">${state.graveyard_count}</span></div><div>Strategy / Mode: <span class=\"text-white font-semibold\">${state.selected_strategy} / ${state.selected_mode}</span></div>`; const errorBanner = document.getElementById('error-banner'); if (state.last_error) { errorBanner.classList.remove('hidden'); errorBanner.innerText = state.last_error; } else { errorBanner.classList.add('hidden'); errorBanner.innerText = ''; } }
async function refresh() { const data = await api('/api/dashboard_state'); renderChat(data.chat_history); renderAgents(data.agents); renderLog(data.activity_log); renderWatchlist(data.watchlist); renderSnapshot(data.system); renderRecommendation(data.system); }
async function sendCommand() { const input = document.getElementById('command-input'); const message = input.value.trim(); if (!message) return; input.value=''; await api('/api/nlp', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message}) }); await refresh(); }
function quick(text) { document.getElementById('command-input').value = text; sendCommand(); }
document.addEventListener('DOMContentLoaded', () => { document.getElementById('command-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendCommand(); }); refresh(); setInterval(refresh, 7000); });
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/dashboard_state")
def dashboard_state():
    return jsonify({"agents": [asdict(agent) for agent in agents.values()], "activity_log": activity_log, "chat_history": chat_history[-30:], "watchlist": watchlist, "positions": positions_snapshot(), "reaper_positions": reaper_snapshot(), "system": current_system_summary()})


@app.route("/api/nlp", methods=["POST"])
def api_nlp():
    payload = request.get_json(force=True) or {}
    message = str(payload.get("message", "")).strip()
    result = route_command(message)
    chat_history.append({"user": message, "agent": result["agent"].upper(), "reply": result["reply"]})
    add_log("nlp", f"Routed command to {result['agent']}: {message}")
    return jsonify(result)


if __name__ == "__main__":
    apply_strategy(selected_strategy)
    set_execution_mode(selected_mode)
    add_log("system", "Conversational NLP dashboard initialized")
    app.run(host="127.0.0.1", port=5055, debug=False, use_reloader=False)
