"""
Kalshi API Client

Kalshi is a CFTC-regulated US prediction market exchange.
This client uses their PUBLIC elections API which does not require authentication.

API Documentation: https://docs.kalshi.com
Elections API Base: https://api.elections.kalshi.com/trade-api/v2

IMPORTANT LIMITATIONS:
1. The public elections API only provides MARKET DATA (prices, volume, open interest)
2. TRADE DATA requires authentication with the trading API (RSA key signing)
3. Even with auth, Kalshi trades do NOT expose trader identities
   - Wallet-based alerts (NEW_WALLET, SMART_MONEY, etc.) won't work
   - Only trade-size based alerts would work if trades were available

Current capabilities:
- Fetch active markets with prices
- Monitor market price changes
- Track volume and open interest

Future (requires auth):
- Fetch trade data for size-based alerts
"""
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
import asyncio

from .config import settings
from .polymarket_client import Trade, Market


# Category keywords for Kalshi markets
KALSHI_CATEGORY_KEYWORDS = {
    "Politics": ["trump", "biden", "election", "president", "congress", "senate", "vote",
                 "democrat", "republican", "governor", "mayor", "party", "nominee"],
    "Crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto", "token", "blockchain"],
    "Finance": ["stock", "s&p", "nasdaq", "fed", "interest rate", "inflation", "gdp",
                "recession", "market", "dow", "treasury", "unemployment"],
    "Science": ["ai ", "openai", "climate", "fda", "vaccine", "space", "nasa", "weather",
                "hurricane", "earthquake", "temperature"],
    "Entertainment": ["oscar", "grammy", "emmy", "movie", "album", "celebrity", "twitter",
                      "tweet", "elon", "streaming"],
    "World": ["war", "ukraine", "russia", "china", "iran", "israel", "military", "invasion",
              "ceasefire", "nato"],
    "Sports": ["nfl", "nba", "mlb", "super bowl", "world series", "championship", "playoff"],
}


class KalshiClient:
    """
    Client for Kalshi's public elections API.

    Uses the public API which doesn't require authentication for read-only access.
    Perfect for monitoring markets and trades.

    IMPORTANT: Kalshi does NOT expose trader identities in their API.
    All trades will have trader_address="KALSHI_ANON".
    """

    # Public elections API - no auth required for reading
    ELECTIONS_API = "https://api.elections.kalshi.com/trade-api/v2"

    # Platform identifier
    PLATFORM_NAME = "Kalshi"

    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def platform_name(self) -> str:
        return self.PLATFORM_NAME

    @property
    def supports_trader_identity(self) -> bool:
        """Kalshi does not expose trader identities."""
        return False

    def is_configured(self) -> bool:
        """Kalshi public API is always available."""
        return settings.KALSHI_ENABLED

    async def __aenter__(self):
        """Set up the HTTP client."""
        self._http_client = httpx.AsyncClient(
            base_url=self.ELECTIONS_API,
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "User-Agent": "PredictionMarketTracker/1.0"
            },
            follow_redirects=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()

    @property
    def http(self) -> httpx.AsyncClient:
        """Get the HTTP client, ensuring it exists."""
        if self._http_client is None:
            raise RuntimeError(
                "KalshiClient must be used as async context manager: "
                "async with KalshiClient() as client: ..."
            )
        return self._http_client

    def _get_category(self, title: str) -> str:
        """Infer category from market title."""
        title_lower = title.lower()
        for category, keywords in KALSHI_CATEGORY_KEYWORDS.items():
            if any(kw in title_lower for kw in keywords):
                return category
        return "Other"

    def _convert_trade(self, item: Dict, market_ticker: str) -> Trade:
        """Convert Kalshi trade data to shared Trade dataclass."""
        # Parse timestamp
        created_time = item.get("created_time", "")
        if created_time:
            try:
                # Handle ISO format with timezone
                if created_time.endswith("Z"):
                    created_time = created_time.replace("Z", "+00:00")
                timestamp = datetime.fromisoformat(created_time)
            except (ValueError, TypeError):
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()

        # Get trade details
        trade_id = item.get("trade_id", str(item.get("id", "")))
        count = int(item.get("count", 0))

        # Kalshi prices are in cents (1-99), convert to 0-1 range
        yes_price_cents = item.get("yes_price", 50)
        price = yes_price_cents / 100.0

        # Determine which side was taken
        taker_side = item.get("taker_side", "yes").lower()
        outcome = "Yes" if taker_side == "yes" else "No"

        # Calculate USD value
        # Each Kalshi contract pays $1 if correct, so price is cost per contract
        amount_usd = count * price

        return Trade(
            id=f"kalshi_{trade_id}",
            market_id=market_ticker,
            trader_address="KALSHI_ANON",  # Kalshi doesn't expose trader identity
            outcome=outcome,
            side="buy",  # Taker is always buying the side they're taking
            size=float(count),
            price=price,
            amount_usd=amount_usd,
            timestamp=timestamp,
            transaction_hash=f"kalshi_{trade_id}",  # No tx hash on Kalshi
            platform="Kalshi"
        )

    def _convert_market(self, item: Dict) -> Market:
        """Convert Kalshi market data to shared Market dataclass."""
        ticker = item.get("ticker", "")
        title = item.get("title", item.get("question", ""))

        # Get prices - Kalshi uses different field names
        yes_bid = item.get("yes_bid", item.get("yes_ask", 50))
        no_bid = item.get("no_bid", item.get("no_ask", 50))

        # Convert cents to decimal (0-1)
        yes_price = yes_bid / 100.0 if yes_bid else 0.5
        no_price = no_bid / 100.0 if no_bid else 0.5

        # Normalize to sum to 1.0
        total = yes_price + no_price
        if total > 0:
            yes_price = yes_price / total
            no_price = no_price / total

        # Parse close time
        close_time_str = item.get("close_time", "")
        end_date = None
        if close_time_str:
            try:
                if close_time_str.endswith("Z"):
                    close_time_str = close_time_str.replace("Z", "+00:00")
                end_date = datetime.fromisoformat(close_time_str)
            except (ValueError, TypeError):
                pass

        # Determine status
        status = item.get("status", "").lower()
        active = status in ("open", "active", "")

        return Market(
            id=ticker,
            question=title,
            slug=ticker,  # Use ticker as slug for URL building
            outcome_prices={"Yes": yes_price, "No": no_price},
            volume=float(item.get("volume", 0) or 0),
            liquidity=float(item.get("open_interest", 0) or 0),
            end_date=end_date,
            active=active,
            category=self._get_category(title)
        )

    async def get_active_markets(self, limit: int = 100) -> List[Market]:
        """
        Fetch active markets from Kalshi.

        Returns Market objects compatible with the whale detection system.
        """
        try:
            response = await self.http.get(
                "/markets",
                params={
                    "limit": min(limit, 200),  # Kalshi max is 200
                    "status": "open"
                }
            )
            response.raise_for_status()
            data = response.json()

            markets = []
            for item in data.get("markets", []):
                try:
                    market = self._convert_market(item)
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse Kalshi market: {e}")
                    continue

            logger.info(f"Fetched {len(markets)} active Kalshi markets")
            return markets

        except httpx.HTTPError as e:
            logger.error(f"Kalshi markets API error: {e}")
            return []

    async def get_recent_trades(
        self,
        market_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        """
        Fetch recent trades from Kalshi.

        NOTE: The public Kalshi elections API does NOT expose trade data.
        Trade data requires authentication with the trading API.
        This method returns an empty list unless authenticated.

        For now, Kalshi integration provides:
        - Market data (prices, volume, open interest)
        - Market monitoring for price changes

        Trade-level whale detection is not available on Kalshi without auth.

        Args:
            market_id: Optional market ticker to filter by
            limit: Maximum trades to fetch (per market)
        """
        # Public API doesn't expose trades - would need authenticated trading API
        # Log this once per session
        logger.debug("Kalshi public API doesn't expose trade data (auth required)")
        return []

    async def _get_market_trades(self, ticker: str, limit: int = 100) -> List[Trade]:
        """Fetch trades for a specific market."""
        try:
            response = await self.http.get(
                f"/markets/{ticker}/trades",
                params={"limit": min(limit, 100)}
            )
            response.raise_for_status()
            data = response.json()

            trades = []
            for item in data.get("trades", []):
                try:
                    trade = self._convert_trade(item, ticker)
                    trades.append(trade)
                except Exception as e:
                    logger.warning(f"Failed to parse Kalshi trade: {e}")
                    continue

            return trades

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"No trades found for market {ticker}")
            else:
                logger.warning(f"Failed to fetch trades for {ticker}: {e}")
            return []
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error fetching trades for {ticker}: {e}")
            return []

    async def get_market_by_ticker(self, ticker: str) -> Optional[Market]:
        """Fetch a specific market by its ticker."""
        try:
            response = await self.http.get(f"/markets/{ticker}")
            response.raise_for_status()
            data = response.json()

            market_data = data.get("market", data)
            return self._convert_market(market_data)

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch Kalshi market {ticker}: {e}")
            return None

    def get_market_url(self, market: Market) -> str:
        """Generate Kalshi market URL."""
        return f"https://kalshi.com/markets/{market.slug}"

    def get_trader_url(self, trader_address: str) -> Optional[str]:
        """Kalshi does not expose trader profiles."""
        return None


