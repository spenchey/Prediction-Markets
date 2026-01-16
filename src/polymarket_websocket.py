"""
Polymarket WebSocket Client for Real-Time Trade Streaming

This module provides a WebSocket connection to Polymarket's real-time data
streaming service for instant whale trade detection.

The WebSocket approach provides:
- ~100ms latency vs 15+ second polling gaps
- No missed trades during high-volume periods
- Reduced API usage (single persistent connection)

WebSocket endpoint: wss://ws-live-data.polymarket.com
Topic: activity
Type: trades
"""
import asyncio
import json
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from loguru import logger

from .polymarket_client import Trade


@dataclass
class WebSocketConfig:
    """Configuration for the WebSocket client."""
    url: str = "wss://ws-live-data.polymarket.com"
    reconnect_delay: float = 5.0  # Seconds to wait before reconnecting
    max_reconnect_attempts: int = 10  # Max consecutive reconnect attempts
    ping_interval: float = 30.0  # Seconds between ping messages
    ping_timeout: float = 10.0  # Seconds to wait for pong response


class PolymarketWebSocket:
    """
    WebSocket client for real-time Polymarket trade data.

    Usage:
        async def on_trade(trade: Trade):
            print(f"New trade: ${trade.amount_usd}")

        ws = PolymarketWebSocket(on_trade=on_trade)
        await ws.connect()
    """

    def __init__(
        self,
        on_trade: Optional[Callable[[Trade], Any]] = None,
        on_connect: Optional[Callable[[], Any]] = None,
        on_disconnect: Optional[Callable[[], Any]] = None,
        config: Optional[WebSocketConfig] = None
    ):
        """
        Initialize the WebSocket client.

        Args:
            on_trade: Callback function called for each trade received
            on_connect: Callback function called when connected
            on_disconnect: Callback function called when disconnected
            config: WebSocket configuration options
        """
        self.on_trade = on_trade
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.config = config or WebSocketConfig()

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_attempts = 0
        self._trades_received = 0
        self._last_trade_time: Optional[datetime] = None

        # Track seen trade IDs to avoid duplicates (shared with polling)
        self.seen_trade_ids: set = set()

    async def connect(self):
        """
        Connect to the WebSocket and start receiving trades.

        This method runs indefinitely, automatically reconnecting on failures.
        """
        self._running = True

        while self._running:
            try:
                await self._connect_and_listen()
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
            except Exception as e:
                logger.error(f"Unexpected WebSocket error: {e}")

            if self._running:
                self._reconnect_attempts += 1

                if self._reconnect_attempts > self.config.max_reconnect_attempts:
                    logger.error(f"Max reconnect attempts ({self.config.max_reconnect_attempts}) exceeded")
                    self._running = False
                    break

                logger.info(f"Reconnecting in {self.config.reconnect_delay}s (attempt {self._reconnect_attempts})...")
                await asyncio.sleep(self.config.reconnect_delay)

    async def _connect_and_listen(self):
        """Establish connection and listen for messages."""
        logger.info(f"Connecting to Polymarket WebSocket: {self.config.url}")

        async with websockets.connect(
            self.config.url,
            ping_interval=self.config.ping_interval,
            ping_timeout=self.config.ping_timeout
        ) as ws:
            self._ws = ws
            self._reconnect_attempts = 0  # Reset on successful connection

            logger.info("WebSocket connected successfully")

            if self.on_connect:
                try:
                    result = self.on_connect()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Error in on_connect callback: {e}")

            # Subscribe to trades
            await self._subscribe()

            # Listen for messages
            async for message in ws:
                try:
                    await self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

    async def _subscribe(self):
        """Subscribe to the trades activity stream."""
        subscribe_message = {
            "action": "subscribe",
            "subscriptions": [
                {
                    "topic": "activity",
                    "type": "trades"
                }
            ]
        }

        await self._ws.send(json.dumps(subscribe_message))
        logger.info("Subscribed to Polymarket trades stream")

    async def _handle_message(self, message: str):
        """
        Parse and handle an incoming WebSocket message.

        Args:
            message: Raw JSON message from WebSocket
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message: {message[:100]}")
            return

        # Handle different message types
        msg_type = data.get("type") or data.get("event_type")

        if msg_type == "trades" or "trade" in str(data.get("topic", "")).lower():
            await self._handle_trade(data)
        elif msg_type == "subscribed":
            logger.debug("Subscription confirmed")
        elif msg_type == "error":
            logger.error(f"WebSocket error message: {data}")
        elif msg_type == "ping" or msg_type == "pong":
            pass  # Heartbeat messages
        else:
            # Log unknown message types for debugging
            logger.debug(f"Unknown message type: {msg_type}, data: {str(data)[:200]}")

    async def _handle_trade(self, data: Dict[str, Any]):
        """
        Parse a trade message and call the callback.

        Trade message fields from Polymarket RTDS:
        - asset: token ID
        - conditionId: market condition ID
        - eventSlug: event slug
        - outcome: outcome name
        - outcomeIndex: outcome index
        - price: trade price
        - proxyWallet: trader wallet address
        - side: BUY or SELL
        - size: trade size
        - timestamp: Unix timestamp
        - title: market title
        - transactionHash: tx hash
        """
        try:
            # Handle both direct trade data and wrapped data
            trade_data = data.get("data", data)

            # If it's a list of trades, process each
            if isinstance(trade_data, list):
                for item in trade_data:
                    await self._process_single_trade(item)
            else:
                await self._process_single_trade(trade_data)

        except Exception as e:
            logger.error(f"Error processing trade data: {e}, data: {str(data)[:200]}")

    async def _process_single_trade(self, item: Dict[str, Any]):
        """Process a single trade item."""
        try:
            # Calculate USD value
            size = float(item.get("size", 0))
            price = float(item.get("price", 0))
            amount_usd = size * price

            # Parse timestamp
            ts = item.get("timestamp")
            if isinstance(ts, int):
                timestamp = datetime.fromtimestamp(ts)
            elif isinstance(ts, str):
                try:
                    timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()

            # Generate unique trade ID
            tx_hash = item.get("transactionHash", "")
            trade_id = f"ws_{tx_hash[:16]}_{size}" if tx_hash else f"ws_{ts}_{size}"

            # Skip if we've already seen this trade
            if trade_id in self.seen_trade_ids:
                return

            self.seen_trade_ids.add(trade_id)

            # Keep seen_trade_ids from growing forever
            if len(self.seen_trade_ids) > 100_000:
                # Remove oldest entries (convert to list, slice, convert back)
                self.seen_trade_ids = set(list(self.seen_trade_ids)[-50_000:])

            # Create Trade object
            trade = Trade(
                id=trade_id,
                market_id=item.get("conditionId", item.get("asset", "")),
                trader_address=item.get("proxyWallet", ""),
                outcome=item.get("outcome", ""),
                side=item.get("side", "").lower(),
                size=size,
                price=price,
                amount_usd=amount_usd,
                timestamp=timestamp,
                transaction_hash=tx_hash,
                platform="Polymarket"
            )

            # Store market info for context
            trade._ws_title = item.get("title", "")
            trade._ws_slug = item.get("slug", item.get("eventSlug", ""))

            # Update stats
            self._trades_received += 1
            self._last_trade_time = datetime.now()

            # Call the trade callback
            if self.on_trade:
                try:
                    result = self.on_trade(trade)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Error in on_trade callback: {e}")

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Failed to parse trade: {e}")

    async def disconnect(self):
        """Disconnect from the WebSocket."""
        self._running = False

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self.on_disconnect:
            try:
                result = self.on_disconnect()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in on_disconnect callback: {e}")

        logger.info("WebSocket disconnected")

    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket statistics."""
        return {
            "connected": self._ws is not None and self._ws.open if self._ws else False,
            "trades_received": self._trades_received,
            "last_trade_time": self._last_trade_time.isoformat() if self._last_trade_time else None,
            "reconnect_attempts": self._reconnect_attempts,
            "seen_trade_ids_count": len(self.seen_trade_ids)
        }

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws is not None and self._ws.open if self._ws else False


