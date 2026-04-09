#!/usr/bin/env python3
"""
X.com Analyst Integration Module
Adapted to work with the Asymmetric Strike Team trading system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Data Models
# ============================================================================

class SignalType(Enum):
    """Types of crypto trading signals detected from X.com"""
    NEW_TOKEN_LAUNCH = "new_token_launch"
    EXCHANGE_LISTING = "exchange_listing"
    WHALE_ACTIVITY = "whale_activity"
    SOCIAL_PUMP = "social_pump"
    AIRDROP = "airdrop"
    GOVERNANCE_VOTE = "governance_vote"

class ConfidenceLevel(Enum):
    """Confidence in the signal"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class Timeframe(Enum):
    """Recommended trading timeframe"""
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"

@dataclass
class XPost:
    """Raw X.com post data"""
    post_id: str
    author_handle: str
    author_verified: bool
    author_followers: int
    content: str
    timestamp: datetime
    likes: int
    retweets: int
    replies: int
    sentiment_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class CryptoSignal:
    """Structured crypto opportunity signal"""
    signal_id: str
    signal_type: SignalType
    confidence: ConfidenceLevel
    timeframe: Timeframe
    source_posts: List[XPost]
    
    asset_name: str
    asset_symbol: str
    
    narrative: str
    catalysts: List[str]
    risks: List[str]
    
    social_velocity: float
    engagement_score: float
    sentiment_trend: float
    
    recommended_action: str
    position_size_suggestion: str
    entry_strategy: str
    exit_strategy: str
    
    detected_at: datetime
    expires_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['signal_type'] = self.signal_type.value
        data['confidence'] = self.confidence.value
        data['timeframe'] = self.timeframe.value
        data['source_posts'] = [post.to_dict() for post in self.source_posts]
        data['detected_at'] = self.detected_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        return data
    
    def to_nlp_summary(self) -> str:
        """Generate human-readable NLP summary"""
        return f"""
🚀 **Crypto Opportunity Detected**
**Asset:** {self.asset_name} ({self.asset_symbol})
**Signal Type:** {self.signal_type.value.replace('_', ' ').title()}
**Confidence:** {self.confidence.value.replace('_', ' ').title()}
**Timeframe:** {self.timeframe.value.replace('_', ' ').title()}

**Narrative:** {self.narrative}

**Key Catalysts:**
{chr(10).join(f'• {c}' for c in self.catalysts)}

**Identified Risks:**
{chr(10).join(f'• {r}' for r in self.risks)}

**Recommended Action:** {self.recommended_action}
**Position Size:** {self.position_size_suggestion}
**Entry Strategy:** {self.entry_strategy}
**Exit Strategy:** {self.exit_strategy}

**Social Metrics:**
• Velocity: {self.social_velocity:.1f} posts/hour
• Engagement Score: {self.engagement_score:.2f}
• Sentiment Trend: {'📈 Positive' if self.sentiment_trend > 0 else '📉 Negative' if self.sentiment_trend < 0 else '➡️ Neutral'}

**Expires:** {self.expires_at.strftime('%Y-%m-%d %H:%M UTC')}
"""

# ============================================================================
# X.com Data Collector
# ============================================================================

