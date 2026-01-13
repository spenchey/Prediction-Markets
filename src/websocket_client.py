"""
Polymarket WebSocket Client for Real-Time Trade Monitoring

This module provides a WebSocket connection to Polymarket for real-time
trade updates, which is ~10 seconds faster than polling the REST API.

Two modes available:
1. Direct Polymarket WebSocket (free, market data only)
2. Dome SDK (requires API key, wallet-level tracking)

Based on:
- Polymarket CLOB WebSocket: wss://ws-subscriptions-clob.polymarket.com/ws
- Dome API SDK: https://pypi.org/project/dome-api-sdk/
"""

import asyncio
import json
from datetime import datetime
from typing import Optional, Callable, Dict, List, Set, Any
from dataclasses import dataclass
from loguru import logger

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets package not installed. WebSocket features disabled.")

from .polymarket_client import Trade


# Polymarket WebSocket endpoints
POLYMARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


@dataclass
class WebSocketConfig:
    """Configuration for WebSocket connection."""
    url: str = POLYMARKET_WS_URL
    reconnect_attempts: int = 5
    reconnect_delay: float = 1.0
    reconnect_delay_max: float = 60.0
    heartbeat_interval: float = 30.0


class PolymarketWebSocket:
    """
    Real-time WebSocket client for Polymarket trade data.

    This provides ~10 second faster alerts compared to REST API polling.

    Usage:
        ws = PolymarketWebSocket()

        async def on_trade(trade: Trade):
            print(f"New trade: ${trade.amount_usd}")

        ws.on_trade = on_trade
        await ws.connect()
        await ws.subscribe_to_markets(["market_id_1", "market_id_2"])

        # Or subscribe to all markets
        await ws.subscribe_all()
    """

    def __init__(self, config: Optional[WebSocketConfig] = None):
        self.config = config or WebSocketConfig()
        self._ws = None
        self._running = False
        self._subscribed_markets: Set[str] = set()
        self._reconnect_count = 0

        # Callbacks
        self.on_trade: Optional[Callable[[Trade], Any]] = None
        self.on_price_change: Optional[Callable[[Dict], Any]] = None
        self.on_connect: Optional[Callable[[], Any]] = None
        self.on_disconnect: Optional[Callable[[], Any]] = None
        self.on_error: Optional[Callable[[Exception], Any]] = None

        # Statistics
        self.trades_received = 0
        self.messages_received = 0
        self.last_message_time: Optional[datetime] = None

    async def connect(self):
        """Establish WebSocket connection."""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets package not installed. Run: pip install websockets")
            return

        self._running = True
        logger.info(f"Connecting to WebSocket: {self.config.url}")

        while self._running and self._reconnect_count < self.config.reconnect_attempts:
            try:
                async with websockets.connect(
                    self.config.url,
                    ping_interval=self.config.heartbeat_interval,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    self._reconnect_count = 0
                    logger.info("WebSocket connected successfully")

                    if self.on_connect:
                        await self._safe_callback(self.on_connect)

                    # Re-subscribe to markets after reconnect
                    if self._subscribed_markets:
                        await self._send_subscriptions()

                    # Message loop
                    await self._message_loop()

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if self.on_error:
                    await self._safe_callback(self.on_error, e)

            if self._running:
                self._reconnect_count += 1
                delay = min(
                    self.config.reconnect_delay * (2 ** self._reconnect_count),
                    self.config.reconnect_delay_max
                )
                logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_count})")
                await asyncio.sleep(delay)

        if self.on_disconnect:
            await self._safe_callback(self.on_disconnect)

    async def disconnect(self):
        """Close WebSocket connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("WebSocket disconnected")

    async def subscribe_to_markets(self, market_ids: List[str]):
        """Subscribe to specific market IDs for trade updates."""
        self._subscribed_markets.update(market_ids)
        if self._ws:
            await self._send_subscriptions()
        logger.info(f"Subscribed to {len(market_ids)} markets")

    async def subscribe_to_tokens(self, token_ids: List[str]):
        """Subscribe to specific token IDs (asset IDs) for trade updates."""
        # Polymarket uses token IDs for the market channel
        if self._ws:
            message = {
                "type": "MARKET",
                "assets_ids": token_ids,
            }
            await self._ws.send(json.dumps(message))
            logger.info(f"Subscribed to {len(token_ids)} tokens")

    async def _send_subscriptions(self):
        """Send subscription message to WebSocket."""
        if not self._ws or not self._subscribed_markets:
            return

        # For market channel, we need token IDs, but we can also use condition IDs
        message = {
            "type": "MARKET",
            "assets_ids": list(self._subscribed_markets),
        }
        await self._ws.send(json.dumps(message))

    async def _message_loop(self):
        """Process incoming WebSocket messages."""
        async for message in self._ws:
            try:
                self.messages_received += 1
                self.last_message_time = datetime.now()

                data = json.loads(message)
                await self._handle_message(data)

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON received: {e}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _handle_message(self, data: Dict):
        """Handle different message types from WebSocket."""
        msg_type = data.get("event_type") or data.get("type", "")

        if msg_type == "last_trade_price" or msg_type == "trade":
            await self._handle_trade(data)
        elif msg_type == "price_change" or msg_type == "book":
            if self.on_price_change:
                await self._safe_callback(self.on_price_change, data)
        elif msg_type == "ping":
            # Respond to ping with pong
            if self._ws:
                await self._ws.send(json.dumps({"type": "pong"}))
        else:
            logger.debug(f"Unhandled message type: {msg_type}")

    async def _handle_trade(self, data: Dict):
        """Parse trade data and trigger callback."""
        try:
            # Extract trade info from different possible formats
            trade_data = data.get("data", data)

            # Parse the trade
            size = float(trade_data.get("size", trade_data.get("shares", 0)))
            price = float(trade_data.get("price", trade_data.get("last_trade_price", 0)))

            # Create Trade object
            trade = Trade(
                id=f"ws_{trade_data.get('id', datetime.now().timestamp())}",
                market_id=trade_data.get("asset_id", trade_data.get("market", "")),
                trader_address=trade_data.get("maker", trade_data.get("user", "")),
                outcome=trade_data.get("outcome", ""),
                side=trade_data.get("side", "").lower(),
                size=size,
                price=price,
                amount_usd=size * price,
                timestamp=datetime.now(),
                transaction_hash=trade_data.get("tx_hash", ""),
            )

            self.trades_received += 1

            if self.on_trade:
                await self._safe_callback(self.on_trade, trade)

        except Exception as e:
            logger.error(f"Error parsing trade: {e}")

    async def _safe_callback(self, callback: Callable, *args):
        """Safely execute a callback, handling both sync and async."""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Callback error: {e}")

    def get_stats(self) -> Dict:
        """Get WebSocket statistics."""
        return {
            "connected": self._ws is not None,
            "running": self._running,
            "subscribed_markets": len(self._subscribed_markets),
            "trades_received": self.trades_received,
            "messages_received": self.messages_received,
            "last_message": self.last_message_time.isoformat() if self.last_message_time else None,
            "reconnect_count": self._reconnect_count,
        }


class DomeWebSocket:
    """
    Dome SDK WebSocket client for wallet-level trade tracking.

    Requires dome-api-sdk package and API key.
    Provides faster (~10s) alerts than polling.

    Usage:
        ws = DomeWebSocket(api_key="your-key")

        async def on_order(event):
            print(f"Trade: {event.data.side} {event.data.shares_normalized}")

        await ws.connect()
        await ws.subscribe_to_wallets(["0x123...", "0x456..."], on_order)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._client = None
        self._ws_client = None
        self._subscriptions: Dict[str, str] = {}  # subscription_id -> type

        # Check if dome-api-sdk is installed
        try:
            from dome_api_sdk import DomeClient
            self._dome_available = True
        except ImportError:
            self._dome_available = False
            logger.warning("dome-api-sdk not installed. Run: pip install dome-api-sdk")

    async def connect(self):
        """Initialize Dome client and connect WebSocket."""
        if not self._dome_available:
            logger.error("dome-api-sdk not installed")
            return False

        if not self.api_key:
            logger.error("Dome API key required")
            return False

        from dome_api_sdk import DomeClient
        self._client = DomeClient({"api_key": self.api_key})
        self._ws_client = self._client.polymarket.websocket
        await self._ws_client.connect()
        logger.info("Dome WebSocket connected")
        return True

    async def subscribe_to_wallets(
        self,
        wallet_addresses: List[str],
        on_event: Callable
    ) -> Optional[str]:
        """Subscribe to order events for specific wallets."""
        if not self._ws_client:
            logger.error("Not connected. Call connect() first.")
            return None

        subscription_id = await self._ws_client.subscribe(
            users=wallet_addresses,
            on_event=on_event
        )
        self._subscriptions[subscription_id] = "wallets"
        logger.info(f"Subscribed to {len(wallet_addresses)} wallets")
        return subscription_id

    async def subscribe_to_markets(
        self,
        condition_ids: List[str],
        on_event: Callable
    ) -> Optional[str]:
        """Subscribe to order events for specific markets."""
        if not self._ws_client:
            logger.error("Not connected. Call connect() first.")
            return None

        subscription_id = await self._ws_client.subscribe(
            condition_ids=condition_ids,
            on_event=on_event
        )
        self._subscriptions[subscription_id] = "markets"
        logger.info(f"Subscribed to {len(condition_ids)} markets")
        return subscription_id

    async def unsubscribe(self, subscription_id: str):
        """Unsubscribe from a subscription."""
        if self._ws_client and subscription_id in self._subscriptions:
            await self._ws_client.unsubscribe(subscription_id)
            del self._subscriptions[subscription_id]

    async def disconnect(self):
        """Disconnect from Dome WebSocket."""
        if self._ws_client:
            # Unsubscribe all
            for sub_id in list(self._subscriptions.keys()):
                await self.unsubscribe(sub_id)
            await self._ws_client.disconnect()
            self._ws_client = None
            logger.info("Dome WebSocket disconnected")


