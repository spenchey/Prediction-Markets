"""
Position & Accumulation Tracker

Tracks whale position building over time to catch slow accumulation strategies.

Features:
1. Rolling 24h/7d wallet volume tracking - flags wallets accumulating >$50K
2. Market position monitoring - tracks top holders per market
3. New large position alerts - alerts when someone builds a big position

This complements real-time trade alerts by catching gradual accumulation.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import httpx
from loguru import logger


@dataclass
class WalletAccumulation:
    """Tracks a wallet's accumulation over time."""
    wallet: str
    name: Optional[str] = None
    pseudonym: Optional[str] = None
    
    # Rolling volume tracking
    volume_24h: float = 0.0
    volume_7d: float = 0.0
    
    # Position tracking by market
    positions: Dict[str, Dict] = field(default_factory=dict)  # market_id -> {shares, avg_price, side}
    
    # Trade history for rolling windows
    trades_24h: List[Dict] = field(default_factory=list)
    trades_7d: List[Dict] = field(default_factory=list)
    
    last_updated: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    
    def add_trade(self, trade: Dict) -> None:
        """Add a trade and update rolling volumes."""
        now = datetime.now()
        ts = datetime.fromtimestamp(trade.get('timestamp', now.timestamp()))
        size = float(trade.get('size', 0))
        price = float(trade.get('price', 0))
        usd_value = size * price
        market_id = trade.get('conditionId', trade.get('market_id', 'unknown'))
        outcome = trade.get('outcome', 'unknown')
        side = trade.get('side', 'BUY')
        
        trade_record = {
            'timestamp': ts,
            'usd_value': usd_value,
            'shares': size,
            'price': price,
            'market_id': market_id,
            'outcome': outcome,
            'side': side,
        }
        
        # Update name/pseudonym if available
        if trade.get('name'):
            self.name = trade['name']
        if trade.get('pseudonym'):
            self.pseudonym = trade['pseudonym']
        
        # Add to rolling windows
        self.trades_24h.append(trade_record)
        self.trades_7d.append(trade_record)
        
        # Update position for this market
        if market_id not in self.positions:
            self.positions[market_id] = {
                'shares': 0,
                'total_cost': 0,
                'outcome': outcome,
                'trade_count': 0,
            }
        
        pos = self.positions[market_id]
        if side == 'BUY':
            pos['shares'] += size
            pos['total_cost'] += usd_value
        else:  # SELL
            pos['shares'] -= size
            pos['total_cost'] -= usd_value
        pos['trade_count'] += 1
        pos['avg_price'] = pos['total_cost'] / pos['shares'] if pos['shares'] > 0 else 0
        
        self.last_updated = now
        if self.first_seen is None:
            self.first_seen = ts
    
    def cleanup_old_trades(self) -> None:
        """Remove trades outside rolling windows."""
        now = datetime.now()
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)
        
        self.trades_24h = [t for t in self.trades_24h if t['timestamp'] > cutoff_24h]
        self.trades_7d = [t for t in self.trades_7d if t['timestamp'] > cutoff_7d]
        
        # Recalculate volumes
        self.volume_24h = sum(t['usd_value'] for t in self.trades_24h)
        self.volume_7d = sum(t['usd_value'] for t in self.trades_7d)


@dataclass
class MarketPositions:
    """Tracks top positions for a specific market."""
    market_id: str
    question: str = ""
    
    # Top holders by shares
    top_yes_holders: List[Dict] = field(default_factory=list)
    top_no_holders: List[Dict] = field(default_factory=list)
    
    # Aggregated stats
    total_yes_shares: float = 0.0
    total_no_shares: float = 0.0
    unique_yes_holders: int = 0
    unique_no_holders: int = 0
    
    last_updated: Optional[datetime] = None


@dataclass
class AccumulationAlert:
    """Alert for significant position accumulation."""
    alert_type: str  # 'new_whale_position', 'rapid_accumulation', 'large_position_change'
    wallet: str
    wallet_name: Optional[str]
    market_id: str
    market_question: str
    outcome: str
    
    shares: float
    usd_spent: float
    potential_payout: float
    
    accumulation_period: str  # '24h', '7d', 'all_time'
    
    message: str
    severity: str  # 'HIGH', 'CRITICAL'
    timestamp: datetime = field(default_factory=datetime.now)