class HybridTradeMonitor:
    """
    Hybrid trade monitor combining WebSocket (primary) and polling (backup).

    This provides the best of both worlds:
    - WebSocket: Real-time trade detection with ~100ms latency
    - Polling: Backup to catch any missed trades, runs every 30s

    Usage:
        monitor = HybridTradeMonitor(
            detector=whale_detector,
            on_alert=alert_callback
        )
        await monitor.start()
    """

    def __init__(
        self,
        detector,  # WhaleDetector instance
        on_alert: Optional[Callable] = None,
        poll_interval: int = 30,  # Backup polling every 30s
        clients: Optional[List] = None  # Platform clients for polling
    ):
        """
        Initialize the hybrid monitor.

        Args:
            detector: WhaleDetector instance for analyzing trades
            on_alert: Callback for whale alerts
            poll_interval: Seconds between backup polls
            clients: List of platform clients (Polymarket, Kalshi, etc.)
        """
        self.detector = detector
        self.on_alert = on_alert
        self.poll_interval = poll_interval
        self.clients = clients or []

        # Statistics
        self.ws_trades_processed = 0
        self.poll_trades_processed = 0
        self.ws_alerts_generated = 0
        self.poll_alerts_generated = 0

        # Shared seen trades set (to avoid duplicates between WS and polling)
        self.seen_trades: set = set()

        # WebSocket client
        self._ws_client: Optional[PolymarketWebSocket] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._running = False

        # Market info cache
        self._market_cache: Dict[str, str] = {}

    async def start(self):
        """Start both WebSocket and polling monitors."""
        self._running = True

        logger.info("Starting hybrid trade monitor...")
        logger.info(f"  - WebSocket: Real-time Polymarket trades")
        logger.info(f"  - Polling: Backup every {self.poll_interval}s for all platforms")

        # Initialize WebSocket client
        self._ws_client = PolymarketWebSocket(
            on_trade=self._on_ws_trade,
            on_connect=self._on_ws_connect,
            on_disconnect=self._on_ws_disconnect
        )

        # Share seen trades set
        self._ws_client.seen_trade_ids = self.seen_trades

        # Start both tasks
        self._ws_task = asyncio.create_task(self._run_websocket())
        self._poll_task = asyncio.create_task(self._run_polling())

        # Wait for both tasks
        await asyncio.gather(self._ws_task, self._poll_task, return_exceptions=True)

    async def stop(self):
        """Stop both monitors."""
        self._running = False

        if self._ws_client:
            await self._ws_client.disconnect()

        if self._ws_task:
            self._ws_task.cancel()

        if self._poll_task:
            self._poll_task.cancel()

        logger.info("Hybrid trade monitor stopped")

    async def _run_websocket(self):
        """Run the WebSocket connection."""
        try:
            await self._ws_client.connect()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WebSocket monitor error: {e}")

    async def _run_polling(self):
        """Run the backup polling loop."""
        from .polymarket_client import PolymarketClient

        while self._running:
            try:
                await asyncio.sleep(self.poll_interval)

                if not self._running:
                    break

                # Poll each configured client
                for client in self.clients:
                    try:
                        platform_name = getattr(client, 'platform_name', client.__class__.__name__)

                        if hasattr(client, 'is_configured') and not client.is_configured():
                            continue

                        async with client as c:
                            trades = await c.get_recent_trades(limit=500)

                            # Filter to trades we haven't seen
                            new_trades = [t for t in trades if t.id not in self.seen_trades]

                            if new_trades:
                                logger.debug(f"Backup poll found {len(new_trades)} new trades from {platform_name}")

                                for trade in new_trades:
                                    self.seen_trades.add(trade.id)

                                # Analyze trades
                                await self._analyze_trades(new_trades, source="poll")
                                self.poll_trades_processed += len(new_trades)

                    except Exception as e:
                        logger.error(f"Error polling {platform_name}: {e}")

                # Cleanup seen_trades
                if len(self.seen_trades) > 100_000:
                    self.seen_trades = set(list(self.seen_trades)[-50_000:])

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")

    async def _on_ws_trade(self, trade: Trade):
        """Handle a trade from WebSocket."""
        self.ws_trades_processed += 1

        # Get market question from trade metadata
        market_question = getattr(trade, '_ws_title', None)
        slug = getattr(trade, '_ws_slug', None)

        # Cache market info
        if market_question:
            self._market_cache[trade.market_id] = market_question

        # Analyze the trade
        market_questions = {trade.market_id: market_question} if market_question else {}

        alerts = await self.detector.analyze_trades([trade], market_questions)

        if alerts:
            self.ws_alerts_generated += len(alerts)
            for alert in alerts:
                if self.on_alert:
                    try:
                        await self.on_alert(alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")

    def _on_ws_connect(self):
        """Called when WebSocket connects."""
        logger.info("WebSocket connected - real-time trade monitoring active")

    def _on_ws_disconnect(self):
        """Called when WebSocket disconnects."""
        logger.warning("WebSocket disconnected - relying on polling backup")

    async def _analyze_trades(self, trades: List[Trade], source: str = "unknown"):
        """Analyze a batch of trades."""
        # Get market questions
        market_questions = {}
        for trade in trades:
            if trade.market_id in self._market_cache:
                market_questions[trade.market_id] = self._market_cache[trade.market_id]

        # Analyze
        alerts = await self.detector.analyze_trades(trades, market_questions)

        if alerts:
            if source == "poll":
                self.poll_alerts_generated += len(alerts)

            for alert in alerts:
                if self.on_alert:
                    try:
                        await self.on_alert(alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get monitor statistics."""
        ws_stats = self._ws_client.get_stats() if self._ws_client else {}

        return {
            "websocket": ws_stats,
            "ws_trades_processed": self.ws_trades_processed,
            "poll_trades_processed": self.poll_trades_processed,
            "ws_alerts_generated": self.ws_alerts_generated,
            "poll_alerts_generated": self.poll_alerts_generated,
            "total_trades": self.ws_trades_processed + self.poll_trades_processed,
            "total_alerts": self.ws_alerts_generated + self.poll_alerts_generated,
            "seen_trades_count": len(self.seen_trades)
        }


# =========================================
# TEST THE WEBSOCKET
# =========================================

async def test_websocket():
    """Test the WebSocket connection."""
    print("Testing Polymarket WebSocket connection...")

    trade_count = 0

    async def on_trade(trade: Trade):
        nonlocal trade_count
        trade_count += 1
        print(f"\n[Trade #{trade_count}]")
        print(f"  Amount: ${trade.amount_usd:,.2f}")
        print(f"  Side: {trade.side}")
        print(f"  Outcome: {trade.outcome}")
        print(f"  Trader: {trade.trader_address[:15]}...")

        if trade.amount_usd >= 1000:
            print(f"  WHALE TRADE!")

    def on_connect():
        print("Connected to Polymarket WebSocket!")

    def on_disconnect():
        print("Disconnected from WebSocket")

    ws = PolymarketWebSocket(
        on_trade=on_trade,
        on_connect=on_connect,
        on_disconnect=on_disconnect
    )

    try:
        # Run for 60 seconds then stop
        await asyncio.wait_for(ws.connect(), timeout=60)
    except asyncio.TimeoutError:
        print(f"\nTest complete. Received {trade_count} trades in 60 seconds.")
        await ws.disconnect()


if __name__ == "__main__":
    asyncio.run(test_websocket())