# =========================================
# REAL-TIME MONITOR WITH WEBSOCKET
# =========================================

class RealTimeTradeMonitor:
    """
    Enhanced trade monitor that uses WebSocket for real-time updates
    with REST API fallback.

    This is ~10 seconds faster than polling-only approach.

    Usage:
        from whale_detector import WhaleDetector

        detector = WhaleDetector()
        monitor = RealTimeTradeMonitor(detector)

        async def handle_alert(alert):
            print(f"ALERT: {alert.message}")

        monitor.on_alert = handle_alert
        await monitor.start()
    """

    def __init__(
        self,
        detector,  # WhaleDetector instance
        use_websocket: bool = True,
        poll_interval: int = 60,  # Fallback poll interval
        dome_api_key: Optional[str] = None,  # For wallet-level tracking
    ):
        self.detector = detector
        self.use_websocket = use_websocket and WEBSOCKETS_AVAILABLE
        self.poll_interval = poll_interval
        self.dome_api_key = dome_api_key

        # WebSocket clients
        self._poly_ws: Optional[PolymarketWebSocket] = None
        self._dome_ws: Optional[DomeWebSocket] = None

        # Callbacks
        self.on_alert: Optional[Callable] = None

        # Statistics
        self.ws_trades_processed = 0
        self.rest_trades_processed = 0
        self.alerts_generated = 0

        self._running = False
        self._seen_trades: Set[str] = set()

    async def start(self):
        """Start the real-time monitor."""
        self._running = True
        logger.info("Starting real-time trade monitor")

        tasks = []

        # Start WebSocket connection if available
        if self.use_websocket:
            self._poly_ws = PolymarketWebSocket()
            self._poly_ws.on_trade = self._handle_ws_trade
            tasks.append(asyncio.create_task(self._poly_ws.connect()))
            logger.info("WebSocket mode enabled (real-time)")
        else:
            logger.info("WebSocket disabled, using REST polling only")

        # Start Dome WebSocket if API key provided
        if self.dome_api_key:
            self._dome_ws = DomeWebSocket(api_key=self.dome_api_key)
            if await self._dome_ws.connect():
                logger.info("Dome WebSocket connected for wallet tracking")

        # Always run REST polling as fallback/supplement
        tasks.append(asyncio.create_task(self._poll_loop()))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        """Stop the monitor."""
        self._running = False
        if self._poly_ws:
            await self._poly_ws.disconnect()
        if self._dome_ws:
            await self._dome_ws.disconnect()
        logger.info(f"Monitor stopped. WS trades: {self.ws_trades_processed}, REST trades: {self.rest_trades_processed}")

    async def _handle_ws_trade(self, trade: Trade):
        """Handle trade received via WebSocket."""
        if trade.id in self._seen_trades:
            return

        self._seen_trades.add(trade.id)
        self.ws_trades_processed += 1

        # Analyze trade for alerts
        alerts = await self.detector.analyze_trade(trade)

        for alert in alerts:
            self.alerts_generated += 1
            if self.on_alert:
                try:
                    result = self.on_alert(alert)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")

    async def _poll_loop(self):
        """REST API polling loop (fallback/supplement)."""
        from .polymarket_client import PolymarketClient

        while self._running:
            try:
                async with PolymarketClient() as client:
                    trades = await client.get_recent_trades(limit=100)
                    markets = await client.get_active_markets(limit=50)

                # Build market questions lookup
                market_questions = {m.id: m.question for m in markets}

                # Cache market prices
                for market in markets:
                    self.detector.update_market_prices(market.id, market.outcome_prices)

                # Process new trades
                new_trades = [t for t in trades if t.id not in self._seen_trades]

                for trade in new_trades:
                    self._seen_trades.add(trade.id)
                    self.rest_trades_processed += 1

                    # Analyze trade
                    market_q = market_questions.get(trade.market_id)
                    alerts = await self.detector.analyze_trade(trade, market_q)

                    for alert in alerts:
                        self.alerts_generated += 1
                        if self.on_alert:
                            try:
                                result = self.on_alert(alert)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception as e:
                                logger.error(f"Alert callback error: {e}")

                # Limit seen trades cache size
                if len(self._seen_trades) > 50000:
                    self._seen_trades = set(list(self._seen_trades)[-25000:])

            except Exception as e:
                logger.error(f"Polling error: {e}")

            await asyncio.sleep(self.poll_interval)

    def get_stats(self) -> Dict:
        """Get monitor statistics."""
        stats = {
            "running": self._running,
            "ws_trades_processed": self.ws_trades_processed,
            "rest_trades_processed": self.rest_trades_processed,
            "total_trades": self.ws_trades_processed + self.rest_trades_processed,
            "alerts_generated": self.alerts_generated,
            "seen_trades_cached": len(self._seen_trades),
        }
        if self._poly_ws:
            stats["websocket"] = self._poly_ws.get_stats()
        return stats


# =========================================
# TEST
# =========================================

async def main():
    """Test WebSocket connection."""
    print("Testing Polymarket WebSocket...")

    if not WEBSOCKETS_AVAILABLE:
        print("ERROR: websockets package not installed")
        print("Run: pip install websockets")
        return

    ws = PolymarketWebSocket()

    trade_count = 0

    async def on_trade(trade: Trade):
        nonlocal trade_count
        trade_count += 1
        print(f"[WS] Trade #{trade_count}: ${trade.amount_usd:,.2f} {trade.side}")

    def on_connect():
        print("[WS] Connected!")

    ws.on_trade = on_trade
    ws.on_connect = on_connect

    # Run for 30 seconds
    try:
        connect_task = asyncio.create_task(ws.connect())
        await asyncio.sleep(30)
        await ws.disconnect()
    except KeyboardInterrupt:
        await ws.disconnect()

    print(f"\nReceived {trade_count} trades via WebSocket")
    print(f"Stats: {ws.get_stats()}")


if __name__ == "__main__":
    asyncio.run(main())
