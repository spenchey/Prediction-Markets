# Kalshi Market Integration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Kalshi prediction market support to track whale trades alongside Polymarket, expanding market coverage to US-regulated prediction markets.

**Architecture:** Create a KalshiClient similar to PolymarketClient, integrate with existing WhaleDetector, and add market source tracking to alerts. Kalshi requires authentication for trade data access.

**Tech Stack:** httpx for async HTTP, existing whale detection infrastructure, Kalshi REST API v2

---

## Background: Kalshi API

Kalshi is a US-regulated prediction market (CFTC-regulated). Key differences from Polymarket:
- Requires authentication (API key or email/password)
- Has demo environment for testing
- Uses different data models (events, markets, positions)
- Prices in cents (0-100) instead of decimals (0-1)

**API Base URLs:**
- Production: `https://trading-api.kalshi.com/trade-api/v2`
- Demo: `https://demo-api.kalshi.co/trade-api/v2`

---

## Task 1: Research Kalshi API Structure

**Files:**
- Reference: Existing `src/kalshi_client.py` (partial implementation)

**Step 1: Review existing Kalshi client**

Read: `src/kalshi_client.py`
Note: Document what's already implemented vs what's needed

**Step 2: Document API endpoints needed**

```markdown
Required Kalshi API Endpoints:
- POST /login - Get auth token (email/password)
- GET /exchange/schedule - Trading schedule
- GET /events - List events (markets)
- GET /events/{event_ticker} - Single event details
- GET /markets - List markets
- GET /markets/{ticker} - Market details
- GET /markets/{ticker}/trades - Recent trades (KEY for whale tracking)
- GET /users/positions - User's positions (for tracking known whales)
```

**Step 3: Commit research notes**

```bash
git add docs/plans/
git commit -m "docs: add kalshi api research notes"
```

---

## Task 2: Complete Kalshi Authentication

**Files:**
- Modify: `src/kalshi_client.py`
- Create: `tests/test_kalshi_client.py`

**Step 1: Write failing test for authentication**

```python
# tests/test_kalshi_client.py
import pytest
from src.kalshi_client import KalshiClient

class TestKalshiAuth:
    """Tests for Kalshi authentication."""

    def test_client_initializes_with_demo_mode(self):
        """Client should initialize in demo mode by default."""
        client = KalshiClient(demo=True)
        assert client.demo == True
        assert "demo-api" in client.base_url

    def test_client_requires_credentials(self):
        """Client should require email and password."""
        client = KalshiClient(
            email="test@example.com",
            password="testpass",
            demo=True
        )
        assert client.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_login_returns_token_structure(self):
        """Login should return token (or error for invalid creds)."""
        client = KalshiClient(
            email="fake@example.com",
            password="fakepass",
            demo=True
        )
        # Will fail with auth error but should have proper structure
        result = await client.login()
        assert "token" in result or "error" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_kalshi_client.py -v`
Expected: FAIL - missing methods

**Step 3: Implement authentication in KalshiClient**

