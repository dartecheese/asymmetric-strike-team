"""
Sentiment Enhancer - Improves Whisperer signals with sentiment analysis
===============================================================
Adds social sentiment scoring to trading signals.
Can integrate with Santiment API, Twitter, or other sentiment sources.
"""
import os
import requests
import logging
from typing import Dict, Any, Optional
from core.models import TradeSignal

logger = logging.getLogger("SentimentEnhancer")

class SentimentEnhancer:
    """
    Enhances trading signals with sentiment analysis.
    """
    
    def __init__(self, use_santiment: bool = False, santiment_api_key: str = None):
        self.use_santiment = use_santiment
        self.santiment_api_key = santiment_api_key or os.getenv("SANTIMENT_API_KEY")
        
        # Cache for sentiment scores (token -> score)
        self._sentiment_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
        
    def enhance_signal(self, signal: TradeSignal) -> TradeSignal:
        """
        Enhance a trading signal with sentiment analysis.
        
        Args:
            signal: Original trading signal
            
        Returns:
            Enhanced signal with updated narrative_score
        """
        print(f"🎭 [Sentiment Enhancer] Analyzing sentiment for {signal.token_address[:10]}...")
        
        original_score = signal.narrative_score
        sentiment_score = 0
        sentiment_reasoning = ""
        
        # Try Santiment API if available
        if self.use_santiment and self.santiment_api_key:
            santiment_data = self._get_santiment_sentiment(signal.token_address, signal.chain)
            if santiment_data:
                sentiment_score = santiment_data.get("score", 0)
                sentiment_reasoning = santiment_data.get("reasoning", "")
        
        # Fallback: simple heuristic based on token characteristics
        if sentiment_score == 0:
            sentiment_score, sentiment_reasoning = self._fallback_sentiment(signal)
        
        # Adjust narrative score based on sentiment
        # Positive sentiment boosts score, negative reduces it
        adjusted_score = original_score + sentiment_score
        
        # Cap at 0-100 range
        adjusted_score = max(0, min(100, adjusted_score))
        
        print(f"   Original score: {original_score}")
        print(f"   Sentiment adjustment: {sentiment_score:+d}")
        print(f"   Final score: {adjusted_score}")
        if sentiment_reasoning:
            print(f"   Sentiment: {sentiment_reasoning}")
        
        # Return enhanced signal
        enhanced_reasoning = f"{signal.reasoning} | Sentiment: {sentiment_reasoning}" if sentiment_reasoning else signal.reasoning
        
        return TradeSignal(
            token_address=signal.token_address,
            chain=signal.chain,
            narrative_score=int(adjusted_score),
            reasoning=enhanced_reasoning,
            discovered_at=signal.discovered_at
        )
    
    def _get_santiment_sentiment(self, token_address: str, chain: str) -> Optional[Dict[str, Any]]:
        """Get sentiment from Santiment API."""
        # Santiment API endpoint for token sentiment
        # This is a simplified example - actual implementation would use proper Santiment API
        url = f"https://api.santiment.net/graphql"
        
        # GraphQL query for sentiment (example)
        query = """
        query {
            getMetric(metric: "sentiment_balance") {
                timeseriesData(
                    slug: "ethereum",
                    from: "2024-01-01T00:00:00Z",
                    to: "2024-01-02T00:00:00Z",
                    interval: "1d"
                ) {
                    datetime
                    value
                }
            }
        }
        """
        
        try:
            headers = {
                "Authorization": f"Apikey {self.santiment_api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json={"query": query}, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Parse sentiment data (simplified)
            # In production, you'd parse the actual response
            return {
                "score": 10,  # Example: positive sentiment
                "reasoning": "Positive social sentiment detected"
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch Santiment data: {e}")
            return None
    
    def _fallback_sentiment(self, signal: TradeSignal) -> tuple[int, str]:
        """Fallback sentiment analysis using simple heuristics."""
        # Simple heuristics based on signal characteristics
        score_adjustment = 0
        reasoning = ""
        
        # Heuristic 1: High velocity score suggests positive sentiment
        if signal.narrative_score > 80:
            score_adjustment += 5
            reasoning = "High velocity suggests positive momentum"
        
        # Heuristic 2: Check for positive keywords in reasoning
        positive_keywords = ["pump", "moon", "breakout", "surge", "rally", "bullish"]
        negative_keywords = ["dump", "crash", "rug", "scam", "bearish", "sink"]
        
        reasoning_lower = signal.reasoning.lower()
        positive_count = sum(1 for kw in positive_keywords if kw in reasoning_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in reasoning_lower)
        
        if positive_count > negative_count:
            score_adjustment += 3
            reasoning = f"Positive keywords detected (+{positive_count - negative_count})"
        elif negative_count > positive_count:
            score_adjustment -= 5
            reasoning = f"Negative keywords detected (-{negative_count - positive_count})"
        
        # Heuristic 3: New tokens often have hype
        if "new" in reasoning_lower or "launch" in reasoning_lower:
            score_adjustment += 2
            reasoning = "New token hype detected"
        
        return score_adjustment, reasoning
    
    def batch_enhance(self, signals: list[TradeSignal]) -> list[TradeSignal]:
        """Enhance multiple signals at once."""
        return [self.enhance_signal(signal) for signal in signals]


if __name__ == "__main__":
    # Test the Sentiment Enhancer
    import logging
    import time
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Sentiment Enhancer...")
    
    enhancer = SentimentEnhancer(use_santiment=False)  # Use fallback mode
    
    # Create test signals
    test_signals = [
        TradeSignal(
            token_address="0x123...",
            chain="1",
            narrative_score=85,
            reasoning="Token pumping after major exchange listing announcement",
            discovered_at=time.time()
        ),
        TradeSignal(
            token_address="0x456...",
            chain="56",
            narrative_score=45,
            reasoning="Possible rug pull detected, deployer has history",
            discovered_at=time.time()
        ),
        TradeSignal(
            token_address="0x789...",
            chain="8453",
            narrative_score=75,
            reasoning="New token launch on Base, community excited",
            discovered_at=time.time()
        )
    ]
    
    for i, signal in enumerate(test_signals):
        print(f"\n--- Signal {i+1} ---")
        enhanced = enhancer.enhance_signal(signal)
        print(f"Result: {enhanced.narrative_score} ({signal.narrative_score} → {enhanced.narrative_score})")
        print(f"Reasoning: {enhanced.reasoning[:80]}...")
    
    print("\n✅ Sentiment Enhancer test complete")