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
    action: str = Field(pattern="^(BUY|SELL)$")
    amount_usd: float
    slippage_tolerance: float = Field(default=0.15, description="15% default for high volatility")
    gas_premium_gwei: float
