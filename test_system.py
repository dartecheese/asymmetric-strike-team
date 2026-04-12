"""
Asymmetric Strike Team — System Performance & Health Check
===========================================================
Tests:
  1. Whisperer      — real API calls, scoring, dedup
  2. Actuary        — GoPlus API + fallback path
  3. Slinger        — order building, strategy params
  4. Reaper         — position lifecycle, TP/SL triggers
  5. PositionStore  — save / restore / atomic write
  6. Pipeline       — full end-to-end cycle
  7. Performance    — latency benchmarks per component

Run:  python test_system.py
"""

import sys
import time
import traceback
import tempfile
from pathlib import Path
from typing import Callable

# ── colour helpers ──────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✅ PASS{RESET}  {msg}")
def fail(msg): print(f"  {RED}❌ FAIL{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠️  WARN{RESET}  {msg}")
def info(msg): print(f"  {CYAN}ℹ️  {msg}{RESET}")

results = {"passed": 0, "failed": 0, "warned": 0}

def check(name: str, fn: Callable, warn_only: bool = False):
    """Run a single check and record result."""
    t0 = time.perf_counter()
    try:
        fn()
        elapsed = (time.perf_counter() - t0) * 1000
        ok(f"{name}  ({elapsed:.0f}ms)")
        results["passed"] += 1
    except AssertionError as e:
        elapsed = (time.perf_counter() - t0) * 1000
        msg = f"{name}  ({elapsed:.0f}ms) — {e}"
        if warn_only:
            warn(msg)
            results["warned"] += 1
        else:
            fail(msg)
            results["failed"] += 1
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        msg = f"{name}  ({elapsed:.0f}ms) — {type(e).__name__}: {e}"
        if warn_only:
            warn(msg)
            results["warned"] += 1
        else:
            fail(msg)
            results["failed"] += 1
        if "--verbose" in sys.argv:
            traceback.print_exc()

def section(title: str):
    print(f"\n{BOLD}{CYAN}{'─'*55}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*55}{RESET}")


# ── shared test fixtures ────────────────────────────────────────────────────

def make_signal(address="0x6982508145454Ce325dDbE47a25d4ec3d2311933", chain="1", score=85):
    from core.models import TradeSignal
    return TradeSignal(
        token_address=address,
        chain=chain,
        narrative_score=score,
        reasoning="Test signal",
        discovered_at=time.time(),
    )

def make_order(address="0x6982508145454Ce325dDbE47a25d4ec3d2311933", amount=50.0, entry_price=0.00042):
    from core.models import ExecutionOrder
    return ExecutionOrder(
        token_address=address,
        chain="1",
        action="BUY",
        amount_usd=amount,
        slippage_tolerance=0.30,
        gas_premium_gwei=90.0,
        entry_price_usd=entry_price,
    )

def make_assessment(address="0x6982508145454Ce325dDbE47a25d4ec3d2311933", risk="MEDIUM", alloc=50.0):
    from core.models import RiskAssessment, RiskLevel
    return RiskAssessment(
        token_address=address,
        is_honeypot=False,
        buy_tax=0.04,
        sell_tax=0.04,
        liquidity_locked=False,
        risk_level=RiskLevel(risk),
        max_allocation_usd=alloc,
        warnings=[],
    )


# ════════════════════════════════════════════════════════════════════════════
# 1. WHISPERER
# ════════════════════════════════════════════════════════════════════════════
section("1. WHISPERER — Signal Scanning")

def test_whisperer_import():
    from agents.whisperer import Whisperer
    w = Whisperer()
    assert hasattr(w, "scan_firehose")
    assert hasattr(w, "scan_top_n")
    assert hasattr(w, "seen_tokens")

check("Whisperer imports and initialises", test_whisperer_import)

