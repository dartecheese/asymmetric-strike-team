import json
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

# --- Agent Configuration Models ---

class WhispererConfig(BaseModel):
    data_sources: list[str] = Field(default=["twitter", "telegram"])
    min_velocity_score: int = Field(default=50)
    scan_interval_seconds: int = Field(default=60)

class ShadowConfig(BaseModel):
    """Watches specific highly-profitable wallets to copy-trade."""
    target_wallets: list[str] = Field(default_factory=list, description="Addresses of Smart Money")
    copy_size_multiplier: float = Field(default=0.1, description="Copy 10% of the target's trade size")
    max_latency_ms: int = Field(default=50, description="Max delay allowed behind target's tx")

class SleuthConfig(BaseModel):
    """On-chain forensics: investigates deployers and holder distribution."""
    max_deployer_rugs_allowed: int = Field(default=0)
    require_insider_clearance: bool = Field(default=True, description="Reject if top 10 holders own > 50%")
    min_creator_funding_eth: float = Field(default=0.1)

class PathfinderConfig(BaseModel):
    """Calculates optimal routing and cross-DEX arbitrage."""
    target_exchanges: list[str] = Field(default=["uniswap_v2", "uniswap_v3", "sushiswap"])
    min_arbitrage_spread_pct: float = Field(default=1.5)
    flash_loan_enabled: bool = Field(default=False)

class OracleConfig(BaseModel):
    """Monitors macro indicators and whale movements."""
    monitor_cex_flows: bool = Field(default=True, description="Track CEX inflows/outflows")
    track_whale_wallets: list[str] = Field(default_factory=list)
    macro_indicators: list[str] = Field(default=["fear_greed", "funding_rates", "oi_change"])
    alert_threshold_eth: float = Field(default=1000.0, description="Minimum whale tx size to alert")

class SentinelConfig(BaseModel):
    """Real-time market structure and liquidity monitoring."""
    monitor_liquidity_pools: bool = Field(default=True)
    track_support_resistance: bool = Field(default=False)
    volatility_alert_threshold: float = Field(default=15.0, description="% price change in 5min to alert")
    liquidation_watch: bool = Field(default=False, description="Monitor for potential liquidation cascades")

class AlchemistConfig(BaseModel):
    """Yield optimization and DeFi strategy automation."""
    target_protocols: list[str] = Field(default=["aave", "compound", "curve"])
    min_apr_threshold: float = Field(default=8.0)
    auto_compound: bool = Field(default=True)
    risk_adjustment_speed: float = Field(default=0.5, description="How quickly to adjust positions (0-1)")

class ActuaryConfig(BaseModel):
    strict_mode: bool = Field(default=False)
    max_tax_allowed: float = Field(default=10.0)
    require_locked_liquidity: bool = Field(default=False)
    allow_unverified_contracts: bool = Field(default=True)

class SlingerConfig(BaseModel):
    use_private_mempool: bool = Field(default=False)
    base_slippage_tolerance: float = Field(default=0.15)
    gas_premium_multiplier: float = Field(default=1.5)

class ReaperConfig(BaseModel):
    take_profit_pct: float = Field(default=100.0)
    stop_loss_pct: float = Field(default=-30.0)
    trailing_stop_pct: float = Field(default=15.0)
    extract_principal_on_tp: bool = Field(default=True)

# --- The Strategy Profile ---

class StrategyProfile(BaseModel):
    name: str
    description: str
    
    # Data Ingestion & Analysis (Choose as needed)
    whisperer: Optional[WhispererConfig] = None
    shadow: Optional[ShadowConfig] = None
    oracle: Optional[OracleConfig] = None
    sentinel: Optional[SentinelConfig] = None
    
    # Forensics & Routing
    sleuth: Optional[SleuthConfig] = None
    pathfinder: Optional[PathfinderConfig] = None
    alchemist: Optional[AlchemistConfig] = None
    
    # Core Pipeline (Mandatory)
    actuary: ActuaryConfig
    slinger: SlingerConfig
    reaper: ReaperConfig

# --- Strategy Factory / Library ---

