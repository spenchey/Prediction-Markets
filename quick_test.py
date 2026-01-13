#!/usr/bin/env python3
"""Quick API test"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test():
    from src.polymarket_client import PolymarketClient

    print('Testing Polymarket API...')
    async with PolymarketClient() as client:
        print('Fetching markets...')
        markets = await client.get_active_markets(limit=3)
        print(f'Got {len(markets)} markets')

        if markets:
            for m in markets[:3]:
                q = m.question[:50] if len(m.question) > 50 else m.question
                print(f'  - {q}...')
                yes_pct = m.outcome_prices["Yes"] * 100
                vol = m.volume
                print(f'    Yes: {yes_pct:.1f}% | Volume: ${vol:,.0f}')
        else:
            print('  No markets returned - API may be blocked or changed')

        print()
        print('Fetching trades...')
        trades = await client.get_recent_trades(limit=20)
        print(f'Got {len(trades)} trades')

        if trades:
            large = [t for t in trades if t.amount_usd >= 100]
            print(f'Trades over $100: {len(large)}')
            if large:
                t = large[0]
                print(f'  Example: ${t.amount_usd:,.2f} {t.side} {t.outcome}')
                print(f'  Trader: {t.trader_address[:20]}...')
        else:
            print('  No trades returned - API may be blocked or changed')

        if markets and trades:
            print()
            print('SUCCESS! API is working.')
            return True
        else:
            print()
            print('ISSUE: API returned empty data.')
            return False

if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