class XDataCollector:
    """Collects data from X.com (simulated for now)"""
    
    def __init__(self):
        self.tracked_keywords = [
            "crypto", "bitcoin", "ethereum", "defi", "nft", "web3",
            "launch", "airdrop", "listing", "whale", "buy", "sell",
            "pump", "alpha", "signal"
        ]
        
    async def fetch_recent_posts(self, hours: int = 1) -> List[XPost]:
        """Fetch recent posts from X.com (simulated)"""
        logger.info(f"Fetching X.com posts from last {hours} hours")
        
        # Simulated data - these would be real X.com posts in production
        simulated_posts = [
            XPost(
                post_id="001",
                author_handle="@CryptoWhale",
                author_verified=True,
                author_followers=125000,
                content="Just loaded up on $NEWTOKEN ahead of major CEX listing announcement next week. Team doxxed, VC backed, real utility. This could 10x.",
                timestamp=datetime.utcnow() - timedelta(minutes=30),
                likes=450,
                retweets=120,
                replies=85,
                sentiment_score=0.8
            ),
            XPost(
                post_id="002",
                author_handle="@DeFiAlpha",
                author_verified=True,
                author_followers=89000,
                content="🚨 WHALE ALERT: 5000 ETH just moved to Binance. Could be preparing for a major buy or sell. Watch $ETH closely.",
                timestamp=datetime.utcnow() - timedelta(minutes=45),
                likes=320,
                retweets=95,
                replies=60,
                sentiment_score=0.3
            ),
            XPost(
                post_id="003",
                author_handle="@NFTInsider",
                author_verified=False,
                author_followers=15000,
                content="New PFP project 'MoonCats' launching tomorrow. Free mint for first 1000. Team anonymous but art looks fire. DYOR.",
                timestamp=datetime.utcnow() - timedelta(minutes=15),
                likes=85,
                retweets=40,
                replies=30,
                sentiment_score=0.6
            ),
            XPost(
                post_id="004",
                author_handle="@SolanaGuru",
                author_verified=True,
                author_followers=75000,
                content="$SOL breaking out! Major ecosystem announcements coming this week. Accumulate on dips.",
                timestamp=datetime.utcnow() - timedelta(minutes=20),
                likes=280,
                retweets=90,
                replies=45,
                sentiment_score=0.7
            ),
            XPost(
                post_id="005",
                author_handle="@ArbitrumNews",
                author_verified=True,
                author_followers=110000,
                content="Arbitrum DAO voting on major protocol upgrade. If passed, could significantly boost $ARB value.",
                timestamp=datetime.utcnow() - timedelta(minutes=10),
                likes=190,
                retweets=65,
                replies=38,
                sentiment_score=0.5
            ),
            XPost(
                post_id="006",
                author_handle="@DexScreenerBot",
                author_verified=True,
                author_followers=85000,
                content="New token $DEGEN pumping hard on Base. Up 300% in 2 hours. Caution: high risk, anonymous team.",
                timestamp=datetime.utcnow() - timedelta(minutes=5),
                likes=150,
                retweets=80,
                replies=45,
                sentiment_score=0.4
            ),
            XPost(
                post_id="007",
                author_handle="@LayerZeroNews",
                author_verified=True,
                author_followers=95000,
                content="LayerZero airdrop confirmed for Q2. If you used the protocol, check eligibility. $ZRO potential.",
                timestamp=datetime.utcnow() - timedelta(minutes=25),
                likes=420,
                retweets=210,
                replies=180,
                sentiment_score=0.9
            ),
        ]
        
        return simulated_posts

# ============================================================================
# Grok-Powered Analysis Engine
# ============================================================================

