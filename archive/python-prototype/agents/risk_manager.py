"""
Risk Manager - Portfolio-level risk management
==============================================
Manages:
1. Position sizing across portfolio
2. Correlation checks between positions
3. Daily/weekly loss limits
4. Circuit breakers for extreme volatility
"""
import json
import time
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from core.models import RiskAssessment, ExecutionOrder

logger = logging.getLogger("RiskManager")


class RiskLevel(Enum):
    GREEN = "GREEN"      # Normal operations
    YELLOW = "YELLOW"    # Elevated risk - reduce position sizes
    RED = "RED"          # High risk - pause new positions
    BLACK = "BLACK"      # Extreme risk - close all positions


@dataclass
class PortfolioMetrics:
    """Portfolio risk metrics."""
    total_value_usd: float = 0.0
    open_positions: int = 0
    max_drawdown_pct: float = 0.0
    daily_pnl_usd: float = 0.0
    daily_pnl_pct: float = 0.0
    weekly_pnl_usd: float = 0.0
    correlation_score: float = 0.0  # 0-1, higher = more correlated positions
    risk_level: RiskLevel = RiskLevel.GREEN


class RiskManager:
    """
    Manages portfolio-level risk for the Asymmetric Strike Team.
    """
    
    def __init__(self, 
                 max_portfolio_size_usd: float = 10000.0,
                 max_position_size_pct: float = 0.10,      # 10% max per position
                 max_daily_loss_pct: float = 0.05,         # 5% daily loss limit
                 max_correlation_threshold: float = 0.7,   # Reject if correlation > 0.7
                 circuit_breaker_volatility: float = 0.20  # 20% price move triggers pause
                 ):
        
        self.max_portfolio_size_usd = max_portfolio_size_usd
        self.max_position_size_pct = max_position_size_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_correlation_threshold = max_correlation_threshold
        self.circuit_breaker_volatility = circuit_breaker_volatility
        
        # State tracking
        self.open_positions: Dict[str, ExecutionOrder] = {}
        self.trade_history: List[Dict] = []
        self.daily_pnl: List[float] = []
        self.circuit_breaker_active = False
        self.circuit_breaker_until: Optional[float] = None
        
        # Load saved state if exists
        self._load_state()
    
    def can_open_position(self, 
                         assessment: RiskAssessment, 
                         proposed_order: ExecutionOrder,
                         market_volatility: float = 0.0) -> Tuple[bool, str]:
        """
        Check if a new position can be opened given current risk limits.
        
        Returns:
            (allowed: bool, reason: str)
        """
        print(f"🛡️  [Risk Manager] Evaluating position request...")
        
        # 1. Check circuit breaker
        if self.circuit_breaker_active:
            if self.circuit_breaker_until and time.time() < self.circuit_breaker_until:
                return False, "Circuit breaker active - trading paused"
            else:
                self.circuit_breaker_active = False
                self.circuit_breaker_until = None
        
        # 2. Check market volatility
        if market_volatility > self.circuit_breaker_volatility:
            self._activate_circuit_breaker(30 * 60)  # 30 minutes
            return False, f"Market volatility {market_volatility*100:.1f}% exceeds threshold"
        
        # 3. Check position size limit
        max_position_usd = self.max_portfolio_size_usd * self.max_position_size_pct
        if proposed_order.amount_usd > max_position_usd:
            return False, f"Position size ${proposed_order.amount_usd:.0f} exceeds ${max_position_usd:.0f} limit"
        
        # 4. Check daily loss limit
        daily_loss = self._calculate_daily_pnl()
        daily_loss_pct = abs(daily_loss) / self.max_portfolio_size_usd if daily_loss < 0 else 0
        if daily_loss_pct > self.max_daily_loss_pct:
            return False, f"Daily loss {daily_loss_pct*100:.1f}% exceeds {self.max_daily_loss_pct*100:.0f}% limit"
        
        # 5. Check portfolio concentration
        current_exposure = sum(pos.amount_usd for pos in self.open_positions.values())
        new_exposure = current_exposure + proposed_order.amount_usd
        if new_exposure > self.max_portfolio_size_usd:
            return False, f"Portfolio exposure ${new_exposure:.0f} exceeds ${self.max_portfolio_size_usd:.0f} limit"
        
        # 6. Check correlation with existing positions
        if self.open_positions:
            correlation = self._calculate_correlation(proposed_order)
            if correlation > self.max_correlation_threshold:
                return False, f"Correlation {correlation:.2f} exceeds {self.max_correlation_threshold:.1f} threshold"
        
        # 7. Check maximum open positions
        max_positions = 5  # Arbitrary limit
        if len(self.open_positions) >= max_positions:
            return False, f"Maximum {max_positions} open positions reached"
        
        print(f"   ✅ Position approved")
        print(f"   Size: ${proposed_order.amount_usd:.0f} ({proposed_order.amount_usd/self.max_portfolio_size_usd*100:.1f}% of portfolio)")
        return True, "Position approved"
    
    def register_position(self, order: ExecutionOrder):
        """Register a new open position."""
        position_id = f"{order.token_address[:8]}_{int(time.time())}"
        self.open_positions[position_id] = order
        
        # Record trade
        trade_record = {
            "id": position_id,
            "timestamp": time.time(),
            "token": order.token_address,
            "chain": order.chain,
            "amount_usd": order.amount_usd,
            "action": order.action,
            "entry_price": order.entry_price_usd,
            "is_cex": order.is_cex
        }
        self.trade_history.append(trade_record)
        
        print(f"🛡️  [Risk Manager] Position registered: {position_id}")
        print(f"   Open positions: {len(self.open_positions)}")
        print(f"   Total exposure: ${self._calculate_total_exposure():.0f}")
        
        self._save_state()
    
    def close_position(self, position_id: str, exit_price: float, pnl_usd: float):
        """Close a position and record P&L."""
        if position_id in self.open_positions:
            order = self.open_positions.pop(position_id)
            
            # Update trade record
            for trade in self.trade_history:
                if trade.get("id") == position_id:
                    trade["exit_timestamp"] = time.time()
                    trade["exit_price"] = exit_price
                    trade["pnl_usd"] = pnl_usd
                    trade["pnl_pct"] = (pnl_usd / order.amount_usd) * 100 if order.amount_usd > 0 else 0
                    break
            
            # Record daily P&L
            self.daily_pnl.append(pnl_usd)
            
            print(f"🛡️  [Risk Manager] Position closed: {position_id}")
            print(f"   P&L: ${pnl_usd:+.2f} ({pnl_usd/order.amount_usd*100:+.1f}%)")
            
            self._save_state()
    
    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate current portfolio metrics."""
        total_exposure = self._calculate_total_exposure()
        daily_pnl = self._calculate_daily_pnl()
        correlation = self._calculate_portfolio_correlation()
        
        # Determine risk level
        risk_level = self._determine_risk_level(daily_pnl, correlation)
        
        return PortfolioMetrics(
            total_value_usd=total_exposure,
            open_positions=len(self.open_positions),
            max_drawdown_pct=self._calculate_max_drawdown(),
            daily_pnl_usd=daily_pnl,
            daily_pnl_pct=(daily_pnl / self.max_portfolio_size_usd) * 100 if self.max_portfolio_size_usd > 0 else 0,
            weekly_pnl_usd=self._calculate_weekly_pnl(),
            correlation_score=correlation,
            risk_level=risk_level
        )
    
    def _calculate_total_exposure(self) -> float:
        """Calculate total USD exposure across all positions."""
        return sum(pos.amount_usd for pos in self.open_positions.values())
    
    def _calculate_daily_pnl(self) -> float:
        """Calculate P&L for the current day."""
        today = datetime.now().date()
        daily_trades = [
            pnl for pnl in self.daily_pnl 
            if datetime.fromtimestamp(time.time() - (len(self.daily_pnl) - i) * 86400).date() == today
        ]
        return sum(daily_trades)
    
    def _calculate_weekly_pnl(self) -> float:
        """Calculate P&L for the current week."""
        week_ago = time.time() - 7 * 86400
        weekly_trades = [pnl for pnl in self.daily_pnl if time.time() - (len(self.daily_pnl) - i) * 86400 > week_ago]
        return sum(weekly_trades)
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from trade history."""
        if not self.daily_pnl:
            return 0.0
        
        peak = 0
        max_dd = 0
        running_total = 0
        
        for pnl in self.daily_pnl:
            running_total += pnl
            if running_total > peak:
                peak = running_total
            dd = (peak - running_total) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        return max_dd * 100  # Return as percentage
    
    def _calculate_correlation(self, new_order: ExecutionOrder) -> float:
        """
        Calculate correlation between new position and existing positions.
        Simplified heuristic based on token type and chain.
        """
        if not self.open_positions:
            return 0.0
        
        # Heuristic: Positions in same chain are more correlated
        same_chain_count = sum(
            1 for pos in self.open_positions.values() 
            if pos.chain == new_order.chain
        )
        
        # Heuristic: Similar token types are more correlated
        # (This is simplified - real implementation would use price data)
        total_positions = len(self.open_positions)
        
        # Weighted correlation score
        chain_correlation = same_chain_count / total_positions if total_positions > 0 else 0
        return min(chain_correlation + 0.2, 1.0)  # Add some base correlation
    
    def _calculate_portfolio_correlation(self) -> float:
        """Calculate overall portfolio correlation."""
        if len(self.open_positions) <= 1:
            return 0.0
        
        # Simplified: count positions on same chain
        chains = [pos.chain for pos in self.open_positions.values()]
        unique_chains = set(chains)
        
        # More concentrated = higher correlation
        concentration = 1 - (len(unique_chains) / len(chains))
        return concentration
    
    def _determine_risk_level(self, daily_pnl: float, correlation: float) -> RiskLevel:
        """Determine current risk level based on metrics."""
        daily_loss_pct = abs(daily_pnl) / self.max_portfolio_size_usd if daily_pnl < 0 else 0
        
        if daily_loss_pct > self.max_daily_loss_pct * 0.8:  # 80% of limit
            return RiskLevel.RED
        elif daily_loss_pct > self.max_daily_loss_pct * 0.5:  # 50% of limit
            return RiskLevel.YELLOW
        elif correlation > self.max_correlation_threshold * 0.8:
            return RiskLevel.YELLOW
        else:
            return RiskLevel.GREEN
    
    def _activate_circuit_breaker(self, duration_seconds: int):
        """Activate circuit breaker to pause trading."""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = time.time() + duration_seconds
        print(f"🛡️  [Risk Manager] ⚡ CIRCUIT BREAKER ACTIVATED")
        print(f"   Trading paused for {duration_seconds/60:.0f} minutes")
    
    def _save_state(self):
        """Save risk manager state to disk."""
        state = {
            "open_positions": {
                pid: {
                    "token": pos.token_address,
                    "chain": pos.chain,
                    "amount_usd": pos.amount_usd,
                    "action": pos.action,
                    "entry_price": pos.entry_price_usd,
                    "timestamp": time.time()
                }
                for pid, pos in self.open_positions.items()
            },
            "trade_history": self.trade_history[-100:],  # Keep last 100 trades
            "daily_pnl": self.daily_pnl[-30:],  # Keep last 30 days
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_until": self.circuit_breaker_until
        }
        
        try:
            with open("risk_manager_state.json", "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save risk manager state: {e}")
    
    def _load_state(self):
        """Load risk manager state from disk."""
        try:
            with open("risk_manager_state.json", "r") as f:
                state = json.load(f)
                
            # Load open positions (simplified - would need full ExecutionOrder reconstruction)
            self.trade_history = state.get("trade_history", [])
            self.daily_pnl = state.get("daily_pnl", [])
            self.circuit_breaker_active = state.get("circuit_breaker_active", False)
            self.circuit_breaker_until = state.get("circuit_breaker_until")
            
            print(f"🛡️  [Risk Manager] Loaded {len(self.trade_history)} historical trades")
            
        except FileNotFoundError:
            print("🛡️  [Risk Manager] No saved state found - starting fresh")
        except Exception as e:
            logger.error(f"Failed to load risk manager state: {e}")
    
    def print_status(self):
        """Print current risk status."""
        metrics = self.get_portfolio_metrics()
        
        print("\n" + "=" * 60)
        print("🛡️  RISK MANAGER STATUS")
        print("=" * 60)
        print(f"Risk Level: {metrics.risk_level.value}")
        print(f"Open Positions: {metrics.open_positions}")
        print(f"Total Exposure: ${metrics.total_value_usd:.0f}")
        print(f"Daily P&L: ${metrics.daily_pnl_usd:+.2f} ({metrics.daily_pnl_pct:+.1f}%)")
        print(f"Max Drawdown: {metrics.max_drawdown_pct:.1f}%")
        print(f"Portfolio Correlation: {metrics.correlation_score:.2f}")
        
        if self.circuit_breaker_active:
            remaining = (self.circuit_breaker_until - time.time()) / 60 if self.circuit_breaker_until else 0
            print(f"⚡ CIRCUIT BREAKER: Active ({remaining:.0f} min remaining)")
        
        print("=" * 60)


