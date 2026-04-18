"""
Simple Configuration Manager
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class SimpleConfig:
    """Simple configuration for testing."""
    execution_mode: str = "paper"  # "paper" or "real"
    default_strategy: str = "degen"
    loop_interval_seconds: int = 60
    private_key: Optional[str] = None
    enable_sentiment: bool = True
    enable_performance_tracking: bool = True
    
    @classmethod
    def load(cls):
        """Load configuration from environment."""
        config = cls()
        
        # Override from environment
        if os.getenv("USE_REAL_EXECUTION", "false").lower() == "true":
            config.execution_mode = "real"
        
        if os.getenv("PRIVATE_KEY"):
            config.private_key = os.getenv("PRIVATE_KEY")
        
        if os.getenv("DEFAULT_STRATEGY"):
            config.default_strategy = os.getenv("DEFAULT_STRATEGY")
        
        if os.getenv("LOOP_INTERVAL"):
            try:
                config.loop_interval_seconds = int(os.getenv("LOOP_INTERVAL"))
            except ValueError:
                pass
        
        return config
    
    def is_real_mode(self) -> bool:
        """Check if real execution mode is enabled."""
        return self.execution_mode == "real"
    
    def print_summary(self):
        """Print configuration summary."""
        print("\n" + "=" * 70)
        print("📋 CONFIGURATION SUMMARY")
        print("=" * 70)
        print(f"Execution Mode: {self.execution_mode.upper()}")
        print(f"Default Strategy: {self.default_strategy}")
        print(f"Loop Interval: {self.loop_interval_seconds}s")
        print(f"Sentiment Analysis: {'✅' if self.enable_sentiment else '❌'}")
        print(f"Performance Tracking: {'✅' if self.enable_performance_tracking else '❌'}")
        print("=" * 70)