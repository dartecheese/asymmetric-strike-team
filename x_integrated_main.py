#!/usr/bin/env python3
"""
X.com Integrated Crypto Trading Bot
Combines Grok-powered X.com analysis with the Asymmetric Strike Team trading system.
"""

import asyncio
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import existing trading system
from agents.whisperer import Whisperer
from agents.actuary import Actuary
from agents.slinger import Slinger
from agents.reaper import Reaper
from core.models import TradeSignal

# Import X.com analyst components
from x_analyst_integrated import XDataCollector, GrokAnalyzer, CryptoSignal

# ============================================================================
# X.com Enhanced Whisperer
# ============================================================================

class XEnhancedWhisperer(Whisperer):
    """
    Enhanced Whisperer that uses X.com social intelligence
    to find high-potential trading opportunities.
    """
    
    def __init__(self):
        super().__init__()
        self.x_collector = XDataCollector()
        self.grok_analyzer = GrokAnalyzer()
        self.recent_signals = []
        
    async def scan_x_for_opportunities(self) -> list:
        """Scan X.com for crypto opportunities using Grok analysis"""
        logger.info("🗣️ [X-Whisperer] Scanning X.com for crypto opportunities...")
        
        try:
            # Fetch recent posts from X.com
            posts = await self.x_collector.fetch_recent_posts(hours=1)
            
            # Analyze with Grok
            signals = await self.grok_analyzer.analyze_posts(posts)
            
            # Filter for high-confidence signals
            high_confidence = [
                sig for sig in signals 
                if sig.confidence.value in ["high", "very_high"]
                and sig.social_velocity > 5.0  # Minimum velocity threshold
            ]
            
            logger.info(f"🗣️ [X-Whisperer] Found {len(high_confidence)} high-confidence opportunities")
            
            # Store for reference
            self.recent_signals = signals
            
            return high_confidence
            
        except Exception as e:
            logger.error(f"🗣️ [X-Whisperer] Error scanning X.com: {e}")
            return []
    
    def x_signal_to_trade_signal(self, x_signal: CryptoSignal) -> TradeSignal:
        """Convert X.com CryptoSignal to TradeSignal for the trading system"""
        
        # Map X.com signal type to narrative score
        narrative_scores = {
            "new_token_launch": 95,
            "exchange_listing": 90,
            "whale_activity": 85,
            "social_pump": 80,
            "airdrop": 75,
            "governance_vote": 70
        }
        
        narrative_score = narrative_scores.get(
            x_signal.signal_type.value, 
            75  # Default
        )
        
        # Adjust based on confidence
        confidence_multiplier = {
            "low": 0.7,
            "medium": 0.85,
            "high": 1.0,
            "very_high": 1.15
        }
        
        narrative_score *= confidence_multiplier.get(x_signal.confidence.value, 1.0)
        
        # Create TradeSignal
        return TradeSignal(
            token_address=None,  # Will need to resolve from symbol
            asset_symbol=x_signal.asset_symbol,
            chain=None,  # Will need to detect chain
            narrative_score=int(narrative_score),
            reasoning=f"X.com Signal: {x_signal.signal_type.value}. {x_signal.narrative}",
            discovered_at=time.time(),
            x_signal_data=x_signal.to_dict()  # Store original X signal data
        )

# ============================================================================
# Enhanced Main Trading Loop
# ============================================================================

