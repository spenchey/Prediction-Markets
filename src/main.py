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
from .whale_detector import WhaleDetector, WhaleAlert, TradeMonitor
from .alerter import Alerter, create_default_alerter

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
monitor: Optional[TradeMonitor] = None
monitor_task: Optional[asyncio.Task] = None
alerter: Optional[Alerter] = None

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
    global db, detector, monitor, monitor_task, alerter
    
    logger.info("🚀 Starting Prediction Market Tracker...")
    
    # Initialize database
    db = Database()
    await db.init()
    logger.info("✅ Database initialized")
    
    # Initialize alerter with all configured channels
    alerter = create_default_alerter()
    logger.info(f"✅ Alerter initialized with channels: {alerter.get_channels()}")
    
    # Initialize whale detector
    detector = WhaleDetector(
        whale_threshold_usd=settings.WHALE_THRESHOLD_USDC,
        std_multiplier=settings.WHALE_STD_MULTIPLIER,
        min_trades_for_stats=settings.MIN_TRADES_FOR_STATS
    )
    logger.info("✅ Whale detector initialized")
    
    # Initialize trade monitor
    monitor = TradeMonitor(
        detector=detector,
        poll_interval=settings.POLL_INTERVAL,
        on_alert=on_alert_detected
    )
    
    # Start monitoring in background
    monitor_task = asyncio.create_task(monitor.start())
    logger.info(f"✅ Trade monitor started (polling every {settings.POLL_INTERVAL}s)")
    
    logger.info("🎉 Application ready!")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    
    if monitor:
        await monitor.stop()
    
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
    
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
    trades_count = len(detector.recent_trade_sizes) if detector else 0
    alerts_count = len(recent_alerts)
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        trades_tracked=trades_count,
        alerts_generated=alerts_count
    )


@app.get("/health")
async def health_check():
    """Simple health check for monitoring."""
    return {"status": "ok"}


# =========================================
# MARKETS ENDPOINTS
# =========================================

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
                "markets_traded": len(w.markets_traded)
            }
            for w in wallets
        ]
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
