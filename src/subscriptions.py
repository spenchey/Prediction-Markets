"""
Subscription Management Module

Handles subscriber management for the prediction market tracker service:
- User registration and authentication
- Subscription tiers (free, pro, enterprise)
- Notification preferences
- Usage tracking and billing integration

This is the foundation for selling the service as a subscription.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from enum import Enum
import uuid
import hashlib
import secrets
from loguru import logger

from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer, Enum as SQLEnum
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SubscriptionTier(str, Enum):
    """Subscription tiers with different feature access."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class AlertChannel(str, Enum):
    """Available notification channels."""
    EMAIL = "email"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    SLACK = "slack"
    PUSH = "push"
    WEBHOOK = "webhook"


@dataclass
class TierLimits:
    """Limits for each subscription tier."""
    max_alerts_per_day: int
    max_tracked_wallets: int
    real_time_alerts: bool
    daily_digest: bool
    weekly_digest: bool
    smart_money_access: bool
    api_access: bool
    custom_thresholds: bool
    webhook_support: bool
    priority_support: bool


# Define tier limits
TIER_LIMITS = {
    SubscriptionTier.FREE: TierLimits(
        max_alerts_per_day=10,
        max_tracked_wallets=5,
        real_time_alerts=False,  # Delayed by 15 min
        daily_digest=True,
        weekly_digest=True,
        smart_money_access=False,
        api_access=False,
        custom_thresholds=False,
        webhook_support=False,
        priority_support=False
    ),
    SubscriptionTier.PRO: TierLimits(
        max_alerts_per_day=100,
        max_tracked_wallets=50,
        real_time_alerts=True,
        daily_digest=True,
        weekly_digest=True,
        smart_money_access=True,
        api_access=True,
        custom_thresholds=True,
        webhook_support=False,
        priority_support=False
    ),
    SubscriptionTier.ENTERPRISE: TierLimits(
        max_alerts_per_day=-1,  # Unlimited
        max_tracked_wallets=-1,  # Unlimited
        real_time_alerts=True,
        daily_digest=True,
        weekly_digest=True,
        smart_money_access=True,
        api_access=True,
        custom_thresholds=True,
        webhook_support=True,
        priority_support=True
    )
}


@dataclass
class NotificationPreferences:
    """User's notification preferences."""
    email_instant: bool = False
    email_daily_digest: bool = True
    email_weekly_digest: bool = True
    discord_enabled: bool = False
    telegram_enabled: bool = False
    slack_enabled: bool = False
    push_enabled: bool = False
    webhook_url: Optional[str] = None

    # Alert type filters
    whale_trades: bool = True
    new_wallets: bool = True
    smart_money: bool = True
    focused_wallets: bool = True
    market_anomalies: bool = True

    # Thresholds (for PRO+ users)
    min_trade_amount: float = 10000.0
    min_severity_score: int = 5

    def to_dict(self) -> Dict:
        return {
            "email_instant": self.email_instant,
            "email_daily_digest": self.email_daily_digest,
            "email_weekly_digest": self.email_weekly_digest,
            "discord_enabled": self.discord_enabled,
            "telegram_enabled": self.telegram_enabled,
            "slack_enabled": self.slack_enabled,
            "push_enabled": self.push_enabled,
            "webhook_url": self.webhook_url,
            "whale_trades": self.whale_trades,
            "new_wallets": self.new_wallets,
            "smart_money": self.smart_money,
            "focused_wallets": self.focused_wallets,
            "market_anomalies": self.market_anomalies,
            "min_trade_amount": self.min_trade_amount,
            "min_severity_score": self.min_severity_score
        }