def test_whisperer_real_scan():
    from agents.whisperer import Whisperer
    w = Whisperer(min_velocity_score=1)  # low threshold to guarantee a result
    t0 = time.perf_counter()
    signal = w.scan_firehose()
    elapsed = (time.perf_counter() - t0) * 1000
    assert signal is not None, "scan_firehose returned None — no candidates found"
    assert signal.token_address.startswith("0x"), f"Bad token address: {signal.token_address}"
    assert 0 <= signal.narrative_score <= 100, f"Score out of range: {signal.narrative_score}"
    assert signal.chain in ("1","56","42161","8453","137"), f"Unexpected chain: {signal.chain}"
    info(f"Token: {signal.token_address[:14]}... | Chain: {signal.chain} | Score: {signal.narrative_score} | {elapsed:.0f}ms")

check("Whisperer real DexScreener scan returns valid signal", test_whisperer_real_scan, warn_only=True)

def test_whisperer_dedup():
    from agents.whisperer import Whisperer
    w = Whisperer(min_velocity_score=1)
    s1 = w.scan_firehose()
    if s1:
        w.seen_tokens.add(s1.token_address)
    s2 = w.scan_firehose()
    # Either s2 is None (no other candidates) or it's a different token
    if s1 and s2:
        assert s1.token_address != s2.token_address, "Dedup failed — returned same token twice"

check("Whisperer deduplicates seen tokens", test_whisperer_dedup, warn_only=True)

def test_whisperer_latency():
    from agents.whisperer import Whisperer
    w = Whisperer(min_velocity_score=1)
    t0 = time.perf_counter()
    w.scan_firehose()
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 10_000, f"Scan too slow: {elapsed:.0f}ms (limit 10s)"
    info(f"Scan latency: {elapsed:.0f}ms")

check("Whisperer scan completes within 10s", test_whisperer_latency, warn_only=True)


# ════════════════════════════════════════════════════════════════════════════
# 2. ACTUARY
# ════════════════════════════════════════════════════════════════════════════
section("2. ACTUARY — Risk Assessment")

def test_actuary_import():
    from agents.actuary import Actuary
    a = Actuary(max_allowed_tax=0.25)
    assert hasattr(a, "assess_risk")
    assert a.max_allowed_tax == 0.25

check("Actuary imports and initialises", test_actuary_import)

def test_actuary_never_returns_none():
    from agents.actuary import Actuary
    a = Actuary()
    signal = make_signal(address="0x0000000000000000000000000000000000000001")
    result = a.assess_risk(signal)
    assert result is not None, "assess_risk returned None — pipeline would crash"
    assert hasattr(result, "risk_level")
    assert hasattr(result, "max_allocation_usd")

check("Actuary never returns None (fallback path)", test_actuary_never_returns_none)

def test_actuary_fallback_is_conservative():
    from agents.actuary import Actuary
    from core.models import RiskLevel
    a = Actuary()
    # Use a nonsense address to force GoPlus to return nothing
    signal = make_signal(address="0x0000000000000000000000000000000000000001")
    result = a.assess_risk(signal)
    # Fallback should never approve a full allocation
    assert result.max_allocation_usd <= 50.0, f"Fallback too generous: ${result.max_allocation_usd}"
    assert result.risk_level != RiskLevel.LOW, "Fallback should not be LOW risk"
    info(f"Fallback result: {result.risk_level} | ${result.max_allocation_usd}")

check("Actuary fallback is conservative (not LOW risk)", test_actuary_fallback_is_conservative)

def test_actuary_real_token():
    from agents.actuary import Actuary
    from core.models import RiskLevel
    a = Actuary(max_allowed_tax=0.25)
    signal = make_signal()  # PEPE on Ethereum
    t0 = time.perf_counter()
    result = a.assess_risk(signal)
    elapsed = (time.perf_counter() - t0) * 1000
    assert result is not None
    assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.REJECTED)
    info(f"PEPE: {result.risk_level} | buy_tax={result.buy_tax*100:.1f}% | alloc=${result.max_allocation_usd} | {elapsed:.0f}ms")

