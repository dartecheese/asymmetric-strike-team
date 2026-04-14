"""
Unified Slinger - Smart Execution Router
=========================================
Routes execution to either DEX (Web3) or CEX (CCXT) based on:
1. Signal chain (Ethereum/Base/Arbitrum -> DEX, "cex" -> CEX)
2. Token availability
3. Liquidity and fees
"""
import logging
from typing import Optional, Dict, Any

from core.models import RiskAssessment, ExecutionOrder
from agents.slinger import Slinger as DEXSlinger
from agents.cex_slinger import CEXSlinger

logger = logging.getLogger("UnifiedSlinger")


class UnifiedSlinger:
    """Unified Slinger: smart execution router for DEX and CEX venues."""

    def __init__(
        self,
        dex_rpc_url: str = None,
        dex_private_key: str = None,
        cex_exchange: str = "binance",
        cex_account: str = "default",
    ):
        self.dex_slinger = DEXSlinger(rpc_url=dex_rpc_url, private_key=dex_private_key)
        self.cex_slinger = CEXSlinger(exchange_id=cex_exchange, account_name=cex_account)
        self._strategy_slippage = 0.15
        self._strategy_gas_multiplier = 1.5
        self._use_private_mempool = False
        self.preferred_venue = "auto"

    def set_strategy_params(self, slippage: float, gas_multiplier: float, private_mempool: bool):
        self._strategy_slippage = slippage
        self._strategy_gas_multiplier = gas_multiplier
        self._use_private_mempool = private_mempool
        self.dex_slinger._strategy_slippage = slippage
        self.dex_slinger._strategy_gas_multiplier = gas_multiplier
        self.dex_slinger._use_private_mempool = private_mempool
        self.cex_slinger._strategy_slippage = slippage

    def execute_order(self, assessment: RiskAssessment, chain_id: str = "1", symbol: str = None) -> Optional[ExecutionOrder]:
        print("🔫 [Unified Slinger] Routing execution...")
        print(f"   Chain: {chain_id} | Token: {assessment.token_address}")
        print(f"   Allocation: ${assessment.max_allocation_usd}")

        venue = self._determine_venue(chain_id, assessment)
        if venue == "dex":
            print(f"   → Routing to DEX (chain {chain_id})")
            return self.dex_slinger.execute_order(assessment, chain_id=chain_id)

        if venue == "cex":
            if not symbol:
                symbol = self._token_to_symbol(assessment.token_address)
                if not symbol:
                    print(f"   ❌ No symbol mapping for token {assessment.token_address}")
                    return None

            print(f"   → Routing to CEX ({self.cex_slinger.exchange_id}: {symbol})")
            return self.cex_slinger.execute_order(assessment, symbol=symbol)

        print(f"   ❌ Unknown venue: {venue}")
        return None

    def _determine_venue(self, chain_id: str, assessment: RiskAssessment) -> str:
        if self.preferred_venue != "auto":
            return self.preferred_venue
        if chain_id == "cex":
            return "cex"

        cex_tokens = {
            "0x6982508145454ce325ddbe47a25d4ec3d2311933": "PEPE/USDT",
            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH/USDT",
            "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC/USDT",
            "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT/USDT",
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC/USDT",
        }
        if assessment.token_address.lower() in cex_tokens:
            print(f"   Token {assessment.token_address[:10]}... is CEX-listed")
            return "cex"
        return "dex"

    def _token_to_symbol(self, token_address: str) -> Optional[str]:
        token_map = {
            "0x6982508145454ce325ddbe47a25d4ec3d2311933": "PEPE/USDT",
            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "ETH/USDT",
            "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "BTC/USDT",
            "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT/USDT",
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC/USDT",
            "BTC": "BTC/USDT",
            "ETH": "ETH/USDT",
            "BNB": "BNB/USDT",
            "SOL": "SOL/USDT",
        }
        return token_map.get(token_address.lower()) or token_map.get(token_address.upper())

    def get_balances(self) -> Dict[str, Any]:
        return {
            "dex": "Not implemented",
            "cex": self.cex_slinger.get_balance(),
        }
