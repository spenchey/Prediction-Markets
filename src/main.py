"""
Prediction Market Tracker - Main Application

This is the main entry point for the application.
It sets up:
1. FastAPI web server (for API endpoints)
2. Background task (for monitoring trades)
3. Database connections

To run locally:
    uvicorn src.main:app --reload

To run in production:
    uvicorn src.main:app --host 0.0.0.0 --port 8000
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
import sys

from .config import settings
from .database import Database, get_db, TradeRecord, AlertRecord
from .polymarket_client import PolymarketClient, Market
from .kalshi_client import KalshiClient
from .whale_detector import WhaleDetector, WhaleAlert, TradeMonitor
from .polymarket_websocket import HybridTradeMonitor
from .alerter import Alerter, create_default_alerter
from .scheduler import DigestScheduler, create_digest_scheduler

# =========================================
# CONFIGURE LOGGING
# =========================================

logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL
)

# =========================================
# GLOBAL STATE
# =========================================

# These are initialized on startup
db: Optional[Database] = None
detector: Optional[WhaleDetector] = None
monitor: Optional[TradeMonitor] = None  # Legacy polling monitor (fallback)
hybrid_monitor: Optional[HybridTradeMonitor] = None  # WebSocket + polling hybrid
monitor_task: Optional[asyncio.Task] = None
alerter: Optional[Alerter] = None
digest_scheduler: Optional[DigestScheduler] = None

# Store recent alerts in memory for quick access
recent_alerts: List[WhaleAlert] = []
MAX_RECENT_ALERTS = 100


# =========================================
# PYDANTIC MODELS (API Request/Response)
# =========================================

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    trades_tracked: int
    alerts_generated: int


class MarketResponse(BaseModel):
    id: str
    question: str
    yes_price: float
    no_price: float
    volume: float


class TradeResponse(BaseModel):
    id: str
    market_id: str
    trader_address: str
    outcome: str
    side: str
    amount_usd: float
    timestamp: str


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    severity: str
    message: str
    trade_amount_usd: float
    trader_address: str
    market_id: str
    outcome: str
    timestamp: str


class StatsResponse(BaseModel):
    total_trades_tracked: int
    total_alerts_generated: int
    whale_trades_24h: int
    unique_wallets: int
    top_wallets: List[dict]


# =========================================
# ALERT CALLBACK
# =========================================

async def on_alert_detected(alert: WhaleAlert):
    """
    Called when a new whale alert is detected.
    
    This:
    1. Saves to database
    2. Sends notifications via all configured channels
    3. Stores in memory for API access
    """
    global recent_alerts
    
    logger.info(f"🚨 NEW ALERT: {alert.message}")
    
    # Add to recent alerts (for API)
    recent_alerts.insert(0, alert)
    if len(recent_alerts) > MAX_RECENT_ALERTS:
        recent_alerts = recent_alerts[:MAX_RECENT_ALERTS]
    
    # Save to database
    if db:
        await db.save_alert(alert)
    
    # Send notifications via all channels
    if alerter:
        await alerter.send_alert(alert)


# =========================================
# LIFESPAN (Startup/Shutdown)
# =========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.

    This runs:
    - On startup: Initialize database, alerter, start monitoring
    - On shutdown: Clean up resources
    """
    global db, detector, monitor, hybrid_monitor, monitor_task, alerter, digest_scheduler

    logger.info("🚀 Starting Prediction Market Tracker...")
    logger.info(f"📊 DATABASE_URL configured: {'Yes' if settings.DATABASE_URL else 'No'}")
    logger.info(f"📊 DATABASE_URL prefix: {settings.DATABASE_URL[:30] if settings.DATABASE_URL else 'None'}...")

    # Initialize database with error handling
    try:
        db = Database()
        await db.init()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.warning("⚠️ Continuing without database - some features will be limited")
        db = None
    
    # Initialize alerter with all configured channels
    try:
        alerter = create_default_alerter()
        logger.info(f"✅ Alerter initialized with channels: {alerter.get_channels()}")
    except Exception as e:
        logger.error(f"❌ Alerter initialization failed: {e}")
        alerter = None

    # Initialize whale detector
    try:
        detector = WhaleDetector(
            whale_threshold_usd=settings.WHALE_THRESHOLD_USDC,
            std_multiplier=settings.WHALE_STD_MULTIPLIER,
            min_trades_for_stats=settings.MIN_TRADES_FOR_STATS
        )
        logger.info("✅ Whale detector initialized")
    except Exception as e:
        logger.error(f"❌ Whale detector initialization failed: {e}")
        detector = None

    # Initialize platform clients
    platform_clients = []
    platform_names = []

    # Always add Polymarket (no auth needed)
    platform_clients.append(PolymarketClient())
    platform_names.append("Polymarket")

    # Add Kalshi if enabled
    if settings.KALSHI_ENABLED:
        kalshi_client = KalshiClient()
        platform_clients.append(kalshi_client)
        platform_names.append("Kalshi")
        logger.info("✅ Kalshi client enabled")
    else:
        logger.info("ℹ️ Kalshi client disabled (KALSHI_ENABLED=false)")

    # Initialize trade monitor (hybrid WebSocket + polling, or legacy polling)
    try:
        if detector:
            if settings.USE_HYBRID_MONITOR:
                # Use hybrid monitor: WebSocket for real-time + polling as backup
                hybrid_monitor = HybridTradeMonitor(
                    detector=detector,
                    on_alert=on_alert_detected,
                    poll_interval=settings.POLL_INTERVAL,  # Backup polling (30s)
                    clients=platform_clients
                )
                monitor_task = asyncio.create_task(hybrid_monitor.start())
                logger.info("✅ Hybrid trade monitor started")
                logger.info("   WebSocket: Real-time Polymarket trades (~100ms latency)")
                logger.info(f"   Polling backup: Every {settings.POLL_INTERVAL}s for all platforms")
                logger.info(f"   Platforms: {', '.join(platform_names)}")
            else:
                # Legacy polling-only monitor
                monitor = TradeMonitor(
                    detector=detector,
                    poll_interval=settings.POLL_INTERVAL,
                    on_alert=on_alert_detected,
                    clients=platform_clients
                )
                monitor_task = asyncio.create_task(monitor.start())
                logger.info(f"✅ Trade monitor started (polling every {settings.POLL_INTERVAL}s)")
                logger.info(f"   Platforms: {', '.join(platform_names)}")
        else:
            logger.warning("⚠️ Trade monitor not started - detector not available")
    except Exception as e:
        logger.error(f"❌ Trade monitor initialization failed: {e}")

    # Initialize digest scheduler
    try:
        if alerter and detector and db:
            digest_scheduler = create_digest_scheduler(alerter, detector, db)
            digest_scheduler.start()
            logger.info("✅ Digest scheduler started")
            logger.info(f"   Daily digest: {settings.DAILY_DIGEST_HOUR}:00 AM {settings.DIGEST_TIMEZONE}")
        else:
            logger.warning("⚠️ Digest scheduler not started - missing dependencies")
    except Exception as e:
        logger.error(f"❌ Digest scheduler initialization failed: {e}")
        digest_scheduler = None

    logger.info("🎉 Application ready!")

    yield  # Application runs here
    
    # Shutdown
    logger.info("🛑 Shutting down...")

    if hybrid_monitor:
        await hybrid_monitor.stop()

    if monitor:
        await monitor.stop()

    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    if digest_scheduler:
        digest_scheduler.stop()

    if db:
        await db.close()

    logger.info("👋 Goodbye!")


