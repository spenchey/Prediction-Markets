"""
Alerter Module - Complete Notification System

Supports ALL notification channels:
- Console (always on)
- Email (via Resend)
- Discord (webhook)
- Telegram (bot)
- Push Notifications (via Expo for mobile apps)
- Slack (webhook)
"""
import asyncio
import json
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from dataclasses import dataclass

from .config import settings


# Severity explanations for users
SEVERITY_INFO = {
    "HIGH": "Large trade size, unusual pattern, or high-confidence signal",
    "MEDIUM": "Notable activity worth monitoring",
    "LOW": "Minor signal, may be noise"
}

@dataclass
class AlertMessage:
    """Standardized alert message for any channel."""
    title: str
    messages: List[str]  # List of reason messages (consolidated)
    severity: str
    alert_types: List[str]  # List of triggered alert types
    trade_amount: float
    trader_address: str
    market_id: str
    market_question: Optional[str]
    outcome: str
    timestamp: datetime
    platform: str = "Polymarket"  # Platform: Polymarket, Kalshi, PredictIt
    side: str = "buy"  # buy or sell
    category: str = "Other"  # Politics, Crypto, Sports, Finance, etc.
    market_url: Optional[str] = None  # Link to market page
    trader_url: Optional[str] = None  # Link to trader profile
    position_action: str = "OPENING"  # OPENING, ADDING, CLOSING - trade intent

    # Backwards compatibility properties
    @property
    def message(self) -> str:
        """Primary message for backwards compatibility."""
        return self.messages[0] if self.messages else ""

    @property
    def alert_type(self) -> str:
        """Primary alert type for backwards compatibility."""
        return self.alert_types[0] if self.alert_types else "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "messages": self.messages,
            "severity": self.severity,
            "alert_type": self.alert_type,
            "alert_types": self.alert_types,
            "trade_amount": self.trade_amount,
            "trader_address": self.trader_address,
            "market_id": self.market_id,
            "market_question": self.market_question,
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat()
        }

    def to_plain_text(self) -> str:
        market_info = self.market_question or "Unknown Market"
        action = self.side.capitalize() if self.side else "Traded"
        market_link = f"\n🔗 Link: {self.market_url}" if self.market_url else ""
        action_emoji = {"OPENING": "🆕", "ADDING": "➕", "CLOSING": "🔚"}.get(self.position_action, "")

        # Format all triggered reasons
        reasons_text = "\n".join(f"  • {msg}" for msg in self.messages)
        types_text = " + ".join(t.replace("_", " ").title() for t in self.alert_types)

        return f"""🚨 {self.title}

🔔 Triggered: {types_text}

{reasons_text}

📊 Market: {market_info}{market_link}
🏷️ Category: {self.category}
🏦 Platform: {self.platform}
💰 Amount: ${self.trade_amount:,.2f}
🎯 Position: {action} {self.outcome} ({action_emoji} {self.position_action})
⚡ Severity: {self.severity}
👤 Trader: {self.trader_address[:20]}...
⏰ Time: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"""

    def to_html(self) -> str:
        severity_color = {"LOW": "#4CAF50", "MEDIUM": "#FFC107", "HIGH": "#F44336"}.get(self.severity, "#9E9E9E")
        market_row = f'<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Market</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{self.market_question[:60]}...</td></tr>' if self.market_question else ""
        
        return f"""<!DOCTYPE html>
<html><body style="margin: 0; padding: 20px; background-color: #f0f0f0;">
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden;">
    <div style="background-color: {severity_color}; padding: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">🐋 {self.title}</h1>
    </div>
    <div style="padding: 25px;">
        <p style="font-size: 18px; color: #333;">{self.message}</p>
        <table style="width: 100%; border-collapse: collapse; background: #fafafa; border-radius: 5px;">
            {market_row}
            <tr><td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>💰 Amount</strong></td><td style="padding: 12px; border-bottom: 1px solid #eee; font-size: 18px; color: #2e7d32;">${self.trade_amount:,.2f}</td></tr>
            <tr><td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>🎯 Outcome</strong></td><td style="padding: 12px; border-bottom: 1px solid #eee;">{self.outcome}</td></tr>
            <tr><td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>👤 Trader</strong></td><td style="padding: 12px; border-bottom: 1px solid #eee;"><code>{self.trader_address[:20]}...</code></td></tr>
            <tr><td style="padding: 12px;"><strong>⏰ Time</strong></td><td style="padding: 12px;">{self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</td></tr>
        </table>
    </div>
</div>
</body></html>"""