# =========================================
# TEST THE CLIENT
# =========================================

async def test_kalshi():
    """Test the Kalshi client."""
    print("\n" + "=" * 60)
    print("TESTING KALSHI CLIENT (Public Elections API)")
    print("=" * 60)

    if not settings.KALSHI_ENABLED:
        print("\nKalshi is disabled in settings. Set KALSHI_ENABLED=true to enable.")
        return

    async with KalshiClient() as client:
        # Fetch markets
        print("\nFetching active markets...")
        markets = await client.get_active_markets(limit=10)

        if markets:
            print(f"Found {len(markets)} markets:\n")
            for m in markets[:5]:
                print(f"  [{m.category}] {m.question[:60]}...")
                print(f"    Ticker: {m.id}")
                print(f"    Yes: {m.outcome_prices['Yes']:.1%} | Volume: {m.volume:,.0f}")
                print(f"    URL: {client.get_market_url(m)}")
                print()
        else:
            print("No markets found (API may be unavailable)")
            return

        # Fetch trades
        print("\nFetching recent trades...")
        trades = await client.get_recent_trades(limit=20)

        if trades:
            print(f"Found {len(trades)} trades:\n")
            for t in trades[:5]:
                print(f"  ${t.amount_usd:,.2f} - {t.side} {t.outcome}")
                print(f"    Market: {t.market_id}")
                print(f"    Trader: {t.trader_address} (anonymous)")
                print(f"    Platform: {t.platform}")
                print()

            # Show any large trades
            large_trades = [t for t in trades if t.amount_usd >= 100]
            if large_trades:
                print(f"\nLarge trades (>=$100): {len(large_trades)}")
                for t in large_trades[:3]:
                    print(f"  ${t.amount_usd:,.2f} on {t.market_id}")
        else:
            print("No trades found")

    print("\n" + "=" * 60)
    print("Kalshi client working correctly!")
    print("Note: Trader identity is always 'KALSHI_ANON' (not exposed by API)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_kalshi())