@dataclass
class Subscriber:
    """A subscriber to the whale tracker service."""
    id: str
    email: str
    tier: SubscriptionTier
    created_at: datetime
    preferences: NotificationPreferences

    # Subscription details
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None

    # Notification targets
    discord_webhook: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    slack_webhook: Optional[str] = None
    push_tokens: List[str] = field(default_factory=list)

    # Tracked wallets (for personalized alerts)
    tracked_wallets: Set[str] = field(default_factory=set)

    # Usage tracking
    alerts_sent_today: int = 0
    last_alert_date: Optional[datetime] = None
    total_alerts_sent: int = 0

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        if self.tier == SubscriptionTier.FREE:
            return True
        if not self.subscription_end:
            return False
        return datetime.now() < self.subscription_end

    @property
    def limits(self) -> TierLimits:
        """Get the limits for this subscriber's tier."""
        return TIER_LIMITS[self.tier]

    def can_receive_alert(self) -> bool:
        """Check if subscriber can receive more alerts today."""
        limits = self.limits
        if limits.max_alerts_per_day == -1:
            return True

        # Reset counter if new day
        if self.last_alert_date and self.last_alert_date.date() < datetime.now().date():
            self.alerts_sent_today = 0

        return self.alerts_sent_today < limits.max_alerts_per_day

    def record_alert_sent(self):
        """Record that an alert was sent."""
        self.alerts_sent_today += 1
        self.total_alerts_sent += 1
        self.last_alert_date = datetime.now()

    def should_receive_alert(self, alert) -> bool:
        """
        Check if this subscriber should receive a specific alert.
        Based on their preferences and tier limits.
        """
        if not self.can_receive_alert():
            return False

        prefs = self.preferences
        alert_type = alert.alert_type if hasattr(alert, 'alert_type') else alert.get('alert_type')
        amount = alert.trade.amount_usd if hasattr(alert, 'trade') else alert.get('trade_amount_usd', 0)
        severity = alert.severity_score if hasattr(alert, 'severity_score') else alert.get('severity_score', 5)

        # Check amount threshold
        if amount < prefs.min_trade_amount:
            return False

        # Check severity threshold
        if severity < prefs.min_severity_score:
            return False

        # Check alert type filters
        type_filters = {
            "WHALE_TRADE": prefs.whale_trades,
            "NEW_WALLET": prefs.new_wallets,
            "SMART_MONEY": prefs.smart_money,
            "FOCUSED_WALLET": prefs.focused_wallets,
            "MARKET_ANOMALY": prefs.market_anomalies,
            "UNUSUAL_SIZE": prefs.whale_trades  # Group with whale trades
        }

        if not type_filters.get(alert_type, True):
            return False

        # Check if tracking specific wallet
        trader = alert.trade.trader_address if hasattr(alert, 'trade') else alert.get('trader_address', '')
        if self.tracked_wallets and trader not in self.tracked_wallets:
            # Only filter if they have specific tracked wallets
            pass  # For now, still send - could be configurable

        return True


