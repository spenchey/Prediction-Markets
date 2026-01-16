"""
Database Module

This module handles storing trades and alerts in a database.
We use SQLite for local development (simple, no setup needed)
and PostgreSQL for production (Railway, Heroku, etc.).

SQLAlchemy makes this database-agnostic!
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, String, Float, DateTime, Boolean, Integer,
    create_engine, select, desc
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from loguru import logger

from .config import settings


def get_async_database_url(url: str) -> str:
    """
    Convert database URL to async-compatible format.

    Railway and other providers give URLs like:
      postgresql://user:pass@host/db

    But SQLAlchemy async needs:
      postgresql+asyncpg://user:pass@host/db

    For SQLite:
      sqlite:///./trades.db -> sqlite+aiosqlite:///./trades.db
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        # Heroku uses postgres:// which is deprecated
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


# Create the base class for our models
Base = declarative_base()


# =========================================
# DATABASE MODELS
# =========================================

class TradeRecord(Base):
    """
    Stores individual trades from prediction markets.
    
    This is your historical record of all trades you've seen.
    """
    __tablename__ = "trades"
    
    id = Column(String, primary_key=True)  # Trade ID from API
    market_id = Column(String, index=True)
    trader_address = Column(String, index=True)  # Index for fast lookups
    outcome = Column(String)  # "Yes" or "No"
    side = Column(String)  # "buy" or "sell"
    size = Column(Float)
    price = Column(Float)
    amount_usd = Column(Float, index=True)  # Index for finding whales
    timestamp = Column(DateTime, index=True)
    transaction_hash = Column(String)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertRecord(Base):
    """
    Stores generated alerts for whale activity.
    
    These are the alerts that get sent to subscribers.
    """
    __tablename__ = "alerts"
    
    id = Column(String, primary_key=True)
    alert_type = Column(String, index=True)
    severity = Column(String)
    message = Column(String)
    
    # Trade info
    trade_id = Column(String)
    trade_amount_usd = Column(Float)
    trader_address = Column(String, index=True)
    market_id = Column(String)
    market_question = Column(String)
    category = Column(String, index=True)  # Auto-detected category for routing
    outcome = Column(String)
    side = Column(String)
    
    # Wallet info
    is_new_wallet = Column(Boolean)
    wallet_total_volume = Column(Float)
    trade_size_percentile = Column(Float)
    
    # Timestamps
    trade_timestamp = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Notification tracking
    email_sent = Column(Boolean, default=False)
    push_sent = Column(Boolean, default=False)


