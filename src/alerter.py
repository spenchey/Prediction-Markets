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


@dataclass
class AlertMessage:
    """Standardized alert message for any channel."""
    title: str
    message: str
    severity: str
    alert_type: str
    trade_amount: float
    trader_address: str
    market_id: str
    market_question: Optional[str]
    outcome: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "alert_type": self.alert_type,
            "trade_amount": self.trade_amount,
            "trader_address": self.trader_address,
            "market_id": self.market_id,
            "market_question": self.market_question,
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_plain_text(self) -> str:
        market_info = f"\n📊 Market: {self.market_question[:50]}..." if self.market_question else ""
        return f"""🚨 {self.title}

{self.message}{market_info}

💰 Amount: ${self.trade_amount:,.2f}
🎯 Outcome: {self.outcome}
👤 Trader: {self.trader_address[:15]}...
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

    If webhook points to a forum channel and neither is set, uses alert title as thread name.
    """
    def __init__(self, webhook_url: str = None, thread_id: str = None, thread_name: str = None):
        self.webhook_url = webhook_url or getattr(settings, 'DISCORD_WEBHOOK_URL', None)
        self.thread_id = thread_id or getattr(settings, 'DISCORD_THREAD_ID', None)
        self.thread_name = thread_name or getattr(settings, 'DISCORD_THREAD_NAME', None)
        self._is_forum_channel = None  # Will be detected on first send

    @property
    def name(self) -> str: return "Discord"

    async def send(self, alert: AlertMessage) -> bool:
        if not self.is_configured(): return False
        try:
            import httpx
            color = {"LOW": 0x4CAF50, "MEDIUM": 0xFFC107, "HIGH": 0xF44336}.get(alert.severity, 0x9E9E9E)
            fields = [
                {"name": "💰 Amount", "value": f"${alert.trade_amount:,.2f}", "inline": True},
                {"name": "🎯 Outcome", "value": alert.outcome, "inline": True},
                {"name": "⚡ Severity", "value": alert.severity, "inline": True},
                {"name": "👤 Trader", "value": f"`{alert.trader_address[:25]}...`", "inline": False},
            ]
            if alert.market_question:
                fields.insert(0, {"name": "📊 Market", "value": alert.market_question[:100], "inline": False})

            payload = {
                "embeds": [{
                    "title": f"🐋 {alert.title}",
                    "description": alert.message,
                    "color": color,
                    "fields": fields,
                    "timestamp": alert.timestamp.isoformat(),
                    "footer": {"text": "Whale Tracker"}
                }],
                "username": "Whale Tracker"
            }

            # Add forum channel support
            if self.thread_id:
                # Post to existing thread
                payload["thread_id"] = self.thread_id
            elif self.thread_name:
                # Create new thread with configured name
                payload["thread_name"] = self.thread_name

            async with httpx.AsyncClient() as client:
                r = await client.post(self.webhook_url, json=payload, timeout=10.0)

                if r.status_code in [200, 204]:
                    logger.info("🎮 Discord alert sent")
                    return True

                # Check if this is a forum channel error
                if r.status_code == 400:
                    try:
                        error_data = r.json()
                        if error_data.get("code") == 220001:
                            # Forum channel requires thread_name or thread_id
                            logger.warning("Discord webhook is a forum channel, retrying with thread_name")
                            self._is_forum_channel = True

                            # Retry with thread_name based on alert
                            thread_title = f"${alert.trade_amount:,.0f} {alert.alert_type.replace('_', ' ').title()}"
                            payload["thread_name"] = thread_title[:100]  # Discord limit

                            r2 = await client.post(self.webhook_url, json=payload, timeout=10.0)
                            if r2.status_code in [200, 204]:
                                logger.info(f"🎮 Discord alert sent (new thread: {thread_title})")
                                return True
                            else:
                                logger.error(f"Discord retry failed: {r2.status_code} - {r2.text}")
                        else:
                            logger.error(f"Discord error: {r.status_code} - {r.text}")
                    except Exception as parse_err:
                        logger.error(f"Discord error: {r.status_code} - {r.text}")
                else:
                    logger.error(f"Discord error: {r.status_code} - {r.text}")

        except Exception as e:
            logger.error(f"Discord error: {e}")
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
    
    async def send_alert(self, whale_alert, market_question: str = None) -> Dict[str, bool]:
        message = AlertMessage(
            title=whale_alert.alert_type.replace('_', ' ').title(),
            message=whale_alert.message,
            severity=whale_alert.severity,
            alert_type=whale_alert.alert_type,
            trade_amount=whale_alert.trade.amount_usd,
            trader_address=whale_alert.trade.trader_address,
            market_id=whale_alert.trade.market_id,
            market_question=market_question or getattr(whale_alert, 'market_question', None),
            outcome=whale_alert.trade.outcome,
            timestamp=whale_alert.timestamp
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


def create_default_alerter() -> Alerter:
    """Create alerter with all configured channels."""
    alerter = Alerter()
    alerter.add_channel(ConsoleAlert())
    alerter.add_channel(EmailAlert())
    alerter.add_channel(DiscordAlert())
    alerter.add_channel(TelegramAlert())
    alerter.add_channel(SlackAlert())
    return alerter
