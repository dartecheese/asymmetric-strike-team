"""
Enhanced Whisperer - Combines DexScreener scanning with sentiment analysis
=======================================================================
Improves signal quality by adding sentiment scoring to velocity signals.
"""
import time
from typing import Optional
from core.models import TradeSignal

from .whisperer import Whisperer as BaseWhisperer
from .sentiment_enhancer import SentimentEnhancer

class EnhancedWhisperer:
    """
    Enhanced Whisperer: DexScreener scanning + sentiment analysis.
    """
    
    def __init__(self, min_velocity_score: int = 50, use_sentiment: bool = True):
        self.base_whisperer = BaseWhisperer(min_velocity_score=min_velocity_score)
        self.use_sentiment = use_sentiment
        
        if use_sentiment:
            self.sentiment_enhancer = SentimentEnhancer(use_santiment=False)  # Fallback mode for now
        else:
            self.sentiment_enhancer = None
    
    def scan_firehose(self) -> Optional[TradeSignal]:
        """
        Scan for signals and enhance with sentiment analysis.
        
        Returns:
            Enhanced TradeSignal or None if no signal found
        """
        print("🗣️  [Enhanced Whisperer] Scanning with sentiment analysis...")
        
        # Get base signal from DexScreener
        base_signal = self.base_whisperer.scan_firehose()
        
        if not base_signal:
            print("   No signal found this cycle.")
            return None
        
        print(f"   Base signal: {base_signal.token_address[:10]}... (score: {base_signal.narrative_score})")
        
        # Enhance with sentiment analysis
        if self.use_sentiment and self.sentiment_enhancer:
            enhanced_signal = self.sentiment_enhancer.enhance_signal(base_signal)
            
            # Only return if sentiment didn't kill the signal
            # (e.g., extremely negative sentiment might invalidate a signal)
            if self._should_keep_signal(enhanced_signal, base_signal):
                return enhanced_signal
            else:
                print(f"   ❌ Signal rejected due to negative sentiment")
                return None
        else:
            return base_signal
    
    def _should_keep_signal(self, enhanced_signal: TradeSignal, base_signal: TradeSignal) -> bool:
        """
        Determine if enhanced signal should be kept.
        
        Rules:
        1. If final score < 40, reject (too low confidence)
        2. If sentiment reduced score by > 20 points, reject (strong negative sentiment)
        3. Otherwise keep
        """
        final_score = enhanced_signal.narrative_score
        score_change = final_score - base_signal.narrative_score
        
        if final_score < 40:
            print(f"   Final score too low: {final_score} < 40")
            return False
        
        if score_change < -20:
            print(f"   Sentiment too negative: {score_change} point reduction")
            return False
        
        return True
    
    def scan_with_filters(self, 
                         min_score: int = 60,
                         max_tokens: int = 5) -> list[TradeSignal]:
        """
        Scan and return multiple filtered signals.
        
        Args:
            min_score: Minimum narrative score to include
            max_tokens: Maximum number of tokens to return
            
        Returns:
            List of enhanced TradeSignals
        """
        # This would implement batch scanning in production
        # For now, just return single scan result as list
        signal = self.scan_firehose()
        if signal and signal.narrative_score >= min_score:
            return [signal]
        return []


if __name__ == "__main__":
    # Test the Enhanced Whisperer
    print("Testing Enhanced Whisperer...")
    
    whisperer = EnhancedWhisperer(min_velocity_score=50, use_sentiment=True)
    
    print("\n1. First scan (with sentiment)...")
    signal1 = whisperer.scan_firehose()
    
    if signal1:
        print(f"\n✅ Signal found:")
        print(f"   Token: {signal1.token_address[:10]}...")
        print(f"   Chain: {signal1.chain}")
        print(f"   Score: {signal1.narrative_score}")
        print(f"   Reason: {signal1.reasoning[:80]}...")
    else:
        print("\n❌ No signal found")
    
    print("\n2. Testing without sentiment...")
    whisperer_no_sentiment = EnhancedWhisperer(min_velocity_score=50, use_sentiment=False)
    signal2 = whisperer_no_sentiment.scan_firehose()
    
    if signal2:
        print(f"   Found signal (score: {signal2.narrative_score})")
    
    print("\n✅ Enhanced Whisperer test complete")