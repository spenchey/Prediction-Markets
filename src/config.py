"""
Configuration settings for the Prediction Market Tracker.

This file loads settings from environment variables (for security)
and provides default values for development.

Combined configuration from both original implementations with
enhanced settings for:
- Sports market filtering
- Subscription management
- Scheduled digests
- Automated trading (future)
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    To use in production, create a .env file with your values:
    DATABASE_URL=postgresql://user:pass@host/db
    RESEND_API_KEY=re_xxxxx
    """

    # ============================================
    # DATABASE SETTINGS
    # ============================================
    DATABASE_URL: str = "sqlite+aiosqlite:///./trades.db"

    # ============================================
    # POLYMARKET API SETTINGS
    # ============================================
    POLYMARKET_API_BASE: str = "https://clob.polymarket.com"
    POLYMARKET_GAMMA_API: str = "https://gamma-api.polymarket.com"
    POLYMARKET_DATA_API: str = "https://data-api.polymarket.com"  # For trade data
    POLL_INTERVAL: int = 60  # Check every minute

    # ============================================
    # KALSHI API SETTINGS (for future use)
    # ============================================
    KALSHI_API_BASE: str = "https://trading-api.kalshi.com/trade-api/v2"
    KALSHI_API_KEY: Optional[str] = None
    KALSHI_PRIVATE_KEY_PATH: Optional[str] = None
    KALSHI_EMAIL: Optional[str] = None
    KALSHI_PASSWORD: Optional[str] = None
    KALSHI_DEMO: bool = True  # Set to False for production

    # ============================================
    # WHALE DETECTION SETTINGS
    # ============================================
    WHALE_THRESHOLD_USDC: float = 10000.0  # $10,000 - minimum for whale alerts
    NEW_WALLET_THRESHOLD_USDC: float = 1000.0  # $1,000 - minimum for new wallet alerts
    FOCUSED_WALLET_THRESHOLD_USDC: float = 5000.0  # $5,000 - minimum for focused wallet alerts
    WHALE_STD_MULTIPLIER: float = 3.0  # Z-score threshold for statistical anomaly
    MIN_TRADES_FOR_STATS: int = 100  # Minimum trades before using statistics

    # ============================================
    # MARKET FILTERING SETTINGS
    # ============================================
    EXCLUDE_SPORTS_MARKETS: bool = True  # Filter out sports betting markets
    # Additional keywords to exclude (comma-separated in .env)
    EXCLUDE_KEYWORDS: Optional[str] = None

    # ============================================
    # SMART MONEY DETECTION
    # ============================================
    SMART_MONEY_MIN_WIN_RATE: float = 0.60  # 60% win rate to be considered smart money
    SMART_MONEY_MIN_VOLUME: float = 50000.0  # $50k minimum volume
    SMART_MONEY_MIN_RESOLVED: int = 10  # Minimum resolved bets for win rate calculation

    # ============================================
    # EMAIL NOTIFICATIONS (Resend.com)
    # ============================================
    RESEND_API_KEY: Optional[str] = None
    ALERT_EMAIL: Optional[str] = None
    FROM_EMAIL: str = "Whale Tracker <alerts@whaletracker.io>"

    # ============================================
    # TELEGRAM NOTIFICATIONS
    # ============================================
    # Get from @BotFather on Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    # Get by messaging your bot and checking /getUpdates
    TELEGRAM_CHAT_ID: Optional[str] = None

    # ============================================
    # DISCORD NOTIFICATIONS
    # ============================================
    # Create webhook in Server Settings → Integrations
    DISCORD_WEBHOOK_URL: Optional[str] = None

    # ============================================
    # SLACK NOTIFICATIONS
    # ============================================
    # Create app at api.slack.com/apps with Incoming Webhooks
    SLACK_WEBHOOK_URL: Optional[str] = None

    # ============================================
    # PUSH NOTIFICATIONS (Expo)
    # ============================================
    # Push tokens are stored per-user in the database
    # No global config needed - handled at runtime

    # ============================================
    # SCHEDULED DIGEST SETTINGS
    # ============================================
    DAILY_DIGEST_HOUR: int = 8  # Send daily digest at 8 AM
    WEEKLY_DIGEST_DAY: str = "mon"  # Send weekly digest on Monday
    WEEKLY_DIGEST_HOUR: int = 9  # Send weekly digest at 9 AM
    DIGEST_TIMEZONE: str = "UTC"  # Timezone for scheduled digests

    # ============================================
    # SUBSCRIPTION SETTINGS
    # ============================================
    # Stripe integration for payments
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Free tier limits
    FREE_ALERTS_PER_DAY: int = 10
    FREE_TRACKED_WALLETS: int = 5

    # Pro tier limits
    PRO_ALERTS_PER_DAY: int = 100
    PRO_TRACKED_WALLETS: int = 50

    # Pricing (in cents)
    PRO_MONTHLY_PRICE: int = 2900  # $29/month
    ENTERPRISE_MONTHLY_PRICE: int = 9900  # $99/month

    # ============================================
    # AUTOMATED TRADING (FUTURE)
    # ============================================
    # Enable automated trading features
    ENABLE_AUTO_TRADING: bool = False
    MAX_AUTO_TRADE_SIZE: float = 100.0  # Maximum $100 per auto trade
    AUTO_TRADE_WALLET_KEY: Optional[str] = None  # Private key (NEVER commit this!)

    # ============================================
    # APPLICATION SETTINGS
    # ============================================
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # API Settings
    API_RATE_LIMIT: int = 100  # Requests per minute
    API_KEY_HEADER: str = "X-API-Key"

    # Frontend URL (for CORS)
    FRONTEND_URL: str = "http://localhost:3000"

    # JWT Settings (for authentication)
    JWT_SECRET: str = "change-this-in-production"  # Override in .env!
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a global settings instance
settings = Settings()
