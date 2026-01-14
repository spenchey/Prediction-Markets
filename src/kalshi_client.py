"""
Kalshi API Client

Kalshi is a CFTC-regulated US prediction market exchange.

Supports both:
- PUBLIC elections API (market data only, no auth)
- AUTHENTICATED trading API (market + trade data, requires RSA signing)

API Documentation: https://docs.kalshi.com

IMPORTANT: Even with auth, Kalshi trades do NOT expose trader identities.
- Wallet-based alerts (NEW_WALLET, SMART_MONEY, etc.) won't work
- Only trade-size based alerts will work (WHALE_TRADE, UNUSUAL_SIZE, etc.)
"""
import httpx
import base64
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
import asyncio

from .config import settings
from .polymarket_client import Trade, Market

# Try to import cryptography for RSA signing
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography package not installed - Kalshi auth disabled")


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
    Client for Kalshi prediction market API.

    Supports:
    - Public elections API (market data, no auth needed)
    - Authenticated elections API (trade data, requires API key + RSA private key)

    Note: The trading API (trading-api.kalshi.com) has been deprecated.
    All requests now go through the elections API.

    IMPORTANT: Kalshi does NOT expose trader identities in their API.
    All trades will have trader_address="KALSHI_ANON".
    """

    # API endpoint (trading API has been deprecated, all goes through elections now)
    ELECTIONS_API = "https://api.elections.kalshi.com/trade-api/v2"

    # Platform identifier
    PLATFORM_NAME = "Kalshi"

    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None
        self._private_key = None
        self._api_key = settings.KALSHI_API_KEY
        self._load_private_key()

    def _load_private_key(self):
        """Load RSA private key from base64-encoded environment variable."""
        if not HAS_CRYPTO:
            return

        key_b64 = settings.KALSHI_PRIVATE_KEY_B64
        if not key_b64:
            return

        try:
            key_pem = base64.b64decode(key_b64)
            self._private_key = serialization.load_pem_private_key(
                key_pem,
                password=None,
                backend=default_backend()
            )
            logger.info("Kalshi RSA private key loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Kalshi private key: {e}")
            self._private_key = None

    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication credentials."""
        return bool(self._api_key and self._private_key and HAS_CRYPTO)

    @property
    def platform_name(self) -> str:
        return self.PLATFORM_NAME

    @property
    def supports_trader_identity(self) -> bool:
        """Kalshi does not expose trader identities."""
        return False

    def is_configured(self) -> bool:
        """Check if Kalshi is enabled."""
        return settings.KALSHI_ENABLED

    def _sign_request(self, method: str, path: str) -> Dict[str, str]:
        """
        Generate authentication headers for Kalshi API request.

        Kalshi uses RSA with PSS padding and SHA256.
        Message format: timestamp + method + path (WITHOUT query parameters)
        Example: "1705123456789GET/trade-api/v2/markets"
        """
        if not self.is_authenticated:
            return {}

        timestamp = str(int(time.time() * 1000))

        # Strip query parameters from path (sign only the path, not query string)
        path_without_query = path.split('?')[0]

        # Build full path for signing
        full_path = f"/trade-api/v2{path_without_query}" if not path_without_query.startswith("/trade-api") else path_without_query
        message = f"{timestamp}{method}{full_path}"

        try:
            # Use PSS padding as per Kalshi docs
            signature = self._private_key.sign(
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            signature_b64 = base64.b64encode(signature).decode('utf-8')

            return {
                "KALSHI-ACCESS-KEY": self._api_key,
                "KALSHI-ACCESS-TIMESTAMP": timestamp,
                "KALSHI-ACCESS-SIGNATURE": signature_b64
            }
        except Exception as e:
            logger.error(f"Failed to sign Kalshi request: {e}")
            return {}

    async def __aenter__(self):
        """Set up the HTTP client."""
        # Always use elections API (trading API has been deprecated)
        self._http_client = httpx.AsyncClient(
            base_url=self.ELECTIONS_API,
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "PredictionMarketTracker/1.0"
            },
            follow_redirects=True
        )

        if self.is_authenticated:
            logger.info("Kalshi client initialized with authentication")
        else:
            logger.debug("Kalshi client initialized without auth (public API only)")

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

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request to Kalshi API."""
        headers = kwargs.pop("headers", {})

        # Add auth headers if available
        if self.is_authenticated:
            auth_headers = self._sign_request(method.upper(), path)
            headers.update(auth_headers)

        return await self.http.request(method, path, headers=headers, **kwargs)

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
        amount_usd = count * price

        return Trade(
            id=f"kalshi_{trade_id}",
            market_id=market_ticker,
            trader_address="KALSHI_ANON",  # Kalshi doesn't expose trader identity
            outcome=outcome,
            side="buy",
            size=float(count),
            price=price,
            amount_usd=amount_usd,
            timestamp=timestamp,
            transaction_hash=f"kalshi_{trade_id}",
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
            slug=ticker,
            outcome_prices={"Yes": yes_price, "No": no_price},
            volume=float(item.get("volume", 0) or 0),
            liquidity=float(item.get("open_interest", 0) or 0),
            end_date=end_date,
            active=active,
            category=self._get_category(title)
        )

    async def get_active_markets(self, limit: int = 100) -> List[Market]:
        """Fetch active markets from Kalshi."""
        try:
            response = await self._request(
                "GET",
                "/markets",
                params={
                    "limit": min(limit, 200),
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
        Fetch recent trades from Kalshi using the global trades endpoint.

        Requires authentication. Without auth, returns empty list.

        Args:
            market_id: Optional market ticker to filter by
            limit: Maximum trades to fetch
        """
        if not self.is_authenticated:
            logger.debug("Kalshi trade fetching requires authentication")
            return []

        try:
            # Use the global /markets/trades endpoint
            params = {"limit": min(limit, 100)}
            if market_id:
                params["ticker"] = market_id

            response = await self._request("GET", "/markets/trades", params=params)
            response.raise_for_status()
            data = response.json()

            trades = []
            for item in data.get("trades", []):
                try:
                    # Get ticker from trade data
                    ticker = item.get("ticker", market_id or "UNKNOWN")
                    trade = self._convert_trade(item, ticker)
                    trades.append(trade)
                except Exception as e:
                    logger.warning(f"Failed to parse Kalshi trade: {e}")
                    continue

            # Sort by timestamp descending
            trades.sort(key=lambda t: t.timestamp, reverse=True)

            if trades:
                logger.info(f"Fetched {len(trades)} Kalshi trades")

            return trades

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning("Kalshi authentication failed - check API key and private key")
            else:
                logger.warning(f"Failed to fetch Kalshi trades: {e}")
            return []
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error fetching Kalshi trades: {e}")
            return []
        except Exception as e:
            logger.error(f"Kalshi trades error: {e}")
            return []

    async def get_market_by_ticker(self, ticker: str) -> Optional[Market]:
        """Fetch a specific market by its ticker."""
        try:
            response = await self._request("GET", f"/markets/{ticker}")
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
    print("TESTING KALSHI CLIENT")
    print("=" * 60)

    if not settings.KALSHI_ENABLED:
        print("\nKalshi is disabled in settings.")
        return

    async with KalshiClient() as client:
        print(f"\nAuthentication: {'YES' if client.is_authenticated else 'NO (public API only)'}")

        # Fetch markets
        print("\nFetching active markets...")
        markets = await client.get_active_markets(limit=10)

        if markets:
            print(f"Found {len(markets)} markets:\n")
            for m in markets[:5]:
                print(f"  [{m.category}] {m.question[:60]}...")
                print(f"    Ticker: {m.id}")
                print(f"    Yes: {m.outcome_prices['Yes']:.1%} | Volume: {m.volume:,.0f}")
                print()

        # Fetch trades (only works with auth)
        print("Fetching recent trades...")
        trades = await client.get_recent_trades(limit=20)

        if trades:
            print(f"Found {len(trades)} trades:\n")
            for t in trades[:5]:
                print(f"  ${t.amount_usd:,.2f} - {t.side} {t.outcome}")
                print(f"    Market: {t.market_id}")
                print(f"    Platform: {t.platform}")
                print()
        else:
            print("No trades found (authentication may be required)")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_kalshi())
