import os
import time
from web3 import Web3
from eth_account import Account
from core.models import RiskAssessment, RiskLevel, ExecutionOrder

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
            
        # Example routers
        self.routers = {
            "1": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", # Uniswap V2
            "8453": "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24" # Base Swap
        }
        self.weth = {
            "1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "8453": "0x4200000000000000000000000000000000000006"
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
        
        slippage = 0.15 # 15% slippage default for extreme volatility degen plays
        gas_premium = 50.0 # Gwei
        
        order = ExecutionOrder(
            token_address=assessment.token_address,
            action="BUY",
            amount_usd=assessment.max_allocation_usd,
            slippage_tolerance=slippage,
            gas_premium_gwei=gas_premium
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
            calldata = router_contract.encodeABI(fn_name="swapExactETHForTokens", args=[
                amount_out_min,
                path,
                self.account.address if self.account else "0xDeGenWalletAddress0000000000000000000000",
                deadline
            ])
            
            print(f"🔫 [Slinger] >> RAW CALLDATA GENERATED <<")
            print(f"   Router Target: {router_address}")
            print(f"   Calldata[:64]...: {calldata[:64]}...")
            
            if self.account:
                print("🔫 [Slinger] Live wallet detected. In production, transaction would broadcast here.")
                # tx = self.w3.eth.send_raw_transaction(...)
            else:
                print("🔫 [Slinger] No private key loaded. Simulated execution complete.")
                
            print(f"   Value: ${order.amount_usd} USD")
            print(f"   Slippage: {order.slippage_tolerance*100}% | Gas Premium: {order.gas_premium_gwei} Gwei")
            
            return order
            
        except Exception as e:
            print(f"🔫 [Slinger] Failed to generate transaction: {e}")
            return None