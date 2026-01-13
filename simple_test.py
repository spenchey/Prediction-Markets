#!/usr/bin/env python3
"""Simple test without emoji issues"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_api():
    """Test Polymarket API client."""
    print("\n" + "=" * 60)
    print("TEST 1: Polymarket API Client")
    print("=" * 60)

    from src.polymarket_client import PolymarketClient

    try:
        async with PolymarketClient() as client:
            print("\nFetching active markets...")
            markets = await client.get_active_markets(limit=5)

            if not markets:
                print("FAIL: No markets returned")
                return False

            print(f"SUCCESS: Fetched {len(markets)} markets")
            for m in markets[:3]:
                q = m.question[:50] if len(m.question) > 50 else m.question
                print(f"  - {q}...")
                print(f"    Yes: {m.outcome_prices.get('Yes', 0)*100:.1f}% | Volume: ${m.volume:,.0f}")

            print("\nFetching recent trades...")
            trades = await client.get_recent_trades(limit=50)

            if not trades:
                print("FAIL: No trades returned")
                return False

            print(f"SUCCESS: Fetched {len(trades)} trades")

            large = [t for t in trades if t.amount_usd >= 100]
            print(f"Trades over $100: {len(large)}")

            if large:
                t = large[0]
                print(f"  Example: ${t.amount_usd:,.2f} {t.side} {t.outcome}")
                print(f"  Trader: {t.trader_address[:25]}...")

            return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_whale_detector():
    """Test whale detection logic."""
    print("\n" + "=" * 60)
    print("TEST 2: Whale Detector")
    print("=" * 60)

    from src.polymarket_client import PolymarketClient
    from src.whale_detector import WhaleDetector

    try:
        detector = WhaleDetector(
            whale_threshold_usd=100,  # Low for testing
            std_multiplier=2.0
        )

        async with PolymarketClient() as client:
            trades = await client.get_recent_trades(limit=50)

        if not trades:
            print("WARN: No trades to analyze")
            return True  # Not a failure

        print(f"\nAnalyzing {len(trades)} trades...")
        alerts = await detector.analyze_trades(trades)

        print(f"SUCCESS: Generated {len(alerts)} alerts")

        if alerts:
            print("\nSample alerts:")
            for alert in alerts[:3]:
                print(f"  [{alert.severity}] {alert.alert_type}")
                print(f"  {alert.message[:60]}...")

        print(f"\nTracked {len(detector.wallet_profiles)} unique wallets")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database():
    """Test database operations."""
    print("\n" + "=" * 60)
    print("TEST 3: Database")
    print("=" * 60)

    from src.database import Database
    from src.polymarket_client import PolymarketClient

    try:
        db = Database("sqlite+aiosqlite:///./test_trades.db")
        await db.init()
        print("SUCCESS: Database initialized")

        async with PolymarketClient() as client:
            trades = await client.get_recent_trades(limit=10)

        if trades:
            saved = await db.save_trades(trades)
            print(f"SUCCESS: Saved {saved} trades")

            recent = await db.get_recent_trades(limit=5)
            print(f"SUCCESS: Retrieved {len(recent)} trades")

        await db.close()

        # Cleanup
        import os
        if os.path.exists("./test_trades.db"):
            os.remove("./test_trades.db")
            print("Cleaned up test database")

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "=" * 60)
    print("PREDICTION MARKET TRACKER - TEST SUITE")
    print("=" * 60)

    results = {}
    results['API Client'] = await test_api()
    results['Whale Detector'] = await test_whale_detector()
    results['Database'] = await test_database()

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED!")
        print("\nNext steps:")
        print("  1. Run: python run.py")
        print("  2. Open: http://localhost:8000/docs")
    else:
        print("SOME TESTS FAILED - check errors above")
    print("=" * 60 + "\n")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
