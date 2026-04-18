"""
Simple Performance Tracker for 48-hour test
"""
import json
import time
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class TradeOutcome(Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    OPEN = "OPEN"
    BREAKEVEN = "BREAKEVEN"


@dataclass
class SimpleTradeRecord:
    """Simple trade record."""
    trade_id: str
    timestamp: float
    strategy: str
    token_address: str
    chain: str
    venue: str
    amount_usd: float
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    outcome: TradeOutcome = TradeOutcome.OPEN


class SimplePerformanceTracker:
    """Simple performance tracker for testing."""
    
    def __init__(self):
        self.trades: List[SimpleTradeRecord] = []
        self.file_path = "simple_performance.json"
        self._load()
    
    def record_trade(self, trade: SimpleTradeRecord):
        """Record a trade."""
        self.trades.append(trade)
        self._save()
        print(f"📊 [Performance] Trade recorded: {trade.trade_id} | ${trade.amount_usd:.0f}")
    
    def record_trade_exit(self, trade_id: str, pnl_usd: float, pnl_pct: float):
        """Record trade exit."""
        for trade in self.trades:
            if trade.trade_id == trade_id:
                trade.pnl_usd = pnl_usd
                trade.pnl_pct = pnl_pct
                trade.outcome = TradeOutcome.WIN if pnl_usd > 0 else TradeOutcome.LOSS if pnl_usd < 0 else TradeOutcome.BREAKEVEN
                self._save()
                print(f"📊 [Performance] Trade exit: {trade_id} | P&L: ${pnl_usd:+.2f} ({pnl_pct:+.1f}%)")
                return
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if not self.trades:
            return {}
        
        closed_trades = [t for t in self.trades if t.outcome != TradeOutcome.OPEN]
        winning_trades = [t for t in closed_trades if t.outcome == TradeOutcome.WIN]
        losing_trades = [t for t in closed_trades if t.outcome == TradeOutcome.LOSS]
        
        total_trades = len(closed_trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        total_pnl = sum(t.pnl_usd for t in closed_trades)
        
        return {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate * 100,
            "total_pnl_usd": total_pnl,
            "avg_win_usd": sum(t.pnl_usd for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            "avg_loss_usd": sum(t.pnl_usd for t in losing_trades) / len(losing_trades) if losing_trades else 0,
        }
    
    def print_report(self):
        """Print performance report."""
        metrics = self.get_metrics()
        
        if not metrics:
            print("📊 [Performance] No trades recorded yet")
            return
        
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE REPORT")
        print("=" * 60)
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Winning Trades: {metrics['winning_trades']}")
        print(f"Losing Trades: {metrics['losing_trades']}")
        print(f"Win Rate: {metrics['win_rate']:.1f}%")
        print(f"Total P&L: ${metrics['total_pnl_usd']:+.2f}")
        print(f"Average Win: ${metrics['avg_win_usd']:+.2f}")
        print(f"Average Loss: ${metrics['avg_loss_usd']:.2f}")
        print("=" * 60)
    
    def _save(self):
        """Save trades to file."""
        data = {
            "trades": [
                {
                    "trade_id": t.trade_id,
                    "timestamp": t.timestamp,
                    "strategy": t.strategy,
                    "token_address": t.token_address,
                    "chain": t.chain,
                    "venue": t.venue,
                    "amount_usd": t.amount_usd,
                    "pnl_usd": t.pnl_usd,
                    "pnl_pct": t.pnl_pct,
                    "outcome": t.outcome.value
                }
                for t in self.trades
            ]
        }
        
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load(self):
        """Load trades from file."""
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            
            self.trades = [
                SimpleTradeRecord(
                    trade_id=t["trade_id"],
                    timestamp=t["timestamp"],
                    strategy=t["strategy"],
                    token_address=t["token_address"],
                    chain=t["chain"],
                    venue=t["venue"],
                    amount_usd=t["amount_usd"],
                    pnl_usd=t["pnl_usd"],
                    pnl_pct=t["pnl_pct"],
                    outcome=TradeOutcome(t["outcome"])
                )
                for t in data.get("trades", [])
            ]
            
            print(f"📊 [Performance] Loaded {len(self.trades)} historical trades")
        except FileNotFoundError:
            print("📊 [Performance] No previous performance data found")
        except Exception as e:
            print(f"📊 [Performance] Error loading data: {e}")