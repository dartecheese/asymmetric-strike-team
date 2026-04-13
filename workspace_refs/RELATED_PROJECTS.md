# Related Asymmetric Strike Team Projects

## Main workspace repo
- `../asymmetric_trading` - primary Python DeFi trading bot and active workspace

## Dedicated sibling project folder
- `../asymmetric_projects/asymmetric-strike-team-mcp` - MCP-focused variant / parallel implementation
- `../asymmetric_projects/asymmetric-strike-team-rust` - Rust rewrite and performance experiments

## Guidance
- Treat `asymmetric_trading` as the main working repo.
- Treat `asymmetric_projects/` as the home for alternate implementations.
- Borrow code or docs from sibling repos deliberately, not by accidental duplication.
- Before porting features from MCP or Rust variants, compare interfaces and update docs in `docs/`.
