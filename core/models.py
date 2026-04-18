from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"
    REJECTED = "REJECTED"

class TradeSignal(BaseModel):
    token_address: str
    chain: str
    narrative_score: int = Field(ge=0, le=100, description="Social velocity and smart money score")
    reasoning: str
    discovered_at: float

class RiskAssessment(BaseModel):
    token_address: str
    is_honeypot: bool
    buy_tax: float
    sell_tax: float
    liquidity_locked: bool
    risk_level: RiskLevel
    max_allocation_usd: float
    warnings: list[str]

class ExecutionOrder(BaseModel):
    token_address: str
    chain: str = Field(default="1", description="GoPlus/DexScreener chain ID or 'cex'")
    action: str = Field(pattern="^(BUY|SELL)$")
    amount_usd: float = Field(gt=0, description="Must be positive")
    slippage_tolerance: float = Field(default=0.15, ge=0, le=1, description="15% default for high volatility (0-1 range)")
    gas_premium_gwei: float = Field(default=0, ge=0, description="Gas premium in Gwei (0 for CEX)")
    entry_price_usd: Optional[float] = Field(default=None, description="Actual price at execution time")
    tx_hash: Optional[str] = Field(default=None, description="Transaction hash if executed on-chain")
    
    @property
    def is_cex(self) -> bool:
        """Check if this is a CEX order."""
        return self.chain == "cex" or self.token_address.startswith("CEX:")
