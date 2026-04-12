import os
import time
import json
import logging
import urllib.request
from typing import Optional
from web3 import Web3
from eth_account import Account
from core.models import RiskAssessment, RiskLevel, ExecutionOrder

logger = logging.getLogger("Slinger")


def fetch_entry_price(token_address: str) -> Optional[float]:
    """Fetch current token price from DexScreener for entry price recording."""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AsymmetricStrikeTeam/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        pairs = data.get("pairs") or []
        if not pairs:
            return None
        best = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0))
        price_str = best.get("priceUsd")
        return float(price_str) if price_str else None
    except Exception as e:
        logger.warning(f"Entry price fetch failed: {e}")
        return None

# Standard Uniswap V2 Router ABI snippet for swapExactETHForTokens
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
    }
]

class Slinger:
    """
    The Slinger: Direct Web3 router execution.
    Bypasses UIs, generates raw Web3 router calldata with high slippage/gas premiums 
    to guarantee block inclusion.
    """
    def __init__(self, rpc_url: str = None, private_key: str = None):
        self.rpc_url = rpc_url or os.getenv("RPC_URL", "https://eth.llamarpc.com")
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.private_key = private_key or os.getenv("PRIVATE_KEY")
        
        if self.private_key:
            self.account = Account.from_key(self.private_key)
        else:
            self.account = None

        # Strategy-profile overrides (set by main.py after instantiation)
        self._strategy_slippage: float = 0.15       # default 15%
        self._strategy_gas_multiplier: float = 1.5  # default 1.5x
        self._use_private_mempool: bool = False

        # Routers per chain
        self.routers = {
            "1":     "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap V2 (Ethereum)
            "8453":  "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24",  # BaseSwap (Base)
            "42161": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",  # SushiSwap (Arbitrum)
            "56":    "0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeSwap (BSC)
        }
        self.weth = {
            "1":     "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "8453":  "0x4200000000000000000000000000000000000006",
            "42161": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
            "56":    "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        }

    def execute_order(self, assessment: RiskAssessment, chain_id: str = "1") -> ExecutionOrder:
        if not assessment or assessment.risk_level == RiskLevel.REJECTED:
            print("🔫 [Slinger] Standing down. Capital preserved.")
            return None
            
        print(f"🔫 [Slinger] Actuary approved. Generating direct Web3 Router calldata...")
        
        # Prepare execution data
        target_token = Web3.to_checksum_address(assessment.token_address)
        router_address = Web3.to_checksum_address(self.routers.get(chain_id, self.routers["1"]))
        weth_address = Web3.to_checksum_address(self.weth.get(chain_id, self.weth["1"]))
        
        # Use strategy-profile params if set, otherwise fall back to defaults
        slippage = self._strategy_slippage
        base_gas_gwei = 30.0
        gas_premium = base_gas_gwei * self._strategy_gas_multiplier

        # Fetch live entry price for Reaper tracking
        entry_price = fetch_entry_price(assessment.token_address)
        if entry_price:
            print(f"🔫 [Slinger] Entry price: ${entry_price:.8f}")
        else:
            print(f"🔫 [Slinger] Entry price unavailable — Reaper will use paper simulation.")

        order = ExecutionOrder(
            token_address=assessment.token_address,
            chain=chain_id,
            action="BUY",
            amount_usd=assessment.max_allocation_usd,
            slippage_tolerance=slippage,
            gas_premium_gwei=gas_premium,
            entry_price_usd=entry_price,
        )
        
        try:
            # We construct the contract object to generate calldata
            router_contract = self.w3.eth.contract(address=router_address, abi=UNISWAP_V2_ROUTER_ABI)
            
            # Simulated swap path: WETH -> Token
            path = [weth_address, target_token]
            deadline = int(time.time()) + 300 # 5 min deadline
            
            # Amount out min = 0 for pure degen "I just want it" execution (dangerous, realistic for this profile)
            # In production, we'd calculate via getAmountsOut
            amount_out_min = 0 
            
            # Generate the raw calldata
            tx_data = router_contract.functions.swapExactETHForTokens(
                amount_out_min,
                path,
                self.account.address if self.account else "0x0000000000000000000000000000000000000000",
                deadline
            ).build_transaction({
                'gas': 250000,
                'gasPrice': self.w3.to_wei(gas_premium, 'gwei'),
                'nonce': 0
            })
            calldata = tx_data['data']
            
            print(f"🔫 [Slinger] >> RAW CALLDATA GENERATED <<")
            print(f"   Router Target: {router_address}")
            print(f"   Calldata[:64]...: {calldata[:64]}...")
            
            mempool_mode = "PRIVATE (Flashbots)" if self._use_private_mempool else "PUBLIC"
            if self.account:
                print(f"🔫 [Slinger] Live wallet detected. Would broadcast via {mempool_mode} mempool.")
            else:
                print(f"🔫 [Slinger] Paper mode — simulated via {mempool_mode} mempool.")

            print(f"   Value    : ${order.amount_usd} USD")
            print(f"   Slippage : {order.slippage_tolerance*100:.1f}% | Gas: {order.gas_premium_gwei:.1f} Gwei")
            
            return order
            
        except Exception as e:
            print(f"🔫 [Slinger] Failed to generate transaction: {e}")
            return None