#!/usr/bin/env python3
"""Debug API responses"""
import asyncio
import httpx
import json

async def debug():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test Gamma API (markets)
        print("=" * 60)
        print("Testing Gamma API (markets)...")
        print("=" * 60)

        try:
            resp = await client.get(
                "https://gamma-api.polymarket.com/markets",
                params={"active": "true", "limit": 2}
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    print(f"Got {len(data)} markets")
                    print("\nFirst market structure:")
                    print(json.dumps(data[0], indent=2)[:2000])
                else:
                    print("Empty response")
        except Exception as e:
            print(f"Error: {e}")

        print()
        print("=" * 60)
        print("Testing CLOB API (trades)...")
        print("=" * 60)

        try:
            resp = await client.get(
                "https://clob.polymarket.com/trades",
                params={"limit": 5}
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(json.dumps(data[:1], indent=2) if data else "Empty")
            else:
                print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

        print()
        print("=" * 60)
        print("Testing alternative: data-api (public trades)")
        print("=" * 60)

        try:
            resp = await client.get(
                "https://data-api.polymarket.com/trades",
                params={"limit": 5}
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    print(f"Got {len(data)} trades")
                    print("\nFirst trade structure:")
                    print(json.dumps(data[0], indent=2)[:1500])
            else:
                print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug())