if __name__ == "__main__":
    # Test the Risk Manager
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Risk Manager...")
    
    risk_manager = RiskManager(
        max_portfolio_size_usd=10000.0,
        max_position_size_pct=0.10,
        max_daily_loss_pct=0.05,
        max_correlation_threshold=0.7
    )
    
    # Create test orders
    from core.models import ExecutionOrder
    
    test_order1 = ExecutionOrder(
        token_address="0x123...BTC",
        chain="cex",
        action="BUY",
        amount_usd=500.0,
        slippage_tolerance=0.15,
        gas_premium_gwei=0.0,
        entry_price_usd=50000.0
    )
    
    test_order2 = ExecutionOrder(
        token_address="0x456...ETH",
        chain="cex",
        action="BUY",
        amount_usd=800.0,
        slippage_tolerance=0.15,
        gas_premium_gwei=0.0,
        entry_price_usd=3000.0
    )
    
    test_order3 = ExecutionOrder(
        token_address="0x789...DEX",
        chain="56",
        action="BUY",
        amount_usd=300.0,
        slippage_tolerance=0.15,
        gas_premium_gwei=45.0,
        entry_price_usd=0.01
    )
    
    # Test position approval
    from core.models import RiskAssessment, RiskLevel
    
    test_assessment = RiskAssessment(
        token_address="0x123...BTC",
        is_honeypot=False,
        buy_tax=0.0,
        sell_tax=0.0,
        liquidity_locked=True,
        risk_level=RiskLevel.MEDIUM,
        max_allocation_usd=1000.0,
        warnings=[]
    )
