"""
Prediction Market Tracker - Source Package

This package contains:
- polymarket_client: API client for Polymarket
- kalshi_client: API client for Kalshi
- whale_detector: Logic for detecting unusual trades
- database: Database models and operations  
- alerter: Multi-channel notification system
- config: Application settings
"""

from .config import settings
from .polymarket_client import PolymarketClient, Trade, Market
from .whale_detector import WhaleDetector, WhaleAlert, TradeMonitor, WalletProfile
from .database import Database, TradeRecord, AlertRecord, WalletRecord, MarketRecord
from .alerter import (
    Alerter, 
    create_default_alerter,
    ConsoleAlert,
    EmailAlert,
    DiscordAlert,
    TelegramAlert,
    SlackAlert,
    ExpoPushAlert,
    AlertMessage
)

__all__ = [
    # Config
    "settings",
    # Polymarket
    "PolymarketClient",
    "Trade", 
    "Market",
    # Whale Detection
    "WhaleDetector",
    "WhaleAlert",
    "TradeMonitor",
    "WalletProfile",
    # Database
    "Database",
    "TradeRecord",
    "AlertRecord",
    "WalletRecord",
    "MarketRecord",
    # Alerter
    "Alerter",
    "create_default_alerter",
    "ConsoleAlert",
    "EmailAlert",
    "DiscordAlert",
    "TelegramAlert",
    "SlackAlert",
    "ExpoPushAlert",
    "AlertMessage",
]