```python
# src/kalshi_client.py - Complete implementation
"""
Kalshi API Client

Handles authentication and data fetching from Kalshi prediction markets.
Kalshi is a CFTC-regulated prediction market in the US.

API Docs: https://trading-api.kalshi.com/v2/docs
"""
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from loguru import logger

from .config import settings


@dataclass
class KalshiMarket:
    """Represents a Kalshi prediction market."""
    ticker: str
    event_ticker: str
    title: str
    subtitle: str
    yes_price: float  # 0-100 cents
    no_price: float
    volume: int
    open_interest: int
    status: str
    close_time: Optional[datetime]


@dataclass
class KalshiTrade:
    """Represents a trade on Kalshi."""
    id: str
    market_ticker: str
    side: str  # "yes" or "no"
    count: int  # Number of contracts
    price: float  # Price in cents (0-100)
    amount_usd: float  # Total value
    timestamp: datetime
    taker_side: str
    # Note: Kalshi doesn't expose trader addresses publicly


class KalshiClient:
    """
    Client for interacting with Kalshi's API.

    Usage:
        async with KalshiClient(email="...", password="...", demo=True) as client:
            await client.login()
            markets = await client.get_markets()
            trades = await client.get_trades("INXD-24JAN01")
    """

    def __init__(
        self,
        email: str = None,
        password: str = None,
        api_key: str = None,
        demo: bool = True
    ):
        self.email = email or settings.KALSHI_EMAIL
        self.password = password or settings.KALSHI_PASSWORD
        self.api_key = api_key or settings.KALSHI_API_KEY
        self.demo = demo if settings.KALSHI_DEMO is None else settings.KALSHI_DEMO

        # Set base URL based on demo mode
        if self.demo:
            self.base_url = "https://demo-api.kalshi.co/trade-api/v2"
        else:
            self.base_url = "https://trading-api.kalshi.com/trade-api/v2"

        self._http_client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None

    async def __aenter__(self):
        """Set up the HTTP client."""
        self._http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()

    @property
    def http(self) -> httpx.AsyncClient:
        """Get HTTP client, ensuring it exists."""
        if self._http_client is None:
            raise RuntimeError("KalshiClient must be used as async context manager")
        return self._http_client

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        elif self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    async def login(self) -> Dict[str, Any]:
        """
        Login to Kalshi and get authentication token.

        Returns dict with 'token' on success or 'error' on failure.
        """
        if not self.email or not self.password:
            return {"error": "Email and password required"}

        try:
            response = await self.http.post(
                f"{self.base_url}/login",
                json={
                    "email": self.email,
                    "password": self.password
                }
            )

            if response.status_code == 200:
                data = response.json()
                self._token = data.get("token")
                logger.info("Successfully logged in to Kalshi")
                return {"token": self._token}
            else:
                error = response.json().get("error", "Login failed")
                logger.error(f"Kalshi login failed: {error}")
                return {"error": error}

        except httpx.HTTPError as e:
            logger.error(f"Kalshi login error: {e}")
            return {"error": str(e)}

    async def get_events(self, limit: int = 100, status: str = "open") -> List[Dict]:
        """
        Get list of events (market categories).

        Args:
            limit: Maximum events to fetch
            status: Filter by status ("open", "closed", "settled")
        """
        try:
            response = await self.http.get(
                f"{self.base_url}/events",
                params={"limit": limit, "status": status},
                headers=self._get_auth_headers()
            )
            response.raise_for_status()
            data = response.json()
            return data.get("events", [])

        except httpx.HTTPError as e:
            logger.error(f"Error fetching Kalshi events: {e}")
            return []

    async def get_markets(
        self,
        event_ticker: str = None,
        limit: int = 100,
        status: str = "open"
    ) -> List[KalshiMarket]:
        """
        Get list of markets.

        Args:
            event_ticker: Filter by event (optional)
            limit: Maximum markets to fetch
            status: Filter by status
        """
        try:
            params = {"limit": limit, "status": status}
            if event_ticker:
                params["event_ticker"] = event_ticker

            response = await self.http.get(
                f"{self.base_url}/markets",
                params=params,
                headers=self._get_auth_headers()
            )
            response.raise_for_status()
            data = response.json()

            markets = []
            for item in data.get("markets", []):
                try:
                    market = KalshiMarket(
                        ticker=item.get("ticker", ""),
                        event_ticker=item.get("event_ticker", ""),
                        title=item.get("title", ""),
                        subtitle=item.get("subtitle", ""),
                        yes_price=float(item.get("yes_bid", 50)),
                        no_price=float(item.get("no_bid", 50)),
                        volume=int(item.get("volume", 0)),
                        open_interest=int(item.get("open_interest", 0)),
                        status=item.get("status", ""),
                        close_time=None  # Parse if needed
                    )
                    markets.append(market)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse Kalshi market: {e}")
                    continue

            logger.info(f"Fetched {len(markets)} Kalshi markets")
            return markets

        except httpx.HTTPError as e:
            logger.error(f"Error fetching Kalshi markets: {e}")
            return []

    async def get_trades(
        self,
        market_ticker: str,
        limit: int = 100,
        min_ts: int = None
    ) -> List[KalshiTrade]:
        """
        Get recent trades for a market.

        This is KEY for whale tracking!

        Args:
            market_ticker: Market ticker (e.g., "INXD-24JAN01-T4750")
            limit: Maximum trades to fetch
            min_ts: Minimum timestamp (unix seconds)
        """
        try:
            params = {"limit": limit}
            if min_ts:
                params["min_ts"] = min_ts

            response = await self.http.get(
                f"{self.base_url}/markets/{market_ticker}/trades",
                params=params,
                headers=self._get_auth_headers()
            )
            response.raise_for_status()
            data = response.json()

            trades = []
            for item in data.get("trades", []):
                try:
                    count = int(item.get("count", 0))
                    price = float(item.get("yes_price", 50))
                    # Calculate USD value (each contract is $1 if it wins)
                    amount_usd = count * (price / 100)  # Convert cents to dollars

                    trade = KalshiTrade(
                        id=item.get("trade_id", ""),
                        market_ticker=market_ticker,
                        side=item.get("taker_side", ""),
                        count=count,
                        price=price,
                        amount_usd=amount_usd,
                        timestamp=datetime.fromisoformat(
                            item.get("created_time", "").replace("Z", "+00:00")
                        ),
                        taker_side=item.get("taker_side", "")
                    )
                    trades.append(trade)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse Kalshi trade: {e}")
                    continue

            logger.info(f"Fetched {len(trades)} trades for {market_ticker}")
            return trades

        except httpx.HTTPError as e:
            logger.error(f"Error fetching Kalshi trades: {e}")
            return []

    async def get_all_recent_trades(self, limit_per_market: int = 50) -> List[KalshiTrade]:
        """
        Get recent trades across all active markets.

        This scans multiple markets for whale activity.
        """
        all_trades = []

        markets = await self.get_markets(limit=50, status="open")

        for market in markets[:20]:  # Limit to top 20 to avoid rate limits
            trades = await self.get_trades(market.ticker, limit=limit_per_market)
            all_trades.extend(trades)

        # Sort by timestamp, newest first
        all_trades.sort(key=lambda t: t.timestamp, reverse=True)

        return all_trades[:200]  # Return max 200
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_kalshi_client.py -v`
Expected: PASS (at least for structure tests)

