# Memory Optimization Plan for Prediction Market Tracker

## Problem
Railway deployment crashed with OOM (out of memory). Several in-memory data structures grow unbounded.

## Memory Budget (Hobby Plan)
- **Total Available:** 8 GB RAM
- **Target Usage:** < 4 GB (50% safety margin)
- **Current:** Unknown (crashed before measurement)

## Data Structures Analysis

### CRITICAL: Unbounded Growth

#### 1. `seen_trades` Set (whale_detector.py:1598)
**Problem:** Tracks ALL trade IDs forever to prevent duplicate alerts
**Current:** `Set[str]` with no size limit
**Growth:** ~100-500 new trades/hour = 720K-3.6M per month
**Memory:** ~50-250 MB/month (assuming 64 bytes per ID)

**Recommended Fix:**
```python
# Add TTL (time-to-live) - only keep last 24 hours
MAX_SEEN_TRADES = 50000  # ~24 hours of trades at 500/hour
seen_trades_with_time: Dict[str, datetime] = {}

def _cleanup_seen_trades(self):
    """Remove trade IDs older than 24 hours"""
    cutoff = datetime.now() - timedelta(hours=24)
    to_remove = [tid for tid, ts in self.seen_trades_with_time.items() if ts < cutoff]
    for tid in to_remove:
        del self.seen_trades_with_time[tid]
```

#### 2. `wallet_profiles` Dict
**Problem:** One WalletProfile per trader, each with:
- `positions` dict (per-market positions)
- `resolved_positions` list (historical)
- `recent_trade_times` list (last 100)
- `markets_traded` set

**Current Size:** ~10K-50K unique wallets
**Memory per wallet:** ~2-10 KB
**Total:** 20-500 MB (depends on activity)

**Recommended Fix:**
```python
# Prune inactive wallets (no trades in 30 days)
MAX_WALLET_INACTIVITY_DAYS = 30

def _cleanup_inactive_wallets(self):
    """Remove wallets that haven't traded in 30 days"""
    cutoff = datetime.now() - timedelta(days=MAX_WALLET_INACTIVITY_DAYS)
    inactive = [
        addr for addr, profile in self.wallet_profiles.items()
        if profile.last_seen and profile.last_seen < cutoff
    ]
    for addr in inactive:
        del self.wallet_profiles[addr]
    logger.info(f"Pruned {len(inactive)} inactive wallets")
```

#### 3. `market_stats` Dict
**Problem:** Per-market statistics with unbounded trade lists
**Current:** `{market_id: {trades: [], mean, std}}`
**Growth:** ~1000 markets, each with full trade history

**Recommended Fix:**
```python
# Only keep recent trades for statistics
MAX_TRADES_PER_MARKET = 500  # Enough for statistical significance

def _update_market_stats(self, market_id: str, trade: Trade):
    if market_id not in self.market_stats:
        self.market_stats[market_id] = {"trades": [], "mean": 0, "std": 0}

    stats = self.market_stats[market_id]
    stats["trades"].append(trade.amount_usd)

    # Limit trade history
    if len(stats["trades"]) > MAX_TRADES_PER_MARKET:
        stats["trades"] = stats["trades"][-MAX_TRADES_PER_MARKET:]

    # Recalculate statistics
    if len(stats["trades"]) >= 10:
        stats["mean"] = statistics.mean(stats["trades"])
        stats["std"] = statistics.stdev(stats["trades"])
```

#### 4. `recent_trade_sizes` List
**Problem:** No explicit size limit
**Recommended Fix:**
```python
MAX_RECENT_TRADES = 10000  # ~24 hours at high volume

def _track_trade_size(self, amount: float):
    self.recent_trade_sizes.append(amount)
    if len(self.recent_trade_sizes) > MAX_RECENT_TRADES:
        self.recent_trade_sizes = self.recent_trade_sizes[-MAX_RECENT_TRADES:]
```

#### 5. `recent_market_trades` Dict
**Problem:** Per-market trade history (unbounded lists)
**Recommended Fix:**
```python
MAX_RECENT_TRADES_PER_MARKET = 100

def _track_market_trade(self, market_id: str, wallet: str, timestamp: datetime, amount: float):
    self.recent_market_trades[market_id].append((wallet, timestamp, amount))

    # Limit per-market history
    if len(self.recent_market_trades[market_id]) > MAX_RECENT_TRADES_PER_MARKET:
        self.recent_market_trades[market_id] = (
            self.recent_market_trades[market_id][-MAX_RECENT_TRADES_PER_MARKET:]
        )
```

## Implementation Strategy

### Phase 1: Add Limits (Quick Fix) ⚡
Add maximum sizes to all unbounded structures:
- `seen_trades`: 50,000 max
- `recent_trade_sizes`: 10,000 max
- `market_stats[market]["trades"]`: 500 max per market
- `recent_market_trades[market]`: 100 max per market

### Phase 2: Add Cleanup Jobs (Medium Priority) 🧹
Add periodic cleanup tasks:
- Every hour: Clean up `seen_trades` older than 24h
- Every day: Prune inactive wallets (30+ days no activity)
- Every week: Prune inactive markets (no trades in 7 days)

### Phase 3: Move to Database (Long-term) 💾
For truly historical data, move to PostgreSQL:
- Wallet profiles → `wallets` table
- Market statistics → `market_stats` table
- Trade history → `trades` table (already exists!)

Keep only "hot" data in memory (last 24-48 hours).

## Estimated Memory Savings

| Optimization | Current | After | Savings |
|--------------|---------|-------|---------|
| `seen_trades` with TTL | 250 MB | 5 MB | **245 MB** |
| Wallet pruning | 500 MB | 50 MB | **450 MB** |
| Market stats limiting | 200 MB | 20 MB | **180 MB** |
| Trade history limiting | 100 MB | 10 MB | **90 MB** |
| **TOTAL** | **~1 GB** | **~85 MB** | **~915 MB** |

## Monitoring

Add memory tracking endpoint:
```python
@app.get("/stats/memory")
async def get_memory_stats():
    import sys

    return {
        "wallet_profiles": len(detector.wallet_profiles),
        "seen_trades": len(detector.seen_trades),
        "market_stats": len(detector.market_stats),
        "recent_trade_sizes": len(detector.recent_trade_sizes),
        "recent_market_trades": sum(len(v) for v in detector.recent_market_trades.values()),
        "wallet_clusters": len(detector.wallet_clusters),
        "total_memory_mb": sys.getsizeof(detector.wallet_profiles) / 1024 / 1024,
    }
```

## Recommended Railway Plan

Current: **Hobby ($5/month)** - up to 8GB RAM

**Options:**
1. **Keep Hobby + Optimize** (recommended) - Implement Phase 1 + 2 above
2. **Upgrade to Pro ($20/month)** - Up to 32GB RAM (if optimization doesn't work)

**Recommendation:** Try optimization first. With the fixes above, you should easily stay under 2GB RAM.