class AlertChannel(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass
    
    @abstractmethod
    async def send(self, alert: AlertMessage) -> bool: pass
    
    @abstractmethod
    def is_configured(self) -> bool: pass


class ConsoleAlert(AlertChannel):
    """Print alerts to console."""
    @property
    def name(self) -> str: return "Console"
    
    async def send(self, alert: AlertMessage) -> bool:
        emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(alert.severity, "⚪")
        print(f"\n{'='*60}\n{emoji} {alert.title}\n{'='*60}")
        print(alert.to_plain_text())
        print("="*60 + "\n")
        return True
    
    def is_configured(self) -> bool: return True


class EmailAlert(AlertChannel):
    """
    Email via Resend.com
    
    Setup:
    1. Sign up at https://resend.com (free: 100/day)
    2. Get API key from dashboard
    3. Add to .env: RESEND_API_KEY=re_xxx and ALERT_EMAIL=you@email.com
    """
    def __init__(self, api_key: str = None, to_email: str = None):
        self.api_key = api_key or getattr(settings, 'RESEND_API_KEY', None)
        self.to_email = to_email or getattr(settings, 'ALERT_EMAIL', None)
    
    @property
    def name(self) -> str: return "Email"
    
    async def send(self, alert: AlertMessage) -> bool:
        if not self.is_configured(): return False
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                r = await client.post("https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"from": "Whale Tracker <onboarding@resend.dev>", "to": [self.to_email],
                          "subject": f"🐋 {alert.title} - ${alert.trade_amount:,.0f}", "html": alert.to_html()},
                    timeout=10.0)
                if r.status_code == 200:
                    logger.info(f"📧 Email sent to {self.to_email}")
                    return True
                logger.error(f"Email failed: {r.text}")
        except Exception as e: logger.error(f"Email error: {e}")
        return False
    
    def is_configured(self) -> bool: return bool(self.api_key and self.to_email)


