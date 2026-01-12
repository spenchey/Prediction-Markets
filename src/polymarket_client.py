"""
Polymarket API Client

This module handles all communication with Polymarket's APIs.
Polymarket has several APIs:
1. Gamma API (gamma-api.polymarket.com) - Market metadata, events
2. Data API (data-api.polymarket.com) - Public trade data (no auth needed!)
3. CLOB API (clob.polymarket.com) - Order book, requires auth for trades

Updated January 2026 to use correct endpoints.
"""
import httpx
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from dataclasses import dataclass
import asyncio


@dataclass
class Market:
    """Represents a prediction market."""
    id: str
    question: str
    slug: str
    outcome_prices: Dict[str, float]  # e.g., {"Yes": 0.65, "No": 0.35}
    volume: float
    liquidity: float
    end_date: Optional[datetime]
    active: bool


@dataclass
class Trade:
    """Represents a single trade on Polymarket."""
    id: str
    market_id: str
    trader_address: str  # Wallet address of the trader
    outcome: str  # "Yes" or "No"
    side: str  # "buy" or "sell"
    size: float  # Number of shares
    price: float  # Price per share (0-1)
    amount_usd: float  # Total USD value of the trade
    timestamp: datetime
    transaction_hash: str


class PolymarketClient:
    """
    Client for interacting with Polymarket's APIs.
    
    Usage:
        async with PolymarketClient() as client:
            markets = await client.get_active_markets()
            trades = await client.get_recent_trades(market_id)
    """
    
    def __init__(
        self,
        gamma_base_url: str = "https://gamma-api.polymarket.com",
        data_api_url: str = "https://data-api.polymarket.com",
        clob_base_url: str = "https://clob.polymarket.com"
    ):
        self.gamma_base_url = gamma_base_url
        self.data_api_url = data_api_url  # Public trades endpoint (no auth)
        self.clob_base_url = clob_base_url  # Order book (auth needed for trades)
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Set up the HTTP client when entering async context."""
        self._http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; PredictionMarketTracker/1.0)"
            },
            follow_redirects=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the HTTP client when exiting async context."""
        if self._http_client:
            await self._http_client.aclose()
    
    @property
    def http(self) -> httpx.AsyncClient:
        """Get the HTTP client, ensuring it exists."""
        if self._http_client is None:
            raise RuntimeError(
                "PolymarketClient must be used as async context manager: "
                "async with PolymarketClient() as client: ..."
            )
        return self._http_client
    
    # =========================================
    # MARKET DATA METHODS
    # =========================================
    
    async def get_active_markets(self, limit: int = 100) -> List[Market]:
        """
        Fetch active prediction markets from Polymarket.

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of Market objects
        """
        try:
            # Use the Gamma API for market metadata
            response = await self.http.get(
                f"{self.gamma_base_url}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "order": "volume24hr",  # Sort by trading volume
                    "ascending": "false"
                }
            )
            response.raise_for_status()
            data = response.json()

            markets = []
            for item in data:
                try:
                    # Skip closed markets
                    if item.get("closed", False):
                        continue

                    # Parse outcomePrices - it's a JSON string like '["0.65", "0.35"]'
                    outcome_prices_raw = item.get("outcomePrices", '["0.5", "0.5"]')
                    if isinstance(outcome_prices_raw, str):
                        prices = json.loads(outcome_prices_raw)
                    else:
                        prices = outcome_prices_raw

                    # Parse outcomes - also a JSON string
                    outcomes_raw = item.get("outcomes", '["Yes", "No"]')
                    if isinstance(outcomes_raw, str):
                        outcomes = json.loads(outcomes_raw)
                    else:
                        outcomes = outcomes_raw

                    # Build outcome prices dict
                    outcome_prices = {}
                    for i, outcome in enumerate(outcomes):
                        if i < len(prices):
                            outcome_prices[outcome] = float(prices[i])

                    # Default to Yes/No if not parsed
                    if "Yes" not in outcome_prices:
                        outcome_prices = {"Yes": 0.5, "No": 0.5}

                    market = Market(
                        id=item.get("conditionId", item.get("id", "")),
                        question=item.get("question", ""),
                        slug=item.get("slug", ""),
                        outcome_prices=outcome_prices,
                        volume=float(item.get("volume", 0) or 0),
                        liquidity=float(item.get("liquidity", 0) or 0),
                        end_date=None,
                        active=item.get("active", True) and not item.get("closed", False)
                    )
                    markets.append(market)
                except (KeyError, ValueError, IndexError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            logger.info(f"Fetched {len(markets)} active markets")
            return markets

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []
    
    async def get_market_by_id(self, market_id: str) -> Optional[Market]:
        """Fetch a specific market by its condition ID."""
        try:
            response = await self.http.get(
                f"{self.gamma_base_url}/markets/{market_id}"
            )
            response.raise_for_status()
            item = response.json()
            
            return Market(
                id=item.get("conditionId", market_id),
                question=item.get("question", ""),
                slug=item.get("slug", ""),
                outcome_prices={
                    "Yes": float(item.get("outcomePrices", ["0.5", "0.5"])[0]),
                    "No": float(item.get("outcomePrices", ["0.5", "0.5"])[1])
                },
                volume=float(item.get("volume", 0) or 0),
                liquidity=float(item.get("liquidity", 0) or 0),
                end_date=None,
                active=item.get("active", True)
            )
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch market {market_id}: {e}")
            return None
    
    # =========================================
    # TRADE DATA METHODS
    # =========================================
    
    async def get_recent_trades(
        self,
        market_id: Optional[str] = None,
        limit: int = 100,
        before_timestamp: Optional[datetime] = None
    ) -> List[Trade]:
        """
        Fetch recent trades from Polymarket.

        Uses the public Data API which provides trade data with wallet addresses
        for whale tracking - no authentication required!

        Args:
            market_id: Filter by specific market (optional)
            limit: Maximum trades to fetch
            before_timestamp: Get trades before this time

        Returns:
            List of Trade objects
        """
        try:
            params = {"limit": limit}

            if market_id:
                params["market"] = market_id

            # Use the public Data API for trades (no auth needed)
            response = await self.http.get(
                f"{self.data_api_url}/trades",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            trades = []
            for item in data:
                try:
                    # Calculate USD value of trade
                    size = float(item.get("size", 0))
                    price = float(item.get("price", 0))
                    amount_usd = size * price

                    # Parse timestamp - data-api returns Unix timestamp
                    ts = item.get("timestamp")
                    if isinstance(ts, int):
                        timestamp = datetime.fromtimestamp(ts)
                    elif isinstance(ts, str):
                        timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        timestamp = datetime.now()

                    # Generate a unique ID from tx hash + size
                    tx_hash = item.get("transactionHash", "")
                    trade_id = f"{tx_hash[:16]}_{size}" if tx_hash else str(ts)

                    trade = Trade(
                        id=trade_id,
                        market_id=item.get("conditionId", item.get("market", "")),
                        trader_address=item.get("proxyWallet", item.get("maker", "")),
                        outcome=item.get("outcome", ""),
                        side=item.get("side", "").lower(),  # Normalize to lowercase
                        size=size,
                        price=price,
                        amount_usd=amount_usd,
                        timestamp=timestamp,
                        transaction_hash=tx_hash
                    )
                    trades.append(trade)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse trade: {e}")
                    continue

            logger.info(f"Fetched {len(trades)} trades")
            return trades

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch trades: {e}")
            return []
    
    async def get_trades_by_address(
        self,
        wallet_address: str,
        limit: int = 100
    ) -> List[Trade]:
        """
        Fetch all trades by a specific wallet address.

        This is KEY for tracking whale behavior - you can see
        their entire trading history!

        Args:
            wallet_address: The Ethereum wallet address
            limit: Maximum trades to fetch

        Returns:
            List of Trade objects from this address
        """
        try:
            # Data API supports filtering by proxyWallet
            response = await self.http.get(
                f"{self.data_api_url}/trades",
                params={
                    "proxyWallet": wallet_address,
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()

            trades = []
            for item in data:
                try:
                    size = float(item.get("size", 0))
                    price = float(item.get("price", 0))

                    # Parse timestamp
                    ts = item.get("timestamp")
                    if isinstance(ts, int):
                        timestamp = datetime.fromtimestamp(ts)
                    elif isinstance(ts, str):
                        timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        timestamp = datetime.now()

                    tx_hash = item.get("transactionHash", "")
                    trade_id = f"{tx_hash[:16]}_{size}" if tx_hash else str(ts)

                    trade = Trade(
                        id=trade_id,
                        market_id=item.get("conditionId", item.get("market", "")),
                        trader_address=wallet_address,
                        outcome=item.get("outcome", ""),
                        side=item.get("side", "").lower(),
                        size=size,
                        price=price,
                        amount_usd=size * price,
                        timestamp=timestamp,
                        transaction_hash=tx_hash
                    )
                    trades.append(trade)
                except (KeyError, ValueError) as e:
                    continue

            logger.info(f"Found {len(trades)} trades for address {wallet_address[:10]}...")
            return trades

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch trades for address: {e}")
            return []
    
    # =========================================
    # ORDER BOOK METHODS
    # =========================================
    
    async def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Fetch the order book for a market.
        
        The order book shows all pending buy/sell orders,
        which can help predict where big moves might happen.
        
        Args:
            token_id: The token ID for the market outcome
            
        Returns:
            Dictionary with bids and asks
        """
        try:
            response = await self.http.get(
                f"{self.clob_base_url}/book",
                params={"token_id": token_id}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch order book: {e}")
            return {"bids": [], "asks": []}


# =========================================
# CONVENIENCE FUNCTIONS
# =========================================

async def fetch_whale_trades(
    min_amount_usd: float = 10000,
    limit: int = 500
) -> List[Trade]:
    """
    Convenience function to fetch trades and filter for whales.
    
    Args:
        min_amount_usd: Minimum USD value to consider a whale
        limit: Maximum trades to scan
        
    Returns:
        List of whale trades (above threshold)
    """
    async with PolymarketClient() as client:
        all_trades = await client.get_recent_trades(limit=limit)
        
        whale_trades = [
            trade for trade in all_trades
            if trade.amount_usd >= min_amount_usd
        ]
        
        logger.info(
            f"Found {len(whale_trades)} whale trades "
            f"(>=${min_amount_usd:,.0f}) out of {len(all_trades)} total"
        )
        
        return whale_trades


# =========================================
# TEST THE CLIENT
# =========================================

async def main():
    """Test the Polymarket client."""
    print("🔍 Testing Polymarket API Client...\n")
    
    async with PolymarketClient() as client:
        # Fetch active markets
        print("📊 Fetching active markets...")
        markets = await client.get_active_markets(limit=5)
        
        for market in markets[:5]:
            print(f"\n  Market: {market.question[:60]}...")
            print(f"  Yes: {market.outcome_prices['Yes']:.1%} | No: {market.outcome_prices['No']:.1%}")
            print(f"  Volume: ${market.volume:,.0f}")
        
        # Fetch recent trades
        print("\n\n💰 Fetching recent trades...")
        trades = await client.get_recent_trades(limit=20)
        
        print(f"\n  Found {len(trades)} recent trades")
        
        # Show any large trades
        large_trades = [t for t in trades if t.amount_usd >= 1000]
        if large_trades:
            print(f"\n  🐋 Large trades (>$1,000):")
            for trade in large_trades[:5]:
                print(f"    ${trade.amount_usd:,.2f} - {trade.side} {trade.outcome}")
                print(f"    Trader: {trade.trader_address[:10]}...")
        
        print("\n✅ Client working correctly!")


if __name__ == "__main__":
    asyncio.run(main())
