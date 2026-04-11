"""
Unified Slinger Agent - Switches between real and paper execution based on environment.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

try:
    from core.models import ExecutionOrder
    from strategy_factory import SlingerConfig
except ImportError:
    # Fallback for standalone testing
    from pydantic import BaseModel
    
    class ExecutionOrder(BaseModel):
        token_address: str
        action: str
        amount_usd: float
        slippage_tolerance: float
        gas_premium_gwei: float
        
    class SlingerConfig(BaseModel):
        use_private_mempool: bool = False
        base_slippage_tolerance: float = 0.15
        gas_premium_multiplier: float = 1.5

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnifiedSlinger")

class UnifiedSlingerAgent:
    """
    Unified execution agent that automatically switches between:
    - Real Web3.py execution (when USE_REAL_EXECUTION=true)
    - Paper trading simulation (default)
    """
    def __init__(self, config: SlingerConfig):
        self.config = config
        self.use_real = os.getenv("USE_REAL_EXECUTION", "false").lower() == "true"
        self.rpc_url = os.getenv("ETH_RPC_URL")
        self.private_key = os.getenv("PRIVATE_KEY")
        
        if self.use_real and self.rpc_url and self.private_key:
            logger.info("🚀 Initializing REAL execution mode")
            try:
                from execution.real_slinger import RealSlingerAgent
                self.real_slinger = RealSlingerAgent(config, self.rpc_url, self.private_key)
                self.mode = "REAL"
            except ImportError as e:
                logger.error(f"Failed to load RealSlingerAgent: {e}")
                self.mode = "PAPER"
                self._init_paper_slinger()
        else:
            logger.info("📝 Initializing PAPER trading mode")
            self.mode = "PAPER"
            self._init_paper_slinger()
    
    def _init_paper_slinger(self):
        """Initialize the paper trading slinger."""
        from execution.slinger import SlingerAgent
        self.paper_slinger = SlingerAgent(self.config, rpc_url="http://localhost:8545")
    
    def execute_order(self, order: ExecutionOrder, wallet_address: str = None, private_key: str = None):
        """Execute order in appropriate mode."""
        logger.info(f"Executing {order.action} for {order.token_address} (${order.amount_usd}) in {self.mode} mode")
        
        if self.mode == "REAL":
            # Real execution - wallet address and private key come from env
            return self.real_slinger.execute_order(order)
        else:
            # Paper execution - use provided or mock credentials
            wallet = wallet_address or "0xMockWalletAddress"
            key = private_key or "MockPrivateKey"
            return self.paper_slinger.execute_order(order, wallet, key)
    
    def get_mode(self):
        """Get current execution mode."""
        return self.mode
    
    def test_connection(self):
        """Test the connection (real mode) or simulation (paper mode)."""
        if self.mode == "REAL":
            try:
                # Test Web3 connection
                from web3 import Web3
                w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                if w3.is_connected():
                    return f"✅ Connected to chain ID: {w3.eth.chain_id}"
                else:
                    return "❌ Failed to connect to RPC"
            except Exception as e:
                return f"❌ Connection test failed: {e}"
        else:
            return "📝 Paper trading mode - no blockchain connection needed"

if __name__ == "__main__":
    # Test the unified slinger
    from strategy_factory import StrategyFactory
    
    factory = StrategyFactory()
    degen_config = factory.get_profile("degen").slinger
    
    slinger = UnifiedSlingerAgent(degen_config)
    print(f"Mode: {slinger.get_mode()}")
    print(f"Connection test: {slinger.test_connection()}")
    
    # Test with a mock order
    order = ExecutionOrder(
        token_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",  # UNI token
        action="BUY",
        amount_usd=100.0,
        slippage_tolerance=0.30,
        gas_premium_gwei=50.0
    )
    
    try:
        tx_hash = slinger.execute_order(order)
        print(f"Transaction result: {tx_hash}")
    except Exception as e:
        print(f"Execution test failed: {e}")
