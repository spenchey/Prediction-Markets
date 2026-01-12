#!/usr/bin/env python3
"""
Quick Test Script

Run this to verify the Polymarket tracker is working correctly.

Usage:
    python test_tracker.py
"""
import asyncio
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, '.')


async def test_polymarket_client():
    """Test the Polymarket API client."""
    print("\n" + "=" * 60)
    print("🔍 TEST 1: Polymarket API Client")
    print("=" * 60)
    
    from src.polymarket_client import PolymarketClient
    
    try:
        async with PolymarketClient() as client:
            # Test fetching markets
            print("\n📊 Fetching active markets...")
            markets = await client.get_active_markets(limit=5)
            
            if not markets:
                print("⚠️  No markets returned - API might be rate limited")
                print("   Try again in a minute")
                return False
            
            print(f"✅ Fetched {len(markets)} markets!\n")
            
            for m in markets[:3]:
                print(f"  📈 {m.question[:55]}...")
                print(f"     Yes: {m.outcome_prices['Yes']:.1%} | "
                      f"No: {m.outcome_prices['No']:.1%} | "
                      f"Volume: ${m.volume:,.0f}")
                print()
            
            # Test fetching trades
            print("💰 Fetching recent trades...")
            trades = await client.get_recent_trades(limit=20)
            
            if not trades:
                print("⚠️  No trades returned")
                return False
                
            print(f"✅ Fetched {len(trades)} trades!\n")
            
            # Show some stats
            total_volume = sum(t.amount_usd for t in trades)
            large_trades = [t for t in trades if t.amount_usd >= 100]
            
            print(f"   Total volume in sample: ${total_volume:,.2f}")
            print(f"   Trades over $100: {len(large_trades)}")
            
            if trades:
                t = max(trades, key=lambda x: x.amount_usd)
                print(f"\n   Largest trade:")
                print(f"   💵 ${t.amount_usd:,.2f} - {t.side} {t.outcome}")
                print(f"   👤 Trader: {t.trader_address[:25]}...")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_whale_detector():
    """Test the whale detection logic."""
    print("\n" + "=" * 60)
    print("🐋 TEST 2: Whale Detector")
    print("=" * 60)
    
    from src.polymarket_client import PolymarketClient
    from src.whale_detector import WhaleDetector
    
    try:
        # Create detector with low thresholds for testing
        detector = WhaleDetector(
            whale_threshold_usd=500,  # Lower for testing
            std_multiplier=2.0
        )
        
        # Fetch some trades
        async with PolymarketClient() as client:
            trades = await client.get_recent_trades(limit=100)
        
        if not trades:
            print("⚠️  No trades to analyze")
            return False
        
        print(f"\n📊 Analyzing {len(trades)} trades...")
        
        # Analyze trades
        alerts = await detector.analyze_trades(trades)
        
        print(f"✅ Generated {len(alerts)} alerts!\n")
        
        if alerts:
            print("🚨 Sample alerts:")
            for alert in alerts[:5]:
                print(f"\n   [{alert.severity}] {alert.alert_type}")
                print(f"   {alert.message}")
                print(f"   Trader: {alert.trade.trader_address[:20]}...")
        
        # Show wallet stats
        print(f"\n👥 Tracked {len(detector.wallet_profiles)} unique wallets")
        
        top_wallets = detector.get_top_wallets(3)
        if top_wallets:
            print("\n   Top wallets by volume:")
            for w in top_wallets:
                print(f"   - {w.address[:15]}... ${w.total_volume_usd:,.0f} ({w.total_trades} trades)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database():
    """Test database operations."""
    print("\n" + "=" * 60)
    print("🗄️  TEST 3: Database")
    print("=" * 60)
    
    from src.database import Database
    from src.polymarket_client import PolymarketClient
    
    try:
        # Use a test database
        db = Database("sqlite+aiosqlite:///./test_trades.db")
        await db.init()
        print("\n✅ Database initialized!")
        
        # Fetch and save some trades
        async with PolymarketClient() as client:
            trades = await client.get_recent_trades(limit=20)
        
        if trades:
            saved = await db.save_trades(trades)
            print(f"✅ Saved {saved} new trades to database")
            
            # Retrieve trades
            recent = await db.get_recent_trades(limit=5)
            print(f"✅ Retrieved {len(recent)} trades from database")
            
            for trade in recent[:3]:
                print(f"   ${trade.amount_usd:,.2f} - {trade.side} {trade.outcome}")
        
        await db.close()
        
        # Clean up test database
        import os
        if os.path.exists("./test_trades.db"):
            os.remove("./test_trades.db")
            print("\n🧹 Cleaned up test database")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "🧪 " * 20)
    print("   PREDICTION MARKET TRACKER - TEST SUITE")
    print("🧪 " * 20)
    print(f"\n   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Run tests
    results['Polymarket Client'] = await test_polymarket_client()
    results['Whale Detector'] = await test_whale_detector()
    results['Database'] = await test_database()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! Your tracker is ready to use.")
        print("\nNext steps:")
        print("   1. Run: uvicorn src.main:app --reload")
        print("   2. Open: http://localhost:8000/docs")
        print("   3. Watch for whale alerts in the console!")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        print("\nCommon fixes:")
        print("   - Make sure you have internet connection")
        print("   - Polymarket might be rate limiting - wait a minute")
        print("   - Check if all dependencies are installed")
    print("=" * 60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