class GrokAnalyzer:
    """Uses Grok model to analyze X.com posts and generate signals"""
    
    def __init__(self):
        self.signal_patterns = {
            SignalType.NEW_TOKEN_LAUNCH: ["launch", "new token", "presale", "ido"],
            SignalType.EXCHANGE_LISTING: ["listing", "binance", "coinbase", "cex"],
            SignalType.WHALE_ACTIVITY: ["whale", "large transfer", "moved"],
            SignalType.SOCIAL_PUMP: ["pump", "moon", "10x", "100x"],
            SignalType.AIRDROP: ["airdrop", "free tokens", "claim"],
            SignalType.GOVERNANCE_VOTE: ["dao", "governance", "voting"]
        }
        
    async def analyze_posts(self, posts: List[XPost]) -> List[CryptoSignal]:
        """Analyze X posts and generate crypto signals"""
        logger.info(f"Analyzing {len(posts)} posts with Grok")
        
        signals = []
        
        # Group posts by asset
        asset_groups = self._group_posts_by_asset(posts)
        
        for asset, asset_posts in asset_groups.items():
            if len(asset_posts) >= 2:  # Need multiple signals for confidence
                signal = await self._analyze_asset_posts(asset, asset_posts)
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _group_posts_by_asset(self, posts: List[XPost]) -> Dict[str, List[XPost]]:
        """Group posts by mentioned cryptocurrency/token"""
        asset_groups = {}
        
        for post in posts:
            assets = self._extract_assets(post.content)
            for asset in assets:
                if asset not in asset_groups:
                    asset_groups[asset] = []
                asset_groups[asset].append(post)
        
        return asset_groups
    
    def _extract_assets(self, text: str) -> List[str]:
        """Extract cryptocurrency/token mentions from text"""
        assets = []
        
        # Match $SYMBOL patterns
        symbol_matches = re.findall(r'\$([A-Z]{2,10})', text)
        assets.extend(symbol_matches)
        
        # Match common crypto names
        crypto_names = ["bitcoin", "ethereum", "solana", "cardano", "polkadot", 
                       "avalanche", "polygon", "arbitrum", "optimism", "base"]
        
        for name in crypto_names:
            if name.lower() in text.lower():
                assets.append(name.upper())
        
        return list(set(assets))
    
    async def _analyze_asset_posts(self, asset: str, posts: List[XPost]) -> Optional[CryptoSignal]:
        """Analyze posts about a specific asset"""
        
        # Calculate metrics
        social_velocity = self._calculate_social_velocity(posts)
        engagement_score = self._calculate_engagement_score(posts)
        sentiment_trend = self._calculate_sentiment_trend(posts)
        
        # Determine signal type
        signal_type = self._determine_signal_type(posts)
        
        # Determine confidence
        confidence = self._determine_confidence(posts)
        
        # Determine timeframe
        timeframe = self._determine_timeframe(signal_type, social_velocity)
        
        # Generate narrative
        narrative = await self._generate_narrative(asset, posts, signal_type)
        
        # Extract catalysts and risks
        catalysts = self._extract_catalysts(posts)
        risks = self._extract_risks(posts)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            asset, signal_type, confidence, timeframe, social_velocity
        )
        
        # Create signal
        signal = CryptoSignal(
            signal_id=f"sig_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{asset}",
            signal_type=signal_type,
            confidence=confidence,
            timeframe=timeframe,
            source_posts=posts,
            asset_name=asset,
            asset_symbol=asset,
            narrative=narrative,
            catalysts=catalysts,
            risks=risks,
            social_velocity=social_velocity,
            engagement_score=engagement_score,
            sentiment_trend=sentiment_trend,
            recommended_action=recommendations["action"],
            position_size_suggestion=recommendations["position_size"],
            entry_strategy=recommendations["entry_strategy"],
            exit_strategy=recommendations["exit_strategy"],
            detected_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=self._get_expiry_hours(timeframe))
        )
        
        return signal
    
    def _calculate_social_velocity(self, posts: List[XPost]) -> float:
        """Calculate posts per hour"""
        if len(posts) < 2:
            return 0.0
        
        timestamps = [post.timestamp for post in posts]
        timestamps.sort()
        
        time_range = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        if time_range == 0:
            return len(posts)
        
        return len(posts) / time_range
    
    def _calculate_engagement_score(self, posts: List[XPost]) -> float:
        """Calculate weighted engagement score"""
        total_score = 0
        for post in posts:
            author_weight = 2.0 if post.author_verified else 1.0
            engagement = post.likes * 0.3 + post.retweets * 0.4 + post.replies * 0.3
            total_score += engagement * author_weight
        
        return total_score / max(len(posts), 1)
    
    def _calculate_sentiment_trend(self, posts: List[XPost]) -> float:
        """Calculate sentiment trend over time"""
        if len(posts) < 2:
            return 0.0
        
        posts_sorted = sorted(posts, key=lambda x: x.timestamp)
        early_sentiment = posts_sorted[0].sentiment_score
        late_sentiment = posts_sorted[-1].sentiment_score
        
        time_diff = (posts_sorted[-1].timestamp - posts_sorted[0].timestamp).total_seconds() / 3600
        
        if time_diff == 0:
            return 0.0
        
        return (late_sentiment - early_sentiment) / time_diff
    
    def _determine_signal_type(self, posts: List[XPost]) -> SignalType:
        """Determine the type of signal from posts"""
        content = " ".join([post.content.lower() for post in posts])
        
        for signal_type, patterns in self.signal_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return signal_type
        
        # Default to social pump if high engagement
        avg_engagement = sum([post.likes + post.retweets for post in posts]) / len(posts)
        if avg_engagement > 100:
            return SignalType.SOCIAL_PUMP
        
        return SignalType.NEW_TOKEN_LAUNCH  # Default
    
    def _determine_confidence(self, posts: List[XPost]) -> ConfidenceLevel:
        """Determine confidence level based on post quality"""
        verified_count = sum(1 for post in posts if post.author_verified)
        avg_followers = sum(post.author_followers for post in posts) / len(posts)
        avg_engagement = self._calculate_engagement_score(posts)
        
        if verified_count >= 2 and avg_followers > 50000 and avg_engagement > 200:
            return ConfidenceLevel.VERY_HIGH
        elif verified_count >= 1 and avg_followers > 10000 and avg_engagement > 50:
            return ConfidenceLevel.HIGH
        elif avg_followers > 5000 and avg_engagement > 20:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def _determine_timeframe(self, signal_type: SignalType, velocity: float) -> Timeframe:
        """Determine trading timeframe"""
        if signal_type == SignalType.WHALE_ACTIVITY:
            return Timeframe.IMMEDIATE
        elif signal_type == SignalType.EXCHANGE_LISTING and velocity > 10:
            return Timeframe.SHORT_TERM
        elif signal_type == SignalType.GOVERNANCE_VOTE:
            return Timeframe.MEDIUM_TERM
        else:
            return Timeframe.LONG_TERM
    
    async def _generate_narrative(self, asset: str, posts: List[XPost], signal_type: SignalType) -> str:
        """Generate narrative summary (simulated Grok analysis)"""
        narratives = {
            SignalType.NEW_TOKEN_LAUNCH: f"{asset} is launching with strong community interest and potential for early gains.",
            SignalType.EXCHANGE_LISTING: f"{asset} is rumored to be listed on a major exchange, which could drive significant price movement.",
            SignalType.WHALE_ACTIVITY: f"Large whale movements detected for {asset}, indicating potential major market moves.",
            SignalType.SOCIAL_PUMP: f"{asset} is gaining rapid social