class PositionTracker:
    """
    Tracks wallet positions and accumulation patterns.
    
    Catches whales who build large positions gradually rather than
    in single large trades.
    """
    
    def __init__(
        self,
        accumulation_threshold_24h: float = 50000,  # $50K in 24h triggers alert
        accumulation_threshold_7d: float = 100000,   # $100K in 7d triggers alert
        position_alert_threshold: float = 50000,     # $50K position triggers alert
        potential_payout_threshold: float = 500000,  # $500K potential payout triggers alert
        top_holders_limit: int = 20,
    ):
        self.accumulation_threshold_24h = accumulation_threshold_24h
        self.accumulation_threshold_7d = accumulation_threshold_7d
        self.position_alert_threshold = position_alert_threshold
        self.potential_payout_threshold = potential_payout_threshold
        self.top_holders_limit = top_holders_limit
        
        # Wallet tracking
        self.wallets: Dict[str, WalletAccumulation] = {}
        
        # Market position tracking
        self.market_positions: Dict[str, MarketPositions] = {}
        
        # Alerts already sent (to avoid duplicates)
        self.sent_alerts: Set[str] = set()
        
        # Market info cache
        self.market_questions: Dict[str, str] = {}
        
        # Stats
        self.total_trades_processed = 0
        self.total_alerts_generated = 0
        
        logger.info(f"PositionTracker initialized:")
        logger.info(f"  24h accumulation threshold: ${accumulation_threshold_24h:,.0f}")
        logger.info(f"  7d accumulation threshold: ${accumulation_threshold_7d:,.0f}")
        logger.info(f"  Position alert threshold: ${position_alert_threshold:,.0f}")
        logger.info(f"  Potential payout threshold: ${potential_payout_threshold:,.0f}")
    
    def process_trade(self, trade: Dict) -> List[AccumulationAlert]:
        """Process a single trade and check for accumulation alerts."""
        alerts = []
        
        wallet = trade.get('proxyWallet', trade.get('trader_address'))
        if not wallet:
            return alerts
        
        # Get or create wallet tracking
        if wallet not in self.wallets:
            self.wallets[wallet] = WalletAccumulation(wallet=wallet)
        
        wallet_data = self.wallets[wallet]
        wallet_data.add_trade(trade)
        wallet_data.cleanup_old_trades()
        
        self.total_trades_processed += 1
        
        # Check for accumulation alerts
        alerts.extend(self._check_accumulation_alerts(wallet_data, trade))
        
        return alerts
    
    def process_trades_batch(self, trades: List[Dict]) -> List[AccumulationAlert]:
        """Process a batch of trades and return any alerts."""
        all_alerts = []
        
        for trade in trades:
            alerts = self.process_trade(trade)
            all_alerts.extend(alerts)
        
        return all_alerts
    
    def _check_accumulation_alerts(
        self, 
        wallet_data: WalletAccumulation, 
        latest_trade: Dict
    ) -> List[AccumulationAlert]:
        """Check if wallet accumulation triggers any alerts."""
        alerts = []
        
        market_id = latest_trade.get('conditionId', latest_trade.get('market_id', 'unknown'))
        outcome = latest_trade.get('outcome', 'unknown')
        market_question = self.market_questions.get(market_id, latest_trade.get('title', 'Unknown market'))
        
        # Get position data
        position = wallet_data.positions.get(market_id, {})
        shares = position.get('shares', 0)
        total_cost = position.get('total_cost', 0)
        potential_payout = shares  # Each share worth $1 if wins
        
        wallet_name = wallet_data.pseudonym or wallet_data.name or wallet_data.wallet[:15]
        
        # Alert key for deduplication
        def make_alert_key(alert_type: str) -> str:
            return f"{alert_type}:{wallet_data.wallet}:{market_id}:{outcome}"
        
        # Check 24h accumulation
        if wallet_data.volume_24h >= self.accumulation_threshold_24h:
            alert_key = make_alert_key('rapid_accumulation_24h')
            if alert_key not in self.sent_alerts:
                alerts.append(AccumulationAlert(
                    alert_type='rapid_accumulation',
                    wallet=wallet_data.wallet,
                    wallet_name=wallet_name,
                    market_id=market_id,
                    market_question=market_question,
                    outcome=outcome,
                    shares=shares,
                    usd_spent=wallet_data.volume_24h,
                    potential_payout=potential_payout,
                    accumulation_period='24h',
                    message=f"🚨 RAPID ACCUMULATION: {wallet_name} spent ${wallet_data.volume_24h:,.0f} in 24h on {outcome} - potential payout ${potential_payout:,.0f}",
                    severity='HIGH',
                ))
                self.sent_alerts.add(alert_key)
                self.total_alerts_generated += 1
        
        # Check 7d accumulation
        if wallet_data.volume_7d >= self.accumulation_threshold_7d:
            alert_key = make_alert_key('accumulation_7d')
            if alert_key not in self.sent_alerts:
                alerts.append(AccumulationAlert(
                    alert_type='large_accumulation',
                    wallet=wallet_data.wallet,
                    wallet_name=wallet_name,
                    market_id=market_id,
                    market_question=market_question,
                    outcome=outcome,
                    shares=shares,
                    usd_spent=wallet_data.volume_7d,
                    potential_payout=potential_payout,
                    accumulation_period='7d',
                    message=f"📈 LARGE ACCUMULATION: {wallet_name} accumulated ${wallet_data.volume_7d:,.0f} over 7d on {outcome} - potential payout ${potential_payout:,.0f}",
                    severity='HIGH',
                ))
                self.sent_alerts.add(alert_key)
                self.total_alerts_generated += 1
        
        # Check for large potential payout positions
        if potential_payout >= self.potential_payout_threshold:
            alert_key = make_alert_key('large_payout_position')
            if alert_key not in self.sent_alerts:
                alerts.append(AccumulationAlert(
                    alert_type='new_whale_position',
                    wallet=wallet_data.wallet,
                    wallet_name=wallet_name,
                    market_id=market_id,
                    market_question=market_question,
                    outcome=outcome,
                    shares=shares,
                    usd_spent=total_cost,
                    potential_payout=potential_payout,
                    accumulation_period='all_time',
                    message=f"🐋 WHALE POSITION: {wallet_name} holds ${potential_payout:,.0f} potential payout on {outcome} (spent ${total_cost:,.0f})",
                    severity='CRITICAL',
                ))
                self.sent_alerts.add(alert_key)
                self.total_alerts_generated += 1
        
        return alerts
    
    async def scan_market_positions(self, market_id: str, market_question: str = "") -> MarketPositions:
        """
        Scan a market's trade history to build position data.
        
        This fetches historical trades and aggregates to find top holders.
        """
        logger.info(f"Scanning positions for market: {market_id[:20]}...")
        
        # Cache market question
        if market_question:
            self.market_questions[market_id] = market_question
        
        positions = MarketPositions(market_id=market_id, question=market_question)
        
        # Fetch trades from data API
        wallet_positions: Dict[str, Dict] = defaultdict(lambda: {
            'yes_shares': 0, 'no_shares': 0,
            'yes_cost': 0, 'no_cost': 0,
            'name': None, 'pseudonym': None
        })
        
        offset = 0
        limit = 1000
        max_trades = 10000  # Cap to avoid infinite loops
        
        async with httpx.AsyncClient(timeout=30) as client:
            while offset < max_trades:
                try:
                    url = f"https://data-api.polymarket.com/trades?market={market_id}&limit={limit}&offset={offset}"
                    resp = await client.get(url)
                    
                    if resp.status_code != 200:
                        break
                    
                    trades = resp.json()
                    if not trades or not isinstance(trades, list):
                        break
                    
                    for trade in trades:
                        wallet = trade.get('proxyWallet', 'unknown')
                        size = float(trade.get('size', 0))
                        price = float(trade.get('price', 0))
                        outcome = trade.get('outcome', 'unknown')
                        side = trade.get('side', 'BUY')
                        
                        # Track name/pseudonym
                        if trade.get('name'):
                            wallet_positions[wallet]['name'] = trade['name']
                        if trade.get('pseudonym'):
                            wallet_positions[wallet]['pseudonym'] = trade['pseudonym']
                        
                        # Calculate position change
                        multiplier = 1 if side == 'BUY' else -1
                        
                        if outcome == 'Yes':
                            wallet_positions[wallet]['yes_shares'] += size * multiplier
                            wallet_positions[wallet]['yes_cost'] += size * price * multiplier
                        else:
                            wallet_positions[wallet]['no_shares'] += size * multiplier
                            wallet_positions[wallet]['no_cost'] += size * price * multiplier
                    
                    if len(trades) < limit:
                        break
                    
                    offset += limit
                    await asyncio.sleep(0.1)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error fetching trades: {e}")
                    break
        
        # Build top holder lists
        yes_holders = []
        no_holders = []
        
        for wallet, pos in wallet_positions.items():
            if pos['yes_shares'] > 0:
                yes_holders.append({
                    'wallet': wallet,
                    'name': pos['name'],
                    'pseudonym': pos['pseudonym'],
                    'shares': pos['yes_shares'],
                    'cost': pos['yes_cost'],
                    'potential_payout': pos['yes_shares'],
                })
                positions.total_yes_shares += pos['yes_shares']
                positions.unique_yes_holders += 1
            
            if pos['no_shares'] > 0:
                no_holders.append({
                    'wallet': wallet,
                    'name': pos['name'],
                    'pseudonym': pos['pseudonym'],
                    'shares': pos['no_shares'],
                    'cost': pos['no_cost'],
                    'potential_payout': pos['no_shares'],
                })
                positions.total_no_shares += pos['no_shares']
                positions.unique_no_holders += 1
        
        # Sort by shares and take top N
        yes_holders.sort(key=lambda x: -x['shares'])
        no_holders.sort(key=lambda x: -x['shares'])
        
        positions.top_yes_holders = yes_holders[:self.top_holders_limit]
        positions.top_no_holders = no_holders[:self.top_holders_limit]
        positions.last_updated = datetime.now()
        
        # Cache positions
        self.market_positions[market_id] = positions
        
        logger.info(f"Found {positions.unique_yes_holders} YES holders, {positions.unique_no_holders} NO holders")
        logger.info(f"Top YES: {positions.top_yes_holders[0]['shares']:,.0f} shares" if positions.top_yes_holders else "No YES positions")
        
        return positions
    
    def get_top_accumulators(self, limit: int = 20) -> List[Dict]:
        """Get wallets with highest recent accumulation."""
        wallets = []
        
        for wallet_id, wallet in self.wallets.items():
            wallet.cleanup_old_trades()
            
            # Find their largest position
            largest_position = 0
            largest_market = None
            for market_id, pos in wallet.positions.items():
                if pos['shares'] > largest_position:
                    largest_position = pos['shares']
                    largest_market = market_id
            
            wallets.append({
                'wallet': wallet_id,
                'name': wallet.pseudonym or wallet.name,
                'volume_24h': wallet.volume_24h,
                'volume_7d': wallet.volume_7d,
                'largest_position_shares': largest_position,
                'largest_position_market': largest_market,
                'total_markets': len(wallet.positions),
            })
        
        # Sort by 24h volume
        wallets.sort(key=lambda x: -x['volume_24h'])
        return wallets[:limit]
    
    def get_stats(self) -> Dict:
        """Get tracker statistics."""
        return {
            'total_trades_processed': self.total_trades_processed,
            'total_alerts_generated': self.total_alerts_generated,
            'wallets_tracked': len(self.wallets),
            'markets_tracked': len(self.market_positions),
            'sent_alerts_count': len(self.sent_alerts),
        }
    
    def cleanup_memory(self, max_wallets: int = 5000) -> Dict:
        """Clean up old data to prevent memory bloat."""
        cleaned = {'wallets_removed': 0, 'alerts_cleared': 0}
        
        # Remove wallets with no recent activity
        if len(self.wallets) > max_wallets:
            # Sort by last_updated, keep most recent
            sorted_wallets = sorted(
                self.wallets.items(),
                key=lambda x: x[1].last_updated or datetime.min,
                reverse=True
            )
            self.wallets = dict(sorted_wallets[:max_wallets])
            cleaned['wallets_removed'] = len(sorted_wallets) - max_wallets
        
        # Clear old sent alerts (older than 7 days won't matter)
        # We'll clear half if it gets too large
        if len(self.sent_alerts) > 10000:
            self.sent_alerts = set(list(self.sent_alerts)[-5000:])
            cleaned['alerts_cleared'] = 5000
        
        return cleaned


# Convenience function to create default tracker
def create_position_tracker() -> PositionTracker:
    """
    Create a position tracker with sensible defaults for whale detection.
    
    Reference: "thesecondhighlander" had ~$100K spent for $4M potential (2.5% odds)
    
    Thresholds calibrated to catch:
    - Rapid position building ($50K in 24h = someone loading up fast)
    - Large positions ($100K over 7d = serious conviction)
    - Meaningful potential payouts ($250K+ = worth alerting about)
    """
    return PositionTracker(
        accumulation_threshold_24h=50000,   # $50K in 24h - someone building fast
        accumulation_threshold_7d=100000,   # $100K in 7d - serious position
        position_alert_threshold=50000,     # $50K position value
        potential_payout_threshold=250000,  # $250K potential win - meaningful upside
    )