class DiscordAlert(AlertChannel):
    """
    Discord webhook (supports both regular channels and forum channels)

    Setup:
    1. Right-click channel → Edit Channel → Integrations → Webhooks
    2. Create webhook, copy URL
    3. Add to .env: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

    For Forum Channels (optional):
    - DISCORD_THREAD_ID: Post to an existing thread (recommended)
    - DISCORD_THREAD_NAME: Create a new thread for each alert (creates many threads)

    Category-based routing:
    - DISCORD_THREAD_POLITICS: Thread ID for politics alerts
    - DISCORD_THREAD_CRYPTO: Thread ID for crypto alerts
    - DISCORD_THREAD_SPORTS: Thread ID for sports alerts
    - DISCORD_THREAD_FINANCE: Thread ID for finance alerts
    - DISCORD_THREAD_ENTERTAINMENT: Thread ID for entertainment alerts
    - DISCORD_THREAD_WORLD: Thread ID for world alerts
    - DISCORD_THREAD_OTHER: Thread ID for uncategorized alerts

    If webhook points to a forum channel and neither is set, uses alert title as thread name.
    """
    def __init__(self, webhook_url: str = None, thread_id: str = None, thread_name: str = None):
        self.webhook_url = webhook_url or getattr(settings, 'DISCORD_WEBHOOK_URL', None)
        self.thread_id = thread_id or getattr(settings, 'DISCORD_THREAD_ID', None)
        self.thread_name = thread_name or getattr(settings, 'DISCORD_THREAD_NAME', None)
        self._is_forum_channel = None  # Will be detected on first send

        # Category-specific thread IDs
        self.category_threads = {
            "Politics": getattr(settings, 'DISCORD_THREAD_POLITICS', None),
            "Crypto": getattr(settings, 'DISCORD_THREAD_CRYPTO', None),
            "Sports": getattr(settings, 'DISCORD_THREAD_SPORTS', None),
            "Finance": getattr(settings, 'DISCORD_THREAD_FINANCE', None),
            "Entertainment": getattr(settings, 'DISCORD_THREAD_ENTERTAINMENT', None),
            "World": getattr(settings, 'DISCORD_THREAD_WORLD', None),
            "Other": getattr(settings, 'DISCORD_THREAD_OTHER', None),
        }

        # Special thread for VIP wallet alerts (overrides category routing)
        self.vip_thread_id = getattr(settings, 'DISCORD_THREAD_VIP', None)

    def _get_thread_id_for_category(self, category: str) -> Optional[str]:
        """Get the appropriate thread ID for a category."""
        # Try exact match first
        thread_id = self.category_threads.get(category)
        if thread_id:
            return thread_id
        # Fallback to "Other" category thread
        if self.category_threads.get("Other"):
            return self.category_threads["Other"]
        # Fallback to default thread ID
        return self.thread_id

    @property
    def name(self) -> str: return "Discord"

    async def send(self, alert: AlertMessage) -> bool:
        if not self.is_configured(): return False
        try:
            import httpx
            color = {"LOW": 0x4CAF50, "MEDIUM": 0xFFC107, "HIGH": 0xF44336}.get(alert.severity, 0x9E9E9E)

            # Format action with position intent: "Bought Yes (OPENING)" or "Sold No (CLOSING)"
            action = alert.side.capitalize() if alert.side else "Traded"
            # Position action emoji
            action_emoji = {
                "OPENING": "🆕",  # New position
                "ADDING": "➕",   # Adding to existing
                "CLOSING": "🔚",  # Closing position
            }.get(alert.position_action, "")
            position_text = f"{action} **{alert.outcome}**\n{action_emoji} {alert.position_action}"

            # Severity with explanation
            severity_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(alert.severity, "⚪")
            severity_explanation = SEVERITY_INFO.get(alert.severity, "")
            severity_text = f"{severity_emoji} {alert.severity}"
            if severity_explanation:
                severity_text += f"\n_{severity_explanation}_"

            # Market with link (Discord markdown)
            market_text = alert.market_question or "Unknown Market"
            if alert.market_url:
                market_text = f"[{market_text}]({alert.market_url})"

            # Trader with link to profile (handle anonymous traders)
            is_anonymous = alert.trader_address.startswith("KALSHI_") or alert.trader_address == "UNKNOWN"
            if is_anonymous:
                trader_text = "_Anonymous (platform doesn't expose trader identity)_"
            elif alert.trader_url:
                trader_short = f"{alert.trader_address[:20]}..."
                trader_text = f"[`{trader_short}`]({alert.trader_url})"
            else:
                trader_short = f"{alert.trader_address[:20]}..."
                trader_text = f"`{trader_short}`"

            # Category emoji
            category_emoji = {
                "Politics": "🏛️",
                "Crypto": "₿",
                "Sports": "⚽",
                "Finance": "📈",
                "Entertainment": "🎬",
                "Science": "🔬",
                "World": "🌍",
                "Other": "📌",
            }.get(alert.category, "📌")

            # Format consolidated reasons - show all triggers
            if len(alert.messages) > 1:
                # Multiple triggers - show all reasons with bullets
                reasons_text = "\n".join(f"• {msg}" for msg in alert.messages)
                # Show trigger types as badges
                trigger_badges = " ".join(f"`{t.replace('_', ' ')}`" for t in alert.alert_types)
                description = f"**🔔 Triggered:** {trigger_badges}\n\n{reasons_text}"
            else:
                # Single trigger - show just the message
                description = alert.messages[0] if alert.messages else ""

            # Build fields - market question is always first and prominent
            fields = [
                {"name": "📊 Market", "value": market_text, "inline": False},
                {"name": f"{category_emoji} Category", "value": alert.category, "inline": True},
                {"name": "🏦 Platform", "value": alert.platform, "inline": True},
                {"name": "💰 Amount", "value": f"${alert.trade_amount:,.2f}", "inline": True},
                {"name": "🎯 Position", "value": position_text, "inline": True},
                {"name": "⚡ Severity", "value": severity_text, "inline": False},
                {"name": "👤 Trader", "value": trader_text, "inline": False},
            ]

            payload = {
                "embeds": [{
                    "title": f"🐋 {alert.title}",
                    "description": description,
                    "color": color,
                    "fields": fields,
                    "timestamp": alert.timestamp.isoformat(),
                    "footer": {"text": f"Whale Tracker • {alert.platform} • {alert.category}"}
                }],
                "username": "Whale Tracker"
            }

            # Build URL with thread_id as query parameter (required for forum channels)
            # VIP alerts go to VIP thread (overrides category routing)
            if "VIP_WALLET" in alert.alert_types and self.vip_thread_id:
                thread_id = self.vip_thread_id
                logger.debug(f"Routing to VIP thread: {thread_id}")
            else:
                # Use category-based routing
                thread_id = self._get_thread_id_for_category(alert.category)
                logger.info(f"📍 Routing alert to {alert.category} thread: {thread_id}")

            url = self.webhook_url
            if thread_id:
                url = f"{self.webhook_url}?thread_id={thread_id}"

            async with httpx.AsyncClient() as client:
                r = await client.post(url, json=payload, timeout=10.0)

                if r.status_code in [200, 204]:
                    logger.info("🎮 Discord alert sent")
                    return True

                # Check if this is a forum channel error (no thread specified)
                if r.status_code == 400:
                    try:
                        error_data = r.json()
                        if error_data.get("code") == 220001:
                            # Forum channel requires thread_name or thread_id
                            logger.warning("Discord webhook is a forum channel, retrying with thread_name")

                            # Retry with thread_name to create a new thread
                            thread_title = self.thread_name or f"${alert.trade_amount:,.0f} {alert.alert_type.replace('_', ' ').title()}"
                            payload["thread_name"] = thread_title[:100]  # Discord limit

                            r2 = await client.post(self.webhook_url, json=payload, timeout=10.0)
                            if r2.status_code in [200, 204]:
                                logger.info(f"🎮 Discord alert sent (new thread: {thread_title})")
                                return True
                            else:
                                logger.error(f"Discord retry failed: {r2.status_code} - {r2.text}")
                        else:
                            logger.error(f"Discord error: {r.status_code} - {r.text}")
                    except Exception:
                        logger.error(f"Discord error: {r.status_code} - {r.text}")
                else:
                    logger.error(f"Discord error: {r.status_code} - {r.text}")

        except Exception as e:
            logger.error(f"Discord error: {e}")
        return False

    async def send_digest(self, payload: dict) -> bool:
        """
        Send a digest report to Discord.

        Args:
            payload: Discord embed payload from DigestReport.to_discord_embed()
        """
        if not self.is_configured():
            return False

        try:
            import httpx

            # Use digest thread if configured, otherwise fall back to "Other" thread
            digest_thread_id = getattr(settings, 'DISCORD_THREAD_DIGEST', None)
            thread_id = digest_thread_id or self.category_threads.get("Other") or self.thread_id

            url = self.webhook_url
            if thread_id:
                url = f"{self.webhook_url}?thread_id={thread_id}"

            async with httpx.AsyncClient() as client:
                r = await client.post(url, json=payload, timeout=10.0)

                if r.status_code in [200, 204]:
                    logger.info("📊 Discord digest sent")
                    return True

                # Handle forum channel error
                if r.status_code == 400:
                    try:
                        error_data = r.json()
                        if error_data.get("code") == 220001:
                            # Forum channel requires thread_name
                            payload["thread_name"] = "📊 Daily Digest"
                            r2 = await client.post(self.webhook_url, json=payload, timeout=10.0)
                            if r2.status_code in [200, 204]:
                                logger.info("📊 Discord digest sent (new thread)")
                                return True
                    except Exception:
                        pass
                logger.error(f"Discord digest error: {r.status_code} - {r.text}")

        except Exception as e:
            logger.error(f"Discord digest error: {e}")
        return False

    def is_configured(self) -> bool: return bool(self.webhook_url)


