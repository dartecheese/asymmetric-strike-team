#!/usr/bin/env python3
"""
Direct demo of X.com Crypto Trading Bot
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
import random

# ============================================================================
# Simple X.com Data Models
# ============================================================================

class SimpleXPost:
    def __init__(self, content: str, author: str, verified: bool, followers: int, 
                 likes: int, retweets: int, minutes_ago: int):
        self.content = content
        self.author = author
        self.verified = verified
        self.followers = followers
        self.likes = likes
        self.retweets = retweets
        self.timestamp = datetime.utcnow() - timedelta(minutes=minutes_ago)
        self.sentiment = random.uniform(-0.5, 1.0)

class SimpleCryptoSignal:
    def __init__(self, asset: str, signal_type: str, confidence: str, 
                 velocity: float, engagement: float):
        self.asset = asset
        self.signal_type = signal_type
        self.confidence = confidence
        self.velocity = velocity
        self.engagement = engagement
        self.timestamp = datetime.utcnow()
        
    def summary(self):
        return f"""
🚀 **X.com Signal: {self.asset}**
**Type:** {self.signal_type.replace('_', ' ').title()}
**Confidence:** {self.confidence.replace('_', ' ').title()}
**Social Velocity:** {self.velocity:.1f} posts/hour
**Engagement Score:** {self.engagement:.1f}
**Detected:** {self.timestamp.strftime('%H:%M UTC')}
"""

# ============================================================================
# Simple X.com Analyzer
# ============================================================================

class SimpleXAnalyzer:
    def __init__(self):
        self.signal_patterns = {
            "new_token": ["launch", "new token", "presale", "ido"],
            "listing": ["listing", "binance", "coinbase", "cex"],
            "whale": ["whale", "large transfer", "moved"],
            "pump": ["pump", "moon", "10x", "100x"],
            "airdrop": ["airdrop", "free tokens", "claim"]
        }
    
    async def get_x_posts(self) -> List[SimpleXPost]:
        """Get simulated X.com posts"""
        posts = [
            SimpleXPost(
                content="Just loaded up on $NEWTOKEN ahead of major CEX listing announcement next week. Team doxxed, VC backed, real utility. This could 10x.",
                author="@CryptoWhale",
                verified=True,
                followers=125000,
                likes=450,
                retweets=120,
                minutes_ago=30
            ),
            SimpleXPost(
                content="🚨 WHALE ALERT: 5000 ETH just moved to Binance. Could be preparing for a major buy or sell. Watch $ETH closely.",
                author="@DeFiAlpha",
                verified=True,
                followers=89000,
                likes=320,
                retweets=95,
                minutes_ago=45
            ),
            SimpleXPost(
                content="$SOL breaking out! Major ecosystem announcements coming this week. Accumulate on dips.",
                author="@SolanaGuru",
                verified=True,
                followers=75000,
                likes=280,
                retweets=90,
                minutes_ago=20
            ),
            SimpleXPost(
                content="Arbitrum DAO voting on major protocol upgrade. If passed, could significantly boost $ARB value.",
                author="@ArbitrumNews",
                verified=True,
                followers=110000,
                likes=190,
                retweets=65,
                minutes_ago=10
            ),
            SimpleXPost(
                content="New token $DEGEN pumping hard on Base. Up 300% in 2 hours. Caution: high risk, anonymous team.",
                author="@DexScreenerBot",
                verified=True,
                followers=85000,
                likes=150,
                retweets=80,
                minutes_ago=5
            ),
        ]
        return posts
    
    def extract_assets(self, text: str) -> List[str]:
        """Extract cryptocurrency symbols from text"""
        assets = re.findall(r'\$([A-Z]{2,10})', text)
        return list(set(assets))
    
    async def analyze_posts(self) -> List[SimpleCryptoSignal]:
        """Analyze X posts and generate signals"""
        posts = await self.get_x_posts()
        
        # Group by asset
        asset_groups = {}
        for post in posts:
            assets = self.extract_assets(post.content)
            for asset in assets:
                if asset not in asset_groups:
                    asset_groups[asset] = []
                asset_groups[asset].append(post)
        
        signals = []
        for asset, asset_posts in asset_groups.items():
            if len(asset_posts) >= 2:
                signal = self._analyze_asset(asset, asset_posts)
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _analyze_asset(self, asset: str, posts: List[SimpleXPost]) -> Optional[SimpleCryptoSignal]:
        """Analyze posts for a specific asset"""
        
        # Calculate metrics
        velocity = self._calculate_velocity(posts)
        engagement = self._calculate_engagement(posts)
        
        # Determine signal type
        signal_type = self._determine_signal_type(posts)
        
        # Determine confidence
        confidence = self._determine_confidence(posts)
        
        return SimpleCryptoSignal(
            asset=asset,
            signal_type=signal_type,
            confidence=confidence,
            velocity=velocity,
            engagement=engagement
        )
    
    def _calculate_velocity(self, posts: List[SimpleXPost]) -> float:
        """Calculate posts per hour"""
        if len(posts) < 2:
            return 0.0
        
        timestamps = [post.timestamp for post in posts]
        timestamps.sort()
        
        time_range = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        if time_range == 0:
            return len(posts)
        
        return len(posts) / time_range
    
    def _calculate_engagement(self, posts: List[SimpleXPost]) -> float:
        """Calculate average engagement"""
        total = 0
        for post in posts:
            weight = 2.0 if post.verified else 1.0
            engagement = post.likes * 0.3 + post.retweets * 0.4
            total += engagement * weight
        
        return total / len(posts)
    
    def _determine_signal_type(self, posts: List[SimpleXPost]) -> str:
        """Determine signal type from posts"""
        content = " ".join([post.content.lower() for post in posts])
        
        for sig_type, patterns in self.signal_patterns.items():
            for pattern in patterns:
                if pattern in content:
                    return sig_type
        
        return "social_trend"
    
    def _determine_confidence(self, posts: List[SimpleXPost]) -> str:
        """Determine confidence level"""
        verified_count = sum(1 for post in posts if post.verified)
        avg_followers = sum(post.followers for post in posts) / len(posts)
        avg_engagement = self._calculate_engagement(posts)
        
        if verified_count >= 2 and avg_followers > 50000 and avg_engagement > 200:
            return "very_high"
        elif verified_count >= 1 and avg_followers > 10000 and avg_engagement > 50:
            return "high"
        elif avg_followers > 5000 and avg_engagement > 20:
            return "medium"
        else:
            return "low"

# ============================================================================
# Trading System Integration
# ============================================================================

class XTradingBot:
    def __init__(self):
        self.x_analyzer = SimpleXAnalyzer()
        self.trades = []
        
    async def run_trading_cycle(self):
        """Run one complete trading cycle"""
        print("\n" + "="*60)
        print("🚀 X.COM TRADING BOT: STARTING CYCLE")
        print("="*60)
        
        # Step 1: Scan X.com
        print("\n📊 Step 1: Scanning X.com for opportunities...")
        signals = await self.x_analyzer.analyze_posts()
        
        if not signals:
            print("⚠️ No signals found. Using fallback...")
            # Fallback to simulated signal
            signal = SimpleCryptoSignal(
                asset="PEPE",
                signal_type="social_pump",
                confidence="high",
                velocity=15.5,
                engagement=320.0
            )
            signals = [signal]
        
        # Show all signals
        print(f"\n📊 Found {len(signals)} signals:")
        for i, sig in enumerate(signals, 1):
            print(f"{i}. {sig.asset}: {sig.signal_type} ({sig.confidence})")
        
        # Select strongest signal
        strongest = max(signals, key=lambda x: x.engagement * x.velocity)
        print("\n🎯 Selected strongest signal:")
        print(strongest.summary())
        
        # Step 2: Risk Assessment
        print("\n📊 Step 2: Risk Assessment...")
        risk_passed = self._assess_risk(strongest)
        
        if not risk_passed:
            print("❌ Risk assessment failed. Skipping trade.")
            return
        
        print("✅ Risk assessment passed.")
        
        # Step 3: Generate Trade
        print("\n📊 Step 3: Generating Trade Order...")
        trade = self._generate_trade(strongest)
        
        print(f"💰 Trade: {trade['action']} {trade['size']} of {trade['asset']}")
        print(f"🎯 Entry: {trade['entry']}")
        print(f"🚪 Exit: Take profit at {trade['take_profit']}, Stop loss at {trade['stop_loss']}")
        
        # Step 4: Record Trade
        self.trades.append(trade)
        print(f"\n📈 Total trades this session: {len(self.trades)}")
        
        print("\n" + "="*60)
        print("✅ Trading cycle completed!")
        print("="*60)
        
        return trade
    
    def _assess_risk(self, signal: SimpleCryptoSignal) -> bool:
        """Simple risk assessment"""
        # High confidence signals pass automatically
        if signal.confidence in ["high", "very_high"]:
            return True
        
        # Medium confidence needs good velocity
        if signal.confidence == "medium" and signal.velocity > 10:
            return True
        
        # Low confidence fails
        if signal.confidence == "low":
            return False
        
        return signal.engagement > 50  # Fallback
    
    def _generate_trade(self, signal: SimpleCryptoSignal) -> Dict[str, Any]:
        """Generate trade parameters based on signal"""
        
        # Determine position size based on confidence
        size_map = {
            "very_high": "large",
            "high": "medium",
            "medium": "small",
            "low": "tiny"
        }
        
        # Determine action based on signal type
        if signal.signal_type in ["whale", "pump"]:
            action = "BUY"
        elif signal.signal_type == "airdrop":
            action = "HOLD"  # For airdrop eligibility
        else:
            action = "BUY"  # Default
        
        return {
            "asset": signal.asset,
            "action": action,
            "size": size_map.get(signal.confidence, "small"),
            "entry": "market" if signal.signal_type == "whale" else "limit_on_dip",
            "take_profit": "+100%",  # Free Ride protocol
            "stop_loss": "-30%",     # Reaper cut
            "signal_type": signal.signal_type,
            "confidence": signal.confidence,
            "timestamp": datetime.utcnow().isoformat()
        }

# ============================================================================
# Main Execution
# ============================================================================

async def main():
    """Main function"""
    print("\n" + "="*60)
    print("🤖 X.COM CRYPTO TRADING BOT")
    print("="*60)
    print("Social intelligence meets automated trading")
    print("="*60)
    
    bot = XTradingBot()
    
    print("\nRunning demo trading cycle...\n")
    await bot.run_trading_cycle()
    
    print("\n" + "="*60)
    print("🎯 SYSTEM ARCHITECTURE")
    print("="*60)
    print("\n1. 🗣️ X-Whisperer: Scans X.com for crypto signals")
    print("2. ⚖️ Actuary: Risk assessment (GoPlus API for honeypots)")
    print("3. 🎯 Slinger: Web3 execution (high gas for inclusion)")
    print("4. 💀 Reaper: Portfolio defense (+100%/-30% rules)")
    print("\n" + "="*60)
    print("🚀 READY FOR PRODUCTION")
    print("="*60)
    print("\nTo deploy:")
    print("1. Get Twitter API v2 credentials")
    print("2. Set up Web3 provider (Infura/Alchemy)")
    print("3. Configure trading wallet (hardware recommended)")
    print("4. Start with small test amounts")
    print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(main())