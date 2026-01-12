"""
Whale Detector Module - Combined Best of Both Implementations

This module analyzes trades to identify "whale" and "smart money" activity:
1. Large trades (above a fixed threshold) - WHALE_TRADE
2. Statistically unusual trades (X standard deviations above mean) - UNUSUAL_SIZE / MARKET_ANOMALY
3. New wallet activity (wallets that never traded before) - NEW_WALLET
4. Smart money (wallets with high historical accuracy) - SMART_MONEY
5. Focused wallets (concentrated in few markets) - FOCUSED_WALLET [NEW from ChatGPT MVP]

Key Features:
- Non-sports market filtering for political/crypto prediction markets
- Granular severity scoring (1-10) plus categorical (LOW/MEDIUM/HIGH)
- Win rate tracking for smart money identification
- Historical performance tracking per wallet

These are the signals you'll send to subscribers!
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import statistics
import re
from loguru import logger

from .polymarket_client import Trade, PolymarketClient


# =========================================
# SPORTS KEYWORDS FOR FILTERING
# =========================================
SPORTS_KEYWORDS = [
    'nfl', 'nba', 'mlb', 'nhl', 'mls', 'ncaa', 'college football', 'college basketball',
    'super bowl', 'world series', 'stanley cup', 'championship game',
    'playoffs', 'draft pick', 'mvp award', 'rookie of the year',
    'touchdown', 'home run', 'goal scored', 'points scored',
    'win total', 'spread', 'over/under', 'moneyline',
    'premier league', 'la liga', 'bundesliga', 'serie a', 'champions league',
    'ufc', 'boxing', 'mma', 'wrestling', 'tennis', 'golf', 'pga',
    'olympics', 'world cup', 'euro 2024', 'cricket', 'rugby',
    'f1', 'formula 1', 'nascar', 'indy 500',
    'player prop', 'game total', 'first scorer', 'anytime scorer',
]


def is_sports_market(market_question: str) -> bool:
    """Check if a market is sports-related based on keywords."""
    if not market_question:
        return False
    question_lower = market_question.lower()
    return any(keyword in question_lower for keyword in SPORTS_KEYWORDS)


@dataclass
class WalletProfile:
    """
    Profile of a wallet's trading history.

    This helps identify "smart money" - wallets that
    have been historically accurate in their bets.

    Enhanced with:
    - Market concentration tracking (for FOCUSED_WALLET detection)
    - Position tracking for win rate calculation
    - Trade history for pattern analysis
    """
    address: str
    total_trades: int = 0
    total_volume_usd: float = 0.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    markets_traded: Set[str] = field(default_factory=set)

    # Track win/loss if we have resolution data
    winning_trades: int = 0
    losing_trades: int = 0

    # Enhanced tracking for smart money detection
    positions: Dict[str, Dict] = field(default_factory=dict)  # market_id -> position details
    resolved_positions: List[Dict] = field(default_factory=list)  # Historical resolved bets

    # Track by market type (non-sports vs sports)
    non_sports_trades: int = 0
    non_sports_volume_usd: float = 0.0

    @property
    def is_new_wallet(self) -> bool:
        """Wallet has less than 5 trades ever."""
        return self.total_trades < 5

    @property
    def is_whale(self) -> bool:
        """Wallet has traded over $100k total."""
        return self.total_volume_usd >= 100_000

    @property
    def is_focused(self) -> bool:
        """Wallet is concentrated in 3 or fewer markets with 5+ trades."""
        return len(self.markets_traded) <= 3 and self.total_trades >= 5

    @property
    def market_concentration(self) -> float:
        """Ratio of trades to unique markets (higher = more focused)."""
        if len(self.markets_traded) == 0:
            return 0.0
        return self.total_trades / len(self.markets_traded)

    @property
    def win_rate(self) -> Optional[float]:
        """Calculate win rate if we have enough data."""
        total = self.winning_trades + self.losing_trades
        if total < 10:
            return None
        return self.winning_trades / total

    @property
    def is_smart_money(self) -> bool:
        """Wallet has >60% win rate with significant volume."""
        win_rate = self.win_rate
        if win_rate is None:
            return False
        return win_rate >= 0.60 and self.total_volume_usd >= 50_000

    @property
    def roi(self) -> Optional[float]:
        """Calculate ROI if we have resolved positions."""
        if not self.resolved_positions:
            return None
        total_invested = sum(p.get('invested', 0) for p in self.resolved_positions)
        total_returned = sum(p.get('returned', 0) for p in self.resolved_positions)
        if total_invested == 0:
            return None
        return (total_returned - total_invested) / total_invested


def severity_to_score(severity: str) -> int:
    """Convert categorical severity to numeric score (1-10)."""
    mapping = {"LOW": 3, "MEDIUM": 6, "HIGH": 9}
    return mapping.get(severity, 5)


def score_to_severity(score: int) -> str:
    """Convert numeric score (1-10) to categorical severity."""
    if score <= 3:
        return "LOW"
    elif score <= 6:
        return "MEDIUM"
    else:
        return "HIGH"


@dataclass
class WhaleAlert:
    """
    An alert generated when unusual trading activity is detected.

    This is what you'll send to subscribers!

    Enhanced with:
    - Granular severity_score (1-10) from ChatGPT MVP
    - is_sports flag for filtering
    - Additional context fields
    """
    id: str
    alert_type: str  # "WHALE_TRADE", "NEW_WALLET", "SMART_MONEY", "FOCUSED_WALLET", etc.
    severity: str  # "LOW", "MEDIUM", "HIGH" (categorical)
    severity_score: int  # 1-10 (granular) - from ChatGPT MVP
    trade: Trade
    wallet_profile: Optional[WalletProfile]
    message: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Context about why this is interesting
    trade_size_percentile: Optional[float] = None  # How big vs other trades
    market_question: Optional[str] = None  # What market is this
    is_sports_market: bool = False  # For filtering out sports
    z_score: Optional[float] = None  # Statistical significance

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/database storage."""
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "severity_score": self.severity_score,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "trade_id": self.trade.id,
            "trade_amount_usd": self.trade.amount_usd,
            "trader_address": self.trade.trader_address,
            "market_id": self.trade.market_id,
            "market_question": self.market_question,
            "outcome": self.trade.outcome,
            "side": self.trade.side,
            "is_new_wallet": self.wallet_profile.is_new_wallet if self.wallet_profile else None,
            "wallet_total_volume": self.wallet_profile.total_volume_usd if self.wallet_profile else None,
            "wallet_win_rate": self.wallet_profile.win_rate if self.wallet_profile else None,
            "is_sports_market": self.is_sports_market,
            "z_score": self.z_score,
        }