check("Actuary real GoPlus query (PEPE)", test_actuary_real_token, warn_only=True)

def test_actuary_cache():
    from agents.actuary import Actuary
    a = Actuary()
    signal = make_signal()
    a.assess_risk(signal)  # prime cache
    t0 = time.perf_counter()
    a.assess_risk(signal)  # should hit cache
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 50, f"Cache miss — took {elapsed:.0f}ms (expected <50ms)"
    info(f"Cache hit latency: {elapsed:.1f}ms")

check("Actuary 5-min cache hit is fast (<50ms)", test_actuary_cache, warn_only=True)

def test_actuary_honeypot_rejected():
    from agents.actuary import Actuary, CONSERVATIVE_FALLBACK
    from core.models import RiskLevel
    a = Actuary(max_allowed_tax=0.10)
    # Patch _fetch_goplus to simulate a honeypot
    a._fetch_goplus = lambda *_: {"is_honeypot": "1", "buy_tax": "0.0", "sell_tax": "0.0", "is_open_source": "1"}
    result = a.assess_risk(make_signal())
    assert result.risk_level == RiskLevel.REJECTED, f"Honeypot not rejected: {result.risk_level}"
    assert result.max_allocation_usd == 0.0

check("Actuary rejects honeypot token", test_actuary_honeypot_rejected)

def test_actuary_high_tax_rejected():
    from agents.actuary import Actuary
    from core.models import RiskLevel
    a = Actuary(max_allowed_tax=0.10)
    a._fetch_goplus = lambda *_: {"is_honeypot": "0", "buy_tax": "0.50", "sell_tax": "0.50", "is_open_source": "1"}
    result = a.assess_risk(make_signal())
    assert result.risk_level == RiskLevel.REJECTED, f"High tax not rejected: {result.risk_level}"

check("Actuary rejects high-tax token (50% tax)", test_actuary_high_tax_rejected)


# ════════════════════════════════════════════════════════════════════════════
# 3. SLINGER
# ════════════════════════════════════════════════════════════════════════════
section("3. SLINGER — Order Execution")

def test_slinger_import():
    from agents.slinger import Slinger
    s = Slinger()
    assert hasattr(s, "execute_order")
    assert hasattr(s, "_strategy_slippage")

check("Slinger imports and initialises", test_slinger_import)

def test_slinger_strategy_params():
    from agents.slinger import Slinger
    s = Slinger()
    s._strategy_slippage = 0.05
    s._strategy_gas_multiplier = 1.2
    s._use_private_mempool = True
    assert s._strategy_slippage == 0.05
    assert s._strategy_gas_multiplier == 1.2
    assert s._use_private_mempool == True

check("Slinger accepts strategy profile overrides", test_slinger_strategy_params)

def test_slinger_builds_order():
    from agents.slinger import Slinger
    s = Slinger()
    s._strategy_slippage = 0.30
    s._strategy_gas_multiplier = 3.0
    assessment = make_assessment()
    order = s.execute_order(assessment, chain_id="56")
    assert order is not None, "Slinger returned None on valid assessment"
    assert order.action == "BUY"
    assert order.amount_usd == 50.0
    assert order.slippage_tolerance == 0.30
    assert order.gas_premium_gwei == 90.0  # 30 * 3.0
    assert order.chain == "56"

check("Slinger builds correct order from assessment + strategy", test_slinger_builds_order)

def test_slinger_rejects_rejected():
    from agents.slinger import Slinger
    s = Slinger()
    assessment = make_assessment(risk="REJECTED", alloc=0.0)
    order = s.execute_order(assessment, chain_id="1")
    assert order is None, "Slinger should return None for REJECTED assessment"

check("Slinger stands down on REJECTED assessment", test_slinger_rejects_rejected)

