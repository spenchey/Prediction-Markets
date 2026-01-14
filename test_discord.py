#!/usr/bin/env python3
"""
Quick test script to verify Discord webhook is working.

Usage:
    python test_discord.py <WEBHOOK_URL>

Or set DISCORD_WEBHOOK_URL in .env and run:
    python test_discord.py
"""
import asyncio
import sys
import os
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def send_test_message(webhook_url: str):
    """Send a test message to Discord (supports forum channels)."""
    import httpx

    embed = {
        "title": "Test Alert - Whale Tracker",
        "description": "This is a test message to verify Discord alerts are working!",
        "color": 0x4CAF50,  # Green
        "fields": [
            {"name": "Amount", "value": "$12,345.67", "inline": True},
            {"name": "Outcome", "value": "Yes", "inline": True},
            {"name": "Severity", "value": "TEST", "inline": True},
            {"name": "Market", "value": "Test Market - Will Bitcoin hit $100k?", "inline": False},
            {"name": "Trader", "value": "`0x1234567890abcdef...`", "inline": False},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Whale Tracker - Test Message"}
    }

    payload = {
        "embeds": [embed],
        "username": "Whale Tracker"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json=payload, timeout=10.0)

        if response.status_code in [200, 204]:
            print("SUCCESS! Test message sent to Discord!")
            print("   Check your Discord channel for the test alert.")
            return True

        # Check if forum channel error
        if response.status_code == 400:
            try:
                error_data = response.json()
                if error_data.get("code") == 220001:
                    print("Detected forum channel, retrying with thread_name...")
                    payload["thread_name"] = "Whale Tracker Test"
                    response2 = await client.post(webhook_url, json=payload, timeout=10.0)
                    if response2.status_code in [200, 204]:
                        print("SUCCESS! Test message sent to Discord forum channel!")
                        print("   Check your Discord channel for the test alert thread.")
                        return True
                    else:
                        print(f"FAILED on retry! Status: {response2.status_code}")
                        print(f"   Response: {response2.text}")
                        return False
            except Exception:
                pass

        print(f"FAILED! Status code: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def main():
    # Try to get webhook URL from argument or environment
    webhook_url = None

    if len(sys.argv) > 1:
        webhook_url = sys.argv[1]
    else:
        # Try to load from .env
        try:
            from dotenv import load_dotenv
            load_dotenv()
            webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        except ImportError:
            pass

    if not webhook_url:
        print("ERROR: No webhook URL provided!")
        print()
        print("Usage:")
        print("  python test_discord.py https://discord.com/api/webhooks/xxx/yyy")
        print()
        print("Or create a .env file with:")
        print("  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy")
        sys.exit(1)

    print(f"Testing webhook: {webhook_url[:50]}...")
    print()

    # Run the async test
    success = asyncio.run(send_test_message(webhook_url))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
