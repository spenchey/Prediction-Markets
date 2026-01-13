"""
Prediction Market Tracker - Main Application

This is the main entry point for the application.
Startup is made resilient to catch import and initialization errors.
"""
import sys

# =========================================
# MINIMAL STARTUP - Always works
# =========================================

# First, try to import FastAPI (should always work)
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    print("OK: FastAPI imported", flush=True)
except Exception as e:
    print(f"FATAL: Cannot import FastAPI: {e}", flush=True)
    sys.exit(1)

# Create app immediately so /health can work
app = FastAPI(
    title="Prediction Market Tracker",
    description="Track whale trades on prediction markets",
    version="1.0.0"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================
# HEALTH ENDPOINT - Always available
# =========================================

startup_status = {
    "config": "not_loaded",
    "database": "not_loaded",
    "detector": "not_loaded",
    "alerter": "not_loaded",
    "monitor": "not_loaded",
    "errors": []
}

@app.get("/health")
async def health_check():
    """Health check - always returns 200."""
    return {
        "status": "ok",
        "message": "App is running",
        "components": startup_status
    }

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "status": "healthy",
        "message": "Prediction Market Tracker",
        "startup": startup_status
    }

# =========================================
# TRY TO IMPORT EVERYTHING ELSE
# =========================================

# Try to import standard library stuff
try:
    import asyncio
    from contextlib import asynccontextmanager
    from datetime import datetime, timedelta
    from typing import List, Optional
    print("OK: Standard library imports", flush=True)
except Exception as e:
    print(f"ERROR: Standard library: {e}", flush=True)
    startup_status["errors"].append(f"stdlib: {e}")

# Try pydantic
try:
    from pydantic import BaseModel
    print("OK: Pydantic imported", flush=True)
except Exception as e:
    print(f"ERROR: Pydantic: {e}", flush=True)
    startup_status["errors"].append(f"pydantic: {e}")

# Try loguru
try:
    from loguru import logger
    logger.remove()
    logger.add(sys.stdout, format="{time} | {level} | {message}", level="INFO")
    print("OK: Loguru imported", flush=True)
except Exception as e:
    print(f"ERROR: Loguru: {e}", flush=True)
    startup_status["errors"].append(f"loguru: {e}")
    # Create a fake logger
    class FakeLogger:
        def info(self, msg): print(f"INFO: {msg}", flush=True)
        def error(self, msg): print(f"ERROR: {msg}", flush=True)
        def warning(self, msg): print(f"WARN: {msg}", flush=True)
    logger = FakeLogger()

# Try config
settings = None
try:
    from .config import settings
    startup_status["config"] = "loaded"
    print(f"OK: Config loaded, DB={settings.DATABASE_URL[:30] if settings.DATABASE_URL else 'None'}...", flush=True)
except Exception as e:
    print(f"ERROR: Config: {e}", flush=True)
    startup_status["config"] = f"error: {e}"
    startup_status["errors"].append(f"config: {e}")

# Try database
Database = None
try:
    from .database import Database
    startup_status["database"] = "module_loaded"
    print("OK: Database module imported", flush=True)
except Exception as e:
    print(f"ERROR: Database module: {e}", flush=True)
    startup_status["database"] = f"import_error: {e}"
    startup_status["errors"].append(f"database: {e}")

# Try polymarket client
PolymarketClient = None
try:
    from .polymarket_client import PolymarketClient
    print("OK: Polymarket client imported", flush=True)
except Exception as e:
    print(f"ERROR: Polymarket client: {e}", flush=True)
    startup_status["errors"].append(f"polymarket: {e}")

# Try whale detector
WhaleDetector = None
TradeMonitor = None
WhaleAlert = None
try:
    from .whale_detector import WhaleDetector, WhaleAlert, TradeMonitor
    startup_status["detector"] = "module_loaded"
    print("OK: Whale detector imported", flush=True)
except Exception as e:
    print(f"ERROR: Whale detector: {e}", flush=True)
    startup_status["detector"] = f"import_error: {e}"
    startup_status["errors"].append(f"whale_detector: {e}")

# Try alerter
Alerter = None
create_default_alerter = None
try:
    from .alerter import Alerter, create_default_alerter
    startup_status["alerter"] = "module_loaded"
    print("OK: Alerter imported", flush=True)
except Exception as e:
    print(f"ERROR: Alerter: {e}", flush=True)
    startup_status["alerter"] = f"import_error: {e}"
    startup_status["errors"].append(f"alerter: {e}")

print(f"Import phase complete. Errors: {len(startup_status['errors'])}", flush=True)

# =========================================
# GLOBAL STATE
# =========================================

db = None
detector = None
monitor = None
monitor_task = None
alerter = None
recent_alerts = []
MAX_RECENT_ALERTS = 100


