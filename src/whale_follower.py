"""
Whale Follower - Track and reverse-engineer whale trading strategies

Specifically designed to analyze distinct-baguette and other top traders
to understand their market making / trading patterns.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import httpx
from loguru import logger


# Known whale wallets to track
TRACKED_WHALES = {
    "distinct-baguette": {
        "wallet": "0xe00740bce98a594e26861838885ab310ec3b548c",
        "pseudonym": "Frozen-Technician",
        "notes": "Top market maker, $477K+ profit, smooth return curve"
    },
    # Add more whales as we discover them
}


@dataclass
class WhaleProfile:
    """Profile of a tracked whale."""
    name: str
    wallet: str
    pseudonym: Optional[str] = None
    
    # Trading stats
    total_trades: int = 0
    total_volume: float = 0.0
    
    # Market activity
    markets_traded: Dict[str, Dict] = field(default_factory=dict)
    
    # Timing patterns
    trades_by_hour: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    trades_by_day: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Position tracking
    positions: Dict[str, Dict] = field(default_factory=dict)  # market_id -> {yes_shares, no_shares, avg_price}
    
    # Trade history
    recent_trades: List[Dict] = field(default_factory=list)
    
    # Analysis
    avg_trade_size: float = 0.0
    avg_spread_from_mid: float = 0.0
    two_sided_ratio: float = 0.0  # How often they quote both sides
    
    last_updated: Optional[datetime] = None


@dataclass 
class MarketMakingPattern:
    """Detected market making pattern."""
    market_id: str
    market_question: str
    
    # Quote patterns
    avg_bid_spread: float = 0.0  # Avg distance from mid for bids
    avg_ask_spread: float = 0.0  # Avg distance from mid for asks
    avg_quote_size: float = 0.0
    
    # Two-sided analysis
    has_two_sided_quotes: bool = False
    quote_balance: float = 0.0  # Ratio of bid vs ask volume
    
    # Timing
    avg_time_in_market: float = 0.0  # How long positions held
    trade_frequency: float = 0.0  # Trades per hour
    
    # P&L estimate
    estimated_spread_capture: float = 0.0
    estimated_reward_share: float = 0.0


class WhaleFollower:
    """
    Track and analyze whale trading patterns.
    
    Use this to reverse-engineer strategies of successful traders
    like distinct-baguette.
    """
    
    def __init__(self):
        self.whales: Dict[str, WhaleProfile] = {}
        self.http = httpx.AsyncClient(timeout=30)
        
        # Initialize tracked whales
        for name, info in TRACKED_WHALES.items():
            self.whales[name] = WhaleProfile(
                name=name,
                wallet=info["wallet"],
                pseudonym=info.get("pseudonym")
            )
    
    async def fetch_whale_trades(
        self, 
        wallet: str, 
        limit: int = 1000
    ) -> List[Dict]:
        """Fetch recent trades for a wallet."""
        trades = []
        
        try:
            # Polymarket data API
            url = f"https://data-api.polymarket.com/trades?user={wallet}&limit={limit}"
            resp = await self.http.get(url)
            
            if resp.status_code == 200:
                trades = resp.json()
                logger.info(f"Fetched {len(trades)} trades for {wallet[:15]}...")
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
        
        return trades
    
    async def analyze_whale(self, name: str) -> WhaleProfile:
        """
        Comprehensive analysis of a whale's trading pattern.
        """
        if name not in self.whales:
            raise ValueError(f"Unknown whale: {name}")
        
        whale = self.whales[name]
        logger.info(f"Analyzing {name} ({whale.wallet[:15]}...)...")
        
        # Fetch their trades
        trades = await self.fetch_whale_trades(whale.wallet, limit=2000)
        
        if not trades:
            logger.warning(f"No trades found for {name}")
            return whale
        
        whale.recent_trades = trades[:100]  # Keep last 100 for reference
        whale.total_trades = len(trades)
        
        # Analyze trading patterns
        for trade in trades:
            size = float(trade.get('size', 0))
            price = float(trade.get('price', 0))
            usd_value = size * price
            market_id = trade.get('conditionId', 'unknown')
            outcome = trade.get('outcome', 'unknown')
            side = trade.get('side', 'BUY')
            timestamp = trade.get('timestamp', 0)
            
            whale.total_volume += usd_value
            
            # Track by market
            if market_id not in whale.markets_traded:
                whale.markets_traded[market_id] = {
                    'question': trade.get('title', 'Unknown'),
                    'trades': 0,
                    'volume': 0,
                    'yes_volume': 0,
                    'no_volume': 0,
                    'buy_volume': 0,
                    'sell_volume': 0,
                    'prices': [],
                    'first_trade': timestamp,
                    'last_trade': timestamp,
                }
            
            mkt = whale.markets_traded[market_id]
            mkt['trades'] += 1
            mkt['volume'] += usd_value
            mkt['prices'].append(price)
            mkt['last_trade'] = max(mkt['last_trade'], timestamp)
            
            if outcome == 'Yes':
                mkt['yes_volume'] += usd_value
            else:
                mkt['no_volume'] += usd_value
                
            if side == 'BUY':
                mkt['buy_volume'] += usd_value
            else:
                mkt['sell_volume'] += usd_value
            
            # Track timing patterns
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                whale.trades_by_hour[dt.hour] += 1
                whale.trades_by_day[dt.strftime('%A')] += 1
            
            # Update positions
            if market_id not in whale.positions:
                whale.positions[market_id] = {
                    'yes_shares': 0, 'no_shares': 0,
                    'yes_cost': 0, 'no_cost': 0,
                }
            
            pos = whale.positions[market_id]
            multiplier = 1 if side == 'BUY' else -1
            
            if outcome == 'Yes':
                pos['yes_shares'] += size * multiplier
                pos['yes_cost'] += usd_value * multiplier
            else:
                pos['no_shares'] += size * multiplier
                pos['no_cost'] += usd_value * multiplier
        
        # Calculate averages
        if whale.total_trades > 0:
            whale.avg_trade_size = whale.total_volume / whale.total_trades
        
        # Calculate two-sided ratio (markets where they trade both YES and NO)
        two_sided_markets = 0
        for mkt_id, mkt in whale.markets_traded.items():
            if mkt['yes_volume'] > 0 and mkt['no_volume'] > 0:
                two_sided_markets += 1
        
        if whale.markets_traded:
            whale.two_sided_ratio = two_sided_markets / len(whale.markets_traded)
        
        whale.last_updated = datetime.now()
        
        return whale
    
    def detect_market_making(self, whale: WhaleProfile) -> List[MarketMakingPattern]:
        """
        Detect if whale is doing market making on specific markets.
        
        Signs of market making:
        - Two-sided activity (both YES and NO)
        - Balanced buy/sell volume
        - Consistent small trades
        - Activity across price levels
        """
        patterns = []
        
        for market_id, mkt in whale.markets_traded.items():
            # Check for two-sided activity
            yes_vol = mkt['yes_volume']
            no_vol = mkt['no_volume']
            buy_vol = mkt['buy_volume']
            sell_vol = mkt['sell_volume']
            
            has_two_sided = yes_vol > 0 and no_vol > 0
            
            # Calculate balance ratios
            total_vol = yes_vol + no_vol
            if total_vol > 0:
                yes_ratio = yes_vol / total_vol
                quote_balance = min(yes_ratio, 1 - yes_ratio) * 2  # 1.0 = perfectly balanced
            else:
                quote_balance = 0
            
            # Calculate buy/sell balance
            total_bs = buy_vol + sell_vol
            if total_bs > 0:
                buy_ratio = buy_vol / total_bs
                bs_balance = min(buy_ratio, 1 - buy_ratio) * 2
            else:
                bs_balance = 0
            
            # Estimate spread from price variance
            prices = mkt.get('prices', [])
            if prices:
                avg_price = sum(prices) / len(prices)
                price_variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
                avg_spread = price_variance ** 0.5  # Rough estimate
            else:
                avg_spread = 0
            
            # Calculate trade frequency
            if mkt['first_trade'] and mkt['last_trade']:
                time_span = mkt['last_trade'] - mkt['first_trade']
                if time_span > 0:
                    hours = time_span / 3600
                    trade_freq = mkt['trades'] / max(1, hours)
                else:
                    trade_freq = 0
            else:
                trade_freq = 0
            
            pattern = MarketMakingPattern(
                market_id=market_id,
                market_question=mkt['question'],
                avg_bid_spread=avg_spread,
                avg_ask_spread=avg_spread,
                avg_quote_size=mkt['volume'] / max(1, mkt['trades']),
                has_two_sided_quotes=has_two_sided,
                quote_balance=quote_balance,
                trade_frequency=trade_freq,
            )
            
            # Only include if it looks like market making
            if has_two_sided and quote_balance > 0.3:  # At least 30% balanced
                patterns.append(pattern)
        
        # Sort by volume
        patterns.sort(key=lambda p: p.avg_quote_size * p.trade_frequency, reverse=True)
        
        return patterns
    
    def generate_report(self, whale: WhaleProfile) -> str:
        """Generate a human-readable analysis report."""
        lines = []
        lines.append(f"# Whale Analysis: {whale.name}")
        lines.append(f"Wallet: `{whale.wallet}`")
        lines.append(f"Pseudonym: {whale.pseudonym or 'Unknown'}")
        lines.append(f"Last Updated: {whale.last_updated}")
        lines.append("")
        
        lines.append("## Trading Summary")
        lines.append(f"- Total Trades: {whale.total_trades:,}")
        lines.append(f"- Total Volume: ${whale.total_volume:,.2f}")
        lines.append(f"- Avg Trade Size: ${whale.avg_trade_size:,.2f}")
        lines.append(f"- Markets Traded: {len(whale.markets_traded)}")
        lines.append(f"- Two-Sided Ratio: {whale.two_sided_ratio:.1%}")
        lines.append("")
        
        lines.append("## Top Markets by Volume")
        sorted_markets = sorted(
            whale.markets_traded.items(),
            key=lambda x: x[1]['volume'],
            reverse=True
        )[:10]
        
        for market_id, mkt in sorted_markets:
            yes_pct = mkt['yes_volume'] / max(1, mkt['volume']) * 100
            lines.append(f"- **{mkt['question'][:60]}...**")
            lines.append(f"  Volume: ${mkt['volume']:,.0f} | YES: {yes_pct:.0f}% | Trades: {mkt['trades']}")
        
        lines.append("")
        lines.append("## Trading Hours (UTC)")
        peak_hours = sorted(whale.trades_by_hour.items(), key=lambda x: -x[1])[:5]
        for hour, count in peak_hours:
            lines.append(f"- {hour:02d}:00 - {count} trades")
        
        lines.append("")
        lines.append("## Current Positions (Net)")
        sorted_positions = sorted(
            whale.positions.items(),
            key=lambda x: abs(x[1]['yes_shares']) + abs(x[1]['no_shares']),
            reverse=True
        )[:10]
        
        for market_id, pos in sorted_positions:
            mkt = whale.markets_traded.get(market_id, {})
            question = mkt.get('question', market_id[:20])[:50]
            yes_net = pos['yes_shares']
            no_net = pos['no_shares']
            if abs(yes_net) > 100 or abs(no_net) > 100:
                lines.append(f"- {question}...")
                lines.append(f"  YES: {yes_net:,.0f} shares | NO: {no_net:,.0f} shares")
        
        # Detect market making
        patterns = self.detect_market_making(whale)
        if patterns:
            lines.append("")
            lines.append("## Detected Market Making Activity")
            for p in patterns[:5]:
                lines.append(f"- **{p.market_question[:50]}...**")
                lines.append(f"  Two-sided: {p.has_two_sided_quotes} | Balance: {p.quote_balance:.1%} | Freq: {p.trade_frequency:.1f}/hr")
        
        return "\n".join(lines)


async def analyze_distinct_baguette():
    """Quick analysis of distinct-baguette's strategy."""
    follower = WhaleFollower()
    
    whale = await follower.analyze_whale("distinct-baguette")
    report = follower.generate_report(whale)
    
    print(report)
    
    # Also detect market making patterns
    patterns = follower.detect_market_making(whale)
    
    print("\n## Market Making Analysis")
    if patterns:
        print(f"Found {len(patterns)} markets with market-making activity:")
        for p in patterns[:10]:
            print(f"- {p.market_question[:60]}")
            print(f"  Balance: {p.quote_balance:.1%}, Freq: {p.trade_frequency:.1f} trades/hr")
    else:
        print("No clear market-making patterns detected.")
    
    return whale, patterns


if __name__ == "__main__":
    asyncio.run(analyze_distinct_baguette())
