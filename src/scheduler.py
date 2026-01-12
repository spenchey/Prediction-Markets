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
        """Generate HTML email content for the digest."""
        period_label = "Daily" if self.report_type == "daily" else "Weekly"

        # Generate top trades table
        trades_rows = ""
        for trade in self.top_trades[:10]:
            trades_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">${trade.get('amount', 0):,.0f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{trade.get('market', 'Unknown')[:50]}...</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{trade.get('outcome', 'N/A')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><code>{trade.get('wallet', '')[:12]}...</code></td>
            </tr>
            """

        # Generate top wallets table
        wallets_rows = ""
        for wallet in self.top_wallets[:10]:
            win_rate = wallet.get('win_rate')
            win_rate_str = f"{win_rate:.0%}" if win_rate else "N/A"
            wallets_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><code>{wallet.get('address', '')[:12]}...</code></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">${wallet.get('volume', 0):,.0f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{wallet.get('trades', 0)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{win_rate_str}</td>
            </tr>
            """

        # Alert type breakdown
        alert_breakdown = ""
        for alert_type, count in self.alerts_by_type.items():
            alert_breakdown += f"<li>{alert_type}: {count}</li>"

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
        .content {{ background: #fff; padding: 25px; border: 1px solid #ddd; border-top: none; }}
        .stat-box {{ display: inline-block; width: 30%; text-align: center; padding: 15px; background: #f8f9fa; border-radius: 8px; margin: 5px; }}
        .stat-number {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #f8f9fa; padding: 12px 8px; text-align: left; font-weight: 600; }}
        h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 8px; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🐋 {period_label} Whale Report</h1>
        <p>{self.period_start.strftime('%b %d')} - {self.period_end.strftime('%b %d, %Y')}</p>
    </div>

    <div class="content">
        <h2>📊 Summary</h2>
        <div style="text-align: center; margin: 20px 0;">
            <div class="stat-box">
                <div class="stat-number">{self.total_alerts}</div>
                <div>Total Alerts</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">${self.total_volume_tracked:,.0f}</div>
                <div>Volume Tracked</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len(self.smart_money_activity)}</div>
                <div>Smart Money Moves</div>
            </div>
        </div>

        <h2>🚨 Alert Breakdown</h2>
        <ul>{alert_breakdown}</ul>

        <h2>💰 Top Trades This Period</h2>
        <table>
            <tr><th>Amount</th><th>Market</th><th>Outcome</th><th>Wallet</th></tr>
            {trades_rows}
        </table>

        <h2>🏆 Top Wallets</h2>
        <table>
            <tr><th>Wallet</th><th>Volume</th><th>Trades</th><th>Win Rate</th></tr>
            {wallets_rows}
        </table>

        <h2>🧠 Smart Money Activity</h2>
        <p>Wallets with >60% win rate made <strong>{len(self.smart_money_activity)}</strong> trades this period.</p>

        <h2>🆕 New Wallets of Interest</h2>
        <p>Found <strong>{len(self.new_wallets_of_interest)}</strong> new wallets making significant first trades.</p>
    </div>

    <div class="footer">
        <p>Prediction Market Whale Tracker | <a href="#">Manage Preferences</a> | <a href="#">Unsubscribe</a></p>
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

    async def send_daily_digest(self, subscriber_emails: List[str] = None):
        """
        Send daily digest email to subscribers.

        Args:
            subscriber_emails: List of emails (defaults to settings.ALERT_EMAIL)
        """
        logger.info("📧 Compiling daily digest...")

        digest = self._compile_digest(hours_back=24)

        if digest.total_alerts == 0:
            logger.info("No alerts in past 24 hours, skipping daily digest")
            return

        # Send via email channel
        if self.alerter and hasattr(self.alerter, 'send_digest'):
            await self.alerter.send_digest(
                subject=f"🐋 Daily Whale Digest - {digest.total_alerts} Alerts",
                html_content=digest.to_html(),
                text_content=digest.to_plain_text()
            )
        else:
            logger.warning("Alerter does not support digest emails")

        logger.info(f"📧 Daily digest sent ({digest.total_alerts} alerts)")

    async def send_weekly_digest(self, subscriber_emails: List[str] = None):
        """
        Send weekly digest email to subscribers.

        Args:
            subscriber_emails: List of emails (defaults to settings.ALERT_EMAIL)
        """
        logger.info("📧 Compiling weekly digest...")

        digest = self._compile_digest(hours_back=168)  # 7 days

        if digest.total_alerts == 0:
            logger.info("No alerts in past week, skipping weekly digest")
            return

        # Send via email channel
        if self.alerter and hasattr(self.alerter, 'send_digest'):
            await self.alerter.send_digest(
                subject=f"🐋 Weekly Whale Report - {digest.total_alerts} Alerts",
                html_content=digest.to_html(),
                text_content=digest.to_plain_text()
            )
        else:
            logger.warning("Alerter does not support digest emails")

        logger.info(f"📧 Weekly digest sent ({digest.total_alerts} alerts)")


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
