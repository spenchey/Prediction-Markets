"""
Scheduler Module - Email Digests & Automated Reports

Provides scheduled email reports for subscribers:
- Daily digest: Summary of all alerts from the past 24 hours
- Weekly digest: Performance report with top wallets, trends
- Instant alerts: Real-time notifications (handled by alerter.py)

Uses APScheduler for job scheduling.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from loguru import logger

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    logger.warning("APScheduler not installed. Scheduled digests disabled.")

from .config import settings


@dataclass
class DigestReport:
    """A compiled digest report for email."""
    report_type: str  # "daily" or "weekly"
    period_start: datetime
    period_end: datetime
    total_alerts: int
    alerts_by_type: Dict[str, int]
    total_volume_tracked: float
    top_trades: List[Dict]
    top_wallets: List[Dict]
    smart_money_activity: List[Dict]
    new_wallets_of_interest: List[Dict]

    def to_html(self) -> str:
        """Generate modern HTML email content (Robinhood/Coinbase style)."""
        period_label = "Daily" if self.report_type == "daily" else "Weekly"

        # Generate top trades cards
        trade_cards = ""
        for i, trade in enumerate(self.top_trades[:5]):
            amount = trade.get('amount', 0)
            market = (trade.get('market') or 'Unknown Market')[:80]
            outcome = trade.get('outcome', 'N/A')
            wallet = (trade.get('wallet') or '')[:12]

            trade_cards += f"""
            <div style="background: #ffffff; border-radius: 12px; padding: 20px; margin-bottom: 12px; border: 1px solid #e5e7eb;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="vertical-align: top; padding: 0;">
                            <div style="font-size: 13px; color: #6b7280; margin-bottom: 4px;">#{i+1} Trade</div>
                            <div style="font-size: 15px; font-weight: 600; color: #1a1a1a; margin-bottom: 8px; line-height: 1.4;">{market}</div>
                            <div style="font-size: 13px; color: #6b7280;">
                                <span style="background: #f3f4f6; padding: 4px 8px; border-radius: 4px; display: inline-block;">{outcome}</span>
                                <span style="margin-left: 8px;">by {wallet}...</span>
                            </div>
                        </td>
                        <td style="vertical-align: top; text-align: right; padding: 0; width: 120px;">
                            <div style="font-size: 24px; font-weight: 700; color: #00d395;">${amount:,.0f}</div>
                        </td>
                    </tr>
                </table>
            </div>
            """

        # Generate alert type pills
        type_pills = ""
        for alert_type, count in sorted(self.alerts_by_type.items(), key=lambda x: x[1], reverse=True):
            formatted_type = alert_type.replace('_', ' ').title()
            type_pills += f"""<span style="display: inline-block; background: #f3f4f6; padding: 8px 16px; border-radius: 20px; margin: 4px; font-size: 13px; color: #374151;">{formatted_type}: <strong>{count}</strong></span>"""

        # Format dates
        date_range = f"{self.period_start.strftime('%b %d')} - {self.period_end.strftime('%b %d, %Y')}"

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{period_label} Whale Report</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">

        <!-- Header -->
        <div style="background: #1a1a1a; border-radius: 16px 16px 0 0; padding: 32px 24px; text-align: center;">
            <div style="font-size: 40px; margin-bottom: 8px;">&#128011;</div>
            <h1 style="color: #ffffff; font-size: 24px; font-weight: 700; margin: 0 0 8px 0;">
                {period_label} Whale Report
            </h1>
            <p style="color: #9ca3af; font-size: 14px; margin: 0;">{date_range}</p>
        </div>

        <!-- Stats Summary -->
        <div style="background: #ffffff; padding: 24px; border-left: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">
            <table style="width: 100%; border-collapse: collapse; text-align: center;">
                <tr>
                    <td style="padding: 0 12px; border-right: 1px solid #e5e7eb; width: 33%;">
                        <div style="font-size: 32px; font-weight: 700; color: #1a1a1a;">{self.total_alerts}</div>
                        <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">Alerts</div>
                    </td>
                    <td style="padding: 0 12px; border-right: 1px solid #e5e7eb; width: 33%;">
                        <div style="font-size: 32px; font-weight: 700; color: #00d395;">${self.total_volume_tracked:,.0f}</div>
                        <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">Volume</div>
                    </td>
                    <td style="padding: 0 12px; width: 33%;">
                        <div style="font-size: 32px; font-weight: 700; color: #1a1a1a;">{len(self.smart_money_activity)}</div>
                        <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">Smart Money</div>
                    </td>
                </tr>
            </table>
        </div>

        <!-- Alert Type Breakdown -->
        <div style="background: #ffffff; padding: 24px; border-left: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">
            <h2 style="font-size: 16px; font-weight: 600; color: #1a1a1a; margin: 0 0 16px 0;">
                Alert Breakdown
            </h2>
            <div style="line-height: 2.2;">
                {type_pills if type_pills else '<span style="color: #6b7280;">No alerts this period.</span>'}
            </div>
        </div>

        <!-- Top Trades Section -->
        <div style="background: #f8f9fa; padding: 24px; border-left: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">
            <h2 style="font-size: 16px; font-weight: 600; color: #1a1a1a; margin: 0 0 16px 0;">
                Top Trades
            </h2>
            {trade_cards if trade_cards else '<p style="color: #6b7280;">No significant trades this period.</p>'}
        </div>

        <!-- Smart Money & New Wallets -->
        <div style="background: #ffffff; padding: 24px; border-left: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="width: 48%; padding-right: 12px; vertical-align: top;">
                        <div style="background: #f0fdf4; border-radius: 12px; padding: 20px; text-align: center;">
                            <div style="font-size: 28px; margin-bottom: 8px;">&#129504;</div>
                            <div style="font-size: 24px; font-weight: 700; color: #15803d;">{len(self.smart_money_activity)}</div>
                            <div style="font-size: 13px; color: #166534;">Smart Money Trades</div>
                        </div>
                    </td>
                    <td style="width: 48%; padding-left: 12px; vertical-align: top;">
                        <div style="background: #eff6ff; border-radius: 12px; padding: 20px; text-align: center;">
                            <div style="font-size: 28px; margin-bottom: 8px;">&#127381;</div>
                            <div style="font-size: 24px; font-weight: 700; color: #1d4ed8;">{len(self.new_wallets_of_interest)}</div>
                            <div style="font-size: 13px; color: #1e40af;">New Whale Wallets</div>
                        </div>
                    </td>
                </tr>
            </table>
        </div>

        <!-- Footer -->
        <div style="background: #1a1a1a; border-radius: 0 0 16px 16px; padding: 24px; text-align: center;">
            <p style="color: #9ca3af; font-size: 13px; margin: 0 0 12px 0;">
                Prediction Market Whale Tracker
            </p>
            <div style="font-size: 12px;">
                <a href="#" style="color: #6b7280; text-decoration: none; margin: 0 8px;">Manage Preferences</a>
                <span style="color: #374151;">|</span>
                <a href="#" style="color: #6b7280; text-decoration: none; margin: 0 8px;">Unsubscribe</a>
            </div>
        </div>

    </div>
</body>
</html>
"""

    def to_plain_text(self) -> str:
        """Generate plain text version of the digest."""
        period_label = "Daily" if self.report_type == "daily" else "Weekly"

        lines = [
            f"🐋 {period_label} Whale Report",
            f"{self.period_start.strftime('%b %d')} - {self.period_end.strftime('%b %d, %Y')}",
            "",
            "📊 SUMMARY",
            f"  Total Alerts: {self.total_alerts}",
            f"  Volume Tracked: ${self.total_volume_tracked:,.0f}",
            f"  Smart Money Moves: {len(self.smart_money_activity)}",
            "",
            "🚨 ALERT BREAKDOWN"
        ]

        for alert_type, count in self.alerts_by_type.items():
            lines.append(f"  {alert_type}: {count}")

        lines.extend([
            "",
            "💰 TOP TRADES"
        ])

        for trade in self.top_trades[:5]:
            lines.append(f"  ${trade.get('amount', 0):,.0f} - {trade.get('market', 'Unknown')[:40]}...")

        lines.extend([
            "",
            "🏆 TOP WALLETS"
        ])

        for wallet in self.top_wallets[:5]:
            lines.append(f"  {wallet.get('address', '')[:15]}... - ${wallet.get('volume', 0):,.0f}")

        return "\n".join(lines)

    def to_discord_embed(self) -> Dict[str, Any]:
        """Generate Discord embed payload for the digest."""
        period_label = "Daily" if self.report_type == "daily" else "Weekly"
        date_range = f"{self.period_start.strftime('%b %d')} - {self.period_end.strftime('%b %d, %Y')}"

        # Alert type breakdown
        type_breakdown = "\n".join(
            f"• **{t.replace('_', ' ').title()}**: {c}"
            for t, c in sorted(self.alerts_by_type.items(), key=lambda x: x[1], reverse=True)[:8]
        ) or "No alerts"

        # Top trades
        top_trades_text = ""
        for i, trade in enumerate(self.top_trades[:5]):
            amount = trade.get('amount', 0)
            market = (trade.get('market') or 'Unknown')[:50]
            outcome = trade.get('outcome', 'N/A')
            top_trades_text += f"**{i+1}.** ${amount:,.0f} - {market}... ({outcome})\n"
        top_trades_text = top_trades_text or "No significant trades"

        # Top wallets
        top_wallets_text = ""
        for wallet in self.top_wallets[:5]:
            addr = wallet.get('address', '')[:12]
            vol = wallet.get('volume', 0)
            win_rate = wallet.get('win_rate')
            wr_text = f" ({win_rate:.0%} WR)" if win_rate else ""
            top_wallets_text += f"• `{addr}...` - ${vol:,.0f}{wr_text}\n"
        top_wallets_text = top_wallets_text or "No wallet data"

        # Color based on volume
        if self.total_volume_tracked >= 100000:
            color = 0x00d395  # Green - high volume
        elif self.total_volume_tracked >= 50000:
            color = 0xffa500  # Orange - medium volume
        else:
            color = 0x5865F2  # Discord blue - normal

        return {
            "embeds": [{
                "title": f"🐋 {period_label} Whale Report",
                "description": f"**{date_range}**\n\nSummary of whale activity over the past {'24 hours' if self.report_type == 'daily' else 'week'}.",
                "color": color,
                "fields": [
                    {
                        "name": "📊 Summary",
                        "value": f"**{self.total_alerts}** Alerts\n**${self.total_volume_tracked:,.0f}** Volume\n**{len(self.smart_money_activity)}** Smart Money",
                        "inline": True
                    },
                    {
                        "name": "🆕 New Whales",
                        "value": f"**{len(self.new_wallets_of_interest)}** wallets",
                        "inline": True
                    },
                    {
                        "name": "🚨 Alert Breakdown",
                        "value": type_breakdown,
                        "inline": False
                    },
                    {
                        "name": "💰 Top Trades",
                        "value": top_trades_text,
                        "inline": False
                    },
                    {
                        "name": "🏆 Top Wallets",
                        "value": top_wallets_text,
                        "inline": False
                    }
                ],
                "footer": {"text": f"Whale Tracker • {period_label} Digest"},
                "timestamp": self.period_end.isoformat()
            }],
            "username": "Whale Tracker"
        }