class StrategyFactory:
    def __init__(self):
        self.profiles: Dict[str, StrategyProfile] = {}
        self._register_default_profiles()

    def _register_default_profiles(self):
        # 1. The Degen / Ape
        self.profiles["degen"] = StrategyProfile(
            name="Degen Ape",
            description="High risk, momentum-based. Ignores deep forensics for sheer speed.",
            whisperer=WhispererConfig(min_velocity_score=40, scan_interval_seconds=15),  # Degen casts a wide net
            sleuth=None, # Too slow for degen mode
            actuary=ActuaryConfig(strict_mode=False, max_tax_allowed=30.0, require_locked_liquidity=False, allow_unverified_contracts=True),
            slinger=SlingerConfig(use_private_mempool=False, base_slippage_tolerance=0.30, gas_premium_multiplier=3.0),
            reaper=ReaperConfig(take_profit_pct=100.0, stop_loss_pct=-50.0, trailing_stop_pct=25.0, extract_principal_on_tp=True)
        )

        # 2. The Safe Sniper
        self.profiles["sniper"] = StrategyProfile(
            name="Safe Sniper",
            description="Waits for safe contracts. Uses full forensics and MEV protection.",
            whisperer=WhispererConfig(min_velocity_score=40, scan_interval_seconds=5),
            sleuth=SleuthConfig(max_deployer_rugs_allowed=0, require_insider_clearance=True),
            actuary=ActuaryConfig(strict_mode=True, max_tax_allowed=0.0, require_locked_liquidity=True, allow_unverified_contracts=False),
            slinger=SlingerConfig(use_private_mempool=True, base_slippage_tolerance=0.05, gas_premium_multiplier=1.2),
            reaper=ReaperConfig(take_profit_pct=20.0, stop_loss_pct=-10.0, trailing_stop_pct=5.0, extract_principal_on_tp=False)
        )
        
        # 3. The Shadow Clone (Copy Trading)
        self.profiles["shadow_clone"] = StrategyProfile(
            name="Shadow Clone",
            description="Ignores social metrics. Strictly copies trades of proven 'Smart Money' wallets.",
            whisperer=None, # Disabled
            shadow=ShadowConfig(target_wallets=["0xSmartMoney1", "0xWhale2"], copy_size_multiplier=0.05),
            sleuth=None, # Assume the whale already did the forensics
            actuary=ActuaryConfig(strict_mode=False, max_tax_allowed=15.0),
            slinger=SlingerConfig(use_private_mempool=True, base_slippage_tolerance=0.10, gas_premium_multiplier=2.0),
            reaper=ReaperConfig(take_profit_pct=50.0, stop_loss_pct=-20.0, trailing_stop_pct=10.0, extract_principal_on_tp=True)
        )
        
        # 4. The Flash Arbitrageur
        self.profiles["arb_hunter"] = StrategyProfile(
            name="Arb Hunter",
            description="Looks for price discrepancies across DEXes. Zero social risk, pure math.",
            whisperer=None,
            pathfinder=PathfinderConfig(min_arbitrage_spread_pct=1.0, flash_loan_enabled=True),
            actuary=ActuaryConfig(strict_mode=True, max_tax_allowed=0.0), # Taxes ruin arbitrage
            slinger=SlingerConfig(use_private_mempool=True, base_slippage_tolerance=0.01, gas_premium_multiplier=1.0),
            reaper=ReaperConfig(take_profit_pct=1.0, stop_loss_pct=-1.0, trailing_stop_pct=0.5, extract_principal_on_tp=False)
        )
        
        # === NEW HIGH-VALUE STRATEGIES ===
        
        # 5. The Oracle's Eye (Macro + Whale Tracking)
        self.profiles["oracle_eye"] = StrategyProfile(
            name="Oracle's Eye",
            description="Combines macro indicators with whale wallet tracking for early trend detection.",
            oracle=OracleConfig(
                monitor_cex_flows=True,
                track_whale_wallets=["0xWhaleAlpha", "0xWhaleBeta", "0xVCfund"],
                macro_indicators=["fear_greed", "funding_rates", "oi_change", "volatility_index"],
                alert_threshold_eth=5000.0
            ),
            sentinel=SentinelConfig(
                monitor_liquidity_pools=True,
                volatility_alert_threshold=20.0,
                liquidation_watch=True
            ),
            actuary=ActuaryConfig(strict_mode=True, max_tax_allowed=5.0),
            slinger=SlingerConfig(use_private_mempool=False, base_slippage_tolerance=0.08, gas_premium_multiplier=1.8),
            reaper=ReaperConfig(take_profit_pct=75.0, stop_loss_pct=-15.0, trailing_stop_pct=8.0, extract_principal_on_tp=True)
        )
        
        # 6. The Liquidity Sentinel (Market Structure)
        self.profiles["liquidity_sentinel"] = StrategyProfile(
            name="Liquidity Sentinel",
            description="Monitors liquidity pools and market structure for optimal entry/exit points.",
            sentinel=SentinelConfig(
                monitor_liquidity_pools=True,
                track_support_resistance=True,
                volatility_alert_threshold=10.0,
                liquidation_watch=True
            ),
            pathfinder=PathfinderConfig(
                target_exchanges=["uniswap_v3", "curve", "balancer"],
                min_arbitrage_spread_pct=0.5,
                flash_loan_enabled=False
            ),
            actuary=ActuaryConfig(strict_mode=True, max_tax_allowed=2.0),
            slinger=SlingerConfig(use_private_mempool=True, base_slippage_tolerance=0.03, gas_premium_multiplier=1.3),
            reaper=ReaperConfig(take_profit_pct=30.0, stop_loss_pct=-8.0, trailing_stop_pct=4.0, extract_principal_on_tp=False)
        )
        
        # 7. The Yield Alchemist (DeFi Optimization)
        self.profiles["yield_alchemist"] = StrategyProfile(
            name="Yield Alchemist",
            description="Automatically rotates capital between highest-yielding DeFi protocols.",
            alchemist=AlchemistConfig(
                target_protocols=["aave", "compound", "curve", "yearn", "balancer"],
                min_apr_threshold=12.0,
                auto_compound=True,
                risk_adjustment_speed=0.7
            ),
            oracle=OracleConfig(
                monitor_cex_flows=False,
                macro_indicators=["funding_rates", "stablecoin_flows"],
                alert_threshold_eth=10000.0
            ),
            actuary=ActuaryConfig(strict_mode=True, max_tax_allowed=0.0), # No memecoins
            slinger=SlingerConfig(use_private_mempool=False, base_slippage_tolerance=0.02, gas_premium_multiplier=1.1),
            reaper=ReaperConfig(take_profit_pct=15.0, stop_loss_pct=-5.0, trailing_stop_pct=3.0, extract_principal_on_tp=False)
        )
        
        # 8. The Forensic Sniper (Deep Due Diligence)
        self.profiles["forensic_sniper"] = StrategyProfile(
            name="Forensic Sniper",
            description="Extreme due diligence: audits code, team, vesting, and tokenomics before any trade.",
            sleuth=SleuthConfig(
                max_deployer_rugs_allowed=0,
                require_insider_clearance=True,
                min_creator_funding_eth=1.0
            ),
            whisperer=WhispererConfig(
                data_sources=["github", "linkedin", "discord", "audit_reports"],
                min_velocity_score=30,
                scan_interval_seconds=300  # Slow, thorough scans
            ),
            actuary=ActuaryConfig(
                strict_mode=True,
                max_tax_allowed=0.0,
                require_locked_liquidity=True,
                allow_unverified_contracts=False
            ),
            slinger=SlingerConfig(
                use_private_mempool=True,
                base_slippage_tolerance=0.02,
                gas_premium_multiplier=1.0
            ),
            reaper=ReaperConfig(
                take_profit_pct=50.0,
                stop_loss_pct=-5.0,
                trailing_stop_pct=2.0,
                extract_principal_on_tp=True
            )
        )

    def get_profile(self, name: str) -> StrategyProfile:
        if name not in self.profiles:
            raise ValueError(f"Strategy '{name}' not found. Available: {list(self.profiles.keys())}")
        return self.profiles[name]

if __name__ == "__main__":
    factory = StrategyFactory()
    print("Available Team Strategies:\n")
    for key, profile in factory.profiles.items():
        print(f"[{key}] {profile.name}")
        print(f"  -> {profile.description}")
        
        # Show team composition
        agents = []
        if profile.whisperer: agents.append("Whisperer")
        if profile.shadow: agents.append("Shadow")
        if profile.oracle: agents.append("Oracle")
        if profile.sentinel: agents.append("Sentinel")
        if profile.sleuth: agents.append("Sleuth")
        if profile.pathfinder: agents.append("Pathfinder")
        if profile.alchemist: agents.append("Alchemist")
        agents.append("Actuary")
        agents.append("Slinger")
        agents.append("Reaper")
        
        print(f"  👥 Team: {' → '.join(agents)}\n")