class TelegramAlert(AlertChannel):
    """
    Telegram bot
    
    Setup:
    1. Message @BotFather, send /newbot, get token
    2. Start chat with your bot
    3. Get chat ID: visit https://api.telegram.org/bot<TOKEN>/getUpdates
    4. Add to .env: TELEGRAM_BOT_TOKEN=123:ABC and TELEGRAM_CHAT_ID=12345
    """
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.chat_id = chat_id or getattr(settings, 'TELEGRAM_CHAT_ID', None)
    
    @property
    def name(self) -> str: return "Telegram"
    
    async def send(self, alert: AlertMessage) -> bool:
        if not self.is_configured(): return False
        try:
            import httpx
            emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(alert.severity, "⚪")
            market = f"\n📊 <b>Market:</b> {alert.market_question[:60]}..." if alert.market_question else ""
            text = f"""{emoji} <b>{alert.title}</b>

{alert.message}{market}

💰 <b>Amount:</b> ${alert.trade_amount:,.2f}
🎯 <b>Outcome:</b> {alert.outcome}
👤 <b>Trader:</b> <code>{alert.trader_address[:25]}...</code>
⏰ {alert.timestamp.strftime('%H:%M:%S UTC')}"""
            
            async with httpx.AsyncClient() as client:
                r = await client.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}, timeout=10.0)
                if r.status_code == 200:
                    logger.info("📱 Telegram alert sent")
                    return True
        except Exception as e: logger.error(f"Telegram error: {e}")
        return False
    
    def is_configured(self) -> bool: return bool(self.bot_token and self.chat_id)


class SlackAlert(AlertChannel):
    """
    Slack webhook
    
    Setup:
    1. Go to https://api.slack.com/apps → Create New App
    2. Add Incoming Webhooks → Activate → Add to Workspace
    3. Copy webhook URL
    4. Add to .env: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
    """
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or getattr(settings, 'SLACK_WEBHOOK_URL', None)
    
    @property
    def name(self) -> str: return "Slack"
    
    async def send(self, alert: AlertMessage) -> bool:
        if not self.is_configured(): return False
        try:
            import httpx
            emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(alert.severity, "⚪")
            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": f"🐋 {alert.title}", "emoji": True}},
                {"type": "section", "text": {"type": "mrkdwn", "text": alert.message}},
                {"type": "divider"},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*💰 Amount*\n${alert.trade_amount:,.2f}"},
                    {"type": "mrkdwn", "text": f"*🎯 Outcome*\n{alert.outcome}"},
                    {"type": "mrkdwn", "text": f"*{emoji} Severity*\n{alert.severity}"},
                    {"type": "mrkdwn", "text": f"*👤 Trader*\n`{alert.trader_address[:15]}...`"}]}
            ]
            async with httpx.AsyncClient() as client:
                r = await client.post(self.webhook_url, json={"blocks": blocks}, timeout=10.0)
                if r.status_code == 200:
                    logger.info("💬 Slack alert sent")
                    return True
        except Exception as e: logger.error(f"Slack error: {e}")
        return False
    
    def is_configured(self) -> bool: return bool(self.webhook_url)


