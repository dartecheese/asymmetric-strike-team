"""Render eval results to markdown and JSON.

The markdown is the artifact you read; the JSON is the artifact you diff
across runs to spot regressions. Both go to eval_results/.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc(ts_ms: int) -> str:
    if not ts_ms:
        return "—"
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h or d:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def _signed_pct(v: float) -> str:
    return f"{v:+.2f}%"


def _collect_warnings(metrics, points, benchmark) -> list[str]:
    """Surface honest findings rather than burying them in metric tables."""
    out: list[str] = []

    if metrics.n_points > 100 and metrics.realized_pnl_usd == 0:
        out.append(
            "No realized PnL recorded in this window — the lab is opening positions "
            "but not closing them. Sharpe and max drawdown below are mark-to-market "
            "only; they will move when positions actually close."
        )

    if points:
        n_neg = sum(1 for p in points if p.equity_usd < 0)
        if n_neg:
            min_eq = min(p.equity_usd for p in points)
            pct = n_neg / len(points) * 100.0
            out.append(
                f"Equity went negative on {n_neg:,}/{len(points):,} ticks ({pct:.1f}%), "
                f"min ${min_eq:,.2f}. Paper trading on a positive cash balance should "
                "never produce negative equity — this is a mark-to-market or accounting "
                "bug (likely a wild DexScreener tick on an illiquid pool). The "
                f"{metrics.max_drawdown_pct:.0f}% max drawdown is mathematically correct "
                "but reflects that bug, not real risk."
            )

    if benchmark is not None and benchmark.stale_reason:
        out.append(
            f"ETH benchmark unreliable: {benchmark.stale_reason}. The reported "
            f"return ({benchmark.return_pct:+.2f}%) is computed against edge prices "
            "and should not be trusted; refresh the OHLCV cache to fix."
        )

    return out


def render_markdown(metrics, strategies, benchmark, generated_at_ms: int,
                    points=None, start_ts_ms: int = 0,
                    end_ts_ms: int = 0) -> str:
    lines = []
    lines.append(f"# AST eval — {_utc(generated_at_ms)}")
    lines.append("")

    if metrics.n_points == 0:
        lines.append("> **No portfolio data found.** `data/learning/portfolio.jsonl` is empty.")
        lines.append("> Run grind for a while and try again.")
        lines.append("")
        return "\n".join(lines)

    # Headline
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- **Window:** {_utc(start_ts_ms)}  →  {_utc(end_ts_ms)}  ({_fmt_duration(metrics.duration_seconds)})")
    lines.append(f"- **Equity:** ${metrics.start_equity:,.2f}  →  ${metrics.end_equity:,.2f}  ({_signed_pct(metrics.total_return_pct)})")
    lines.append(f"- **Realized PnL:** ${metrics.realized_pnl_usd:+,.2f}")
    lines.append(f"- **Unrealized PnL:** ${metrics.unrealized_pnl_usd:+,.2f}")
    lines.append(f"- **Fees paid:** ${metrics.fees_paid_usd:,.2f}")
    lines.append(f"- **Sharpe (annualized):** {metrics.sharpe_annualized:.2f}")
    lines.append(f"- **Max drawdown:** {metrics.max_drawdown_pct:.2f}%  (at {_utc(metrics.max_drawdown_at_ts_ms)})")
    lines.append(f"- **CAGR (extrapolated, fragile if window <30d):** {_signed_pct(metrics.cagr_pct)}")
    lines.append("")

    # Warnings — surface the truth before anyone reads the metrics.
    warnings = _collect_warnings(metrics, points or [], benchmark)
    if warnings:
        lines.append("## Warnings — read first")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Benchmark
    lines.append("## Benchmark — ETH buy-and-hold (same window)")
    lines.append("")
    if benchmark is None:
        lines.append("ETH OHLCV not available. Skipped.")
    elif benchmark.stale_reason:
        lines.append(f"Skipped: {benchmark.stale_reason}.")
        lines.append(f"- OHLCV coverage: {_utc(benchmark.ohlcv_first_ts_ms)} → {_utc(benchmark.ohlcv_last_ts_ms)}")
        lines.append(f"- Eval window:    {_utc(benchmark.eval_first_ts_ms)} → {_utc(benchmark.eval_last_ts_ms)}")
    else:
        delta = metrics.total_return_pct - benchmark.return_pct
        verdict = "**beats**" if delta > 0 else ("**lags**" if delta < 0 else "matches")
        lines.append(f"- ETH return: {_signed_pct(benchmark.return_pct)}  "
                     f"(${benchmark.start_price_usd:,.2f} → ${benchmark.end_price_usd:,.2f})")
        lines.append(f"- AST return: {_signed_pct(metrics.total_return_pct)}")
        lines.append(f"- AST {verdict} ETH by {_signed_pct(delta)}.")
        if benchmark.coverage_ratio < 0.95:
            lines.append(f"- ⚠ OHLCV covers only {benchmark.coverage_ratio:.0%} of the window.")
    lines.append("")

    # Per-strategy
    lines.append("## Per-strategy activity")
    lines.append("")
    lines.append("| Strategy | Signals | Risk checks | Fills | Orders | Safety blocks | Notional executed | Fees | Avg slippage |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in strategies:
        lines.append(
            f"| {s.name} | {s.signals:,} | {s.risk_checks:,} | {s.fills:,} | {s.orders:,} | "
            f"{s.safety_blocks:,} | ${s.total_executed_notional_usd:,.0f} | "
            f"${s.total_fees_usd:,.2f} | {s.avg_slippage_bps:.0f} bps |"
        )
    lines.append("")

    return "\n".join(lines)


def to_json_payload(metrics, strategies, benchmark, generated_at_ms: int) -> dict:
    def dc(x):
        if x is None:
            return None
        if is_dataclass(x):
            return asdict(x)
        return x
    return {
        "generated_at_ms": generated_at_ms,
        "metrics": dc(metrics),
        "strategies": [dc(s) for s in strategies],
        "benchmark": dc(benchmark),
    }


def write_report(out_dir: Path, metrics, strategies, benchmark,
                 generated_at_ms: int, points=None,
                 start_ts_ms: int = 0, end_ts_ms: int = 0) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_label = datetime.fromtimestamp(generated_at_ms / 1000.0, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md_path = out_dir / f"eval_{ts_label}.md"
    json_path = out_dir / f"eval_{ts_label}.json"

    md_path.write_text(render_markdown(metrics, strategies, benchmark,
                                       generated_at_ms, points=points,
                                       start_ts_ms=start_ts_ms,
                                       end_ts_ms=end_ts_ms))
    json_path.write_text(json.dumps(
        to_json_payload(metrics, strategies, benchmark, generated_at_ms),
        indent=2,
    ))
    return md_path, json_path
