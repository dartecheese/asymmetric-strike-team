#!/usr/bin/env python3
"""Refresh OHLCV cache from GeckoTerminal — currently only WETH on Base.

The eval harness's ETH buy-and-hold benchmark requires fresh WETH OHLCV in
data/ohlcv/. The original AST loader that wrote these files no longer exists
in the repo, so this script fills the gap.

Output schema matches the existing files:
  {
    "token": "<full address>",
    "chain": "base",
    "pool": "<pool address>",
    "ohlcv": [[ts_seconds, open, high, low, close, volume], ...]
  }

GeckoTerminal is free, rate-limited to ~30 req/min, no auth required. We fetch
hour bars and write 720 of them (30 days). If you want different tokens, add
entries to TARGETS below.

Usage:
    python bin/refresh_ohlcv.py
    python bin/refresh_ohlcv.py --limit 240   # 10 days of hourly bars
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA_DIR = Path(os.environ.get("AST_DATA_DIR", "data"))
OHLCV_DIR = DATA_DIR / "ohlcv"

# token_address (full), chain, pool_address (where price is most liquid)
TARGETS = [
    {
        "token": "0x4200000000000000000000000000000000000006",  # WETH on Base
        "chain": "base",
        "pool": "0x6c561b446416e1a00e8e93e221854d6ea4171372",   # WETH/USDC Uniswap v3 pool
        "label": "WETH/USDC (Base)",
    },
]

API = "https://api.geckoterminal.com/api/v2"
UA = "ast-eval-refresh/0.1"


def _fetch(network: str, pool: str, limit: int) -> list[list[float]] | None:
    url = f"{API}/networks/{network}/pools/{pool}/ohlcv/hour?aggregate=1&limit={limit}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            blob = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"[refresh_ohlcv] ERROR fetching {pool}: {e}", file=sys.stderr)
        return None

    bars = (blob.get("data") or {}).get("attributes", {}).get("ohlcv_list") or []
    # GeckoTerminal returns newest first; flip to ascending and coerce to float.
    parsed = []
    for b in reversed(bars):
        if not isinstance(b, list) or len(b) < 6:
            continue
        try:
            parsed.append([
                int(b[0]),
                float(b[1]), float(b[2]), float(b[3]), float(b[4]),
                float(b[5]),
            ])
        except (TypeError, ValueError):
            continue
    return parsed


def _short_filename(token: str, chain: str) -> str:
    # Existing files use chain_0x + first10hex.json (e.g. base_0x4200000000.json).
    # token comes in as "0x42...", so we slice the first 12 chars to keep "0x" + 10 hex.
    return f"{chain}_{token[:12].lower()}.json"


def main() -> int:
    p = argparse.ArgumentParser(description="Refresh OHLCV cache from GeckoTerminal")
    p.add_argument("--limit", type=int, default=720,
                   help="number of hourly bars to fetch (default 720 = 30 days)")
    p.add_argument("--target", action="append",
                   help="token symbol substring to limit (default: all targets)")
    args = p.parse_args()

    OHLCV_DIR.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    n_fail = 0
    for t in TARGETS:
        if args.target and not any(s.lower() in t["label"].lower() for s in args.target):
            continue
        print(f"[refresh_ohlcv] fetching {t['label']}: {t['chain']}:{t['pool']}",
              file=sys.stderr)
        bars = _fetch(t["chain"], t["pool"], args.limit)
        if not bars:
            n_fail += 1
            continue
        out_path = OHLCV_DIR / _short_filename(t["token"], t["chain"])
        payload = {
            "token": t["token"],
            "chain": t["chain"],
            "pool": t["pool"],
            "ohlcv": bars,
            "refreshed_at_ms": int(time.time() * 1000),
            "source": "geckoterminal",
        }
        out_path.write_text(json.dumps(payload, separators=(",", ":")))
        n_ok += 1
        first = bars[0][0] if bars else 0
        last = bars[-1][0] if bars else 0
        print(f"[refresh_ohlcv]   wrote {out_path}  ({len(bars)} bars, {first}→{last})",
              file=sys.stderr)
        time.sleep(2.0)  # be nice to the free tier

    print(f"[refresh_ohlcv] done — {n_ok} ok, {n_fail} failed", file=sys.stderr)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