class ExpoPushAlert(AlertChannel):
    """
    Mobile push via Expo (for React Native apps)
    
    Setup: Get push tokens from your mobile app, add them with add_token()
    """
    def __init__(self, push_tokens: List[str] = None):
        self.push_tokens = push_tokens or []
    
    @property
    def name(self) -> str: return "Push"
    
    def add_token(self, token: str):
        if token and token not in self.push_tokens:
            self.push_tokens.append(token)
    
    async def send(self, alert: AlertMessage) -> bool:
        if not self.is_configured(): return False
        try:
            import httpx
            messages = [{"to": t, "title": f"🐋 {alert.title}",
                        "body": f"${alert.trade_amount:,.0f} {alert.outcome}", "data": alert.to_dict(),
                        "sound": "default", "priority": "high" if alert.severity == "HIGH" else "default"
                        } for t in self.push_tokens]
            async with httpx.AsyncClient() as client:
                r = await client.post("https://exp.host/--/api/v2/push/send", json=messages, timeout=10.0)
                if r.status_code == 200:
                    logger.info(f"📲 Push sent to {len(messages)} devices")
                    return True
        except Exception as e: logger.error(f"Push error: {e}")
        return False
    
    def is_configured(self) -> bool: return len(self.push_tokens) > 0


class TwitterFormatter:
    """
    Formats alerts into tweet-ready text with hashtags.

    - Keeps tweets under 280 characters
    - Includes evergreen tags (#PredictionMarkets #WhaleAlert)
    - Adds relevant category/topic tags
    """

    # Evergreen hashtags (always included)
    EVERGREEN_TAGS = ["#PredictionMarkets", "#WhaleAlert"]

    # Category-specific hashtags
    CATEGORY_TAGS = {
        "Politics": ["#Politics", "#Election"],
        "Crypto": ["#Crypto", "#Bitcoin", "#Ethereum"],
        "Finance": ["#Stocks", "#Finance", "#Markets"],
        "Entertainment": ["#Entertainment", "#Showbiz"],
        "World": ["#WorldNews", "#Geopolitics"],
        "Sports": ["#Sports", "#Betting"],
        "Other": [],
    }

    # Topic-specific hashtags (matched against market question)
    TOPIC_TAGS = {
        "trump": "#Trump",
        "biden": "#Biden",
        "elon": "#Elon",
        "musk": "#Musk",
        "tesla": "#Tesla",
        "spacex": "#SpaceX",
        "bitcoin": "#BTC",
        "ethereum": "#ETH",
        "fed": "#FederalReserve",
        "inflation": "#Inflation",
        "ai": "#AI",
        "openai": "#OpenAI",
        "chatgpt": "#ChatGPT",
        "apple": "#Apple",
        "google": "#Google",
        "meta": "#Meta",
        "amazon": "#Amazon",
        "microsoft": "#Microsoft",
        "nvidia": "#NVIDIA",
        "ukraine": "#Ukraine",
        "russia": "#Russia",
        "china": "#China",
        "congress": "#Congress",
        "senate": "#Senate",
        "supreme court": "#SCOTUS",
        "oscar": "#Oscars",
        "grammy": "#Grammys",
        "super bowl": "#SuperBowl",
    }

    @classmethod
    def get_hashtags(cls, alert: AlertMessage) -> str:
        """Generate relevant hashtags for an alert (for copy/paste)."""
        tags = list(cls.EVERGREEN_TAGS)

        # Add category tags (up to 2)
        cat_tags = cls.CATEGORY_TAGS.get(alert.category, [])
        tags.extend(cat_tags[:2])

        # Add topic tags based on market question (up to 3)
        market = (alert.market_question or "").lower()
        topic_tags_added = 0
        for keyword, tag in cls.TOPIC_TAGS.items():
            if keyword in market and tag not in tags:
                tags.append(tag)
                topic_tags_added += 1
                if topic_tags_added >= 3:
                    break

        return " ".join(tags)

    @classmethod
    def format_tweet(cls, alert: AlertMessage) -> str:
        """Generate a tweet-ready string from an alert."""
        # Build the main tweet content
        amount_str = f"${alert.trade_amount:,.0f}"

        # Shorten market question if needed
        market = alert.market_question or "Unknown Market"
        if len(market) > 100:
            market = market[:97] + "..."

        # Position info
        action = alert.side.capitalize() if alert.side else "Trade"
        outcome = alert.outcome

        # Alert type summary
        if len(alert.alert_types) > 1:
            type_summary = f"{len(alert.alert_types)} signals"
        else:
            type_summary = alert.alert_types[0].replace('_', ' ').title()

        # Build main content
        main_content = f"🐋 {amount_str} {action} {outcome}\n\n📊 {market}\n\n🔔 {type_summary}"

        # Collect hashtags
        tags = list(cls.EVERGREEN_TAGS)

        # Add category tags
        cat_tags = cls.CATEGORY_TAGS.get(alert.category, [])
        tags.extend(cat_tags[:2])  # Max 2 category tags

        # Add topic tags (check market question for keywords)
        market_lower = market.lower()
        topic_tags_added = 0
        for keyword, tag in cls.TOPIC_TAGS.items():
            if keyword in market_lower and tag not in tags:
                tags.append(tag)
                topic_tags_added += 1
                if topic_tags_added >= 2:  # Max 2 topic tags
                    break

        # Build final tweet, ensuring under 280 chars
        tags_str = " ".join(tags)
        tweet = f"{main_content}\n\n{tags_str}"

        # Truncate if needed (shouldn't happen with our limits)
        if len(tweet) > 280:
            # Remove topic tags first, then category tags
            while len(tweet) > 280 and len(tags) > 2:
                tags.pop()
                tags_str = " ".join(tags)
                tweet = f"{main_content}\n\n{tags_str}"

            # If still too long, truncate market question
            if len(tweet) > 280:
                excess = len(tweet) - 277
                market = market[:len(market) - excess - 3] + "..."
                main_content = f"🐋 {amount_str} {action} {outcome}\n\n📊 {market}\n\n🔔 {type_summary}"
                tweet = f"{main_content}\n\n{tags_str}"

        return tweet

    @classmethod
    def is_twitter_worthy(cls, alert: AlertMessage, min_amount: float = 1000.0) -> bool:
        """
        Determine if an alert is truly exceptional and worthy of the Twitter highlight reel.

        STRICT criteria - must be genuinely noteworthy:
        1. $10,000+ trades (true whale territory)
        2. $1,000+ with multi-trade patterns (REPEAT_ACTOR, HEAVY_ACTOR, CLUSTER_ACTIVITY)
        3. $5,000+ with SMART_MONEY (proven winners making significant bets)
        4. $5,000+ with NEW_WALLET (first-time whale - rare and interesting)
        5. 4+ simultaneous triggers (highly unusual activity)
        """
        amount = alert.trade_amount
        types = set(alert.alert_types)

        # Tier 1: True whales ($10k+) always noteworthy
        if amount >= 10_000:
            return True

        # Tier 2: Multi-trade patterns at $1k+ (coordinated/repeat activity)
        multi_trade_types = {"REPEAT_ACTOR", "HEAVY_ACTOR", "CLUSTER_ACTIVITY"}
        if amount >= 1_000 and types & multi_trade_types:
            return True

        # Tier 3: Smart money or new whales at $5k+ (quality signals)
        quality_types = {"SMART_MONEY", "NEW_WALLET", "VIP_WALLET"}
        if amount >= 5_000 and types & quality_types:
            return True

        # Tier 4: Highly unusual activity (4+ triggers at once)
        if len(types) >= 4:
            return True

        return False


