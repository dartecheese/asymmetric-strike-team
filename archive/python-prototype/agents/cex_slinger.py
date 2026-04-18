"""
CEX Slinger - Centralized Exchange Execution Module
===================================================
Uses CCXT for Binance, Bybit, OKX, etc. execution.
Works alongside the existing Web3 Slinger for DEX execution.
"""
import os
import ccxt
import logging
from typing import Optional, Dict, Any
from core.models import RiskAssessment, ExecutionOrder

logger = logging.getLogger("CEXSlinger")

class CEXSlinger:
    """
    CEX Slinger: Centralized exchange execution via CCXT.
    Supports spot and futures trading on 100+ exchanges.
    """
    
    def __init__(self, exchange_id: str = "binance", account_name: str = "default"):
        """
        Initialize CCXT exchange instance.
        
        Args:
            exchange_id: CCXT exchange id (binance, bybit, okx, etc.)
            account_name: Name for this account config (for multiple accounts)
        """
        self.exchange_id = exchange_id
        self.account_name = account_name
        
        # Load API keys from environment
        api_key = os.getenv(f"{exchange_id.upper()}_{account_name.upper()}_API_KEY")
        api_secret = os.getenv(f"{exchange_id.upper()}_{account_name.upper()}_SECRET")
        
        if not api_key or not api_secret:
            logger.warning(f"No API keys found for {exchange_id}/{account_name} - paper mode only")
            self.paper_mode = True
            self.exchange = None
        else:
            self.paper_mode = False
            exchange_class = getattr(ccxt, exchange_id)
            self.exchange = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',  # or 'future', 'swap'
                }
            })
            
            # Test connection
            try:
                self.exchange.load_markets()
                logger.info(f"Connected to {exchange_id} ({len(self.exchange.markets)} markets)")
            except Exception as e:
                logger.error(f"Failed to connect to {exchange_id}: {e}")
                self.exchange = None
                self.paper_mode = True
        
        # Strategy params (set by main.py like Web3 Slinger)
        self._strategy_slippage = 0.15
        self._strategy_gas_multiplier = 1.5  # Not used for CEX, but kept for consistency
        
    def execute_order(self, assessment: RiskAssessment, symbol: str = "BTC/USDT") -> Optional[ExecutionOrder]:
        """
        Execute order on CEX.
        
        Args:
            assessment: RiskAssessment from Actuary
            symbol: Trading pair symbol (e.g., "BTC/USDT", "ETH/USDT")
            
        Returns:
            ExecutionOrder if successful, None otherwise
        """
        if self.paper_mode or not self.exchange:
            print(f"🔫 [CEX Slinger] Paper mode - would execute on {self.exchange_id}")
            print(f"   Symbol: {symbol} | Amount: ${assessment.max_allocation_usd}")
            print(f"   Slippage tolerance: {self._strategy_slippage*100:.1f}%")
            
            # Return paper order
            try:
                return ExecutionOrder(
                    token_address=f"CEX:{symbol}",
                    chain="cex",
                    action="BUY",
                    amount_usd=assessment.max_allocation_usd,
                    slippage_tolerance=self._strategy_slippage,
                    gas_premium_gwei=0.0,  # CEX doesn't use gas
                    entry_price_usd=None,  # No price in paper mode
                )
            except Exception as e:
                print(f"🔫 [CEX Slinger] Failed to create paper order: {e}")
                return None
        
        # Real execution
        print(f"🔫 [CEX Slinger] Executing on {self.exchange_id}...")
        print(f"   Symbol: {symbol} | Amount: ${assessment.max_allocation_usd}")
        
        try:
            # Get current price for entry price recording
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # Calculate position size
            amount_usd = assessment.max_allocation_usd
            amount_base = amount_usd / current_price
            
            # Apply slippage tolerance to limit price
            limit_price = current_price * (1 + self._strategy_slippage)
            
            print(f"   Current price: ${current_price:.2f}")
            print(f"   Limit price: ${limit_price:.2f} (+{self._strategy_slippage*100:.1f}%)")
            print(f"   Amount: {amount_base:.6f} {symbol.split('/')[0]}")
            
            # Place limit order
            # In production, we might use market order with slippage control
            # or limit order with good-till-canceled
            order = self.exchange.create_limit_buy_order(
                symbol=symbol,
                amount=amount_base,
                price=limit_price
            )
            
            print(f"   Order placed: {order['id']}")
            print(f"   Status: {order['status']}")
            
            return ExecutionOrder(
                token_address=f"CEX:{symbol}:{order['id']}",
                chain="cex",
                action="BUY",
                amount_usd=amount_usd,
                slippage_tolerance=self._strategy_slippage,
                gas_premium_gwei=0,
                entry_price_usd=current_price,
                tx_hash=order['id']
            )
            
        except Exception as e:
            print(f"🔫 [CEX Slinger] Execution failed: {e}")
            return None
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from exchange."""
        try:
            if self.exchange:
                ticker = self.exchange.fetch_ticker(symbol)
                return ticker['last']
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
        return None
    
    def get_balance(self) -> Dict[str, float]:
        """Get account balances."""
        if self.paper_mode or not self.exchange:
            return {"USDT": 10000.0, "BTC": 0.0}  # Paper balances
        
        try:
            balance = self.exchange.fetch_balance()
            free_balances = {}
            for currency, info in balance['free'].items():
                if info > 0.001:  # Only show non-trivial balances
                    free_balances[currency] = info
            return free_balances
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return {}


if __name__ == "__main__":
    # Test the CEX Slinger
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Testing CEX Slinger...")
    
    # Create a mock assessment
    from core.models import RiskAssessment, RiskLevel
    
    mock_assessment = RiskAssessment(
        token_address="BTC",
        is_honeypot=False,
        buy_tax=0.0,
        sell_tax=0.0,
        liquidity_locked=True,
        risk_level=RiskLevel.MEDIUM,
        max_allocation_usd=100.0,
        warnings=[]
    )
    
    # Test with paper mode (no API keys)
    slinger = CEXSlinger(exchange_id="binance", account_name="test")
    order = slinger.execute_order(mock_assessment, symbol="BTC/USDT")
    
    if order:
        print(f"\n✅ Order created:")
        print(f"   Token: {order.token_address}")
        print(f"   Amount: ${order.amount_usd}")
        print(f"   Action: {order.action}")
    else:
        print("\n❌ Failed to create order")