class DigestScheduler:
    """
    Manages scheduled email digests.

    Usage:
        scheduler = DigestScheduler(alerter, detector, db)
        scheduler.start()  # Start scheduled jobs

        # Manual triggers
        await scheduler.send_daily_digest()
        await scheduler.send_weekly_digest()
    """

    def __init__(
        self,
        alerter,  # Alerter instance for sending emails
        detector,  # WhaleDetector for wallet stats
        database,  # Database for alert history
        daily_hour: int = 8,  # Send daily digest at 8 AM
        weekly_day: str = "mon",  # Send weekly digest on Monday
        weekly_hour: int = 9,  # Send weekly digest at 9 AM
        timezone: str = "UTC"
    ):
        self.alerter = alerter
        self.detector = detector
        self.database = database
        self.daily_hour = daily_hour
        self.weekly_day = weekly_day
        self.weekly_hour = weekly_hour
        self.timezone = timezone

        self._scheduler: Optional[Any] = None
        self._running = False

        # Store recent alerts in memory for digest compilation
        self.recent_alerts: List[Dict] = []
        self.max_stored_alerts = 10000

    def add_alert(self, alert):
        """Add an alert to the digest queue."""
        self.recent_alerts.append(alert.to_dict())
        if len(self.recent_alerts) > self.max_stored_alerts:
            self.recent_alerts = self.recent_alerts[-self.max_stored_alerts:]

    def start(self):
        """Start the scheduler with daily and weekly digest jobs."""
        if not HAS_APSCHEDULER:
            logger.warning("APScheduler not available. Digests must be triggered manually.")
            return

        self._scheduler = AsyncIOScheduler(timezone=self.timezone)

        # Daily digest at specified hour
        self._scheduler.add_job(
            self._run_daily_digest,
            CronTrigger(hour=self.daily_hour, minute=0),
            id="daily_digest",
            name="Daily Whale Digest"
        )

        # Weekly digest on specified day and hour
        self._scheduler.add_job(
            self._run_weekly_digest,
            CronTrigger(day_of_week=self.weekly_day, hour=self.weekly_hour, minute=0),
            id="weekly_digest",
            name="Weekly Whale Digest"
        )

        self._scheduler.start()
        self._running = True
        logger.info(f"📅 Digest scheduler started")
        logger.info(f"   Daily digest: {self.daily_hour}:00 {self.timezone}")
        logger.info(f"   Weekly digest: {self.weekly_day.upper()} {self.weekly_hour}:00 {self.timezone}")

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown()
            self._running = False
            logger.info("📅 Digest scheduler stopped")

    async def _run_daily_digest(self):
        """Internal wrapper for async daily digest."""
        try:
            await self.send_daily_digest()
        except Exception as e:
            logger.error(f"Error sending daily digest: {e}")

    async def _run_weekly_digest(self):
        """Internal wrapper for async weekly digest."""
        try:
            await self.send_weekly_digest()
        except Exception as e:
            logger.error(f"Error sending weekly digest: {e}")

    def _compile_digest(self, hours_back: int) -> DigestReport:
        """Compile a digest report from recent alerts."""
        cutoff = datetime.now() - timedelta(hours=hours_back)

        # Filter alerts within time period
        period_alerts = [
            a for a in self.recent_alerts
            if datetime.fromisoformat(a.get('timestamp', '')) > cutoff
        ]

        # Count by type
        alerts_by_type: Dict[str, int] = {}
        for alert in period_alerts:
            alert_type = alert.get('alert_type', 'UNKNOWN')
            alerts_by_type[alert_type] = alerts_by_type.get(alert_type, 0) + 1

        # Calculate total volume
        total_volume = sum(a.get('trade_amount_usd', 0) for a in period_alerts)

        # Get top trades
        top_trades = sorted(period_alerts, key=lambda x: x.get('trade_amount_usd', 0), reverse=True)[:10]
        top_trades_formatted = [
            {
                "amount": t.get('trade_amount_usd', 0),
                "market": t.get('market_question', 'Unknown'),
                "outcome": t.get('outcome', 'N/A'),
                "wallet": t.get('trader_address', '')
            }
            for t in top_trades
        ]

        # Get top wallets from detector
        top_wallets = []
        if self.detector:
            for profile in self.detector.get_top_wallets(10, non_sports_only=True):
                top_wallets.append({
                    "address": profile.address,
                    "volume": profile.total_volume_usd,
                    "trades": profile.total_trades,
                    "win_rate": profile.win_rate
                })

        # Smart money activity
        smart_money = [a for a in period_alerts if a.get('alert_type') == 'SMART_MONEY']

        # New wallet activity
        new_wallets = [a for a in period_alerts if a.get('alert_type') == 'NEW_WALLET']

        return DigestReport(
            report_type="daily" if hours_back <= 24 else "weekly",
            period_start=cutoff,
            period_end=datetime.now(),
            total_alerts=len(period_alerts),
            alerts_by_type=alerts_by_type,
            total_volume_tracked=total_volume,
            top_trades=top_trades_formatted,
            top_wallets=top_wallets,
            smart_money_activity=smart_money,
            new_wallets_of_interest=new_wallets
        )

    async def _compile_digest_from_db(self, hours_back: int) -> Optional[DigestReport]:
        """
        Compile a digest report from database alerts.

        Falls back to in-memory if database unavailable.
        """
        if not self.database:
            logger.warning("No database available, falling back to in-memory digest")
            return self._compile_digest(hours_back)

        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)

            # Query database for summary
            summary = await self.database.get_digest_summary(start_time, end_time)

            if summary["total_alerts"] == 0:
                return None

            # Get top wallets from detector (still uses in-memory)
            top_wallets = []
            if self.detector:
                for profile in self.detector.get_top_wallets(10, non_sports_only=True):
                    top_wallets.append({
                        "address": profile.address,
                        "volume": profile.total_volume_usd,
                        "trades": profile.total_trades,
                        "win_rate": profile.win_rate
                    })

            # Count smart money and new wallet alerts
            smart_money_count = summary["alerts_by_type"].get("SMART_MONEY", 0)
            new_wallet_count = summary["alerts_by_type"].get("NEW_WALLET", 0)

            return DigestReport(
                report_type="daily" if hours_back <= 24 else "weekly",
                period_start=start_time,
                period_end=end_time,
                total_alerts=summary["total_alerts"],
                alerts_by_type=summary["alerts_by_type"],
                total_volume_tracked=summary["total_volume"],
                top_trades=summary["top_trades"],
                top_wallets=top_wallets,
                smart_money_activity=[{}] * smart_money_count,  # Placeholder for count
                new_wallets_of_interest=[{}] * new_wallet_count  # Placeholder for count
            )

        except Exception as e:
            logger.error(f"Database digest failed, falling back to in-memory: {e}")
            return self._compile_digest(hours_back)

    async def send_daily_digest(self, subscriber_emails: List[str] = None):
        """
        Send daily digest to subscribers via email and Discord.

        Args:
            subscriber_emails: List of emails (defaults to settings.ALERT_EMAIL)
        """
        logger.info("📧 Compiling daily digest...")

        # Use database-backed digest (falls back to in-memory if unavailable)
        digest = await self._compile_digest_from_db(hours_back=24)

        if digest is None or digest.total_alerts == 0:
            logger.info("No alerts in past 24 hours, skipping daily digest")
            return

        # Send via email channel
        if self.alerter and hasattr(self.alerter, 'send_digest'):
            await self.alerter.send_digest(
                subject=f"🐋 Daily Whale Digest - {digest.total_alerts} Alerts",
                html_content=digest.to_html(),
                text_content=digest.to_plain_text()
            )

        # Send via Discord channel
        await self._send_discord_digest(digest)

        logger.info(f"📧 Daily digest sent ({digest.total_alerts} alerts)")

    async def send_weekly_digest(self, subscriber_emails: List[str] = None):
        """
        Send weekly digest to subscribers via email and Discord.

        Args:
            subscriber_emails: List of emails (defaults to settings.ALERT_EMAIL)
        """
        logger.info("📧 Compiling weekly digest...")

        # Use database-backed digest (falls back to in-memory if unavailable)
        digest = await self._compile_digest_from_db(hours_back=168)  # 7 days

        if digest is None or digest.total_alerts == 0:
            logger.info("No alerts in past week, skipping weekly digest")
            return

        # Send via email channel
        if self.alerter and hasattr(self.alerter, 'send_digest'):
            await self.alerter.send_digest(
                subject=f"🐋 Weekly Whale Report - {digest.total_alerts} Alerts",
                html_content=digest.to_html(),
                text_content=digest.to_plain_text()
            )

        # Send via Discord channel
        await self._send_discord_digest(digest)

        logger.info(f"📧 Weekly digest sent ({digest.total_alerts} alerts)")

    async def _send_discord_digest(self, digest: DigestReport):
        """Send digest to Discord channel."""
        if not self.alerter or not hasattr(self.alerter, 'channels'):
            return

        # Find the Discord channel
        from .alerter import DiscordAlert
        for channel in self.alerter.channels:
            if isinstance(channel, DiscordAlert) and channel.is_configured():
                try:
                    discord_payload = digest.to_discord_embed()
                    await channel.send_digest(discord_payload)
                    return
                except Exception as e:
                    logger.error(f"Error sending Discord digest: {e}")


# =========================================
# CONVENIENCE FUNCTION
# =========================================

def create_digest_scheduler(alerter, detector, database) -> DigestScheduler:
    """Create a digest scheduler with default settings."""
    return DigestScheduler(
        alerter=alerter,
        detector=detector,
        database=database,
        daily_hour=getattr(settings, 'DAILY_DIGEST_HOUR', 8),
        weekly_day=getattr(settings, 'WEEKLY_DIGEST_DAY', 'mon'),
        weekly_hour=getattr(settings, 'WEEKLY_DIGEST_HOUR', 9),
        timezone=getattr(settings, 'DIGEST_TIMEZONE', 'UTC')
    )