class TwitterQueueAlert(AlertChannel):
    """
    Sends truly exceptional alerts to a private Discord channel for manual posting to X.

    Features:
    - STRICT filtering: Only the most noteworthy alerts make it through
      - $10k+ whale trades
      - $1k+ multi-trade patterns (repeat/heavy actors, clusters)
      - $5k+ smart money or new wallet whales
      - 4+ simultaneous triggers
    - Posts to a private #for-twitter Discord channel
    - Rate limits to 20/hour as safety net (criteria should naturally limit)

    Setup:
    1. Create private Discord text channel called #for-twitter
    2. Create webhook in that channel
    3. Set DISCORD_TWITTER_WEBHOOK_URL in environment
    """

    def __init__(self, webhook_url: str = None, min_amount: float = None, max_per_hour: int = None):
        self.webhook_url = webhook_url or getattr(settings, 'DISCORD_TWITTER_WEBHOOK_URL', None)
        self.min_amount = min_amount or getattr(settings, 'TWITTER_MIN_AMOUNT', 1000.0)
        self.max_per_hour = max_per_hour or getattr(settings, 'TWITTER_MAX_PER_HOUR', 20)
        self._recent_posts: List[datetime] = []

    @property
    def name(self) -> str:
        return "TwitterQueue"

    def _check_rate_limit(self) -> bool:
        """Check if we're under the hourly rate limit."""
        now = datetime.now()
        one_hour_ago = now.replace(hour=now.hour - 1 if now.hour > 0 else 23)

        # Clean up old entries
        self._recent_posts = [t for t in self._recent_posts if t > one_hour_ago]

        return len(self._recent_posts) < self.max_per_hour

    async def send(self, alert: AlertMessage) -> bool:
        """Send full alert to Twitter queue channel (same format as main Discord alerts)."""
        if not self.is_configured():
            return False

        # Check if alert is Twitter-worthy
        if not TwitterFormatter.is_twitter_worthy(alert, self.min_amount):
            logger.debug(f"Alert not Twitter-worthy: ${alert.trade_amount:.0f} {alert.severity}")
            return True  # Return True to not count as failure

        # Check rate limit
        if not self._check_rate_limit():
            logger.warning(f"Twitter queue rate limit reached ({self.max_per_hour}/hour)")
            return True  # Return True to not count as failure

        try:
            import httpx

            # Use the SAME format as main Discord alerts
            color = {"LOW": 0x4CAF50, "MEDIUM": 0xFFC107, "HIGH": 0xF44336}.get(alert.severity, 0x9E9E9E)

            # Format action with position intent
            action = alert.side.capitalize() if alert.side else "Traded"
            action_emoji = {
                "OPENING": "🆕",
                "ADDING": "➕",
                "CLOSING": "🔚",
            }.get(alert.position_action, "")
            position_text = f"{action} **{alert.outcome}**\n{action_emoji} {alert.position_action}"

            # Severity with explanation
            severity_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(alert.severity, "⚪")
            severity_explanation = SEVERITY_INFO.get(alert.severity, "")
            severity_text = f"{severity_emoji} {alert.severity}"
            if severity_explanation:
                severity_text += f"\n_{severity_explanation}_"

            # Market with link
            market_text = alert.market_question or "Unknown Market"
            if alert.market_url:
                market_text = f"[{market_text}]({alert.market_url})"

            # Trader with link (handle anonymous)
            is_anonymous = alert.trader_address.startswith("KALSHI_") or alert.trader_address == "UNKNOWN"
            if is_anonymous:
                trader_text = "_Anonymous (platform doesn't expose trader identity)_"
            elif alert.trader_url:
                trader_short = f"{alert.trader_address[:20]}..."
                trader_text = f"[`{trader_short}`]({alert.trader_url})"
            else:
                trader_short = f"{alert.trader_address[:20]}..."
                trader_text = f"`{trader_short}`"

            # Category emoji
            category_emoji = {
                "Politics": "🏛️", "Crypto": "₿", "Sports": "⚽", "Finance": "📈",
                "Entertainment": "🎬", "Science": "🔬", "World": "🌍", "Other": "📌",
            }.get(alert.category, "📌")

            # Format consolidated reasons
            if len(alert.messages) > 1:
                reasons_text = "\n".join(f"• {msg}" for msg in alert.messages)
                trigger_badges = " ".join(f"`{t.replace('_', ' ')}`" for t in alert.alert_types)
                description = f"**🔔 Triggered:** {trigger_badges}\n\n{reasons_text}"
            else:
                description = alert.messages[0] if alert.messages else ""

            # Generate hashtags for footer
            hashtags = TwitterFormatter.get_hashtags(alert)

            # Build fields - same as main Discord alerts
            fields = [
                {"name": "📊 Market", "value": market_text, "inline": False},
                {"name": f"{category_emoji} Category", "value": alert.category, "inline": True},
                {"name": "🏦 Platform", "value": alert.platform, "inline": True},
                {"name": "💰 Amount", "value": f"${alert.trade_amount:,.2f}", "inline": True},
                {"name": "🎯 Position", "value": position_text, "inline": True},
                {"name": "⚡ Severity", "value": severity_text, "inline": False},
                {"name": "👤 Trader", "value": trader_text, "inline": False},
            ]

            payload = {
                "embeds": [{
                    "title": f"🐋 {alert.title}",
                    "description": description,
                    "color": color,
                    "fields": fields,
                    "timestamp": alert.timestamp.isoformat(),
                    "footer": {"text": hashtags}
                }],
                "username": "Whale Tracker"
            }

            async with httpx.AsyncClient() as client:
                r = await client.post(self.webhook_url, json=payload, timeout=10.0)

                if r.status_code in [200, 204]:
                    self._recent_posts.append(datetime.now())
                    logger.info(f"🐦 Tweet queued: ${alert.trade_amount:,.0f}")
                    return True
                else:
                    logger.error(f"Twitter queue error: {r.status_code} - {r.text}")
                    return False

        except Exception as e:
            logger.error(f"Twitter queue error: {e}")
            return False

    def is_configured(self) -> bool:
        return bool(self.webhook_url)