class WalletRecord(Base):
    """
    Stores wallet profiles for tracking trader behavior.
    """
    __tablename__ = "wallets"
    
    address = Column(String, primary_key=True)
    total_trades = Column(Integer, default=0)
    total_volume_usd = Column(Float, default=0.0)
    first_seen = Column(DateTime)
    last_seen = Column(DateTime)
    markets_count = Column(Integer, default=0)
    
    # Performance tracking (if you add resolution data later)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    
    # Flags
    is_flagged_whale = Column(Boolean, default=False)
    is_smart_money = Column(Boolean, default=False)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketRecord(Base):
    """
    Stores market information for reference.
    """
    __tablename__ = "markets"
    
    id = Column(String, primary_key=True)
    question = Column(String)
    slug = Column(String)
    yes_price = Column(Float)
    no_price = Column(Float)
    volume = Column(Float)
    liquidity = Column(Float)
    active = Column(Boolean)
    end_date = Column(DateTime, nullable=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =========================================
# DATABASE MANAGER
# =========================================

class Database:
    """
    Database manager class.
    
    Handles all database operations with async support.
    
    Usage:
        db = Database()
        await db.init()  # Create tables
        await db.save_trade(trade)
    """
    
    def __init__(self, database_url: str = None):
        raw_url = database_url or settings.DATABASE_URL
        # Convert to async-compatible URL format
        self.database_url = get_async_database_url(raw_url)

        # PostgreSQL-specific settings for better performance
        engine_kwargs = {
            "echo": settings.DEBUG,  # Log SQL queries in debug mode
        }
        if "postgresql" in self.database_url:
            engine_kwargs["pool_size"] = 5
            engine_kwargs["max_overflow"] = 10
            engine_kwargs["pool_pre_ping"] = True  # Check connections before use

        self.engine = create_async_engine(self.database_url, **engine_kwargs)
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def init(self):
        """
        Initialize the database - create all tables.
        
        Call this once when your app starts.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"✅ Database initialized: {self.database_url}")
    
    async def close(self):
        """Close database connections."""
        await self.engine.dispose()
    
    # =========================================
    # TRADE OPERATIONS
    # =========================================
    
    async def save_trade(self, trade) -> bool:
        """
        Save a trade to the database.
        
        Returns True if saved, False if already exists.
        """
        async with self.async_session() as session:
            # Check if already exists
            result = await session.execute(
                select(TradeRecord).where(TradeRecord.id == trade.id)
            )
            if result.scalar_one_or_none():
                return False
            
            record = TradeRecord(
                id=trade.id,
                market_id=trade.market_id,
                trader_address=trade.trader_address,
                outcome=trade.outcome,
                side=trade.side,
                size=trade.size,
                price=trade.price,
                amount_usd=trade.amount_usd,
                timestamp=trade.timestamp,
                transaction_hash=trade.transaction_hash
            )
            
            session.add(record)
            await session.commit()
            return True
    
    async def save_trades(self, trades: list) -> int:
        """
        Save multiple trades at once.
        
        Returns the number of new trades saved.
        """
        saved = 0
        for trade in trades:
            if await self.save_trade(trade):
                saved += 1
        return saved
    
    async def get_recent_trades(self, limit: int = 100) -> List[TradeRecord]:
        """Get the most recent trades from database."""
        async with self.async_session() as session:
            result = await session.execute(
                select(TradeRecord)
                .order_by(desc(TradeRecord.timestamp))
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_trades_by_wallet(
        self,
        wallet_address: str,
        limit: int = 100
    ) -> List[TradeRecord]:
        """Get all trades by a specific wallet."""
        async with self.async_session() as session:
            result = await session.execute(
                select(TradeRecord)
                .where(TradeRecord.trader_address == wallet_address)
                .order_by(desc(TradeRecord.timestamp))
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_whale_trades(
        self,
        min_amount: float = 10000,
        limit: int = 100
    ) -> List[TradeRecord]:
        """Get trades above a certain amount."""
        async with self.async_session() as session:
            result = await session.execute(
                select(TradeRecord)
                .where(TradeRecord.amount_usd >= min_amount)
                .order_by(desc(TradeRecord.timestamp))
                .limit(limit)
            )
            return result.scalars().all()
    
    # =========================================
    # ALERT OPERATIONS
    # =========================================
    
    async def save_alert(self, alert) -> bool:
        """Save an alert to the database."""
        async with self.async_session() as session:
            # Check if already exists
            result = await session.execute(
                select(AlertRecord).where(AlertRecord.id == alert.id)
            )
            if result.scalar_one_or_none():
                return False
            
            record = AlertRecord(
                id=alert.id,
                alert_type=alert.alert_type,
                severity=alert.severity,
                message=alert.message,
                trade_id=alert.trade.id,
                trade_amount_usd=alert.trade.amount_usd,
                trader_address=alert.trade.trader_address,
                market_id=alert.trade.market_id,
                market_question=alert.market_question,
                category=getattr(alert, 'category', None),  # Store category for digest routing
                outcome=alert.trade.outcome,
                side=alert.trade.side,
                is_new_wallet=alert.wallet_profile.is_new_wallet if alert.wallet_profile else None,
                wallet_total_volume=alert.wallet_profile.total_volume_usd if alert.wallet_profile else None,
                trade_size_percentile=alert.trade_size_percentile,
                trade_timestamp=alert.trade.timestamp,
            )
            
            session.add(record)
            await session.commit()
            return True
    
    async def get_recent_alerts(self, limit: int = 50) -> List[AlertRecord]:
        """Get recent alerts."""
        async with self.async_session() as session:
            result = await session.execute(
                select(AlertRecord)
                .order_by(desc(AlertRecord.created_at))
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_alerts_by_type(
        self,
        alert_type: str,
        limit: int = 50
    ) -> List[AlertRecord]:
        """Get alerts of a specific type."""
        async with self.async_session() as session:
            result = await session.execute(
                select(AlertRecord)
                .where(AlertRecord.alert_type == alert_type)
                .order_by(desc(AlertRecord.created_at))
                .limit(limit)
            )
            return result.scalars().all()

    async def get_alerts_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[AlertRecord]:
        """
        Get alerts within a specific date range.

        Args:
            start_time: Start of the date range (inclusive)
            end_time: End of the date range (inclusive)
            limit: Maximum number of alerts to return

        Returns:
            List of AlertRecord objects ordered by created_at DESC
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(AlertRecord)
                .where(AlertRecord.created_at >= start_time)
                .where(AlertRecord.created_at <= end_time)
                .order_by(desc(AlertRecord.created_at))
                .limit(limit)
            )
            return result.scalars().all()

    async def get_digest_summary(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> dict:
        """
        Get aggregated summary data for digest email.

        Returns dict with:
        - total_alerts: int
        - alerts_by_type: dict
        - alerts_by_severity: dict
        - total_volume: float
        - top_trades: list (top 10 by amount)
        - all_alerts: list
        """
        alerts = await self.get_alerts_by_date_range(start_time, end_time)

        alerts_by_type = {}
        alerts_by_severity = {}
        total_volume = 0.0

        for alert in alerts:
            # Count by type
            alerts_by_type[alert.alert_type] = alerts_by_type.get(alert.alert_type, 0) + 1
            # Count by severity
            alerts_by_severity[alert.severity] = alerts_by_severity.get(alert.severity, 0) + 1
            # Sum volume
            total_volume += alert.trade_amount_usd or 0.0

        # Get top trades (sorted by amount)
        top_trades = sorted(alerts, key=lambda a: a.trade_amount_usd or 0, reverse=True)[:10]

        return {
            "total_alerts": len(alerts),
            "alerts_by_type": alerts_by_type,
            "alerts_by_severity": alerts_by_severity,
            "total_volume": total_volume,
            "top_trades": [
                {
                    "amount": a.trade_amount_usd,
                    "market": a.market_question,
                    "market_id": a.market_id,  # Include for Kalshi ticker-based category detection
                    "category": a.category,  # Stored category from alert creation
                    "outcome": a.outcome,
                    "wallet": a.trader_address,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                }
                for a in top_trades
            ],
            "all_alerts": alerts,
        }

    # =========================================
    # WALLET OPERATIONS
    # =========================================
    
    async def update_wallet(self, profile) -> None:
        """Update or create a wallet profile."""
        async with self.async_session() as session:
            result = await session.execute(
                select(WalletRecord).where(WalletRecord.address == profile.address)
            )
            record = result.scalar_one_or_none()
            
            if record:
                # Update existing
                record.total_trades = profile.total_trades
                record.total_volume_usd = profile.total_volume_usd
                record.last_seen = profile.last_seen
                record.markets_count = len(profile.markets_traded)
                record.is_flagged_whale = profile.is_whale
                record.is_smart_money = profile.is_smart_money
            else:
                # Create new
                record = WalletRecord(
                    address=profile.address,
                    total_trades=profile.total_trades,
                    total_volume_usd=profile.total_volume_usd,
                    first_seen=profile.first_seen,
                    last_seen=profile.last_seen,
                    markets_count=len(profile.markets_traded),
                    is_flagged_whale=profile.is_whale,
                    is_smart_money=profile.is_smart_money
                )
                session.add(record)
            
            await session.commit()
    
    async def get_top_wallets(self, limit: int = 20) -> List[WalletRecord]:
        """Get top wallets by volume."""
        async with self.async_session() as session:
            result = await session.execute(
                select(WalletRecord)
                .order_by(desc(WalletRecord.total_volume_usd))
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_whale_wallets(self, limit: int = 50) -> List[WalletRecord]:
        """Get all whale wallets."""
        async with self.async_session() as session:
            result = await session.execute(
                select(WalletRecord)
                .where(WalletRecord.is_flagged_whale == True)
                .order_by(desc(WalletRecord.total_volume_usd))
                .limit(limit)
            )
            return result.scalars().all()


# =========================================
# CONVENIENCE FUNCTION
# =========================================

# Global database instance
_db: Optional[Database] = None

async def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        await _db.init()
    return _db


# =========================================
# TEST THE DATABASE
# =========================================

async def main():
    """Test the database."""
    print("🗄️ Testing Database...\n")
    
    db = Database("sqlite+aiosqlite:///./test_trades.db")
    await db.init()
    
    # Import and fetch some trades
    from .polymarket_client import PolymarketClient
    
    async with PolymarketClient() as client:
        trades = await client.get_recent_trades(limit=50)
    
    # Save trades
    saved = await db.save_trades(trades)
    print(f"✅ Saved {saved} new trades")
    
    # Retrieve recent trades
    recent = await db.get_recent_trades(limit=5)
    print(f"\n📊 Recent trades from database:")
    for trade in recent:
        print(f"  ${trade.amount_usd:,.2f} - {trade.side} {trade.outcome}")
    
    # Get whale trades
    whales = await db.get_whale_trades(min_amount=1000)
    print(f"\n🐋 Found {len(whales)} trades over $1,000")
    
    await db.close()
    print("\n✅ Database working correctly!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
