import json
import logging
from typing import Optional
from web3 import Web3
from pydantic import BaseModel

# Try to import from core models, but fallback if running standalone
try:
    from core.models import ExecutionOrder
    from strategy_factory import SlingerConfig
except ImportError:
    # Fallbacks for standalone testing
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Slinger")

class SlingerAgent:
    """
    The Execution Engine.
    Takes an ExecutionOrder and converts it into raw Web3 calldata.
    Bypasses UIs and routes directly to the contract or via MEV bundles.
    """
    def __init__(self, config: SlingerConfig, rpc_url: str = "http://localhost:8545"):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # In a real scenario, you'd load the Router ABI and set your wallet
        self.router_address = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D" # Uniswap V2 Router as example
        
        # Note: In production, MEV builders (Flashbots) require a specific relayer endpoint
        self.mev_relay_url = "https://relay.flashbots.net"
        
    def _calculate_gas_params(self, order_premium_gwei: float):
        """Calculates gas fees based on current network base fee + strategy multiplier."""
        # For EIP-1559 transactions
        try:
            base_fee = self.w3.eth.fee_history(1, 'latest')['baseFeePerGas'][0]
        except Exception:
            base_fee = self.w3.to_wei(30, 'gwei') # Fallback mock
            
        priority_fee = self.w3.to_wei(order_premium_gwei * self.config.gas_premium_multiplier, 'gwei')
        max_fee = base_fee + priority_fee
        
        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority_fee
        }

    def build_transaction(self, order: ExecutionOrder, wallet_address: str):
        """Constructs the raw contract calldata."""
        logger.info(f"Building {order.action} tx for {order.token_address} | Amount: ${order.amount_usd}")
        
        # Apply strategy-level slippage tolerance overrides if they are looser
        effective_slippage = max(order.slippage_tolerance, self.config.base_slippage_tolerance)
        logger.info(f"Effective Slippage configured at {effective_slippage * 100}%")
        
        gas_params = self._calculate_gas_params(order.gas_premium_gwei)
        
        # MOCK CALLEDATA GENERATION
        # In reality: contract.functions.swapExactETHForTokens(...).build_transaction(...)
        tx = {
            'to': self.router_address,
            'value': self.w3.to_wei(order.amount_usd / 3000, 'ether') if order.action == 'BUY' else 0, # Mock ETH conversion
            'gas': 250000,
            'maxFeePerGas': gas_params['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_params['maxPriorityFeePerGas'],
            'nonce': 42, # Mock nonce
            'chainId': 1
        }
        return tx

    def submit_public_mempool(self, signed_tx: str):
        """Slams the transaction into the public mempool with high gas."""
        logger.info("💥 Slinging transaction into PUBLIC mempool...")
        # self.w3.eth.send_raw_transaction(signed_tx)
        return "0xMockTxHashPublic1234567890abcdef"

    def submit_private_bundle(self, signed_tx: str):
        """Wraps the transaction in an MEV bundle to prevent front-running."""
        logger.info("🥷 Sending transaction directly to block builders (Flashbots)...")
        # mev_provider.send_bundle([signed_tx])
        return "0xMockTxHashPrivate1234567890abcdef"

    def execute_order(self, order: ExecutionOrder, wallet_address: str, private_key: str):
        """Main entry point for order execution."""
        tx = self.build_transaction(order, wallet_address)
        
        # Mock Signing
        # signed_tx = self.w3.eth.account.sign_transaction(tx, private_key).rawTransaction
        signed_tx = "0xMockSignedTransactionData"
        
        # Routing decision based on strategy profile
        if self.config.use_private_mempool:
            tx_hash = self.submit_private_bundle(signed_tx)
        else:
            tx_hash = self.submit_public_mempool(signed_tx)
            
        logger.info(f"✅ Execution Complete. Hash: {tx_hash}")
        return tx_hash

if __name__ == "__main__":
    # Test Run
    from strategy_factory import StrategyFactory
    factory = StrategyFactory()
    
    # 1. Test Degen Mode
    print("\n--- Testing Degen Execution ---")
    degen_config = factory.get_profile("degen").slinger
    slinger = SlingerAgent(config=degen_config)
    order = ExecutionOrder(token_address="0xPEPE", action="BUY", amount_usd=500.0, slippage_tolerance=0.10, gas_premium_gwei=50.0)
    slinger.execute_order(order, "0xMyWallet", "MyPrivateKey")

    # 2. Test Sniper Mode
    print("\n--- Testing Sniper Execution ---")
    sniper_config = factory.get_profile("sniper").slinger
    slinger_sniper = SlingerAgent(config=sniper_config)
    slinger_sniper.execute_order(order, "0xMyWallet", "MyPrivateKey")