# =========================================
# CREATE FASTAPI APP
# =========================================

app = FastAPI(
    title="Prediction Market Tracker",
    description="Track whale trades and unusual activity on prediction markets",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware (allows web frontends to call this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev
        "http://127.0.0.1:3000",
        settings.FRONTEND_URL,    # Production frontend
        "*"  # Allow all for development - restrict in production!
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================
# API ENDPOINTS
# =========================================

@app.get("/", response_model=HealthResponse)
async def root():
    """
    Health check endpoint.

    Returns the current status of the tracker.
    """
    try:
        trades_count = len(detector.recent_trade_sizes) if detector else 0
    except Exception:
        trades_count = 0
    alerts_count = len(recent_alerts)

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        trades_tracked=trades_count,
        alerts_generated=alerts_count
    )


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Railway/container monitoring.

    Returns 200 to pass healthcheck - shows component status in response.
    """
    # Build list of enabled platforms
    platforms = ["Polymarket"]
    if settings.KALSHI_ENABLED:
        platforms.append("Kalshi")

    health = {
        "status": "ok",
        "database": "unknown",
        "monitor": "unknown",
        "platforms": platforms,
        "message": "App is running"
    }

    # Check database connectivity
    try:
        if db:
            from sqlalchemy import text
            async with db.async_session() as session:
                await session.execute(text("SELECT 1"))
            health["database"] = "connected"
        else:
            health["database"] = "not_initialized"
    except Exception as e:
        health["database"] = f"error: {str(e)[:50]}"

    # Check monitor status
    if hybrid_monitor:
        health["monitor"] = "hybrid"
        health["monitor_mode"] = "WebSocket + Polling backup"
        ws_stats = hybrid_monitor.get_stats()
        health["websocket"] = {
            "connected": ws_stats.get("websocket", {}).get("connected", False),
            "trades_received": ws_stats.get("ws_trades_processed", 0),
            "alerts_generated": ws_stats.get("ws_alerts_generated", 0)
        }
        health["polling"] = {
            "trades_received": ws_stats.get("poll_trades_processed", 0),
            "alerts_generated": ws_stats.get("poll_alerts_generated", 0)
        }
    elif monitor and monitor_task:
        health["monitor"] = "running" if not monitor_task.done() else "stopped"
        health["monitor_mode"] = "Polling only"
    else:
        health["monitor"] = "not_started"

    # Always return 200 so healthcheck passes
    return health


# =========================================
# MARKETS ENDPOINTS
# =========================================

@app.get("/platforms")
async def get_platforms():
    """
    Get information about configured prediction market platforms.
    """
    platforms = {
        "polymarket": {
            "enabled": True,
            "name": "Polymarket",
            "whale_tracking": True,
            "trade_data": True,
            "description": "Crypto-native prediction market on Polygon"
        },
        "kalshi": {
            "enabled": settings.KALSHI_ENABLED,
            "name": "Kalshi",
            "whale_tracking": False,
            "trade_data": False,
            "description": "CFTC-regulated US exchange - market data only (trade data requires auth)"
        }
    }

    enabled_platforms = [k for k, v in platforms.items() if v["enabled"]]

    return {
        "enabled": enabled_platforms,
        "platforms": platforms,
        "note": "Kalshi public API provides market data only. Trade data requires authentication."
    }


@app.get("/markets/kalshi", response_model=List[MarketResponse])
async def get_kalshi_markets(limit: int = Query(20, ge=1, le=100)):
    """
    Get active Kalshi prediction markets.
    """
    if not settings.KALSHI_ENABLED:
        raise HTTPException(status_code=400, detail="Kalshi is not enabled")

    async with KalshiClient() as client:
        markets = await client.get_active_markets(limit=limit)

    return [
        MarketResponse(
            id=m.id,
            question=m.question,
            yes_price=m.outcome_prices.get("Yes", 0.5),
            no_price=m.outcome_prices.get("No", 0.5),
            volume=m.volume
        )
        for m in markets
    ]


@app.get("/markets", response_model=List[MarketResponse])
async def get_markets(limit: int = Query(20, ge=1, le=100)):
    """
    Get active prediction markets.
    
    Returns markets sorted by trading volume.
    """
    async with PolymarketClient() as client:
        markets = await client.get_active_markets(limit=limit)
    
    return [
        MarketResponse(
            id=m.id,
            question=m.question,
            yes_price=m.outcome_prices["Yes"],
            no_price=m.outcome_prices["No"],
            volume=m.volume
        )
        for m in markets
    ]


@app.get("/markets/{market_id}")
async def get_market(market_id: str):
    """Get a specific market by ID."""
    async with PolymarketClient() as client:
        market = await client.get_market_by_id(market_id)
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    return {
        "id": market.id,
        "question": market.question,
        "slug": market.slug,
        "yes_price": market.outcome_prices["Yes"],
        "no_price": market.outcome_prices["No"],
        "volume": market.volume,
        "liquidity": market.liquidity,
        "active": market.active
    }


# =========================================
# TRADES ENDPOINTS
# =========================================

@app.get("/trades", response_model=List[TradeResponse])
async def get_trades(
    limit: int = Query(50, ge=1, le=500),
    min_amount: Optional[float] = Query(None, description="Minimum trade amount in USD")
):
    """
    Get recent trades.
    
    Optionally filter by minimum amount to see only large trades.
    """
    async with PolymarketClient() as client:
        trades = await client.get_recent_trades(limit=limit)
    
    if min_amount:
        trades = [t for t in trades if t.amount_usd >= min_amount]
    
    return [
        TradeResponse(
            id=t.id,
            market_id=t.market_id,
            trader_address=t.trader_address,
            outcome=t.outcome,
            side=t.side,
            amount_usd=t.amount_usd,
            timestamp=t.timestamp.isoformat()
        )
        for t in trades
    ]


@app.get("/trades/whales", response_model=List[TradeResponse])
async def get_whale_trades(
    threshold: float = Query(10000, description="Minimum amount for whale trades")
):
    """
    Get whale trades (large trades above threshold).
    """
    async with PolymarketClient() as client:
        trades = await client.get_recent_trades(limit=500)
    
    whale_trades = [t for t in trades if t.amount_usd >= threshold]
    
    return [
        TradeResponse(
            id=t.id,
            market_id=t.market_id,
            trader_address=t.trader_address,
            outcome=t.outcome,
            side=t.side,
            amount_usd=t.amount_usd,
            timestamp=t.timestamp.isoformat()
        )
        for t in sorted(whale_trades, key=lambda x: x.amount_usd, reverse=True)
    ]


@app.get("/trades/wallet/{wallet_address}")
async def get_wallet_trades(wallet_address: str, limit: int = Query(50, ge=1, le=200)):
    """
    Get all trades by a specific wallet address.
    
    This lets you track what a specific whale is doing!
    """
    async with PolymarketClient() as client:
        trades = await client.get_trades_by_address(wallet_address, limit=limit)
    
    total_volume = sum(t.amount_usd for t in trades)
    
    return {
        "wallet_address": wallet_address,
        "total_trades": len(trades),
        "total_volume_usd": total_volume,
        "trades": [
            TradeResponse(
                id=t.id,
                market_id=t.market_id,
                trader_address=t.trader_address,
                outcome=t.outcome,
                side=t.side,
                amount_usd=t.amount_usd,
                timestamp=t.timestamp.isoformat()
            )
            for t in trades
        ]
    }


# =========================================
# ALERTS ENDPOINTS
# =========================================

@app.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    limit: int = Query(20, ge=1, le=100),
    alert_type: Optional[str] = Query(None, description="Filter by alert type")
):
    """
    Get recent whale alerts.
    
    Types: WHALE_TRADE, UNUSUAL_SIZE, NEW_WALLET, SMART_MONEY
    """
    alerts = recent_alerts[:limit]
    
    if alert_type:
        alerts = [a for a in alerts if a.alert_type == alert_type]
    
    return [
        AlertResponse(
            id=a.id,
            alert_type=a.alert_type,
            severity=a.severity,
            message=a.message,
            trade_amount_usd=a.trade.amount_usd,
            trader_address=a.trade.trader_address,
            market_id=a.trade.market_id,
            outcome=a.trade.outcome,
            timestamp=a.timestamp.isoformat()
        )
        for a in alerts
    ]


@app.get("/alerts/stream")
async def stream_alerts():
    """
    Server-Sent Events (SSE) endpoint for real-time alerts.
    
    Connect to this endpoint to receive alerts as they happen!
    
    Example (JavaScript):
        const source = new EventSource('/alerts/stream');
        source.onmessage = (event) => {
            const alert = JSON.parse(event.data);
            console.log('New alert:', alert);
        };
    """
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        last_count = len(recent_alerts)
        
        while True:
            await asyncio.sleep(1)  # Check every second
            
            current_count = len(recent_alerts)
            if current_count > last_count:
                # New alerts!
                new_alerts = recent_alerts[:current_count - last_count]
                for alert in reversed(new_alerts):
                    data = {
                        "id": alert.id,
                        "type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "amount": alert.trade.amount_usd,
                        "timestamp": alert.timestamp.isoformat()
                    }
                    yield f"data: {str(data)}\n\n"
                last_count = current_count
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# =========================================
# STATS ENDPOINTS
# =========================================

@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get overall statistics about tracked activity.
    """
    trades_count = len(detector.recent_trade_sizes) if detector else 0
    alerts_count = len(recent_alerts)
    wallets_count = len(detector.wallet_profiles) if detector else 0
    
    # Count whale trades in last 24h
    cutoff = datetime.now() - timedelta(hours=24)
    whale_24h = len([
        a for a in recent_alerts
        if a.alert_type == "WHALE_TRADE" and a.timestamp > cutoff
    ])
    
    # Get top wallets
    top_wallets = []
    if detector:
        for profile in detector.get_top_wallets(5):
            top_wallets.append({
                "address": profile.address[:15] + "...",
                "total_volume_usd": profile.total_volume_usd,
                "total_trades": profile.total_trades,
                "is_whale": profile.is_whale
            })
    
    return StatsResponse(
        total_trades_tracked=trades_count,
        total_alerts_generated=alerts_count,
        whale_trades_24h=whale_24h,
        unique_wallets=wallets_count,
        top_wallets=top_wallets
    )


@app.get("/stats/wallets")
async def get_wallet_stats(limit: int = Query(20, ge=1, le=100)):
    """
    Get statistics about tracked wallets.
    """
    if not detector:
        return {"wallets": []}

    wallets = detector.get_top_wallets(limit)

    return {
        "total_wallets": len(detector.wallet_profiles),
        "wallets": [
            {
                "address": w.address,
                "total_trades": w.total_trades,
                "total_volume_usd": w.total_volume_usd,
                "first_seen": w.first_seen.isoformat() if w.first_seen else None,
                "last_seen": w.last_seen.isoformat() if w.last_seen else None,
                "is_whale": w.is_whale,
                "is_new": w.is_new_wallet,
                "is_repeat_actor": w.is_repeat_actor,
                "is_heavy_actor": w.is_heavy_actor,
                "is_focused": w.is_focused,
                "markets_traded": len(w.markets_traded),
                "trades_last_hour": w.trades_last_hour,
                "trades_last_24h": w.trades_last_24h,
            }
            for w in wallets
        ]
    }


# =========================================
# ENHANCED DETECTION ENDPOINTS (v2.0)
# =========================================

@app.get("/stats/detection")
async def get_detection_stats():
    """
    Get comprehensive detection statistics.

    Shows counts for all 11 detection types:
    - Original: WHALE_TRADE, UNUSUAL_SIZE, MARKET_ANOMALY, NEW_WALLET, FOCUSED_WALLET, SMART_MONEY
    - New: REPEAT_ACTOR, HEAVY_ACTOR, EXTREME_CONFIDENCE, WHALE_EXIT, CONTRARIAN, CLUSTER_ACTIVITY
    """
    if not detector:
        return {"error": "Detector not initialized"}

    return detector.get_detection_stats()


@app.get("/stats/velocity")
async def get_velocity_stats(limit: int = Query(20, ge=1, le=100)):
    """
    Get wallets with high trading velocity (repeat actors and heavy actors).

    - Repeat Actors: 2+ trades in last hour
    - Heavy Actors: 5+ trades in last 24 hours
    """
    if not detector:
        return {"repeat_actors": [], "heavy_actors": []}

    repeat_actors = detector.get_repeat_actors(limit)
    heavy_actors = detector.get_heavy_actors(limit)

    return {
        "repeat_actors": [
            {
                "address": w.address,
                "trades_last_hour": w.trades_last_hour,
                "trades_last_24h": w.trades_last_24h,
                "total_volume_usd": w.total_volume_usd,
            }
            for w in repeat_actors
        ],
        "heavy_actors": [
            {
                "address": w.address,
                "trades_last_hour": w.trades_last_hour,
                "trades_last_24h": w.trades_last_24h,
                "total_volume_usd": w.total_volume_usd,
            }
            for w in heavy_actors
        ]
    }


@app.get("/stats/clusters")
async def get_cluster_stats(min_volume: float = Query(10000, ge=0)):
    """
    Get detected wallet clusters (potentially coordinated trading).

    Clusters are groups of wallets that trade the same markets
    within short time windows with similar trade sizes.
    """
    if not detector:
        return {"clusters": []}

    clusters = detector.get_active_clusters(min_volume=min_volume)

    return {
        "total_clusters": len(clusters),
        "clusters": clusters[:20]  # Limit response size
    }


@app.get("/stats/exits")
async def get_whale_exits(hours: int = Query(24, ge=1, le=168)):
    """
    Get wallets that are exiting positions (selling).

    Tracks whales who are unwinding their positions.
    """
    if not detector:
        return {"exits": []}

    exits = detector.get_whale_exits(since_hours=hours)

    return {
        "timeframe_hours": hours,
        "exiting_wallets": [
            {
                "address": w.address,
                "sell_volume_usd": w.sell_volume_usd,
                "buy_volume_usd": w.buy_volume_usd,
                "sell_ratio": w.sell_ratio,
                "total_trades": w.total_trades,
            }
            for w in exits[:20]
        ]
    }


@app.get("/alerts/types")
async def get_alert_types():
    """
    Get counts of alerts by type.

    Shows distribution of all 14 detection types.
    """
    type_counts = {}
    for alert in recent_alerts:
        type_counts[alert.alert_type] = type_counts.get(alert.alert_type, 0) + 1

    return {
        "total_alerts": len(recent_alerts),
        "by_type": type_counts,
        "available_types": [
            # Original
            "WHALE_TRADE", "UNUSUAL_SIZE", "MARKET_ANOMALY",
            "NEW_WALLET", "FOCUSED_WALLET", "SMART_MONEY",
            # New (January 2026)
            "REPEAT_ACTOR", "HEAVY_ACTOR", "EXTREME_CONFIDENCE",
            "WHALE_EXIT", "CONTRARIAN", "CLUSTER_ACTIVITY",
            # Advanced (from ChatGPT v5)
            "HIGH_IMPACT", "ENTITY_ACTIVITY"
        ]
    }


# =========================================
# ENTITY ENDPOINTS (Advanced Clustering)
# =========================================

@app.get("/stats/entities")
async def get_entity_stats():
    """
    Get detected entities (multi-wallet clusters).

    Entities are groups of wallets that appear to be controlled
    by the same person/group, detected via:
    - Shared funder wallet
    - Time-coupled trading (same market, close timing)
    - Market overlap (similar trading patterns)
    """
    if not detector:
        return {"entities": [], "stats": {}}

    entities = detector.get_all_entities()
    engine = detector.get_entity_engine()
    engine_stats = engine.get_entity_stats() if engine else {}

    return {
        "total_entities": len(entities),
        "entities": entities[:50],  # Limit response size
        "stats": engine_stats,
    }


@app.get("/entity/{wallet_address}")
async def get_wallet_entity(wallet_address: str):
    """
    Get the entity containing a specific wallet.

    Returns entity details if the wallet is part of a detected cluster.
    """
    if not detector:
        return {"entity": None, "message": "Detector not initialized"}

    entity = detector.get_entity_for_wallet(wallet_address)

    if not entity:
        return {
            "wallet": wallet_address,
            "entity": None,
            "message": "Wallet not part of any detected entity"
        }

    return {
        "wallet": wallet_address,
        "entity": {
            "entity_id": entity.entity_id,
            "wallet_count": entity.wallet_count,
            "wallets": list(entity.wallets),
            "confidence": entity.confidence,
            "reason": entity.reason,
        }
    }


# =========================================
# MANUAL TRIGGER (for testing)
# =========================================

@app.post("/scan")
async def manual_scan():
    """
    Manually trigger a scan for new trades.

    Useful for testing without waiting for the polling interval.
    """
    if not monitor:
        raise HTTPException(status_code=500, detail="Monitor not initialized")

    await monitor._check_for_trades()

    return {
        "status": "scan_complete",
        "alerts_generated": len(recent_alerts)
    }


# =========================================
# DIGEST ENDPOINTS
# =========================================

@app.post("/digest/daily")
async def trigger_daily_digest():
    """
    Manually trigger the daily digest email.

    Useful for testing without waiting for 5 AM.
    """
    if not digest_scheduler:
        raise HTTPException(status_code=500, detail="Digest scheduler not initialized")

    try:
        await digest_scheduler.send_daily_digest()
        return {
            "status": "success",
            "message": "Daily digest sent (if alerts exist)"
        }
    except Exception as e:
        logger.error(f"Failed to send digest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send digest: {str(e)}")


@app.post("/digest/weekly")
async def trigger_weekly_digest():
    """
    Manually trigger the weekly digest email.

    Useful for testing the weekly report.
    """
    if not digest_scheduler:
        raise HTTPException(status_code=500, detail="Digest scheduler not initialized")

    try:
        await digest_scheduler.send_weekly_digest()
        return {
            "status": "success",
            "message": "Weekly digest sent (if alerts exist)"
        }
    except Exception as e:
        logger.error(f"Failed to send digest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send digest: {str(e)}")


@app.get("/digest/preview")
async def preview_digest(hours: int = Query(24, ge=1, le=168)):
    """
    Preview digest content without sending email.

    Returns the compiled digest data for inspection.
    """
    if not digest_scheduler:
        raise HTTPException(status_code=500, detail="Digest scheduler not initialized")

    try:
        digest = await digest_scheduler._compile_digest_from_db(hours_back=hours)

        if digest is None:
            return {
                "status": "empty",
                "message": f"No alerts in the past {hours} hours",
                "period_hours": hours
            }

        return {
            "status": "success",
            "period_hours": hours,
            "report_type": digest.report_type,
            "period_start": digest.period_start.isoformat(),
            "period_end": digest.period_end.isoformat(),
            "total_alerts": digest.total_alerts,
            "alerts_by_type": digest.alerts_by_type,
            "total_volume_tracked": digest.total_volume_tracked,
            "top_trades": digest.top_trades[:5],
            "smart_money_count": len(digest.smart_money_activity),
            "new_wallets_count": len(digest.new_wallets_of_interest),
            "top_wallets_count": len(digest.top_wallets)
        }
    except Exception as e:
        logger.error(f"Failed to preview digest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to preview digest: {str(e)}")


@app.get("/digest/preview/html")
async def preview_digest_html(hours: int = Query(24, ge=1, le=168)):
    """
    Preview digest HTML email template.

    Returns the full HTML that would be sent in the email.
    """
    from fastapi.responses import HTMLResponse

    if not digest_scheduler:
        raise HTTPException(status_code=500, detail="Digest scheduler not initialized")

    try:
        digest = await digest_scheduler._compile_digest_from_db(hours_back=hours)

        if digest is None:
            return HTMLResponse(
                content="<html><body><h1>No alerts in the past {} hours</h1></body></html>".format(hours),
                status_code=200
            )

        return HTMLResponse(content=digest.to_html(), status_code=200)
    except Exception as e:
        logger.error(f"Failed to preview digest HTML: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to preview digest: {str(e)}")


# =========================================
# ERROR HANDLERS
# =========================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# =========================================
# RUN DIRECTLY
# =========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
