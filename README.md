# Asymmetric Strike Team

Primary workspace for the Python-based Asymmetric Strike Team DeFi trading bot.

## What this repo is
- Main active Python implementation
- Home for agent pipeline work, dashboard work, validation, and execution integration
- Canonical workspace among related sibling repos in this workspace

## Related repos in the same workspace
- `../asymmetric-strike-team-mcp` - MCP-oriented sibling implementation
- `../asymmetric-strike-team-rust` - Rust rewrite / performance branch

See `workspace_refs/RELATED_PROJECTS.md` for guidance.

## Workspace layout
- `agents/`, `core/`, `execution/`, `optimized/`, `visualization/` - source code
- `data/` - runtime state
- `logs/`, `monitoring_reports/`, `test_results/` - generated artifacts retained for compatibility
- `docs/` - organized documentation, plans, reports, validation, guides
- `scripts/run/` - launch and operational scripts
- `results/` - top-level result artifacts moved out of root clutter

See `WORKSPACE_ORGANIZATION.md` for the current layout.

## Quick start
```bash
cd asymmetric_trading
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Dashboard
```bash
cd asymmetric_trading
./scripts/run/start_nlp_dashboard.sh
```
Then open `http://127.0.0.1:5055`

## Important note
This repo was reorganized to reduce root clutter. Documentation and operational scripts now live in grouped folders instead of the repo root.
