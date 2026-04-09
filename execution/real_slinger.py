import json
import logging
import time
from typing import Optional
from web3 import Web3
from eth_account import Account
from pydantic import BaseModel

from core.models import ExecutionOrder
from strategy_factory import SlingerConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RealSlinger")

# --- Real Router ABIs (Simplified) ---

UNISWAP_V2_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

class RealSlingerAgent:
    """
    Real Web3.py execution layer.
    Connects to live RPC, builds actual transactions, and signs them.
    """
    def __init__(self, config: SlingerConfig, rpc_url: str, private_key: str):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = Account.from_key(private_key)
        self.router_address = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
        self.router = self.w3.eth.contract(address=self.router_address, abi=UNISWAP_V2_ROUTER_ABI)
        
        # Validate connection
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {rpc_url}")
        logger.info(f"✅ Connected to chain ID: {self.w3.eth.chain_id}")
        logger.info(f"   Wallet: {self.account.address}")
        
    def _get_gas_params(self, order_premium_gwei: float):
        """Fetch current base fee and apply strategy multipliers."""
        try:
            fee_history = self.w3.eth.fee_history(1, 'latest')
            base_fee = fee_history['baseFeePerGas'][0]
        except Exception as e:
            logger.warning(f"Could not fetch fee history: {e}. Using fallback.")
            base_fee = self.w3.to_wei(30, 'gwei')
            
        priority_fee = self.w3.to_wei(order_premium_gwei * self.config.gas_premium_multiplier, 'gwei')
        max_fee = base_fee + priority_fee
        
        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority_fee
        }

    def _build_buy_tx(self, order: ExecutionOrder, wallet_address: str):
        """Construct a BUY transaction (swap ETH for tokens)."""
        # Path: WETH -> target token (assuming token is paired with WETH)
        path = [
            Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"), # WETH
            Web3.to_checksum_address(order.token_address)
        ]
        
        # Calculate amountOutMin based on slippage tolerance
        # In reality, you'd fetch the current quote from the router
        amount_out_min = 0  # Placeholder: we'd compute from current reserves
        
        # Deadline: 20 minutes from now
        deadline = int(time.time()) + 1200
        
        # Build the transaction
        tx = self.router.functions.swapExactETHForTokens(
            amount_out_min,
            path,
            wallet_address,
            deadline
        ).build_transaction({
            'from': wallet_address,
            'value': self.w3.to_wei(order.amount_usd / 3000, 'ether'), # Mock conversion
            'gas': 250000,
            'nonce': self.w3.eth.get_transaction_count(wallet_address),
            'chainId': self.w3.eth.chain_id,
        })
        
        # Override with our gas strategy
        gas_params = self._get_gas_params(order.gas_premium_gwei)
        tx.update(gas_params)
        
        return tx

    def _build_sell_tx(self, order: ExecutionOrder, wallet_address: str):
        """Construct a SELL transaction (swap tokens for ETH)."""
        # Path: token -> WETH
        path = [
            Web3.to_checksum_address(order.token_address),
            Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
        ]
        
        # For selling, we need to approve the router first (not implemented here)
        # amountIn = token balance
        amount_in = 0  # Placeholder
        amount_out_min = 0
        
        deadline = int(time.time()) + 1200
        
        tx = self.router.functions.swapExactTokensForETH(
            amount_in,
            amount_out_min,
            path,
            wallet_address,
            deadline
        ).build_transaction({
            'from': wallet_address,
            'gas': 300000,
            'nonce': self.w3.eth.get_transaction_count(wallet_address),
            'chainId': self.w3.eth.chain_id,
        })
        
        gas_params = self._get_gas_params(order.gas_premium_gwei)
        tx.update(gas_params)
        
        return tx

    def execute_order(self, order: ExecutionOrder):
        """Sign and broadcast the transaction."""
        logger.info(f"🔧 Building {order.action} for {order.token_address} (${order.amount_usd})")
        
        if order.action == "BUY":
            tx = self._build_buy_tx(order, self.account.address)
        elif order.action == "SELL":
            tx = self._build_sell_tx(order, self.account.address)
        else:
            raise ValueError(f"Invalid action: {order.action}")
        
        # Sign
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        
        # Send
        if self.config.use_private_mempool:
            logger.info("🥷 Sending via private mempool (Flashbots) - NOT IMPLEMENTED")
            # In reality: bundle = flashbots.sign_bundle([signed_tx])
            # flashbots.send_bundle(bundle)
            tx_hash = "0xPrivateMockHash"
        else:
            logger.info("💥 Broadcasting to public mempool...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            logger.info(f"✅ Transaction sent: {tx_hash.hex()}")
            
        return tx_hash.hex()

if __name__ == "__main__":
    # Example configuration for testing (NEVER commit real private keys)
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    RPC_URL = os.getenv("ETH_RPC_URL", "http://localhost:8545")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0x" + "a" * 64)  # Dummy key
    
    from strategy_factory import StrategyFactory
    factory = StrategyFactory()
    degen_config = factory.get_profile("degen").slinger
    
    slinger = RealSlingerAgent(degen_config, RPC_URL, PRIVATE_KEY)
    
    # Mock order
    order = ExecutionOrder(
        token_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",  # UNI token
        action="BUY",
        amount_usd=100.0,
        slippage_tolerance=0.30,
        gas_premium_gwei=50.0
    )
    
    try:
        tx_hash = slinger.execute_order(order)
        print(f"Transaction Hash: {tx_hash}")
    except Exception as e:
        print(f"Execution failed: {e}")