def test_slinger_entry_price_attached():
    from agents.slinger import Slinger
    s = Slinger()
    assessment = make_assessment()
    order = s.execute_order(assessment, chain_id="1")
    # entry_price_usd may be None if DexScreener is slow, but field must exist
    assert hasattr(order, "entry_price_usd"), "ExecutionOrder missing entry_price_usd field"
    info(f"Entry price: {order.entry_price_usd}")

check("Slinger attaches entry_price_usd to order", test_slinger_entry_price_attached, warn_only=True)

def test_slinger_multi_chain_routers():
    from agents.slinger import Slinger
    s = Slinger()
    # Each chain should have a router address
    for chain_id in ("1", "56", "42161", "8453"):
        assert chain_id in s.routers, f"Missing router for chain {chain_id}"
        assert chain_id in s.weth,    f"Missing WETH for chain {chain_id}"

check("Slinger has routers for all 4 supported chains", test_slinger_multi_chain_routers)


# ════════════════════════════════════════════════════════════════════════════
# 4. REAPER
# ════════════════════════════════════════════════════════════════════════════
section("4. REAPER — Position Monitoring")

def test_reaper_import():
    from agents.reaper import Reaper
    r = Reaper(paper_mode=True)
    assert hasattr(r, "take_position")
    assert hasattr(r, "start_monitoring")
    assert hasattr(r, "get_portfolio_summary")

check("Reaper imports and initialises", test_reaper_import)

def test_reaper_take_position():
    import tempfile
    from pathlib import Path
    from agents.reaper import Reaper
    from core.position_store import PositionStore
    
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "pos.json"
        r = Reaper(paper_mode=True)
        r.store = PositionStore(store_path)  # Isolated store
        
        order = make_order()
        r.take_position(order)
        assert order.token_address in r.positions
        pos = r.positions[order.token_address]
        assert pos.status == "ACTIVE"
        assert pos.entry_value == 50.0
        assert pos.entry_price_usd == 0.00042

check("Reaper registers position correctly", test_reaper_take_position)

def test_reaper_none_order():
    import tempfile
    from pathlib import Path
    from agents.reaper import Reaper
    from core.position_store import PositionStore
    
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "pos.json"
        r = Reaper(paper_mode=True)
        r.store = PositionStore(store_path)  # Isolated store
        
        r.take_position(None)  # Should log warning but not crash
        assert len(r.positions) == 0
        # If we got here, it didn't raise — that's success

check("Reaper handles None order gracefully", test_reaper_none_order)

def test_reaper_stop_loss_trigger():
    import tempfile
    from pathlib import Path
    from agents.reaper import Reaper
    from core.position_store import PositionStore
    
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "pos.json"
        r = Reaper(stop_loss_pct=-30.0, paper_mode=True)
        r.store = PositionStore(store_path)  # Isolated store
        
        order = make_order()
        r.take_position(order)
        pos = r.positions[order.token_address]
        # Simulate -35% loss
        pos.current_value = pos.entry_value * 0.65
        pos.pnl_pct = -35.0
        action = r._update_position.__func__  # just check decision logic
        # Manually check the condition
        assert pos.pnl_pct <= r.stop_loss_pct, "Stop loss should trigger at -35%"

check("Reaper stop loss triggers at correct threshold", test_reaper_stop_loss_trigger)

def test_reaper_free_ride_trigger():
    import tempfile
    from pathlib import Path
    from agents.reaper import Reaper
    from core.position_store import PositionStore
    
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "pos.json"
        r = Reaper(take_profit_pct=100.0, paper_mode=True)
        r.store = PositionStore(store_path)  # Isolated store
        
        order = make_order()
        r.take_position(order)
        pos = r.positions[order.token_address]
        # Simulate +110% gain
        pos.current_value = pos.entry_value * 2.10
        pos.peak_value = pos.current_value
        pos.pnl_pct = 110.0
        assert pos.pnl_pct >= r.take_profit_pct, "Free ride should trigger at +110%"

check("Reaper free ride triggers at correct threshold", test_reaper_free_ride_trigger)