class SubscriptionManager:
    """
    Manages subscribers and their preferences.

    In production, this would connect to a database.
    For now, it uses in-memory storage.
    """

    def __init__(self, database=None):
        self.database = database
        self._subscribers: Dict[str, Subscriber] = {}
        self._email_to_id: Dict[str, str] = {}

    def create_subscriber(
        self,
        email: str,
        tier: SubscriptionTier = SubscriptionTier.FREE
    ) -> Subscriber:
        """Create a new subscriber."""
        # Check if already exists
        if email.lower() in self._email_to_id:
            raise ValueError(f"Subscriber with email {email} already exists")

        subscriber_id = str(uuid.uuid4())
        subscriber = Subscriber(
            id=subscriber_id,
            email=email.lower(),
            tier=tier,
            created_at=datetime.now(),
            preferences=NotificationPreferences()
        )

        self._subscribers[subscriber_id] = subscriber
        self._email_to_id[email.lower()] = subscriber_id

        logger.info(f"Created new subscriber: {email} (tier: {tier.value})")
        return subscriber

    def get_subscriber(self, subscriber_id: str) -> Optional[Subscriber]:
        """Get a subscriber by ID."""
        return self._subscribers.get(subscriber_id)

    def get_subscriber_by_email(self, email: str) -> Optional[Subscriber]:
        """Get a subscriber by email."""
        subscriber_id = self._email_to_id.get(email.lower())
        if subscriber_id:
            return self._subscribers.get(subscriber_id)
        return None

    def update_tier(self, subscriber_id: str, new_tier: SubscriptionTier, duration_days: int = 30):
        """Update a subscriber's tier."""
        subscriber = self.get_subscriber(subscriber_id)
        if not subscriber:
            raise ValueError(f"Subscriber {subscriber_id} not found")

        subscriber.tier = new_tier
        subscriber.subscription_start = datetime.now()
        subscriber.subscription_end = datetime.now() + timedelta(days=duration_days)

        logger.info(f"Updated subscriber {subscriber_id} to tier {new_tier.value}")

    def update_preferences(self, subscriber_id: str, preferences: Dict):
        """Update a subscriber's notification preferences."""
        subscriber = self.get_subscriber(subscriber_id)
        if not subscriber:
            raise ValueError(f"Subscriber {subscriber_id} not found")

        for key, value in preferences.items():
            if hasattr(subscriber.preferences, key):
                setattr(subscriber.preferences, key, value)

        logger.info(f"Updated preferences for subscriber {subscriber_id}")

    def add_tracked_wallet(self, subscriber_id: str, wallet_address: str):
        """Add a wallet to a subscriber's tracked list."""
        subscriber = self.get_subscriber(subscriber_id)
        if not subscriber:
            raise ValueError(f"Subscriber {subscriber_id} not found")

        limits = subscriber.limits
        if limits.max_tracked_wallets != -1 and len(subscriber.tracked_wallets) >= limits.max_tracked_wallets:
            raise ValueError(f"Maximum tracked wallets ({limits.max_tracked_wallets}) reached for tier {subscriber.tier.value}")

        subscriber.tracked_wallets.add(wallet_address.lower())
        logger.info(f"Added tracked wallet for subscriber {subscriber_id}")

    def remove_tracked_wallet(self, subscriber_id: str, wallet_address: str):
        """Remove a wallet from a subscriber's tracked list."""
        subscriber = self.get_subscriber(subscriber_id)
        if not subscriber:
            raise ValueError(f"Subscriber {subscriber_id} not found")

        subscriber.tracked_wallets.discard(wallet_address.lower())

    def get_subscribers_for_alert(self, alert) -> List[Subscriber]:
        """
        Get all subscribers who should receive a specific alert.
        Filters based on preferences, limits, and subscription status.
        """
        recipients = []

        for subscriber in self._subscribers.values():
            if not subscriber.is_active:
                continue
            if subscriber.should_receive_alert(alert):
                recipients.append(subscriber)

        return recipients

    def get_all_active_subscribers(self) -> List[Subscriber]:
        """Get all active subscribers."""
        return [s for s in self._subscribers.values() if s.is_active]

    def get_digest_subscribers(self, digest_type: str = "daily") -> List[Subscriber]:
        """Get subscribers who want to receive digests."""
        subscribers = []

        for subscriber in self._subscribers.values():
            if not subscriber.is_active:
                continue

            prefs = subscriber.preferences
            if digest_type == "daily" and prefs.email_daily_digest:
                subscribers.append(subscriber)
            elif digest_type == "weekly" and prefs.email_weekly_digest:
                subscribers.append(subscriber)

        return subscribers

    def generate_api_key(self, subscriber_id: str) -> str:
        """
        Generate an API key for a subscriber.
        Only available for PRO+ tiers.
        """
        subscriber = self.get_subscriber(subscriber_id)
        if not subscriber:
            raise ValueError(f"Subscriber {subscriber_id} not found")

        if not subscriber.limits.api_access:
            raise ValueError(f"API access not available for tier {subscriber.tier.value}")

        # Generate a secure API key
        api_key = secrets.token_urlsafe(32)
        # In production, hash and store this
        return api_key

    def get_stats(self) -> Dict:
        """Get subscription statistics."""
        total = len(self._subscribers)
        by_tier = {tier.value: 0 for tier in SubscriptionTier}
        active = 0

        for subscriber in self._subscribers.values():
            by_tier[subscriber.tier.value] += 1
            if subscriber.is_active:
                active += 1

        return {
            "total_subscribers": total,
            "active_subscribers": active,
            "by_tier": by_tier,
            "total_alerts_sent": sum(s.total_alerts_sent for s in self._subscribers.values())
        }


# =========================================
# DATABASE MODELS (for persistence)
# =========================================

class SubscriberRecord(Base):
    """SQLAlchemy model for persisting subscribers."""
    __tablename__ = "subscribers"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True)
    tier = Column(String)
    created_at = Column(DateTime)
    subscription_start = Column(DateTime, nullable=True)
    subscription_end = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)

    # Notification targets
    discord_webhook = Column(String, nullable=True)
    telegram_chat_id = Column(String, nullable=True)
    slack_webhook = Column(String, nullable=True)

    # Preferences stored as JSON
    preferences_json = Column(String)

    # Usage
    total_alerts_sent = Column(Integer, default=0)
    alerts_sent_today = Column(Integer, default=0)
    last_alert_date = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)


class TrackedWalletRecord(Base):
    """SQLAlchemy model for tracked wallets."""
    __tablename__ = "tracked_wallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subscriber_id = Column(String, index=True)
    wallet_address = Column(String, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)


# =========================================
# CONVENIENCE FUNCTIONS
# =========================================

def create_subscription_manager(database=None) -> SubscriptionManager:
    """Create a subscription manager instance."""
    return SubscriptionManager(database=database)