**Step 5: Commit**

```bash
git add src/kalshi_client.py tests/test_kalshi_client.py
git commit -m "feat: complete kalshi client implementation"
```

---

## Task 3: Add Kalshi to Whale Detector

**Files:**
- Modify: `src/whale_detector.py`
- Modify: `src/polymarket_client.py`

**Step 1: Write failing test**

```python
# Add to tests/test_whale_detector.py

class TestMultiSourceDetection:
    """Tests for detecting whales across multiple platforms."""

    @pytest.mark.asyncio
    async def test_alert_includes_market_source(self):
        """Alerts should indicate which platform the trade came from."""
        detector = create_detector(whale_threshold=1000)
        trade = create_trade(amount_usd=5000)

        # Add market_source attribute to trade
        trade.market_source = "polymarket"

        alerts = await detector.analyze_trade(trade, "Test Market")

        # Alerts should track the source
        assert len(alerts) > 0
        assert hasattr(alerts[0], 'market_source') or 'market_source' in alerts[0].to_dict()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_whale_detector.py::TestMultiSourceDetection -v`
Expected: FAIL

**Step 3: Add market_source to Trade and Alert**

```python
# Modify Trade dataclass in src/polymarket_client.py:
@dataclass
class Trade:
    """Represents a single trade on a prediction market."""
    id: str
    market_id: str
    trader_address: str
    outcome: str
    side: str
    size: float
    price: float
    amount_usd: float
    timestamp: datetime
    transaction_hash: str
    market_source: str = "polymarket"  # NEW: Track source platform

# Modify WhaleAlert in src/whale_detector.py:
@dataclass
class WhaleAlert:
    # ... existing fields ...
    market_source: str = "polymarket"  # NEW
```

**Step 4: Update to_dict() methods**

```python
# In WhaleAlert.to_dict():
def to_dict(self) -> Dict:
    return {
        # ... existing fields ...
        "market_source": self.market_source,
    }
```

**Step 5: Run tests**

Run: `pytest tests/test_whale_detector.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/whale_detector.py src/polymarket_client.py tests/test_whale_detector.py
git commit -m "feat: add market source tracking for multi-platform support"
```

---

## Task 4: Create Unified Trade Monitor

**Files:**
- Modify: `src/whale_detector.py`

**Step 1: Write failing test**

```python
# tests/test_multi_source_monitor.py
import pytest
from src.whale_detector import MultiSourceTradeMonitor

class TestMultiSourceMonitor:
    """Tests for monitoring multiple prediction market sources."""

    def test_monitor_initializes_with_sources(self):
        """Monitor should initialize with multiple data sources."""
        monitor = MultiSourceTradeMonitor(
            sources=["polymarket", "kalshi"],
            detector=None  # Will use real detector in impl
        )
        assert "polymarket" in monitor.sources
        assert "kalshi" in monitor.sources
```

**Step 2: Implement MultiSourceTradeMonitor**

