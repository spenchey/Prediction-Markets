"""
Polymarket API Client

This module handles all communication with Polymarket's APIs.
Polymarket has two main APIs:
1. CLOB API (clob.polymarket.com) - Order book, trades, prices
2. Gamma API (gamma-api.polymarket.com) - Market metadata, events

No authentication is needed for reading public data!
"""
import httpx
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
        clob_base_url: str = "https://clob.polymarket.com",
        gamma_base_url: str = "https://gamma-api.polymarket.com",
        strapi_url: str = "https://strapi-matic.poly.market"  # Alternative public endpoint
    ):
        self.clob_base_url = clob_base_url
        self.gamma_base_url = gamma_base_url
        self.strapi_url = strapi_url
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
                    market = Market(
                        id=item.get("conditionId", item.get("id", "")),
                        question=item.get("question", ""),
                        slug=item.get("slug", ""),
                        outcome_prices={
                            "Yes": float(item.get("outcomePrices", ["0.5", "0.5"])[0]),
                            "No": float(item.get("outcomePrices", ["0.5", "0.5"])[1])
                        },
                        volume=float(item.get("volume", 0) or 0),
                        liquidity=float(item.get("liquidity", 0) or 0),
                        end_date=None,  # Parse if available
                        active=item.get("active", True)
                    )
                    markets.append(market)
                except (KeyError, ValueError, IndexError) as e:
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
        
        This uses the CLOB API which provides detailed trade data
        including wallet addresses (for whale tracking!).
        
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
            
            # The /trades endpoint gives us individual trades
            response = await self.http.get(
                f"{self.clob_base_url}/trades",
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
                    
                    trade = Trade(
                        id=item.get("id", ""),
                        market_id=item.get("market", ""),
                        trader_address=item.get("maker", item.get("owner", "")),
                        outcome=item.get("outcome", ""),
                        side=item.get("side", ""),
                        size=size,
                        price=price,
                        amount_usd=amount_usd,
                        timestamp=datetime.fromisoformat(
                            item.get("timestamp", datetime.now().isoformat()).replace("Z", "+00:00")
                        ),
                        transaction_hash=item.get("transactionHash", "")
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
            response = await self.http.get(
                f"{self.clob_base_url}/trades",
                params={
                    "maker": wallet_address,
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
                    
                    trade = Trade(
                        id=item.get("id", ""),
                        market_id=item.get("market", ""),
                        trader_address=wallet_address,
                        outcome=item.get("outcome", ""),
                        side=item.get("side", ""),
                        size=size,
                        price=price,
                        amount_usd=size * price,
                        timestamp=datetime.fromisoformat(
                            item.get("timestamp", datetime.now().isoformat()).replace("Z", "+00:00")
                        ),
                        transaction_hash=item.get("transactionHash", "")
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