# =========================================
# STARTUP EVENT
# =========================================

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global db, detector, monitor, monitor_task, alerter

    print("Starting initialization...", flush=True)

    # Initialize database
    if Database and settings:
        try:
            db = Database()
            await db.init()
            startup_status["database"] = "connected"
            print("OK: Database initialized", flush=True)
        except Exception as e:
            print(f"ERROR: Database init: {e}", flush=True)
            startup_status["database"] = f"init_error: {e}"

    # Initialize alerter
    if create_default_alerter:
        try:
            alerter = create_default_alerter()
            startup_status["alerter"] = "initialized"
            print("OK: Alerter initialized", flush=True)
        except Exception as e:
            print(f"ERROR: Alerter init: {e}", flush=True)
            startup_status["alerter"] = f"init_error: {e}"

    # Initialize detector
    if WhaleDetector and settings:
        try:
            detector = WhaleDetector(
                whale_threshold_usd=settings.WHALE_THRESHOLD_USDC,
                std_multiplier=settings.WHALE_STD_MULTIPLIER,
                min_trades_for_stats=settings.MIN_TRADES_FOR_STATS
            )
            startup_status["detector"] = "initialized"
            print("OK: Whale detector initialized", flush=True)
        except Exception as e:
            print(f"ERROR: Detector init: {e}", flush=True)
            startup_status["detector"] = f"init_error: {e}"

    # Initialize monitor
    if TradeMonitor and detector:
        try:
            monitor = TradeMonitor(
                detector=detector,
                poll_interval=settings.POLL_INTERVAL if settings else 60,
                on_alert=on_alert_detected
            )
            monitor_task = asyncio.create_task(monitor.start())
            startup_status["monitor"] = "running"
            print("OK: Monitor started", flush=True)
        except Exception as e:
            print(f"ERROR: Monitor init: {e}", flush=True)
            startup_status["monitor"] = f"init_error: {e}"

    print(f"Initialization complete. Status: {startup_status}", flush=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global monitor, monitor_task, db

    if monitor:
        try:
            await monitor.stop()
        except:
            pass

    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except:
            pass

    if db:
        try:
            await db.close()
        except:
            pass


# =========================================
# ALERT CALLBACK
# =========================================

async def on_alert_detected(alert):
    """Handle new alerts."""
    global recent_alerts

    print(f"ALERT: {alert.message}", flush=True)

    recent_alerts.insert(0, alert)
    if len(recent_alerts) > MAX_RECENT_ALERTS:
        recent_alerts = recent_alerts[:MAX_RECENT_ALERTS]

    if db:
        try:
            await db.save_alert(alert)
        except Exception as e:
            print(f"ERROR saving alert: {e}", flush=True)

    if alerter:
        try:
            await alerter.send_alert(alert)
        except Exception as e:
            print(f"ERROR sending alert: {e}", flush=True)


# =========================================
# API ENDPOINTS (only if imports worked)
# =========================================

if PolymarketClient:
    @app.get("/markets")
    async def get_markets(limit: int = 20):
        """Get active markets."""
        try:
            async with PolymarketClient() as client:
                markets = await client.get_active_markets(limit=limit)
            return [
                {
                    "id": m.id,
                    "question": m.question,
                    "yes_price": m.outcome_prices.get("Yes", 0),
                    "no_price": m.outcome_prices.get("No", 0),
                    "volume": m.volume
                }
                for m in markets
            ]
        except Exception as e:
            return {"error": str(e)}

    @app.get("/trades")
    async def get_trades(limit: int = 50):
        """Get recent trades."""
        try:
            async with PolymarketClient() as client:
                trades = await client.get_recent_trades(limit=limit)
            return [
                {
                    "id": t.id,
                    "market_id": t.market_id,
                    "trader": t.trader_address,
                    "amount_usd": t.amount_usd,
                    "outcome": t.outcome,
                    "side": t.side
                }
                for t in trades
            ]
        except Exception as e:
            return {"error": str(e)}


@app.get("/alerts")
async def get_alerts(limit: int = 20):
    """Get recent alerts."""
    return [
        {
            "id": a.id,
            "type": a.alert_type,
            "severity": a.severity,
            "message": a.message,
            "amount": a.trade.amount_usd if hasattr(a, 'trade') else 0
        }
        for a in recent_alerts[:limit]
    ]


@app.get("/stats")
async def get_stats():
    """Get statistics."""
    return {
        "total_alerts": len(recent_alerts),
        "detector_active": detector is not None,
        "monitor_active": monitor is not None,
        "database_connected": db is not None,
        "startup_status": startup_status
    }


# =========================================
# RUN DIRECTLY
# =========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