```python
# Add to src/whale_detector.py:

class MultiSourceTradeMonitor:
    """
    Monitors multiple prediction market platforms for whale activity.

    Combines trades from Polymarket and Kalshi into unified stream.
    """

    def __init__(
        self,
        detector: WhaleDetector,
        sources: List[str] = None,
        poll_interval: int = 60,
        on_alert=None
    ):
        self.detector = detector
        self.sources = sources or ["polymarket"]
        self.poll_interval = poll_interval
        self.on_alert = on_alert
        self.seen_trades: Dict[str, Set[str]] = {s: set() for s in self.sources}
        self._running = False

        # Statistics per source
        self.stats: Dict[str, Dict] = {
            s: {"trades": 0, "alerts": 0} for s in self.sources
        }

    async def start(self):
        """Start monitoring all sources."""
        self._running = True
        logger.info(f"Starting multi-source monitor: {self.sources}")

        while self._running:
            try:
                await self._check_all_sources()
            except Exception as e:
                logger.error(f"Error in multi-source monitor: {e}")

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop monitoring."""
        self._running = False

    async def _check_all_sources(self):
        """Check all configured sources for new trades."""
        tasks = []

        if "polymarket" in self.sources:
            tasks.append(self._check_polymarket())

        if "kalshi" in self.sources:
            tasks.append(self._check_kalshi())

        await asyncio.gather(*tasks)

    async def _check_polymarket(self):
        """Check Polymarket for new trades."""
        from .polymarket_client import PolymarketClient

        async with PolymarketClient() as client:
            trades = await client.get_recent_trades(limit=100)

        # Mark source
        for trade in trades:
            trade.market_source = "polymarket"

        await self._process_trades(trades, "polymarket")

    async def _check_kalshi(self):
        """Check Kalshi for new trades."""
        from .kalshi_client import KalshiClient

        try:
            async with KalshiClient() as client:
                login_result = await client.login()
                if "error" in login_result:
                    logger.warning(f"Kalshi login failed: {login_result['error']}")
                    return

                kalshi_trades = await client.get_all_recent_trades()

            # Convert to unified Trade format
            from .polymarket_client import Trade
            trades = []
            for kt in kalshi_trades:
                trade = Trade(
                    id=kt.id,
                    market_id=kt.market_ticker,
                    trader_address="kalshi_anonymous",  # Kalshi doesn't expose
                    outcome="Yes" if kt.side == "yes" else "No",
                    side="buy" if kt.taker_side == "yes" else "sell",
                    size=kt.count,
                    price=kt.price / 100,
                    amount_usd=kt.amount_usd,
                    timestamp=kt.timestamp,
                    transaction_hash="",
                    market_source="kalshi"
                )
                trades.append(trade)

            await self._process_trades(trades, "kalshi")

        except Exception as e:
            logger.error(f"Error checking Kalshi: {e}")

    async def _process_trades(self, trades: List, source: str):
        """Process trades from a source."""
        new_trades = [
            t for t in trades
            if t.id not in self.seen_trades[source]
        ]

        if not new_trades:
            return

        for trade in new_trades:
            self.seen_trades[source].add(trade.id)

        # Keep set from growing forever
        if len(self.seen_trades[source]) > 50000:
            self.seen_trades[source] = set(list(self.seen_trades[source])[-25000:])

        # Analyze for alerts
        alerts = await self.detector.analyze_trades(new_trades)

        # Update stats
        self.stats[source]["trades"] += len(new_trades)
        self.stats[source]["alerts"] += len(alerts)

        # Trigger callbacks
        if self.on_alert and alerts:
            for alert in alerts:
                alert.market_source = source
                await self.on_alert(alert)
```

**Step 3: Run tests**

Run: `pytest tests/test_multi_source_monitor.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/whale_detector.py tests/test_multi_source_monitor.py
git commit -m "feat: add multi-source trade monitor for polymarket and kalshi"
```

---

## Task 5: Update Configuration for Kalshi

**Files:**
- Modify: `.env.example`

**Step 1: Add Kalshi configuration**

Already partially done in config.py. Update .env.example:

```bash
# ============================================================
# 🔷 KALSHI API
# ============================================================
# Get credentials from kalshi.com account

# For demo/testing environment:
# KALSHI_EMAIL=your@email.com
# KALSHI_PASSWORD=your-password
# KALSHI_DEMO=true

# For production (API key method):
# KALSHI_API_KEY=your-api-key
# KALSHI_DEMO=false
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add kalshi configuration to .env.example"
```

---

## Verification Checklist

Before marking complete:

- [ ] KalshiClient authenticates successfully (demo mode)
- [ ] Can fetch Kalshi markets
- [ ] Can fetch Kalshi trades
- [ ] Trades include market_source field
- [ ] MultiSourceTradeMonitor runs both sources
- [ ] Alerts indicate source platform
- [ ] All tests passing
- [ ] Configuration documented

---

## Next Steps After Implementation

1. **Get Kalshi Account:**
   - Sign up at kalshi.com
   - Enable API access
   - Test in demo environment first

2. **Market Filtering:**
   - Add Kalshi-specific market categories
   - Some Kalshi markets may overlap with sports

3. **Production Deployment:**
   - Configure Kalshi credentials
   - Enable both sources in TradeMonitor
   - Monitor for rate limit issues
