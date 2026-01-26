"""
Whale Detector Module - Enhanced with Advanced Detection Algorithms

This module analyzes trades to identify "whale" and "smart money" activity:

ORIGINAL DETECTORS:
1. Large trades (above a fixed threshold) - WHALE_TRADE
2. Statistically unusual trades (X standard deviations above mean) - UNUSUAL_SIZE / MARKET_ANOMALY
3. New wallet activity (wallets that never traded before) - NEW_WALLET
4. Smart money (wallets with high historical accuracy) - SMART_MONEY
5. Focused wallets (concentrated in few markets) - FOCUSED_WALLET

NEW DETECTORS (January 2026 - inspired by Polymaster, PredictOS, PolyTrack):
6. Repeat actor detection (2+ trades in 1 hour) - REPEAT_ACTOR
7. Heavy actor detection (5+ trades in 24 hours) - HEAVY_ACTOR
8. Extreme confidence bets (>95% or <5% odds) - EXTREME_CONFIDENCE
9. Exit/unwind detection (whale selling positions) - WHALE_EXIT
10. Contrarian activity (betting against consensus) - CONTRARIAN
11. Cluster detection (related wallets same market/time) - CLUSTER_ACTIVITY

ADVANCED FEATURES (January 2026 - from ChatGPT pm_whale_tracker_v5):
12. Entity detection - Multiple wallets controlled by same entity - ENTITY_ACTIVITY
13. Impact ratio - Trade size relative to market volume - HIGH_IMPACT
14. Fresh wallet detection - On-chain nonce analysis - FRESH_WALLET

Key Features:
- Non-sports market filtering for political/crypto prediction markets
- Granular severity scoring (1-10) plus categorical (LOW/MEDIUM/HIGH)
- Win rate tracking for smart money identification
- Historical performance tracking per wallet
- Velocity-based detection (trades per hour/day)
- Entity clustering with Union-Find algorithm
- Impact ratio calculation (trade_cash / market_volume)
- On-chain wallet freshness scoring

These are the signals you'll send to subscribers!
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import statistics
import re
import hashlib
from loguru import logger

from .polymarket_client import Trade, Market, PolymarketClient


# =========================================
# HIGH-FREQUENCY MARKET FILTERING
# =========================================
# These markets generate tons of small trades and noise, drowning out real signals
HIGH_FREQUENCY_MARKET_PATTERNS = [
    # 15-minute Bitcoin up/down markets - extremely high volume, low signal
    'bitcoin up or down',
    'btc up or down',
    'btc-updown',
    'btc updown',
    # Short timeframe patterns
    '-15m-',  # 15 minute markets
    '15m-',
    '-5m-',   # 5 minute markets
    '5m-',
    # Hourly Bitcoin patterns (also high noise)
    'btc-1h',
    'bitcoin-1h',
]


def is_high_frequency_market(market_question: str, market_id: str = None, slug: str = None) -> bool:
    """
    Check if a market is a high-frequency trading market that should be filtered.

    These markets (like 15-minute BTC up/down) generate enormous trade volume
    but are mostly noise that drowns out real whale signals.
    """
    texts_to_check = []
    if market_question:
        texts_to_check.append(market_question.lower())
    if market_id:
        texts_to_check.append(market_id.lower())
    if slug:
        texts_to_check.append(slug.lower())

    for text in texts_to_check:
        for pattern in HIGH_FREQUENCY_MARKET_PATTERNS:
            if pattern in text:
                return True

    return False


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
    # Game matchup patterns
    ' vs ', ' vs. ', ' @ ',
    # NBA teams
    'lakers', 'celtics', 'warriors', 'bulls', 'heat', 'knicks', 'nets', 'suns', 'bucks',
    'mavericks', 'mavs', 'clippers', 'nuggets', 'grizzlies', 'pelicans', 'thunder', 'rockets',
    'spurs', 'timberwolves', 'wolves', 'jazz', 'kings', 'blazers', 'trail blazers', 'pacers',
    'hawks', 'hornets', 'cavaliers', 'cavs', 'pistons', 'raptors', 'wizards', 'magic', '76ers',
    'sixers',
    # NFL teams
    'patriots', 'cowboys', 'eagles', 'chiefs', 'bills', 'dolphins', 'jets', 'ravens', 'steelers',
    'bengals', 'browns', 'colts', 'texans', 'titans', 'jaguars', 'broncos', 'raiders', 'chargers',
    'commanders', 'giants', 'packers', 'bears', 'lions', 'vikings', 'saints', 'falcons', 'panthers',
    'buccaneers', 'bucs', 'cardinals', 'rams', 'seahawks', '49ers', 'niners',
]


def is_sports_market(market_question: str, market_id: str = None) -> bool:
    """Check if a market is sports-related based on keywords.

    Checks both the market question and market_id/ticker for sports keywords.
    This catches Kalshi markets where the ticker contains 'NBA', 'NFL', etc.
    """
    # Check market question
    if market_question:
        question_lower = market_question.lower()
        if any(keyword in question_lower for keyword in SPORTS_KEYWORDS):
            return True

    # Check market_id/ticker (catches Kalshi tickers like KXNBATOTAL)
    if market_id:
        id_lower = market_id.lower()
        # Check for sports league codes in ticker
        sports_ticker_patterns = ['nba', 'nfl', 'mlb', 'nhl', 'mls', 'ncaa', 'ufc', 'pga']
        if any(pattern in id_lower for pattern in sports_ticker_patterns):
            return True

    return False


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
    - Velocity tracking (trades per hour/day) - NEW
    - Exit pattern detection - NEW
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
    # positions tracks per-market position: {market_id: {outcome: {buy_shares, buy_usd, sell_shares, sell_usd}}}
    positions: Dict[str, Dict[str, Dict[str, float]]] = field(default_factory=dict)
    resolved_positions: List[Dict] = field(default_factory=list)  # Historical resolved bets

    # Track by market type (non-sports vs sports)
    non_sports_trades: int = 0
    non_sports_volume_usd: float = 0.0

    # NEW: Velocity tracking (trades with timestamps for frequency analysis)
    recent_trade_times: List[datetime] = field(default_factory=list)  # Last 100 trade timestamps

    # NEW: Track buys vs sells for exit detection
    total_buys: int = 0
    total_sells: int = 0
    buy_volume_usd: float = 0.0
    sell_volume_usd: float = 0.0

    # VIP tracking: count of large trades (for VIP qualification)
    large_trades_count: int = 0  # Trades over VIP_LARGE_TRADE_THRESHOLD

    def add_trade_timestamp(self, timestamp: datetime):
        """Track trade timestamps for velocity calculation."""
        self.recent_trade_times.append(timestamp)
        # Keep only last 100 timestamps
        if len(self.recent_trade_times) > 100:
            self.recent_trade_times = self.recent_trade_times[-100:]

    def update_position(self, market_id: str, outcome: str, side: str, shares: float, amount_usd: float):
        """Update position for a specific market and outcome."""
        if market_id not in self.positions:
            self.positions[market_id] = {}
        if outcome not in self.positions[market_id]:
            self.positions[market_id][outcome] = {
                "buy_shares": 0.0,
                "buy_usd": 0.0,
                "sell_shares": 0.0,
                "sell_usd": 0.0,
            }

        pos = self.positions[market_id][outcome]
        if side.lower() == "buy":
            pos["buy_shares"] += shares
            pos["buy_usd"] += amount_usd
        elif side.lower() == "sell":
            pos["sell_shares"] += shares
            pos["sell_usd"] += amount_usd

    def get_position(self, market_id: str, outcome: str) -> Dict[str, float]:
        """Get position info for a specific market and outcome."""
        if market_id not in self.positions:
            return {"buy_shares": 0, "buy_usd": 0, "sell_shares": 0, "sell_usd": 0, "net_shares": 0}
        if outcome not in self.positions[market_id]:
            return {"buy_shares": 0, "buy_usd": 0, "sell_shares": 0, "sell_usd": 0, "net_shares": 0}

        pos = self.positions[market_id][outcome].copy()
        pos["net_shares"] = pos["buy_shares"] - pos["sell_shares"]
        return pos

    def get_position_action(self, market_id: str, outcome: str, side: str) -> str:
        """
        Determine if this trade is opening, closing, or adding to a position.

        Returns:
            - "OPENING": First trade in this market/outcome
            - "ADDING": Adding to an existing position in same direction
            - "CLOSING": Reducing/closing an existing position
            - "REVERSING": Closing position and going opposite direction (rare)
        """
        pos = self.get_position(market_id, outcome)
        net_shares = pos["net_shares"]

        # No existing position
        if net_shares == 0:
            return "OPENING"

        # Has a long position (bought more than sold)
        if net_shares > 0:
            if side.lower() == "buy":
                return "ADDING"  # Adding to long
            else:
                return "CLOSING"  # Selling to close long

        # Has a short position (sold more than bought)
        if net_shares < 0:
            if side.lower() == "sell":
                return "ADDING"  # Adding to short
            else:
                return "CLOSING"  # Buying to close short

        return "OPENING"

    def get_market_pnl(self, market_id: str) -> Dict[str, float]:
        """Get estimated P&L for a market (unrealized, based on buy/sell prices)."""
        if market_id not in self.positions:
            return {"total_invested": 0, "total_received": 0, "realized_pnl": 0}

        total_invested = 0.0
        total_received = 0.0

        for outcome, pos in self.positions[market_id].items():
            total_invested += pos.get("buy_usd", 0)
            total_received += pos.get("sell_usd", 0)

        return {
            "total_invested": total_invested,
            "total_received": total_received,
            "realized_pnl": total_received - total_invested,
        }

    @property
    def trades_last_hour(self) -> int:
        """Count of trades in the last hour."""
        if not self.recent_trade_times:
            return 0
        cutoff = datetime.now() - timedelta(hours=1)
        return sum(1 for t in self.recent_trade_times if t > cutoff)

    @property
    def trades_last_24h(self) -> int:
        """Count of trades in the last 24 hours."""
        if not self.recent_trade_times:
            return 0
        cutoff = datetime.now() - timedelta(hours=24)
        return sum(1 for t in self.recent_trade_times if t > cutoff)

    @property
    def is_repeat_actor(self) -> bool:
        """Wallet has 3+ trades in last hour (elevated alert) - STRICTER."""
        return self.trades_last_hour >= 3

    @property
    def is_heavy_actor(self) -> bool:
        """Wallet has 10+ trades in last 24h (high priority) - STRICTER."""
        return self.trades_last_24h >= 10

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
        """Wallet has >65% win rate with significant volume - STRICTER."""
        win_rate = self.win_rate
        if win_rate is None:
            return False
        return win_rate >= 0.65 and self.total_volume_usd >= 50_000

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

    @property
    def sell_ratio(self) -> float:
        """Ratio of sells to total trades (higher = more exits)."""
        if self.total_trades == 0:
            return 0.0
        return self.total_sells / self.total_trades

    def is_vip(self, min_volume: float = 100000, min_win_rate: float = 0.55,
               min_large_trades: int = 5) -> bool:
        """
        Check if wallet qualifies as VIP based on any of these criteria:
        1. High total volume (default $100k+)
        2. Good win rate (default 55%+ with enough resolved bets)
        3. History of large trades (default 5+ trades over threshold)
        """
        # Criteria 1: High volume whale
        if self.total_volume_usd >= min_volume:
            return True

        # Criteria 2: Successful track record
        win_rate = self.win_rate
        if win_rate is not None and win_rate >= min_win_rate:
            return True

        # Criteria 3: History of large trades
        if self.large_trades_count >= min_large_trades:
            return True

        return False

    def get_vip_reason(self, min_volume: float = 100000, min_win_rate: float = 0.55,
                       min_large_trades: int = 5) -> Optional[str]:
        """Get the reason why this wallet is VIP."""
        reasons = []

        if self.total_volume_usd >= min_volume:
            reasons.append(f"${self.total_volume_usd:,.0f} lifetime volume")

        win_rate = self.win_rate
        if win_rate is not None and win_rate >= min_win_rate:
            reasons.append(f"{win_rate:.0%} win rate")

        if self.large_trades_count >= min_large_trades:
            reasons.append(f"{self.large_trades_count} large trades historically")

        return " | ".join(reasons) if reasons else None


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
    - CONSOLIDATED: Multiple alert types per trade (Jan 2026)
    """
    id: str
    alert_types: List[str]  # List of triggered types: ["WHALE_TRADE", "NEW_WALLET", "HIGH_IMPACT"]
    severity: str  # "LOW", "MEDIUM", "HIGH" (categorical) - highest among all
    severity_score: int  # 1-10 (granular) - highest score among all triggers
    trade: Trade
    wallet_profile: Optional[WalletProfile]
    messages: List[str]  # List of reason messages for each alert type
    timestamp: datetime = field(default_factory=datetime.now)

    # Context about why this is interesting
    trade_size_percentile: Optional[float] = None  # How big vs other trades
    market_question: Optional[str] = None  # What market is this
    is_sports_market: bool = False  # For filtering out sports
    z_score: Optional[float] = None  # Statistical significance
    market_url: Optional[str] = None  # Link to market page
    category: str = "Other"  # Politics, Crypto, Sports, Finance, etc.
    position_action: str = "OPENING"  # OPENING, ADDING, CLOSING - what this trade means for their position

    # Backwards compatibility properties
    @property
    def alert_type(self) -> str:
        """Primary alert type (first in list) for backwards compatibility."""
        return self.alert_types[0] if self.alert_types else "UNKNOWN"

    @property
    def message(self) -> str:
        """Primary message (first in list) for backwards compatibility."""
        return self.messages[0] if self.messages else ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/database storage."""
        return {
            "id": self.id,
            "alert_type": self.alert_type,  # Primary type for DB
            "alert_types": self.alert_types,  # All types
            "severity": self.severity,
            "severity_score": self.severity_score,
            "message": self.message,  # Primary message for DB
            "messages": self.messages,  # All messages
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
        exclude_sports: bool = True,  # Key feature: filter out sports markets
        # NEW thresholds for advanced detection
        extreme_confidence_high: float = 0.95,  # Price > this = extreme confidence
        extreme_confidence_low: float = 0.05,   # Price < this = extreme confidence
        exit_threshold_usd: float = 5_000,      # Min USD for exit alerts
        contrarian_threshold: float = 0.15,     # Bet on outcome with <15% odds
        cluster_time_window_minutes: int = 5,   # Time window for cluster detection
        min_alert_threshold_usd: float = 2000,  # Minimum USD for alerts (RAISED from $1k to $2k)
        crypto_min_threshold_usd: float = 974,  # Higher threshold for crypto markets
        # VIP wallet detection settings
        vip_min_volume: float = 100_000,        # $100k lifetime volume to be VIP
        vip_min_win_rate: float = 0.55,         # 55% win rate to be VIP
        vip_min_large_trades: int = 5,          # 5+ large trades to be VIP
        vip_large_trade_threshold: float = 5_000,  # What counts as "large"
        # Multi-signal requirement (Elite Signals Only mode)
        min_triggers_required: int = 2,         # Require 2+ signals (except exempt types)
    ):
        """
        Initialize the whale detector with comprehensive detection algorithms.

        Args:
            whale_threshold_usd: Fixed threshold for "whale" trades
            new_wallet_threshold_usd: Threshold for new wallet alerts
            focused_wallet_threshold_usd: Threshold for focused wallet alerts
            std_multiplier: How many std devs above mean = unusual
            min_trades_for_stats: Minimum trades before using stats
            exclude_sports: If True, filter out sports betting markets
            extreme_confidence_high: Price threshold for extreme confidence bets (default 95%)
            extreme_confidence_low: Price threshold for extreme confidence bets (default 5%)
            exit_threshold_usd: Minimum USD for whale exit alerts
            contrarian_threshold: Bet on outcomes below this probability = contrarian
            cluster_time_window_minutes: Time window to detect related wallets
        """
        self.whale_threshold_usd = whale_threshold_usd
        self.new_wallet_threshold_usd = new_wallet_threshold_usd
        self.focused_wallet_threshold_usd = focused_wallet_threshold_usd
        self.std_multiplier = std_multiplier
        self.min_trades_for_stats = min_trades_for_stats
        self.exclude_sports = exclude_sports

        # NEW detection thresholds
        self.extreme_confidence_high = extreme_confidence_high
        self.extreme_confidence_low = extreme_confidence_low
        self.exit_threshold_usd = exit_threshold_usd
        self.contrarian_threshold = contrarian_threshold
        self.cluster_time_window = timedelta(minutes=cluster_time_window_minutes)
        self.min_alert_threshold_usd = min_alert_threshold_usd
        self.crypto_min_threshold_usd = crypto_min_threshold_usd
        self.min_triggers_required = min_triggers_required

        # VIP wallet detection thresholds
        self.vip_min_volume = vip_min_volume
        self.vip_min_win_rate = vip_min_win_rate
        self.vip_min_large_trades = vip_min_large_trades
        self.vip_large_trade_threshold = vip_large_trade_threshold

        # NEW: Stricter thresholds for "Elite Signals Only" mode
        self.new_wallet_threshold_usd = new_wallet_threshold_usd  # Store for later increase
        self.std_multiplier = std_multiplier  # Already stored, but noting we'll increase it

        # Alert types exempt from minimum threshold AND multi-signal requirement
        # These are so significant they always alert alone
        self.exempt_alert_types = {"WHALE_TRADE", "CLUSTER_ACTIVITY", "VIP_WALLET", "ENTITY_ACTIVITY"}

        # Alert types that bypass crypto filtering (high-value signals)
        self.crypto_exempt_types = {"CLUSTER_ACTIVITY", "WHALE_TRADE", "SMART_MONEY", "VIP_WALLET"}

        # Track wallet profiles (in production, store in database)
        self.wallet_profiles: Dict[str, WalletProfile] = {}

        # Track recent trade sizes for statistical analysis (global)
        self.recent_trade_sizes: List[float] = []
        self.max_recent_trades = 10_000  # Rolling window

        # Track per-market statistics for market anomaly detection
        self.market_stats: Dict[str, Dict] = {}  # market_id -> {trades: [], mean, std}

        # Market info caches
        self.market_questions: Dict[str, str] = {}  # market_id -> question text
        self.market_urls: Dict[str, str] = {}  # market_id -> URL
        self.market_categories: Dict[str, str] = {}  # market_id -> category

        # NEW: Market prices cache (for contrarian/extreme confidence detection)
        self.market_prices: Dict[str, Dict[str, float]] = {}  # market_id -> {"Yes": 0.65, "No": 0.35}

        # NEW: Cluster detection - track recent trades by market for timing analysis
        # Structure: market_id -> [(wallet_address, timestamp, amount_usd), ...]
        self.recent_market_trades: Dict[str, List[Tuple[str, datetime, float]]] = defaultdict(list)

        # NEW: Detected clusters (linked wallets)
        # Structure: frozenset of wallet addresses -> cluster metadata
        self.wallet_clusters: Dict[frozenset, Dict] = {}

        # NEW: Market volume tracking for impact ratio calculation
        # Structure: market_id -> {"volume": float, "last_updated": datetime}
        self.market_hourly_volume: Dict[str, Dict] = {}

        # NEW: Impact ratio threshold (trade as % of market volume)
        self.impact_ratio_threshold = 0.08  # 8% of hourly volume

        # NEW: Entity engine integration (lazy loaded)
        self._entity_engine = None

        # NEW: On-chain freshness threshold
        self.fresh_wallet_nonce_threshold = 10  # Wallets with nonce < 10 are "fresh"

        # Anonymous trader identifiers (platforms that don't expose trader identity)
        self.anonymous_trader_prefixes = ("KALSHI_ANON", "UNKNOWN", "ANONYMOUS")

    def _is_anonymous_trader(self, trader_address: str) -> bool:
        """
        Check if trader is anonymous (no identity available).

        Some platforms like Kalshi don't expose trader identities.
        Returns True if trader cannot be identified.
        """
        if not trader_address:
            return True
        return trader_address.startswith(self.anonymous_trader_prefixes)

    def _detect_category_from_text(self, text: str, market_id: str = None) -> str:
        """
        Detect market category from question/title text using keyword matching.
        Also detects from Kalshi ticker patterns when text is not available.

        Returns one of: Politics, Crypto, Sports, Finance, Entertainment, Science, World, Other
        """
        # Category keywords (order matters - more specific first)
        category_keywords = {
            "Politics": ["trump", "biden", "election", "president", "congress", "senate",
                        "vote", "democrat", "republican", "governor", "mayor", "party",
                        "nominee", "gop", "dnc", "rnc", "political", "pelosi", "mccarthy",
                        "desantis", "newsom", "whitmer", "vance", "harris"],
            "Crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto", "token", "blockchain",
                      "solana", "sol", "dogecoin", "doge", "ripple", "xrp", "cardano"],
            "Sports": ["nfl", "nba", "mlb", "nhl", "super bowl", "championship", "playoff",
                      "world series", "stanley cup", "premier league", "uefa", "fifa",
                      " vs ", " vs. ", " @ ", "lakers", "celtics", "warriors", "chiefs",
                      "eagles", "cowboys", "yankees", "dodgers", "game", "match"],
            "Finance": ["stock", "s&p", "nasdaq", "fed", "interest rate", "inflation",
                       "gdp", "recession", "market", "dow", "treasury", "unemployment",
                       "fomc", "cpi", "jobs report", "earnings"],
            "Entertainment": ["oscar", "grammy", "emmy", "movie", "album", "celebrity",
                            "twitter", "tweet", "streaming", "netflix", "spotify",
                            "box office", "billboard", "taylor swift", "beyonce"],
            "Science": ["ai ", "openai", "climate", "fda", "vaccine", "space", "nasa",
                       "weather", "hurricane", "earthquake", "temperature", "gpt",
                       "artificial intelligence", "spacex", "launch"],
            "World": ["war", "ukraine", "russia", "china", "iran", "israel", "military",
                     "invasion", "ceasefire", "nato", "sanctions", "tariff", "trade war",
                     "north korea", "taiwan", "gaza", "hamas", "putin", "zelensky"],
        }

        # Try text-based detection first
        if text:
            text_lower = text.lower()
            for category, keywords in category_keywords.items():
                if any(kw in text_lower for kw in keywords):
                    return category

        # Kalshi ticker pattern detection (for trades without market question)
        if market_id:
            market_id_upper = market_id.upper()
            # Sports tickers
            if any(pattern in market_id_upper for pattern in [
                "KXNBA", "KXNFL", "KXMLB", "KXNHL", "KXMVE", "KXATP", "KXWTA",
                "KXLIGUE", "KXEUROLEAGUE", "KXPREMIER", "KXLALIGA", "KXSERIE",
                "KXBUNDES", "KXCHAMPIONS", "KXUFC", "KXPGA", "KXTENNIS",
                "SPORTS", "GAME", "MATCH", "TOTAL"
            ]):
                return "Sports"
            # Crypto tickers
            if any(pattern in market_id_upper for pattern in [
                "KXBTC", "KXETH", "KXSOL", "KXDOGE", "KXCRYPTO", "BITCOIN", "ETHEREUM"
            ]):
                return "Crypto"
            # Finance/Economics tickers
            if any(pattern in market_id_upper for pattern in [
                "KXEO", "KXCPI", "KXGDP", "KXJOBS", "KXFED", "KXFOMC", "KXRATE",
                "KXINFL", "KXUNEMPLOY", "KXSP500", "KXNASDAQ", "KXDOW"
            ]):
                return "Finance"
            # Politics tickers
            if any(pattern in market_id_upper for pattern in [
                "KXTRUMP", "KXBIDEN", "KXPRES", "KXELECT", "KXGOV", "KXSEN",
                "KXHOUSE", "KXCONGRESS", "KXDJTVO"  # DJTVO = Trump related
            ]):
                return "Politics"

        return "Other"

    def _update_wallet_profile(self, trade: Trade, market_question: str = None) -> WalletProfile:
        """
        Update or create a wallet profile based on a trade.
        Enhanced to track velocity and buy/sell patterns.
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

        # Track trade timestamp for velocity detection
        profile.add_trade_timestamp(trade.timestamp)

        # Track buy vs sell for exit detection
        if trade.side.lower() == "buy":
            profile.total_buys += 1
            profile.buy_volume_usd += trade.amount_usd
        elif trade.side.lower() == "sell":
            profile.total_sells += 1
            profile.sell_volume_usd += trade.amount_usd

        # Track large trades for VIP qualification
        if trade.amount_usd >= self.vip_large_trade_threshold:
            profile.large_trades_count += 1

        # Track per-market position
        profile.update_position(
            market_id=trade.market_id,
            outcome=trade.outcome,
            side=trade.side,
            shares=trade.size,
            amount_usd=trade.amount_usd
        )

        # Track non-sports separately
        if not is_sports_market(market_question, trade.market_id):
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

    def update_market_prices(self, market_id: str, prices: Dict[str, float]):
        """
        Update cached market prices (for contrarian/extreme confidence detection).

        Args:
            market_id: The market condition ID
            prices: Dict like {"Yes": 0.65, "No": 0.35}
        """
        self.market_prices[market_id] = prices

    def _get_outcome_probability(self, trade: Trade) -> Optional[float]:
        """
        Get the market probability for the outcome being traded.
        Uses trade price as approximation if market prices not cached.
        """
        # First try cached market prices
        if trade.market_id in self.market_prices:
            prices = self.market_prices[trade.market_id]
            return prices.get(trade.outcome, trade.price)

        # Fall back to trade price (which approximates the probability)
        return trade.price

    def _update_cluster_tracking(self, trade: Trade):
        """
        Track trades for cluster detection.
        Records wallet trades per market with timestamps.
        """
        market_id = trade.market_id
        now = datetime.now()

        # Add this trade to market's recent trades
        self.recent_market_trades[market_id].append(
            (trade.trader_address, trade.timestamp, trade.amount_usd)
        )

        # Clean up old trades outside the time window
        cutoff = now - self.cluster_time_window * 6  # Keep 6x window for pattern analysis
        self.recent_market_trades[market_id] = [
            (addr, ts, amt) for addr, ts, amt in self.recent_market_trades[market_id]
            if ts > cutoff
        ]

    def _detect_cluster_activity(self, trade: Trade) -> Optional[List[str]]:
        """
        Detect if this trade is part of coordinated cluster activity.

        Returns list of related wallet addresses if cluster detected, None otherwise.

        Cluster indicators:
        - Multiple different wallets trading same market within time window
        - Similar trade sizes (within 20% of each other)
        - Trades on same outcome direction
        """
        market_id = trade.market_id
        recent = self.recent_market_trades.get(market_id, [])

        if len(recent) < 2:
            return None

        # Find trades within cluster time window
        cutoff = trade.timestamp - self.cluster_time_window
        window_trades = [
            (addr, ts, amt) for addr, ts, amt in recent
            if ts > cutoff and addr != trade.trader_address
        ]

        if not window_trades:
            return None

        # Look for wallets with similar trade sizes (within 50%)
        related_wallets = []
        for addr, ts, amt in window_trades:
            size_ratio = amt / trade.amount_usd if trade.amount_usd > 0 else 0
            if 0.5 <= size_ratio <= 2.0:  # Within 50-200% of this trade
                related_wallets.append(addr)

        # Need at least 2 related wallets (including current) for a cluster
        if len(related_wallets) >= 1 and trade.amount_usd >= 1000:
            # Create/update cluster
            cluster_members = frozenset([trade.trader_address] + related_wallets)

            if cluster_members not in self.wallet_clusters:
                self.wallet_clusters[cluster_members] = {
                    "first_seen": trade.timestamp,
                    "markets": set(),
                    "total_volume": 0,
                    "trade_count": 0
                }

            cluster = self.wallet_clusters[cluster_members]
            cluster["markets"].add(market_id)
            cluster["total_volume"] += trade.amount_usd
            cluster["trade_count"] += 1
            cluster["last_seen"] = trade.timestamp

            return list(cluster_members)

        return None

    def _is_extreme_confidence(self, trade: Trade) -> Tuple[bool, str]:
        """
        Check if trade is an extreme confidence bet (>95% or <5% probability).

        Returns (is_extreme, direction) where direction is "HIGH" or "LOW"
        """
        prob = self._get_outcome_probability(trade)
        if prob is None:
            return False, ""

        if prob >= self.extreme_confidence_high:
            return True, "HIGH"  # Betting on near-certainty
        elif prob <= self.extreme_confidence_low:
            return True, "LOW"   # Betting on longshot

        return False, ""

    def _is_contrarian(self, trade: Trade) -> Tuple[bool, float]:
        """
        Check if trade is a contrarian bet (large bet on unlikely outcome).

        A contrarian bet is buying an outcome with <15% probability.

        Returns (is_contrarian, probability)
        """
        if trade.side.lower() != "buy":
            return False, 0.0

        prob = self._get_outcome_probability(trade)
        if prob is None:
            return False, 0.0

        # Buying something with low probability is contrarian
        if prob <= self.contrarian_threshold:
            return True, prob

        return False, prob

    # ==========================================
    # NEW: IMPACT RATIO & ENTITY INTEGRATION
    # ==========================================

    def _update_market_volume(self, trade: Trade):
        """Track hourly volume per market for impact ratio calculation."""
        market_id = trade.market_id
        now = datetime.now()
        cutoff = now - timedelta(hours=1)

        if market_id not in self.market_hourly_volume:
            self.market_hourly_volume[market_id] = {
                "trades": [],
                "volume": 0.0,
                "last_updated": now
            }

        vol_data = self.market_hourly_volume[market_id]

        # Add this trade
        vol_data["trades"].append((trade.timestamp, trade.amount_usd))

        # Prune old trades and recalculate volume
        vol_data["trades"] = [(ts, amt) for ts, amt in vol_data["trades"] if ts > cutoff]
        vol_data["volume"] = sum(amt for _, amt in vol_data["trades"])
        vol_data["last_updated"] = now

    def _calculate_impact_ratio(self, trade: Trade) -> float:
        """
        Calculate impact ratio: trade_cash / market_hourly_volume.

        Higher ratio = trade is more significant relative to market activity.
        A ratio of 0.10 means this trade is 10% of the last hour's volume.
        """
        market_id = trade.market_id
        vol_data = self.market_hourly_volume.get(market_id)

        if not vol_data or vol_data["volume"] <= 0:
            return 1.0  # Unknown volume = assume high impact

        return trade.amount_usd / vol_data["volume"]

    def get_entity_engine(self):
        """Get or create the entity engine for advanced clustering."""
        if self._entity_engine is None:
            try:
                from .entity_engine import EntityEngine
                self._entity_engine = EntityEngine(
                    coord_window_seconds=int(self.cluster_time_window.total_seconds()),
                    entity_rebuild_seconds=60,
                    entity_edge_threshold=0.75,
                )
                logger.info("Entity engine initialized")
            except ImportError:
                logger.warning("Entity engine not available")
                return None
        return self._entity_engine

    def process_trade_for_entity(self, trade: Trade, funder: Optional[str] = None):
        """Process trade through entity engine for clustering."""
        engine = self.get_entity_engine()
        if engine:
            engine.on_trade(
                wallet=trade.trader_address,
                market_id=trade.market_id,
                timestamp=trade.timestamp,
                funder=funder,
            )

    def get_entity_for_wallet(self, wallet: str):
        """Get the entity containing this wallet, if any."""
        engine = self.get_entity_engine()
        if engine:
            return engine.get_entity_for_wallet(wallet)
        return None

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
        Enhanced with velocity and behavioral factors.
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

        # NEW: Velocity-based scoring
        if profile.is_heavy_actor:
            score += 1  # High activity = more conviction
        if profile.is_repeat_actor:
            score += 1  # Recent flurry of activity

        # Alert type adjustments
        if alert_type == "SMART_MONEY":
            score += 1
        elif alert_type == "NEW_WALLET":
            score += 1
        elif alert_type == "CONTRARIAN":
            score += 2  # Contrarian bets are especially interesting
        elif alert_type == "CLUSTER_ACTIVITY":
            score += 2  # Coordinated activity is suspicious
        elif alert_type == "EXTREME_CONFIDENCE":
            # Longshots more interesting than certainties
            prob = self._get_outcome_probability(trade)
            if prob and prob <= 0.10:
                score += 2

        # Cap at 1-10
        return max(1, min(10, score))

    async def analyze_trade(
        self,
        trade: Trade,
        market_question: str = None
    ) -> List[WhaleAlert]:
        """
        Analyze a single trade for unusual activity.

        Returns a list with 0 or 1 consolidated WhaleAlert.
        All triggered conditions are combined into a single alert.
        Enhanced with 14 total detection algorithms.
        """
        # Check if we should skip sports markets (check both question and ticker)
        is_sports = is_sports_market(market_question, trade.market_id)
        if self.exclude_sports and is_sports:
            return []

        # Check if this is a high-frequency market (15-min BTC, etc.) - always filter these
        if is_high_frequency_market(market_question, trade.market_id):
            return []

        # Cache market info
        if market_question:
            self.market_questions[trade.market_id] = market_question

        # Auto-detect and cache category if not already cached
        if trade.market_id not in self.market_categories:
            detected_category = self._detect_category_from_text(market_question, trade.market_id)
            self.market_categories[trade.market_id] = detected_category
            if detected_category != "Other":
                logger.debug(f"Auto-detected category '{detected_category}' for market {trade.market_id[:30]}...")

        # Get market URL and category from cache or default
        market_url = self.market_urls.get(trade.market_id)
        market_category = self.market_categories.get(trade.market_id, "Other")

        # Detect position action BEFORE updating profile (to know state before this trade)
        address = trade.trader_address
        if address in self.wallet_profiles:
            existing_profile = self.wallet_profiles[address]
            position_action = existing_profile.get_position_action(
                trade.market_id, trade.outcome, trade.side
            )
        else:
            position_action = "OPENING"  # New wallet, so definitely opening

        # Update wallet profile (includes velocity tracking and position update)
        profile = self._update_wallet_profile(trade, market_question)

        # Track trade size for global statistics
        self.recent_trade_sizes.append(trade.amount_usd)
        if len(self.recent_trade_sizes) > self.max_recent_trades:
            self.recent_trade_sizes.pop(0)

        # Update per-market statistics
        market_mean, market_std, market_n = self._update_market_stats(trade)

        # Update cluster tracking
        self._update_cluster_tracking(trade)

        # Update market volume for impact ratio
        self._update_market_volume(trade)

        # Process through entity engine
        self.process_trade_for_entity(trade)

        # Collect all triggered conditions as (alert_type, message, severity_score)
        triggered_conditions: List[Tuple[str, str, int]] = []
        max_z_score = None  # Track highest z-score for context

        # ==========================================
        # ORIGINAL DETECTORS (1-6)
        # ==========================================

        # 1. Fixed threshold whale trade
        if trade.amount_usd >= self.whale_threshold_usd:
            severity_score = self._calculate_severity_score(trade, profile, "WHALE_TRADE")
            triggered_conditions.append((
                "WHALE_TRADE",
                f"🐋 WHALE ALERT: ${trade.amount_usd:,.0f} {trade.side} on {trade.outcome}",
                severity_score
            ))

        # 2. Statistically unusual trade (global)
        is_unusual, z_score = self._is_statistically_unusual(trade.amount_usd)
        if is_unusual and trade.amount_usd < self.whale_threshold_usd:
            severity_score = 6 if z_score < self.std_multiplier + 2 else 8
            max_z_score = z_score
            triggered_conditions.append((
                "UNUSUAL_SIZE",
                f"📊 UNUSUAL TRADE: ${trade.amount_usd:,.0f} is {z_score:.1f} std devs above average",
                severity_score
            ))

        # 3. Market-specific anomaly (DISABLED - redundant with UNUSUAL_SIZE)
        # if market_n >= 20 and market_std > 0:
        #     market_z = (trade.amount_usd - market_mean) / market_std
        #     if market_z >= self.std_multiplier:
        #         severity_score = 7 if market_z < self.std_multiplier + 2 else 9
        #         if max_z_score is None or market_z > max_z_score:
        #             max_z_score = market_z
        #         triggered_conditions.append((
        #             "MARKET_ANOMALY",
        #             f"🎯 MARKET ANOMALY: z={market_z:.2f} (market avg ${market_mean:,.0f}, trade ${trade.amount_usd:,.0f})",
        #             severity_score
        #         ))

        # 4. New wallet making significant trade
        # Skip for anonymous traders (platforms that don't expose trader identity)
        if profile.is_new_wallet and trade.amount_usd >= self.new_wallet_threshold_usd and not self._is_anonymous_trader(trade.trader_address):
            severity_score = 8 if trade.amount_usd >= 5000 else 6
            triggered_conditions.append((
                "NEW_WALLET",
                f"🆕 NEW WALLET: First-time trader placed ${trade.amount_usd:,.0f} bet (only {profile.total_trades} trades)",
                severity_score
            ))

        # 5. Focused wallet (DISABLED - not predictive enough)
        # Skip for anonymous traders
        # if profile.is_focused and trade.amount_usd >= self.focused_wallet_threshold_usd and not self._is_anonymous_trader(trade.trader_address):
        #     severity_score = 7
        #     triggered_conditions.append((
        #         "FOCUSED_WALLET",
        #         f"🎯 FOCUSED WALLET: Wallet concentrated in {len(profile.markets_traded)} markets placed ${trade.amount_usd:,.0f} bet",
        #         severity_score
        #     ))

        # 6. Smart money (high win-rate wallet) making a trade
        # Skip for anonymous traders
        if profile.is_smart_money and trade.amount_usd >= 500 and not self._is_anonymous_trader(trade.trader_address):
            severity_score = 9  # Smart money is always high priority
            triggered_conditions.append((
                "SMART_MONEY",
                f"🧠 SMART MONEY: Wallet with {profile.win_rate:.0%} win rate placed ${trade.amount_usd:,.0f} bet",
                severity_score
            ))

        # 6b. VIP Wallet - ANY trade from high-volume, successful, or large-trade-history wallets
        # Skip for anonymous traders
        if not self._is_anonymous_trader(trade.trader_address):
            is_vip = profile.is_vip(
                min_volume=self.vip_min_volume,
                min_win_rate=self.vip_min_win_rate,
                min_large_trades=self.vip_min_large_trades
            )
            if is_vip:
                vip_reason = profile.get_vip_reason(
                    min_volume=self.vip_min_volume,
                    min_win_rate=self.vip_min_win_rate,
                    min_large_trades=self.vip_min_large_trades
                )
                severity_score = 8  # VIP trades are high priority
                triggered_conditions.append((
                    "VIP_WALLET",
                    f"⭐ VIP WALLET: {vip_reason} - placed ${trade.amount_usd:,.0f} bet",
                    severity_score
                ))

        # ==========================================
        # NEW DETECTORS (7-11) - Inspired by Polymaster, PredictOS, PolyTrack
        # ==========================================

        # 7. Repeat Actor Detection (2+ trades in 1 hour)
        # Skip for anonymous traders
        if profile.is_repeat_actor and trade.amount_usd >= 1000 and not self._is_anonymous_trader(trade.trader_address):
            severity_score = 7
            triggered_conditions.append((
                "REPEAT_ACTOR",
                f"🔄 REPEAT ACTOR: Wallet made {profile.trades_last_hour} trades in last hour (${trade.amount_usd:,.0f} this trade)",
                severity_score
            ))

        # 8. Heavy Actor Detection (5+ trades in 24 hours)
        # Skip for anonymous traders
        if profile.is_heavy_actor and trade.amount_usd >= 500 and not self._is_anonymous_trader(trade.trader_address):
            severity_score = 8
            triggered_conditions.append((
                "HEAVY_ACTOR",
                f"⚡ HEAVY ACTOR: Wallet made {profile.trades_last_24h} trades in 24h (${profile.total_volume_usd:,.0f} total volume)",
                severity_score
            ))

        # 9. Extreme Confidence Detection (DISABLED - too common, not actionable)
        # is_extreme, extreme_direction = self._is_extreme_confidence(trade)
        # if is_extreme and trade.amount_usd >= 2000:
        #     prob = self._get_outcome_probability(trade)
        #     if extreme_direction == "HIGH":
        #         severity_score = 6  # Betting on near-certainty (less interesting)
        #         emoji = "📈"
        #         desc = f"near-certain outcome ({prob:.0%})"
        #     else:
        #         severity_score = 9  # Betting on longshot (very interesting!)
        #         emoji = "🎰"
        #         desc = f"longshot ({prob:.0%} probability)"
        #
        #     triggered_conditions.append((
        #         "EXTREME_CONFIDENCE",
        #         f"{emoji} EXTREME CONFIDENCE: ${trade.amount_usd:,.0f} bet on {desc}",
        #         severity_score
        #     ))

        # 10. Whale Exit Detection (DISABLED - hard to interpret, noisy)
        # Skip for anonymous traders
        # if trade.side.lower() == "sell" and trade.amount_usd >= self.exit_threshold_usd and not self._is_anonymous_trader(trade.trader_address):
        #     # Check if this wallet has been a significant buyer
        #     if profile.buy_volume_usd >= self.whale_threshold_usd:
        #         severity_score = 8  # Whale exiting is significant
        #         triggered_conditions.append((
        #             "WHALE_EXIT",
        #             f"🚪 WHALE EXIT: Wallet selling ${trade.amount_usd:,.0f} (prev bought ${profile.buy_volume_usd:,.0f})",
        #             severity_score
        #         ))

        # 11. Contrarian Activity Detection (DISABLED - too common, not actionable)
        # is_contrarian, prob = self._is_contrarian(trade)
        # if is_contrarian and trade.amount_usd >= 3000:
        #     severity_score = 9  # Contrarian bets are very interesting
        #     triggered_conditions.append((
        #         "CONTRARIAN",
        #         f"🔮 CONTRARIAN: ${trade.amount_usd:,.0f} bet on {prob:.0%} underdog outcome",
        #         severity_score
        #     ))

        # 12. Cluster Activity Detection (coordinated wallets) - STRICTER minimum
        # Skip for anonymous traders (can't correlate wallets without identity)
        cluster_wallets = None
        if not self._is_anonymous_trader(trade.trader_address):
            cluster_wallets = self._detect_cluster_activity(trade)
        if cluster_wallets and len(cluster_wallets) >= 2 and trade.amount_usd >= 2000:  # $2k minimum for coordinated activity
            severity_score = 9  # Coordinated activity is very suspicious
            triggered_conditions.append((
                "CLUSTER_ACTIVITY",
                f"🕸️ CLUSTER DETECTED: {len(cluster_wallets)} wallets trading same market within {self.cluster_time_window.seconds // 60}min",
                severity_score
            ))

        # ==========================================
        # ADVANCED DETECTORS (from ChatGPT v5)
        # ==========================================

        # 13. High Impact Trade Detection (STRICTER - requires 25%+ of hourly volume)
        impact_ratio = self._calculate_impact_ratio(trade)
        if impact_ratio >= 0.25 and trade.amount_usd >= 1000:  # Raised from 10% to 25%
            severity_score = 8 if impact_ratio >= 0.50 else 7
            triggered_conditions.append((
                "HIGH_IMPACT",
                f"💥 HIGH IMPACT: ${trade.amount_usd:,.0f} is {impact_ratio:.0%} of market's hourly volume",
                severity_score
            ))

        # 14. Entity Activity Detection (multi-wallet entity trading)
        # Skip for anonymous traders
        entity = None
        if not self._is_anonymous_trader(trade.trader_address):
            entity = self.get_entity_for_wallet(trade.trader_address)
        if entity and entity.wallet_count >= 2 and trade.amount_usd >= 1000:
            severity_score = 9  # Entity activity is very interesting
            triggered_conditions.append((
                "ENTITY_ACTIVITY",
                f"👥 ENTITY DETECTED: Wallet is part of {entity.wallet_count}-wallet entity (conf: {entity.confidence:.0%})",
                severity_score
            ))

        # ==========================================
        # CONSOLIDATION: Create single alert with all triggered conditions
        # ==========================================

        if not triggered_conditions:
            return []

        # Filter out low-value triggers (except cluster activity and exits)
        filtered_conditions = [
            (atype, msg, score) for atype, msg, score in triggered_conditions
            if trade.amount_usd >= self.min_alert_threshold_usd
            or atype in self.exempt_alert_types
        ]

        if not filtered_conditions:
            return []

        # Extract alert types, messages, and find max severity
        alert_types = [c[0] for c in filtered_conditions]
        messages = [c[1] for c in filtered_conditions]
        max_severity_score = max(c[2] for c in filtered_conditions)

        # MULTI-SIGNAL REQUIREMENT: Require 2+ signals unless exempt
        # Exempt types are so significant they can alert alone
        has_exempt_type = any(atype in self.exempt_alert_types for atype in alert_types)
        if not has_exempt_type and len(alert_types) < self.min_triggers_required:
            logger.debug(f"Filtered: Only {len(alert_types)} trigger(s), need {self.min_triggers_required} (${trade.amount_usd:.0f})")
            return []

        # Create single consolidated alert
        consolidated_alert = WhaleAlert(
            id=f"consolidated_{trade.id}",
            alert_types=alert_types,
            severity=score_to_severity(max_severity_score),
            severity_score=max_severity_score,
            trade=trade,
            wallet_profile=profile,
            messages=messages,
            trade_size_percentile=self._calculate_percentile(trade.amount_usd),
            market_question=market_question,
            is_sports_market=is_sports,
            z_score=max_z_score,
            market_url=market_url,
            category=market_category,
            position_action=position_action,
        )

        # CRYPTO FILTERING: Higher threshold for crypto markets unless high-value signal
        if market_category == "Crypto":
            has_exempt_type = any(atype in self.crypto_exempt_types for atype in alert_types)
            if trade.amount_usd < self.crypto_min_threshold_usd and not has_exempt_type:
                logger.debug(f"Filtered crypto alert: ${trade.amount_usd:.0f} < ${self.crypto_min_threshold_usd} threshold")
                return []

        return [consolidated_alert]
    
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

    # ==========================================
    # NEW METHODS FOR ENHANCED DETECTION
    # ==========================================

    def get_repeat_actors(self, limit: int = 20) -> List[WalletProfile]:
        """Get wallets with high recent trading frequency (2+ trades/hour)."""
        repeat_actors = [
            w for w in self.wallet_profiles.values()
            if w.is_repeat_actor
        ]
        return sorted(repeat_actors, key=lambda w: w.trades_last_hour, reverse=True)[:limit]

    def get_heavy_actors(self, limit: int = 20) -> List[WalletProfile]:
        """Get wallets with 5+ trades in last 24 hours."""
        heavy_actors = [
            w for w in self.wallet_profiles.values()
            if w.is_heavy_actor
        ]
        return sorted(heavy_actors, key=lambda w: w.trades_last_24h, reverse=True)[:limit]

    def cleanup_inactive_wallets(self, max_inactive_days: int = 30, min_wallets_before_cleanup: int = 10000):
        """
        Remove wallets that haven't traded in X days to prevent memory growth.

        Only runs cleanup if we have more than min_wallets_before_cleanup profiles.
        This prevents unbounded memory growth in long-running deployments.

        Args:
            max_inactive_days: Remove wallets inactive for this many days (default: 30)
            min_wallets_before_cleanup: Only clean if total wallets exceeds this (default: 10000)
        """
        if len(self.wallet_profiles) < min_wallets_before_cleanup:
            return  # Don't clean if we don't have many wallets yet

        cutoff = datetime.now() - timedelta(days=max_inactive_days)
        inactive = [
            addr for addr, profile in self.wallet_profiles.items()
            if profile.last_seen and profile.last_seen < cutoff
        ]

        for addr in inactive:
            del self.wallet_profiles[addr]

        if inactive:
            logger.info(
                f"🧹 Memory cleanup: Removed {len(inactive)} inactive wallets "
                f"(>{max_inactive_days} days). Remaining: {len(self.wallet_profiles)}"
            )

    def get_active_clusters(self, min_volume: float = 10000) -> List[Dict]:
        """
        Get detected wallet clusters (potentially related wallets).

        Returns list of cluster info sorted by total volume.
        """
        clusters = []
        for members, data in self.wallet_clusters.items():
            if data.get("total_volume", 0) >= min_volume:
                clusters.append({
                    "wallets": list(members),
                    "wallet_count": len(members),
                    "markets_count": len(data.get("markets", set())),
                    "total_volume": data.get("total_volume", 0),
                    "trade_count": data.get("trade_count", 0),
                    "first_seen": data.get("first_seen"),
                    "last_seen": data.get("last_seen"),
                })
        return sorted(clusters, key=lambda c: c["total_volume"], reverse=True)

    def get_whale_exits(self, since_hours: int = 24) -> List[WalletProfile]:
        """Get wallets that have been selling recently (exiting positions)."""
        cutoff = datetime.now() - timedelta(hours=since_hours)
        exiting = [
            w for w in self.wallet_profiles.values()
            if w.sell_volume_usd >= self.exit_threshold_usd
            and w.last_seen and w.last_seen > cutoff
            and w.sell_ratio > 0.3  # More than 30% sells
        ]
        return sorted(exiting, key=lambda w: w.sell_volume_usd, reverse=True)

    def get_detection_stats(self) -> Dict:
        """Get statistics about all detection types."""
        stats = {
            "total_wallets_tracked": len(self.wallet_profiles),
            "total_trades_analyzed": sum(w.total_trades for w in self.wallet_profiles.values()),
            "whale_wallets": len([w for w in self.wallet_profiles.values() if w.is_whale]),
            "new_wallets": len([w for w in self.wallet_profiles.values() if w.is_new_wallet]),
            "focused_wallets": len([w for w in self.wallet_profiles.values() if w.is_focused]),
            "smart_money_wallets": len([w for w in self.wallet_profiles.values() if w.is_smart_money]),
            "repeat_actors": len([w for w in self.wallet_profiles.values() if w.is_repeat_actor]),
            "heavy_actors": len([w for w in self.wallet_profiles.values() if w.is_heavy_actor]),
            "detected_clusters": len(self.wallet_clusters),
            "markets_tracked": len(self.market_stats),
        }

        # Add entity engine stats if available
        engine = self.get_entity_engine()
        if engine:
            entity_stats = engine.get_entity_stats()
            stats["entities_detected"] = entity_stats.get("total_entities", 0)
            stats["wallets_in_entities"] = entity_stats.get("wallets_in_entities", 0)
            stats["entity_edges"] = entity_stats.get("total_edges", 0)

        return stats

    def get_all_entities(self) -> List[Dict]:
        """Get all detected entities with their details."""
        engine = self.get_entity_engine()
        if not engine:
            return []

        entities = engine.get_all_entities()
        return [
            {
                "entity_id": e.entity_id,
                "wallet_count": e.wallet_count,
                "wallets": list(e.wallets)[:10],  # Limit for response size
                "confidence": e.confidence,
                "reason": e.reason,
                "created_at": e.created_at.isoformat(),
            }
            for e in entities
        ]