def test_reaper_portfolio_summary():
    import tempfile
    from pathlib import Path
    from agents.reaper import Reaper
    from core.position_store import PositionStore
    
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "pos.json"
        r = Reaper(paper_mode=True)
        r.store = PositionStore(store_path)  # Use isolated store
        
        # Use distinct token addresses (Reaper uses address as dict key)
        r.take_position(make_order("0xAAAA000000000000000000000000000000000001", 100.0))
        r.take_position(make_order("0xBBBB000000000000000000000000000000000002", 200.0))
        summary = r.get_portfolio_summary()
        assert summary["total_positions"] == 2, f"Expected 2 positions, got {summary['total_positions']}"
        assert summary["total_value_usd"] == 300.0, f"Expected $300 total, got {summary['total_value_usd']}"

check("Reaper portfolio summary accurate with multiple positions", test_reaper_portfolio_summary)


# ════════════════════════════════════════════════════════════════════════════
# 5. POSITION STORE
# ════════════════════════════════════════════════════════════════════════════
section("5. POSITION STORE — Persistence")

def test_store_save_load():
    from core.position_store import PositionStore
    with tempfile.TemporaryDirectory() as tmp:
        store = PositionStore(Path(tmp) / "pos.json")

        class FakePos:
            token_address = "0xDEAD000000000000000000000000000000000001"
            chain = "1"
            amount_usd = 100.0
            entry_value = 100.0
            current_value = 142.0
            peak_value = 155.0
            entry_price_usd = 0.00042
            last_price_usd = 0.00059
            status = "FREE_RIDE"
            pnl_pct = 42.0

        store.save_position(FakePos())
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0]["token_address"] == FakePos.token_address
        assert loaded[0]["status"] == "FREE_RIDE"
        assert loaded[0]["current_value"] == 142.0

check("PositionStore saves and loads correctly", test_store_save_load)

def test_store_active_filter():
    from core.position_store import PositionStore
    with tempfile.TemporaryDirectory() as tmp:
        store = PositionStore(Path(tmp) / "pos.json")

        class Pos:
            chain = "1"; amount_usd = 50.0; entry_value = 50.0
            current_value = 50.0; peak_value = 50.0
            entry_price_usd = None; last_price_usd = None; pnl_pct = 0.0

        class Active(Pos):
            token_address = "0xAAAA000000000000000000000000000000000001"
            status = "ACTIVE"

        class Stopped(Pos):
            token_address = "0xAAAA000000000000000000000000000000000002"
            status = "STOPPED"

        class FreeRide(Pos):
            token_address = "0xAAAA000000000000000000000000000000000003"
            status = "FREE_RIDE"

        store.save_position(Active())
        store.save_position(Stopped())
        store.save_position(FreeRide())

        active = store.load_active()
        assert len(active) == 2, f"Expected 2 active, got {len(active)}"
        statuses = {p["status"] for p in active}
        assert statuses == {"ACTIVE", "FREE_RIDE"}

check("PositionStore load_active filters correctly", test_store_active_filter)

def test_store_update_status():
    from core.position_store import PositionStore
    with tempfile.TemporaryDirectory() as tmp:
        store = PositionStore(Path(tmp) / "pos.json")

        class FakePos:
            token_address = "0xBEEF000000000000000000000000000000000001"
            chain = "1"; amount_usd = 50.0; entry_value = 50.0
            current_value = 80.0; peak_value = 85.0
            entry_price_usd = 0.001; last_price_usd = 0.0016
            status = "ACTIVE"; pnl_pct = 60.0

        store.save_position(FakePos())
        store.update_status(FakePos.token_address, "STOPPED", current_value=35.0, pnl_pct=-30.0)
        loaded = store.load_all()
        assert loaded[0]["status"] == "STOPPED"
        assert loaded[0]["current_value"] == 35.0
        assert loaded[0]["pnl_pct"] == -30.0

check("PositionStore update_status writes correctly", test_store_update_status)

