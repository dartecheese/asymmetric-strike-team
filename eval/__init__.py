"""AST evaluation harness.

Answers the single question TradingAgents-shaped projects routinely fail to
answer: did this actually work?

The harness reads file-backed lab state under data/ and produces an honest
summary report (Sharpe / max drawdown / total return / fees / per-strategy
breakdown, vs a buy-and-hold ETH benchmark over the same window).

Nothing here writes back to data/ — it's strictly a read-only summarizer.
"""

from .metrics import equity_metrics, returns_from_equity
from .portfolio import load_portfolio_curve, PortfolioPoint
from .strategy import per_strategy_stats, StrategyStats
from .benchmark import eth_buy_and_hold

__all__ = [
    "equity_metrics",
    "returns_from_equity",
    "load_portfolio_curve",
    "PortfolioPoint",
    "per_strategy_stats",
    "StrategyStats",
    "eth_buy_and_hold",
]
