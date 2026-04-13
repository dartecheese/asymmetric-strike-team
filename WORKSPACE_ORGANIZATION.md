# Asymmetric Trading Workspace Organization

## Purpose
This repo is the main working home for the Asymmetric Strike Team Python system.

## Layout
- `agents/`, `core/`, `execution/`, `optimized/`, `visualization/`: source code
- `data/`: runtime state and persisted data
- `logs/`, `monitoring_reports/`, `test_results/`: generated artifacts kept in place for compatibility
- `docs/guides/`: setup, MCP, execution, deployment, whitepaper-style docs
- `docs/plans/`: future plans, rewrite plans, optimization plans, testing plans
- `docs/validation/`: validation docs and checklists
- `docs/performance/`: analysis and benchmark notes
- `docs/visualization/`: visualization-specific docs
- `docs/reports/`: status reports and milestone summaries
- `scripts/run/`: launch, setup, demo, and monitoring scripts
- `results/logs/`, `results/tests/`: moved top-level generated outputs
- `workspace_refs/RELATED_PROJECTS.md`: pointers to sibling MCP and Rust repos

## Notes
- This reorg is intentionally non-destructive.
- Core imports and package structure were left intact.
- Existing subdirectories like `logs/`, `monitoring_reports/`, and `test_results/` were preserved.
- If any script assumed old top-level doc paths, update it to the new `docs/...` paths.
