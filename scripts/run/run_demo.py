#!/usr/bin/env python3
"""
Demo runner for X.com Trading Bot
"""

import asyncio
import sys

# Add the simple bot to path
sys.path.insert(0, '.')

async def run_demo():
    """Run the demo"""
    from x_trading_bot_simple import XTradingBot
    
    print("\n" + "="*60)
    print("🚀 DEMO: X.COM CRYPTO TRADING BOT")
    print("="*60)
    
    bot = XTradingBot()
    
    # Run single cycle
    print("\nRunning single trading cycle...\n")
    await bot.run_trading_cycle()
    
    print("\n" + "="*60)
    print("✅ DEMO COMPLETE")
    print("="*60)
    print("\nWhat was demonstrated:")
    print("1. 📊 X.com social signal scanning")
    print("2. 🎯 Signal analysis and selection")
    print("3. ⚠️ Risk assessment")
    print("4. 💰 Trade generation with Free Ride protocol")
    print("5. 📈 Position sizing based on confidence")
    print("\nNext steps:")
    print("• Connect real X.com API (Twitter API v2)")
    print("• Integrate with actual Web3 execution")
    print("• Add real-time price monitoring")
    print("• Implement portfolio management")

if __name__ == "__main__":
    asyncio.run(run_demo())