class WhaleDetector:
    """
    Detects unusual trading activity on prediction markets.

    Combined implementation with best features from both codebases:
    - Original: Async architecture, wallet profiling, smart money detection
    - ChatGPT MVP: Focused wallet detection, granular severity, market anomaly

    Usage:
        detector = WhaleDetector()
        alerts = await detector.analyze_trades(trades)
    """

    def __init__(
        self,
        whale_threshold_usd: float = 10_000,
        new_wallet_threshold_usd: float = 1_000,
        focused_wallet_threshold_usd: float = 5_000,
        std_multiplier: float = 3.0,
        min_trades_for_stats: int = 100,
        exclude_sports: bool = True  # Key feature: filter out sports markets
    ):
        """
        Initialize the whale detector.

        Args:
            whale_threshold_usd: Fixed threshold for "whale" trades
            new_wallet_threshold_usd: Threshold for new wallet alerts
            focused_wallet_threshold_usd: Threshold for focused wallet alerts
            std_multiplier: How many std devs above mean = unusual
            min_trades_for_stats: Minimum trades before using stats
            exclude_sports: If True, filter out sports betting markets
        """
        self.whale_threshold_usd = whale_threshold_usd
        self.new_wallet_threshold_usd = new_wallet_threshold_usd
        self.focused_wallet_threshold_usd = focused_wallet_threshold_usd
        self.std_multiplier = std_multiplier
        self.min_trades_for_stats = min_trades_for_stats
        self.exclude_sports = exclude_sports

        # Track wallet profiles (in production, store in database)
        self.wallet_profiles: Dict[str, WalletProfile] = {}

        # Track recent trade sizes for statistical analysis (global)
        self.recent_trade_sizes: List[float] = []
        self.max_recent_trades = 10_000  # Rolling window

        # Track per-market statistics for market anomaly detection
        self.market_stats: Dict[str, Dict] = {}  # market_id -> {trades: [], mean, std}

        # Market question cache
        self.market_questions: Dict[str, str] = {}

    def _update_wallet_profile(self, trade: Trade, market_question: str = None) -> WalletProfile:
        """
        Update or create a wallet profile based on a trade.
        """
        address = trade.trader_address

        if address not in self.wallet_profiles:
            self.wallet_profiles[address] = WalletProfile(
                address=address,
                first_seen=trade.timestamp
            )

        profile = self.wallet_profiles[address]
        profile.total_trades += 1
        profile.total_volume_usd += trade.amount_usd
        profile.last_seen = trade.timestamp
        profile.markets_traded.add(trade.market_id)

        # Track non-sports separately
        if market_question and not is_sports_market(market_question):
            profile.non_sports_trades += 1
            profile.non_sports_volume_usd += trade.amount_usd

        return profile

    def _update_market_stats(self, trade: Trade) -> Tuple[float, float, int]:
        """
        Update per-market statistics and return (mean, std, n).
        Used for market-specific anomaly detection from ChatGPT MVP.
        """
        market_id = trade.market_id

        if market_id not in self.market_stats:
            self.market_stats[market_id] = {"trades": []}

        stats = self.market_stats[market_id]
        stats["trades"].append(trade.amount_usd)

        # Keep only last 1000 trades per market
        if len(stats["trades"]) > 1000:
            stats["trades"] = stats["trades"][-1000:]

        n = len(stats["trades"])
        if n < 2:
            return 0.0, 0.0, n

        mean = statistics.mean(stats["trades"])
        std = statistics.stdev(stats["trades"]) if n >= 2 else 0.0

        return mean, std, n

    def _calculate_percentile(self, value: float) -> Optional[float]:
        """
        Calculate what percentile a trade size falls into.

        Returns None if not enough data.
        """
        if len(self.recent_trade_sizes) < self.min_trades_for_stats:
            return None

        smaller = sum(1 for x in self.recent_trade_sizes if x < value)
        return (smaller / len(self.recent_trade_sizes)) * 100

    def _calculate_z_score(self, amount: float) -> Optional[float]:
        """
        Calculate z-score for a trade amount.
        Returns None if not enough data.
        """
        if len(self.recent_trade_sizes) < self.min_trades_for_stats:
            return None

        mean = statistics.mean(self.recent_trade_sizes)
        stdev = statistics.stdev(self.recent_trade_sizes)

        if stdev == 0:
            return None

        return (amount - mean) / stdev

    def _is_statistically_unusual(self, amount: float) -> Tuple[bool, Optional[float]]:
        """
        Check if a trade is statistically unusual.

        A trade is unusual if it's more than X standard deviations
        above the mean trade size.

        Returns (is_unusual, z_score)
        """
        z_score = self._calculate_z_score(amount)
        if z_score is None:
            return False, None

        return z_score >= self.std_multiplier, z_score

    def _calculate_severity_score(self, trade: Trade, profile: WalletProfile, alert_type: str) -> int:
        """
        Calculate granular severity score (1-10) based on multiple factors.
        Inspired by ChatGPT MVP's more granular approach.
        """
        score = 5  # Base score

        # Amount-based scoring
        if trade.amount_usd >= 100_000:
            score += 4
        elif trade.amount_usd >= 50_000:
            score += 3
        elif trade.amount_usd >= 25_000:
            score += 2
        elif trade.amount_usd >= 10_000:
            score += 1

        # Wallet-based scoring
        if profile.is_new_wallet:
            score += 2  # New wallets making big bets are more interesting
        if profile.is_smart_money:
            score += 2  # Smart money is always interesting
        if profile.is_focused:
            score += 1  # Focused wallets may have specific knowledge

        # Alert type adjustments
        if alert_type == "SMART_MONEY":
            score += 1
        elif alert_type == "NEW_WALLET":
            score += 1

        # Cap at 1-10
        return max(1, min(10, score))

    async def analyze_trade(
        self,
        trade: Trade,
        market_question: str = None
    ) -> List[WhaleAlert]:
        """
        Analyze a single trade for unusual activity.

        Returns a list of WhaleAlerts (can return multiple per trade).
        Enhanced to detect multiple signal types simultaneously.
        """
        # Check if we should skip sports markets
        is_sports = is_sports_market(market_question) if market_question else False
        if self.exclude_sports and is_sports:
            return []

        # Cache market question
        if market_question:
            self.market_questions[trade.market_id] = market_question

        # Update wallet profile
        profile = self._update_wallet_profile(trade, market_question)

        # Track trade size for global statistics
        self.recent_trade_sizes.append(trade.amount_usd)
        if len(self.recent_trade_sizes) > self.max_recent_trades:
            self.recent_trade_sizes.pop(0)

        # Update per-market statistics
        market_mean, market_std, market_n = self._update_market_stats(trade)

        # Collect all triggered alerts
        alerts: List[WhaleAlert] = []

        # 1. Fixed threshold whale trade
        if trade.amount_usd >= self.whale_threshold_usd:
            severity_score = self._calculate_severity_score(trade, profile, "WHALE_TRADE")
            severity = score_to_severity(severity_score)

            alerts.append(WhaleAlert(
                id=f"whale_{trade.id}",
                alert_type="WHALE_TRADE",
                severity=severity,
                severity_score=severity_score,
                trade=trade,
                wallet_profile=profile,
                message=f"🐋 WHALE ALERT: ${trade.amount_usd:,.0f} {trade.side} on {trade.outcome}",
                trade_size_percentile=self._calculate_percentile(trade.amount_usd),
                market_question=market_question,
                is_sports_market=is_sports,
            ))

        # 2. Statistically unusual trade (global)
        is_unusual, z_score = self._is_statistically_unusual(trade.amount_usd)
        if is_unusual and trade.amount_usd < self.whale_threshold_usd:
            severity_score = 6 if z_score < self.std_multiplier + 2 else 8
            alerts.append(WhaleAlert(
                id=f"unusual_{trade.id}",
                alert_type="UNUSUAL_SIZE",
                severity=score_to_severity(severity_score),
                severity_score=severity_score,
                trade=trade,
                wallet_profile=profile,
                message=f"📊 UNUSUAL TRADE: ${trade.amount_usd:,.0f} is {z_score:.1f} std devs above average",
                trade_size_percentile=self._calculate_percentile(trade.amount_usd),
                market_question=market_question,
                is_sports_market=is_sports,
                z_score=z_score,
            ))

        # 3. Market-specific anomaly (from ChatGPT MVP)
        if market_n >= 20 and market_std > 0:
            market_z = (trade.amount_usd - market_mean) / market_std
            if market_z >= self.std_multiplier:
                severity_score = 7 if market_z < self.std_multiplier + 2 else 9
                alerts.append(WhaleAlert(
                    id=f"anomaly_{trade.id}",
                    alert_type="MARKET_ANOMALY",
                    severity=score_to_severity(severity_score),
                    severity_score=severity_score,
                    trade=trade,
                    wallet_profile=profile,
                    message=f"🎯 MARKET ANOMALY: z={market_z:.2f} (market avg ${market_mean:,.0f}, trade ${trade.amount_usd:,.0f})",
                    market_question=market_question,
                    is_sports_market=is_sports,
                    z_score=market_z,
                ))

        # 4. New wallet making significant trade
        if profile.is_new_wallet and trade.amount_usd >= self.new_wallet_threshold_usd:
            severity_score = 8 if trade.amount_usd >= 5000 else 6
            alerts.append(WhaleAlert(
                id=f"new_{trade.id}",
                alert_type="NEW_WALLET",
                severity=score_to_severity(severity_score),
                severity_score=severity_score,
                trade=trade,
                wallet_profile=profile,
                message=f"🆕 NEW WALLET: First-time trader placed ${trade.amount_usd:,.0f} bet (only {profile.total_trades} trades)",
                market_question=market_question,
                is_sports_market=is_sports,
            ))

        # 5. Focused wallet making big trade (from ChatGPT MVP)
        if profile.is_focused and trade.amount_usd >= self.focused_wallet_threshold_usd:
            severity_score = 7
            alerts.append(WhaleAlert(
                id=f"focused_{trade.id}",
                alert_type="FOCUSED_WALLET",
                severity=score_to_severity(severity_score),
                severity_score=severity_score,
                trade=trade,
                wallet_profile=profile,
                message=f"🎯 FOCUSED WALLET: Wallet concentrated in {len(profile.markets_traded)} markets placed ${trade.amount_usd:,.0f} bet",
                market_question=market_question,
                is_sports_market=is_sports,
            ))

        # 6. Smart money (high win-rate wallet) making a trade
        if profile.is_smart_money and trade.amount_usd >= 500:
            severity_score = 9  # Smart money is always high priority
            alerts.append(WhaleAlert(
                id=f"smart_{trade.id}",
                alert_type="SMART_MONEY",
                severity="HIGH",
                severity_score=severity_score,
                trade=trade,
                wallet_profile=profile,
                message=f"🧠 SMART MONEY: Wallet with {profile.win_rate:.0%} win rate placed ${trade.amount_usd:,.0f} bet",
                market_question=market_question,
                is_sports_market=is_sports,
            ))

        return alerts
    
    async def analyze_trades(self, trades: List[Trade], market_questions: Dict[str, str] = None) -> List[WhaleAlert]:
        """
        Analyze multiple trades and return all alerts.

        Args:
            trades: List of trades to analyze
            market_questions: Optional dict mapping market_id -> question text

        Returns:
            List of WhaleAlert objects for notable trades
        """
        market_questions = market_questions or {}
        alerts = []

        for trade in trades:
            market_question = market_questions.get(trade.market_id)
            trade_alerts = await self.analyze_trade(trade, market_question)
            alerts.extend(trade_alerts)

        logger.info(f"Analyzed {len(trades)} trades, generated {len(alerts)} alerts")
        return alerts

    def get_wallet_summary(self, address: str) -> Optional[WalletProfile]:
        """Get the profile for a specific wallet."""
        return self.wallet_profiles.get(address)

    def get_top_wallets(self, limit: int = 10, non_sports_only: bool = False) -> List[WalletProfile]:
        """Get the top wallets by volume."""
        if non_sports_only:
            sorted_wallets = sorted(
                self.wallet_profiles.values(),
                key=lambda w: w.non_sports_volume_usd,
                reverse=True
            )
        else:
            sorted_wallets = sorted(
                self.wallet_profiles.values(),
                key=lambda w: w.total_volume_usd,
                reverse=True
            )
        return sorted_wallets[:limit]

    def get_smart_money_wallets(self, limit: int = 20) -> List[WalletProfile]:
        """Get wallets identified as smart money (high win rate)."""
        smart_wallets = [
            w for w in self.wallet_profiles.values()
            if w.is_smart_money
        ]
        return sorted(smart_wallets, key=lambda w: w.win_rate or 0, reverse=True)[:limit]

    def get_focused_wallets(self, limit: int = 20) -> List[WalletProfile]:
        """Get wallets that are focused on few markets (potential insiders)."""
        focused = [
            w for w in self.wallet_profiles.values()
            if w.is_focused and w.total_volume_usd >= 5000
        ]
        return sorted(focused, key=lambda w: w.market_concentration, reverse=True)[:limit]

    def update_wallet_win_rate(self, address: str, won: bool):
        """
        Update a wallet's win/loss record after market resolution.
        Call this when a market resolves to track smart money.
        """
        if address in self.wallet_profiles:
            profile = self.wallet_profiles[address]
            if won:
                profile.winning_trades += 1
            else:
                profile.losing_trades += 1


