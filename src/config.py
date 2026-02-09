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
    POLYMARKET_WS_URL: str = "wss://ws-live-data.polymarket.com"  # WebSocket for real-time trades

    # Hybrid monitoring: WebSocket (real-time) + Polling (backup)
    USE_HYBRID_MONITOR: bool = True  # Enable WebSocket + polling hybrid
    POLL_INTERVAL: int = 30  # Backup polling interval (30s when using hybrid, 15s otherwise)
    WS_RECONNECT_DELAY: float = 5.0  # Seconds to wait before WebSocket reconnect

    # ============================================
    # KALSHI API SETTINGS
    # ============================================
    KALSHI_ENABLED: bool = True  # Enable Kalshi market tracking
    KALSHI_ELECTIONS_API: str = "https://api.elections.kalshi.com/trade-api/v2"  # Public API
    KALSHI_API_BASE: str = "https://trading-api.kalshi.com/trade-api/v2"  # Auth required
    KALSHI_API_KEY: Optional[str] = None  # API Key ID from Kalshi dashboard
    KALSHI_PRIVATE_KEY_B64: Optional[str] = None  # Base64-encoded RSA private key

    # ============================================
    # WHALE DETECTION SETTINGS (Elite Signals Only - Industry Standard)
    # ============================================
    WHALE_THRESHOLD_USDC: float = 10000.0  # $10,000 - minimum for whale alerts
    NEW_WALLET_THRESHOLD_USDC: float = 5000.0  # $5,000 - new wallets must be significant
    FOCUSED_WALLET_THRESHOLD_USDC: float = 5000.0  # $5,000 - minimum for focused wallet alerts
    WHALE_STD_MULTIPLIER: float = 4.0  # Z-score threshold for statistical anomaly
    MIN_TRADES_FOR_STATS: int = 100  # Minimum trades before using statistics
    MIN_ALERT_THRESHOLD_USD: float = 10000.0  # $10,000 - industry standard whale threshold

    # Concentrated activity detection (new wallets making repeated bets)
    CONCENTRATED_ACTIVITY_THRESHOLD: float = 5000.0  # $5k cumulative on single market
    CONCENTRATED_ACTIVITY_WINDOW_MINUTES: int = 60  # Within 1 hour

    # ============================================
    # MARKET FILTERING SETTINGS
    # ============================================
    EXCLUDE_SPORTS_MARKETS: bool = True  # Filter out sports betting markets
    # Additional keywords to exclude (comma-separated in .env)
    EXCLUDE_KEYWORDS: Optional[str] = None

    # ============================================
    # SMART MONEY DETECTION (Industry Standard - PolyTrack criteria)
    # ============================================
    SMART_MONEY_MIN_WIN_RATE: float = 0.55  # 55% win rate to be considered smart money
    SMART_MONEY_MIN_VOLUME: float = 100000.0  # $100k minimum volume (industry standard)
    SMART_MONEY_MIN_RESOLVED: int = 50  # Minimum resolved bets for win rate calculation

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
    # For forum channels: post to existing thread (recommended)
    DISCORD_THREAD_ID: Optional[str] = None
    # For forum channels: create new thread with this name (creates many threads)
    DISCORD_THREAD_NAME: Optional[str] = None

    # Category-specific thread IDs (for routing alerts by category)
    DISCORD_THREAD_POLITICS: Optional[str] = None
    DISCORD_THREAD_CRYPTO: Optional[str] = None
    DISCORD_THREAD_SPORTS: Optional[str] = None
    DISCORD_THREAD_ESPORTS: Optional[str] = None  # Esports/gaming alerts
    DISCORD_THREAD_FINANCE: Optional[str] = None
    DISCORD_THREAD_ENTERTAINMENT: Optional[str] = None
    DISCORD_THREAD_WORLD: Optional[str] = None
    DISCORD_THREAD_OTHER: Optional[str] = None  # Fallback for uncategorized
    DISCORD_THREAD_ESPORTS: Optional[str] = None  # Esports/gaming alerts thread
    DISCORD_THREAD_VIP: Optional[str] = None  # VIP wallet alerts thread
    DISCORD_THREAD_DIGEST: Optional[str] = None  # Daily/weekly digest thread

    # VIP Wallet Detection Settings
    VIP_MIN_TOTAL_VOLUME: float = 100000.0  # $100k lifetime volume to be VIP
    VIP_MIN_WIN_RATE: float = 0.55  # 55% win rate to be VIP (if enough resolved)
    VIP_MIN_LARGE_TRADES: int = 5  # 5+ trades over $5k to be VIP
    VIP_LARGE_TRADE_THRESHOLD: float = 5000.0  # What counts as a "large trade"
    VIP_MIN_ALERT_THRESHOLD: float = 5000.0  # $5k minimum for VIP alerts (single trade OR 24h cumulative on market)

    # Twitter Queue - private channel for high-value alerts to post to X
    DISCORD_TWITTER_WEBHOOK_URL: Optional[str] = None
    TWITTER_MIN_AMOUNT: float = 1000.0  # Minimum USD for Twitter-worthy alerts
    TWITTER_MAX_PER_HOUR: int = 20  # Rate limit for Twitter posts (strict criteria limits naturally)

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
    DAILY_DIGEST_HOUR: int = 5  # Send daily digest at 5 AM ET
    WEEKLY_DIGEST_DAY: str = "mon"  # Send weekly digest on Monday
    WEEKLY_DIGEST_HOUR: int = 9  # Send weekly digest at 9 AM ET
    DIGEST_TIMEZONE: str = "America/New_York"  # Eastern Time

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