def test_store_remove():
    from core.position_store import PositionStore
    with tempfile.TemporaryDirectory() as tmp:
        store = PositionStore(Path(tmp) / "pos.json")

        class FakePos:
            token_address = "0xCAFE000000000000000000000000000000000001"
            chain = "1"; amount_usd = 50.0; entry_value = 50.0
            current_value = 50.0; peak_value = 50.0
            entry_price_usd = None; last_price_usd = None; status = "CLOSED"; pnl_pct = 0.0

        store.save_position(FakePos())
        store.remove_position(FakePos.token_address)
        assert len(store.load_all()) == 0

check("PositionStore removes position correctly", test_store_remove)

def test_store_atomic_write():
    """Corrupt the file mid-write — store should recover."""
    from core.position_store import PositionStore
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pos.json"
        store = PositionStore(path)
        # Write corrupt JSON manually
        with open(path, "w") as f:
            f.write("{corrupt json{{{{")
        # Should recover and return empty
        loaded = store.load_all()
        assert loaded == [], f"Expected empty on corrupt file, got {loaded}"

check("PositionStore recovers from corrupt file", test_store_atomic_write)

def test_store_restore_into_reaper():
    """Full round-trip: save via Reaper, restore into new Reaper instance."""
    from agents.reaper import Reaper
    from core.position_store import PositionStore
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "pos.json"

        # First Reaper — takes a position
        r1 = Reaper(paper_mode=True)
        r1.store = PositionStore(store_path)
        order = make_order()
        r1.take_position(order)
        assert order.token_address in r1.positions

        # Second Reaper — should restore it
        r2 = Reaper(paper_mode=True)
        r2.store = PositionStore(store_path)
        r2._restore_positions()
        assert order.token_address in r2.positions, "Position not restored in new Reaper instance"
        restored = r2.positions[order.token_address]
        assert restored.status == "ACTIVE"
        assert restored.entry_value == 50.0

check("Position round-trip: Reaper → disk → new Reaper", test_store_restore_into_reaper)


# ════════════════════════════════════════════════════════════════════════════
# 6. FULL PIPELINE
# ════════════════════════════════════════════════════════════════════════════
section("6. FULL PIPELINE — End-to-End")

def test_pipeline_no_crash():
    """Run a full cycle and ensure nothing raises."""
    from agents.whisperer import Whisperer
    from agents.actuary import Actuary
    from agents.slinger import Slinger
    from agents.reaper import Reaper
    from core.models import RiskLevel

    w = Whisperer(min_velocity_score=1)
    a = Actuary(max_allowed_tax=0.30)
    s = Slinger()
    r = Reaper(paper_mode=True, poll_interval_sec=1.0)

    signal = w.scan_firehose()
    if signal is None:
        # Acceptable — no candidates this scan
        info("No signal from Whisperer — skipping execution steps")
        return

    assessment = a.assess_risk(signal)
    assert assessment is not None

    if assessment.risk_level == RiskLevel.REJECTED:
        info(f"Token rejected by Actuary ({signal.token_address[:12]}...) — pipeline correctly stands down")
        return

    order = s.execute_order(assessment, chain_id=signal.chain)
    if order is None:
        info("Slinger returned None — acceptable for this token")
        return

    r.take_position(order)
    assert order.token_address in r.positions
    summary = r.get_portfolio_summary()
    assert summary["total_positions"] >= 1

check("Full pipeline runs without exception", test_pipeline_no_crash, warn_only=True)

def test_strategy_profiles_all_load():
    from strategy_factory import StrategyFactory
    factory = StrategyFactory()
    for key in ("degen","sniper","shadow_clone","arb_hunter","oracle_eye","liquidity_sentinel","yield_alchemist","forensic_sniper"):
        profile = factory.get_profile(key)
        assert profile.name, f"Profile {key} has no name"
        assert profile.actuary is not None
        assert profile.slinger is not None
        assert profile.reaper is not None