# =========================================
# REAL-TIME MONITORING
# =========================================

class TradeMonitor:
    """
    Continuously monitors prediction markets for whale activity.

    This is the main loop that runs in production.

    Enhanced with:
    - Market question fetching for sports filtering
    - Better error handling and retry logic
    - Statistics tracking
    """

    def __init__(
        self,
        detector: WhaleDetector,
        poll_interval: int = 60,
        on_alert=None,  # Callback function when alert detected
        fetch_market_info: bool = True  # Fetch market questions for context
    ):
        self.detector = detector
        self.poll_interval = poll_interval
        self.on_alert = on_alert
        self.fetch_market_info = fetch_market_info
        self.seen_trades: Set[str] = set()  # Avoid duplicate alerts
        self._running = False

        # Statistics
        self.total_trades_processed = 0
        self.total_alerts_generated = 0
        self.last_check_time: Optional[datetime] = None

        # Market question cache
        self._market_cache: Dict[str, str] = {}

    async def start(self):
        """Start the monitoring loop."""
        self._running = True
        logger.info(f"🚀 Starting trade monitor (polling every {self.poll_interval}s)")
        logger.info(f"   Sports filtering: {'ENABLED' if self.detector.exclude_sports else 'DISABLED'}")

        while self._running:
            try:
                await self._check_for_trades()
                self.last_check_time = datetime.now()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        logger.info("🛑 Stopping trade monitor")
        logger.info(f"   Total trades processed: {self.total_trades_processed}")
        logger.info(f"   Total alerts generated: {self.total_alerts_generated}")

    async def _fetch_market_questions(self, market_ids: Set[str]) -> Dict[str, str]:
        """Fetch market questions for a set of market IDs."""
        questions = {}

        # Return cached values first
        uncached = [mid for mid in market_ids if mid not in self._market_cache]

        if uncached and self.fetch_market_info:
            try:
                async with PolymarketClient() as client:
                    markets = await client.get_active_markets(limit=200)
                    for market in markets:
                        self._market_cache[market.id] = market.question
            except Exception as e:
                logger.warning(f"Failed to fetch market info: {e}")

        # Return all from cache
        for mid in market_ids:
            if mid in self._market_cache:
                questions[mid] = self._market_cache[mid]

        return questions

    async def _check_for_trades(self):
        """Fetch new trades and check for alerts."""
        async with PolymarketClient() as client:
            trades = await client.get_recent_trades(limit=100)

        # Filter to new trades only
        new_trades = [
            t for t in trades
            if t.id not in self.seen_trades
        ]

        if not new_trades:
            return

        # Mark as seen
        for trade in new_trades:
            self.seen_trades.add(trade.id)

        # Keep seen_trades from growing forever
        if len(self.seen_trades) > 50_000:
            # Remove oldest half
            self.seen_trades = set(list(self.seen_trades)[-25_000:])

        # Fetch market questions for context and filtering
        market_ids = {t.market_id for t in new_trades}
        market_questions = await self._fetch_market_questions(market_ids)

        # Analyze for alerts
        alerts = await self.detector.analyze_trades(new_trades, market_questions)

        # Update statistics
        self.total_trades_processed += len(new_trades)
        self.total_alerts_generated += len(alerts)

        # Trigger callback for each alert
        if self.on_alert and alerts:
            for alert in alerts:
                try:
                    await self.on_alert(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")


# =========================================
# TEST THE DETECTOR
# =========================================

import asyncio

async def main():
    """Test the whale detector."""
    print("🐋 Testing Whale Detector...\n")
    
    # Create detector with lower thresholds for testing
    detector = WhaleDetector(
        whale_threshold_usd=1000,  # Lower for testing
        std_multiplier=2.0
    )
    
    # Fetch some real trades
    async with PolymarketClient() as client:
        trades = await client.get_recent_trades(limit=200)
    
    print(f"📊 Fetched {len(trades)} trades\n")
    
    # Analyze trades
    alerts = await detector.analyze_trades(trades)
    
    print(f"\n🚨 Generated {len(alerts)} alerts:\n")
    
    for alert in alerts[:10]:  # Show first 10
        print(f"  [{alert.severity}] {alert.alert_type}")
        print(f"  {alert.message}")
        print(f"  Trader: {alert.trade.trader_address[:15]}...")
        if alert.trade_size_percentile:
            print(f"  Percentile: {alert.trade_size_percentile:.1f}%")
        print()
    
    # Show wallet stats
    print("\n💰 Top Wallets by Volume:")
    for profile in detector.get_top_wallets(5):
        print(f"  {profile.address[:15]}... - ${profile.total_volume_usd:,.0f} ({profile.total_trades} trades)")
    
    print("\n✅ Detector working correctly!")


if __name__ == "__main__":
    asyncio.run(main())