class Alerter:
    """Main alerter managing all channels."""
    
    def __init__(self):
        self.channels: List[AlertChannel] = []
        self.expo_push = ExpoPushAlert()  # Keep reference for adding tokens
    
    def add_channel(self, channel: AlertChannel):
        if channel.is_configured():
            self.channels.append(channel)
            logger.info(f"✅ Alert channel added: {channel.name}")
    
    def add_push_token(self, token: str):
        """Add a mobile device for push notifications."""
        self.expo_push.add_token(token)
        if self.expo_push not in self.channels and self.expo_push.is_configured():
            self.channels.append(self.expo_push)
    
    def get_channels(self) -> List[str]:
        return [c.name for c in self.channels]
    
    async def send_alert(self, whale_alert, market_question: str = None, market_url: str = None, category: str = None) -> Dict[str, bool]:
        # Get market question - use passed value, alert value, or fallback
        mkt_question = market_question or getattr(whale_alert, 'market_question', None)
        if not mkt_question:
            mkt_question = f"Market {whale_alert.trade.market_id[:12]}..."  # Fallback

        # Get platform from trade (defaults to Polymarket)
        platform = getattr(whale_alert.trade, 'platform', 'Polymarket')

        # Get market URL and category
        mkt_url = market_url or getattr(whale_alert, 'market_url', None)
        mkt_category = category or getattr(whale_alert, 'category', 'Other')

        # Get trader URL from trade (platform-aware)
        trader_url = getattr(whale_alert.trade, 'trader_url', None)
        if not trader_url and whale_alert.trade.trader_address:
            # Generate platform-specific trader URL
            trader_addr = whale_alert.trade.trader_address
            if trader_addr.startswith("KALSHI_") or trader_addr == "UNKNOWN":
                trader_url = None  # Kalshi doesn't expose trader profiles
            elif platform == "Polymarket":
                trader_url = f"https://polymarket.com/profile/{trader_addr}"
            elif platform == "Kalshi":
                trader_url = None  # Kalshi doesn't expose trader profiles
            else:
                trader_url = None  # Unknown platform

        # Handle both old single-type and new consolidated multi-type alerts
        alert_types = getattr(whale_alert, 'alert_types', None)
        if alert_types is None:
            # Old format - single alert_type
            alert_types = [whale_alert.alert_type]

        messages = getattr(whale_alert, 'messages', None)
        if messages is None:
            # Old format - single message
            messages = [whale_alert.message]

        # Generate title based on number of triggers
        if len(alert_types) == 1:
            title = alert_types[0].replace('_', ' ').title()
        else:
            # Multiple triggers - show count
            title = f"Multi-Signal Alert ({len(alert_types)} triggers)"

        message = AlertMessage(
            title=title,
            messages=messages,
            severity=whale_alert.severity,
            alert_types=alert_types,
            trade_amount=whale_alert.trade.amount_usd,
            trader_address=whale_alert.trade.trader_address,
            market_id=whale_alert.trade.market_id,
            market_question=mkt_question,
            outcome=whale_alert.trade.outcome,
            timestamp=whale_alert.timestamp,
            platform=platform,
            side=whale_alert.trade.side,
            category=mkt_category,
            market_url=mkt_url,
            trader_url=trader_url,
            position_action=getattr(whale_alert, 'position_action', 'OPENING'),
        )
        
        results = {}
        for channel in self.channels:
            try:
                results[channel.name] = await channel.send(message)
            except Exception as e:
                logger.error(f"Error in {channel.name}: {e}")
                results[channel.name] = False
        
        success = sum(1 for v in results.values() if v)
        logger.info(f"📢 Alert sent to {success}/{len(self.channels)} channels")
        return results

    async def send_digest(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        to_email: str = None
    ) -> bool:
        """
        Send a digest email via the Email channel.

        Args:
            subject: Email subject line
            html_content: HTML body of the email
            text_content: Plain text fallback
            to_email: Override recipient (uses ALERT_EMAIL if not provided)

        Returns:
            True if sent successfully, False otherwise
        """
        # Find the email channel
        email_channel = None
        for channel in self.channels:
            if channel.name == "Email":
                email_channel = channel
                break

        if not email_channel or not email_channel.is_configured():
            logger.warning("Email channel not configured, skipping digest")
            return False

        try:
            import httpx
            recipient = to_email or email_channel.to_email

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {email_channel.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from": settings.FROM_EMAIL,
                        "to": [recipient],
                        "subject": subject,
                        "html": html_content,
                        "text": text_content,
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    logger.info(f"📧 Digest email sent to {recipient}")
                    return True
                else:
                    logger.error(f"Digest email failed: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Error sending digest email: {e}")
            return False

    async def send_message(
        self,
        message: str,
        channels: List[str] = None
    ) -> Dict[str, bool]:
        """
        Send a plain text message to specified channels (for system alerts, not whale alerts).

        Args:
            message: The message text to send
            channels: List of channel names to send to (e.g., ['discord', 'email'])
                     If None, sends to all channels

        Returns:
            Dict mapping channel name to success boolean
        """
        results = {}

        for channel in self.channels:
            # Filter by requested channels if specified
            if channels and channel.name.lower() not in [c.lower() for c in channels]:
                continue

            try:
                # Only send to Discord for system messages (no email spam)
                if channel.name == "Discord":
                    import httpx
                    async with httpx.AsyncClient() as client:
                        # Format message for Discord
                        payload = {
                            "content": message
                        }

                        # Add thread_id if this is a Discord channel with thread routing
                        webhook_url = channel.webhook_url
                        if hasattr(channel, 'thread_id') and channel.thread_id:
                            webhook_url = f"{webhook_url}?thread_id={channel.thread_id}"

                        response = await client.post(
                            webhook_url,
                            json=payload,
                            timeout=10.0
                        )

                        if response.status_code == 204:
                            results[channel.name] = True
                        else:
                            logger.error(f"Discord message failed: {response.status_code}")
                            results[channel.name] = False

            except Exception as e:
                logger.error(f"Error sending message to {channel.name}: {e}")
                results[channel.name] = False

        success = sum(1 for v in results.values() if v)
        logger.info(f"📢 Message sent to {success}/{len(results)} requested channels")
        return results


def create_default_alerter() -> Alerter:
    """Create alerter with all configured channels."""
    alerter = Alerter()
    alerter.add_channel(ConsoleAlert())
    alerter.add_channel(EmailAlert())
    alerter.add_channel(DiscordAlert())
    alerter.add_channel(TelegramAlert())
    alerter.add_channel(SlackAlert())
    alerter.add_channel(TwitterQueueAlert())  # Twitter queue for high-value alerts
    return alerter