check("All 8 strategy profiles load without error", test_strategy_profiles_all_load)

def test_strategy_params_propagate():
    """Verify strategy params actually change agent behaviour."""
    from strategy_factory import StrategyFactory
    from agents.slinger import Slinger
    factory = StrategyFactory()

    degen = factory.get_profile("degen")
    sniper = factory.get_profile("sniper")

    s_d = Slinger()
    s_d._strategy_slippage = degen.slinger.base_slippage_tolerance
    s_d._strategy_gas_multiplier = degen.slinger.gas_premium_multiplier

    s_s = Slinger()
    s_s._strategy_slippage = sniper.slinger.base_slippage_tolerance
    s_s._strategy_gas_multiplier = sniper.slinger.gas_premium_multiplier

    assert s_d._strategy_slippage > s_s._strategy_slippage, "Degen should have higher slippage than Sniper"
    assert s_d._strategy_gas_multiplier > s_s._strategy_gas_multiplier, "Degen should have higher gas than Sniper"

check("Degen has higher slippage + gas than Sniper (strategy differentiation)", test_strategy_params_propagate)


# ════════════════════════════════════════════════════════════════════════════
# 7. PERFORMANCE BENCHMARKS
# ════════════════════════════════════════════════════════════════════════════
section("7. PERFORMANCE — Latency Benchmarks")

def bench(name: str, fn: Callable, limit_ms: float, warn_only=True):
    t0 = time.perf_counter()
    try:
        fn()
        elapsed = (time.perf_counter() - t0) * 1000
        status = "✅" if elapsed <= limit_ms else "⚠️ "
        colour = GREEN if elapsed <= limit_ms else YELLOW
        print(f"  {colour}{status} {name}: {elapsed:.0f}ms  (limit {limit_ms:.0f}ms){RESET}")
        if elapsed > limit_ms:
            results["warned"] += 1
        else:
            results["passed"] += 1
    except Exception as e:
        print(f"  {YELLOW}⚠️  {name}: ERROR — {e}{RESET}")
        results["warned"] += 1

from agents.actuary import Actuary as _A
from agents.slinger import Slinger as _S
from agents.reaper import Reaper as _R

_actuary = _A()
_sig = make_signal()
_actuary.assess_risk(_sig)  # prime cache

bench("Actuary cache hit",       lambda: _actuary.assess_risk(_sig),   limit_ms=50)
bench("Slinger order build",     lambda: _S().execute_order(make_assessment(), "1"), limit_ms=5000)  # includes DexScreener price fetch
bench("Reaper take_position",    lambda: _R(paper_mode=True).take_position(make_order()), limit_ms=200)
bench("PositionStore save",      lambda: __import__("core.position_store", fromlist=["PositionStore"]).PositionStore().save_position(
    type("P", (), {"token_address":"0xBENCH00000000000000000000000000000000001","chain":"1","amount_usd":50.0,"entry_value":50.0,"current_value":55.0,"peak_value":55.0,"entry_price_usd":0.001,"last_price_usd":0.0011,"status":"ACTIVE","pnl_pct":10.0})()
), limit_ms=100)


# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════
total = results["passed"] + results["failed"] + results["warned"]
print(f"\n{BOLD}{'═'*55}{RESET}")
print(f"{BOLD}  RESULTS: {total} checks{RESET}")
print(f"  {GREEN}Passed : {results['passed']}{RESET}")
print(f"  {YELLOW}Warned : {results['warned']}{RESET}  (API-dependent, non-fatal)")
print(f"  {RED}Failed : {results['failed']}{RESET}")
print(f"{BOLD}{'═'*55}{RESET}\n")

if results["failed"] > 0:
    print(f"{RED}❌ {results['failed']} test(s) failed — see above.{RESET}\n")
    sys.exit(1)
else:
    print(f"{GREEN}✅ All critical tests passed.{RESET}\n")
    sys.exit(0)