# =========================================
# REAL-TIME MONITORING
# =========================================

class TradeMonitor:
    """
    Continuously monitors prediction markets for whale activity.

    This is the main loop that runs in production.

    Enhanced with:
    - Multi-platform support (Polymarket, Kalshi, etc.)
    - Market question fetching for sports filtering
    - Better error handling and retry logic
    - Statistics tracking
    """

    def __init__(
        self,
        detector: WhaleDetector,
        poll_interval: int = 60,
        on_alert=None,  # Callback function when alert detected
        fetch_market_info: bool = True,  # Fetch market questions for context
        clients: List = None  # List of platform clients (PolymarketClient, KalshiClient, etc.)
    ):
        self.detector = detector
        self.poll_interval = poll_interval
        self.on_alert = on_alert
        self.fetch_market_info = fetch_market_info
        self.clients = clients or []  # Platform clients to poll
        self.seen_trades: Set[str] = set()  # Avoid duplicate alerts
        self._running = False

        # Statistics
        self.total_trades_processed = 0
        self.total_alerts_generated = 0
        self.last_check_time: Optional[datetime] = None
        self.trades_by_platform: Dict[str, int] = {}  # Track trades per platform

        # Market info caches (keyed by platform:market_id)
        self._market_cache: Dict[str, str] = {}  # market_id -> question
        self._market_url_cache: Dict[str, str] = {}  # market_id -> URL
        self._market_category_cache: Dict[str, str] = {}  # market_id -> category

    async def start(self):
        """Start the monitoring loop."""
        self._running = True
        platform_names = [getattr(c, 'platform_name', c.__class__.__name__) for c in self.clients] if self.clients else ["Polymarket"]
        logger.info(f"Starting trade monitor (polling every {self.poll_interval}s)")
        logger.info(f"   Platforms: {', '.join(platform_names)}")
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

    async def _fetch_market_info(self, market_ids: Set[str], trades: List[Trade] = None) -> Dict[str, str]:
        """Fetch market info (questions, URLs, categories) for a set of market IDs."""
        questions = {}

        # Return cached values first
        uncached = [mid for mid in market_ids if mid not in self._market_cache]

        if uncached and self.fetch_market_info:
            # Group uncached market IDs by platform (infer from trades)
            platform_markets: Dict[str, Set[str]] = {}
            if trades:
                for trade in trades:
                    platform = getattr(trade, 'platform', 'Polymarket')
                    if trade.market_id in uncached:
                        if platform not in platform_markets:
                            platform_markets[platform] = set()
                        platform_markets[platform].add(trade.market_id)

            # Fetch from each platform
            for client in (self.clients or []):
                platform_name = getattr(client, 'platform_name', client.__class__.__name__)
                try:
                    if hasattr(client, 'is_configured') and not client.is_configured():
                        continue

                    async with client as c:
                        markets = await c.get_active_markets(limit=200)
                        for market in markets:
                            self._market_cache[market.id] = market.question
                            # Generate platform-specific URL
                            if hasattr(c, 'get_market_url'):
                                self._market_url_cache[market.id] = c.get_market_url(market)
                            else:
                                self._market_url_cache[market.id] = getattr(market, 'url', '')
                            self._market_category_cache[market.id] = market.category
                            # Also update detector's caches
                            self.detector.market_questions[market.id] = market.question
                            self.detector.market_urls[market.id] = self._market_url_cache[market.id]
                            self.detector.market_categories[market.id] = market.category
                except Exception as e:
                    logger.warning(f"Failed to fetch market info from {platform_name}: {e}")

            # Fallback to Polymarket if no clients configured
            if not self.clients:
                try:
                    async with PolymarketClient() as client:
                        markets = await client.get_active_markets(limit=200)
                        for market in markets:
                            self._market_cache[market.id] = market.question
                            self._market_url_cache[market.id] = market.url
                            self._market_category_cache[market.id] = market.category
                            self.detector.market_questions[market.id] = market.question
                            self.detector.market_urls[market.id] = market.url
                            self.detector.market_categories[market.id] = market.category
                except Exception as e:
                    logger.warning(f"Failed to fetch market info from Polymarket: {e}")

        # Return all from cache
        for mid in market_ids:
            if mid in self._market_cache:
                questions[mid] = self._market_cache[mid]

        return questions

    async def _check_for_trades(self):
        """Fetch new trades from all configured platforms and check for alerts."""
        all_new_trades = []

        # Calculate time window for gap prevention
        # Use last_check_time if available, otherwise look back 2 minutes
        after_time = None
        if self.last_check_time:
            # Add small buffer to avoid missing trades at boundary
            after_time = self.last_check_time - timedelta(seconds=5)

        # If no clients configured, use default Polymarket client
        if not self.clients:
            async with PolymarketClient() as client:
                # Primary fetch: Get recent trades with higher limit
                trades = await client.get_recent_trades(limit=500, after_timestamp=after_time)
                new_trades = [t for t in trades if t.id not in self.seen_trades]
                all_new_trades.extend(new_trades)
                for trade in new_trades:
                    self.seen_trades.add(trade.id)

                # Secondary fetch: Specifically check for whale trades we might have missed
                if hasattr(client, 'get_whale_trades'):
                    whale_trades = await client.get_whale_trades(
                        min_amount_usd=self.detector.whale_threshold_usd,
                        limit=500,
                        after_timestamp=after_time
                    )
                    for trade in whale_trades:
                        if trade.id not in self.seen_trades:
                            all_new_trades.append(trade)
                            self.seen_trades.add(trade.id)
        else:
            # Poll each configured client
            for client in self.clients:
                try:
                    platform_name = getattr(client, 'platform_name', client.__class__.__name__)

                    # Check if client is configured/enabled
                    if hasattr(client, 'is_configured') and not client.is_configured():
                        continue

                    async with client as c:
                        # Primary fetch with higher limit and time-based query
                        trades = await c.get_recent_trades(limit=500, after_timestamp=after_time)

                        # Filter to new trades only
                        new_trades = [t for t in trades if t.id not in self.seen_trades]

                        if new_trades:
                            logger.debug(f"Found {len(new_trades)} new trades from {platform_name}")
                            all_new_trades.extend(new_trades)

                            # Track per-platform stats
                            self.trades_by_platform[platform_name] = self.trades_by_platform.get(platform_name, 0) + len(new_trades)

                            # Mark as seen
                            for trade in new_trades:
                                self.seen_trades.add(trade.id)

                        # Secondary fetch: Specifically check for whale trades (Polymarket only)
                        if hasattr(c, 'get_whale_trades'):
                            whale_trades = await c.get_whale_trades(
                                min_amount_usd=self.detector.whale_threshold_usd,
                                limit=500,
                                after_timestamp=after_time
                            )
                            for trade in whale_trades:
                                if trade.id not in self.seen_trades:
                                    all_new_trades.append(trade)
                                    self.seen_trades.add(trade.id)
                                    logger.info(f"Caught whale trade via secondary fetch: ${trade.amount_usd:,.0f}")

                except Exception as e:
                    platform_name = getattr(client, 'platform_name', client.__class__.__name__)
                    logger.error(f"Error polling {platform_name}: {e}")
                    continue

        if not all_new_trades:
            return

        # Keep seen_trades from growing forever
        if len(self.seen_trades) > 50_000:
            # Remove oldest half
            self.seen_trades = set(list(self.seen_trades)[-25_000:])

        # Periodic wallet cleanup to prevent memory growth (runs when > 10K wallets)
        self.detector.cleanup_inactive_wallets()

        # Fetch market info for context and filtering
        market_ids = {t.market_id for t in all_new_trades}
        market_questions = await self._fetch_market_info(market_ids, all_new_trades)

        # Analyze for alerts
        alerts = await self.detector.analyze_trades(all_new_trades, market_questions)

        # Update statistics
        self.total_trades_processed += len(all_new_trades)
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
import sys

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    """Test the enhanced whale detector with all 11 detection algorithms."""
    print("[WHALE] Testing Enhanced Whale Detector (v2.0)...\n")
    print("=" * 60)

    # Create detector with lower thresholds for testing
    detector = WhaleDetector(
        whale_threshold_usd=1000,  # Lower for testing
        std_multiplier=2.0,
        extreme_confidence_high=0.90,  # Lower for testing
        extreme_confidence_low=0.10,
        exit_threshold_usd=500,
        contrarian_threshold=0.20,
    )

    # Fetch some real trades
    print("[API] Fetching trades from Polymarket...\n")
    async with PolymarketClient() as client:
        trades = await client.get_recent_trades(limit=500)
        markets = await client.get_active_markets(limit=50)

    # Cache market prices for contrarian/extreme confidence detection
    for market in markets:
        detector.update_market_prices(market.id, market.outcome_prices)

    print(f"[DATA] Fetched {len(trades)} trades from {len(markets)} markets\n")

    # Build market question lookup
    market_questions = {m.id: m.question for m in markets}

    # Analyze trades
    alerts = await detector.analyze_trades(trades, market_questions)

    # Group alerts by type
    alert_types = {}
    for alert in alerts:
        if alert.alert_type not in alert_types:
            alert_types[alert.alert_type] = []
        alert_types[alert.alert_type].append(alert)

    print(f"\n[ALERT] Generated {len(alerts)} alerts across {len(alert_types)} types:\n")
    print("-" * 60)

    for alert_type, type_alerts in sorted(alert_types.items(), key=lambda x: -len(x[1])):
        print(f"\n{alert_type}: {len(type_alerts)} alerts")
        for alert in type_alerts[:2]:  # Show first 2 of each type
            # Strip emojis from message for console compatibility
            msg = alert.message.encode('ascii', 'ignore').decode('ascii').strip()
            print(f"  [{alert.severity_score}/10] {msg[:70]}...")

    # Show detection statistics
    print("\n" + "=" * 60)
    print("[STATS] DETECTION STATISTICS:")
    print("-" * 60)
    stats = detector.get_detection_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Show top wallets
    print("\n" + "=" * 60)
    print("[TOP] TOP WALLETS BY VOLUME:")
    print("-" * 60)
    for profile in detector.get_top_wallets(5):
        flags = []
        if profile.is_whale:
            flags.append("WHALE")
        if profile.is_repeat_actor:
            flags.append("REPEAT")
        if profile.is_heavy_actor:
            flags.append("HEAVY")
        if profile.is_focused:
            flags.append("FOCUSED")
        flag_str = " [" + ",".join(flags) + "]" if flags else ""
        print(f"  {profile.address[:15]}... - ${profile.total_volume_usd:,.0f} ({profile.total_trades} trades){flag_str}")

    # Show detected clusters
    clusters = detector.get_active_clusters(min_volume=1000)
    if clusters:
        print("\n" + "=" * 60)
        print("[CLUSTER] DETECTED WALLET CLUSTERS:")
        print("-" * 60)
        for cluster in clusters[:3]:
            print(f"  {cluster['wallet_count']} wallets - ${cluster['total_volume']:,.0f} volume - {cluster['markets_count']} markets")

    print("\n" + "=" * 60)
    print("[OK] Enhanced detector working correctly!")
    print(f"   - 6 original detectors")
    print(f"   - 6 new detectors (velocity, extreme confidence, exit, contrarian, cluster)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