class XIntegratedTradingBot:
    """
    Main trading bot that integrates X.com social intelligence
    with the Asymmetric Strike Team trading system.
    """
    
    def __init__(self):
        load_dotenv()
        
        # Initialize enhanced components
        self.x_whisperer = XEnhancedWhisperer()
        self.actuary = Actuary(max_allowed_tax=0.25)
        self.slinger = Slinger()
        self.reaper = Reaper()
        
        # Trading state
        self.active_positions = []
        self.signal_history = []
        
    async def run_trading_cycle(self):
        """Run one complete trading cycle"""
        logger.info("="*60)
        logger.info("🚀 X-INTEGRATED TRADING BOT: STARTING CYCLE")
        logger.info("="*60)
        
        # Step 1: Scan X.com for opportunities
        logger.info("📊 Step 1: Scanning X.com for crypto opportunities...")
        x_signals = await self.x_whisperer.scan_x_for_opportunities()
        
        if not x_signals:
            logger.info("📊 No high-confidence X.com signals found. Checking DexScreener...")
            # Fall back to original whisperer
            trade_signal = self.x_whisperer.scan_firehose()
            self.signal_history.append({
                "type": "dex_screener",
                "signal": trade_signal.__dict__,
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            # Use the strongest X.com signal
            strongest_signal = max(x_signals, key=lambda x: x.engagement_score * x.social_velocity)
            logger.info(f"📊 Strongest X.com signal: {strongest_signal.asset_symbol} "
                       f"(Engagement: {strongest_signal.engagement_score:.1f}, "
                       f"Velocity: {strongest_signal.social_velocity:.1f})")
            
            # Convert to trade signal
            trade_signal = self.x_whisperer.x_signal_to_trade_signal(strongest_signal)
            
            self.signal_history.append({
                "type": "x_com",
                "signal": strongest_signal.to_dict(),
                "trade_signal": trade_signal.__dict__,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Display X.com signal summary
            logger.info("📊 X.com Signal Summary:")
            logger.info(strongest_signal.to_nlp_summary())
        
        logger.info("-" * 60)
        
        # Step 2: Risk Assessment
        logger.info("📊 Step 2: Risk Assessment with Actuary...")
        assessment = self.actuary.assess_risk(trade_signal)
        
        if not assessment.passed:
            logger.warning(f"⚠️ Risk assessment failed: {assessment.reason}")
            return
        
        logger.info(f"✅ Risk assessment passed: {assessment.reason}")
        logger.info("-" * 60)
        
        # Step 3: Execution (Simulated for now)
        logger.info("📊 Step 3: Preparing Execution Order...")
        
        # For demo purposes, we'll simulate execution
        # In production, this would call the Slinger
        logger.info(f"🎯 Would execute trade for: {trade_signal.asset_symbol or 'Unknown Token'}")
        logger.info(f"📈 Narrative Score: {trade_signal.narrative_score}/100")
        logger.info(f"📝 Reasoning: {trade_signal.reasoning}")
        
        # Simulate order creation
        order = {
            "asset": trade_signal.asset_symbol or "Unknown",
            "narrative_score": trade_signal.narrative_score,
            "timestamp": datetime.utcnow().isoformat(),
            "x_signal": trade_signal.__dict__.get('x_signal_data', {})
        }
        
        logger.info("-" * 60)
        
        # Step 4: Position Monitoring
        logger.info("📊 Step 4: Starting Position Monitoring...")
        if order:
            # In production: self.reaper.take_position(order)
            logger.info(f"👁️ Monitoring position for: {order['asset']}")
            logger.info("💀 [Reaper] Free Ride protocol active: Take principal at +100%, cut at -30%")
            
            # Simulate monitoring start
            self.active_positions.append(order)
            
        logger.info("="*60)
        logger.info("✅ Trading cycle completed successfully")
        logger.info("="*60)
        
        return order
    
    async def run_continuous(self, interval_minutes: int = 15):
        """Run continuous trading cycles"""
        logger.info(f"🔄 Starting continuous trading with {interval_minutes} minute intervals")
        
        try:
            while True:
                await self.run_trading_cycle()
                
                # Save signal history
                self.save_signal_history()
                
                # Wait for next cycle
                logger.info(f"⏳ Waiting {interval_minutes} minutes for next cycle...")
                await asyncio.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("🛑 Trading bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Trading bot error: {e}")
        finally:
            self.save_signal_history()
            logger.info("💾 Signal history saved")
    
    def save_signal_history(self):
        """Save signal history to file"""
        try:
            filename = f"signal_history_{datetime.utcnow().strftime('%Y%m%d')}.json"
            with open(filename, 'w') as f:
                json.dump(self.signal_history, f, indent=2)
            logger.info(f"💾 Signal history saved to {filename}")
        except Exception as e:
            logger.error(f"❌ Failed to save signal history: {e}")

# ============================================================================
# Main Execution
# ============================================================================

async def main():
    """Main async entry point"""
    
    print("\n" + "="*60)
    print("🚀 X.COM INTEGRATED CRYPTO TRADING BOT")
    print("="*60)
    print("🤖 Combining Grok-powered X.com analysis with Asymmetric Strike Team")
    print("="*60 + "\n")
    
    # Initialize bot
    bot = XIntegratedTradingBot()
    
    # Ask for mode
    print("Select mode:")
    print("1. Single trading cycle (demo)")
    print("2. Continuous trading (15 min intervals)")
    print("3. Continuous trading (custom interval)")
    
    try:
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            # Single cycle
            await bot.run_trading_cycle()
            
        elif choice == "2":
            # Continuous with 15 min intervals
            await bot.run_continuous(interval_minutes=15)
            
        elif choice == "3":
            # Custom interval
            interval = int(input("Enter interval in minutes: "))
            await bot.run_continuous(interval_minutes=interval)
            
        else:
            print("Invalid choice. Running single cycle...")
            await bot.run_trading_cycle()
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        print("\n👋 Trading bot session ended")

if __name__ == '__main__':
    asyncio.run(main())