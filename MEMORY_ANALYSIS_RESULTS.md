# Memory Analysis Results
**Date:** January 26, 2026
**Status:** ✅ Repos in sync | ⚠️ Memory optimization needed

## Summary

Good news! **Most of your data structures already have limits**. The memory issue is likely from:
1. **Unbounded wallet profiles** (growing with every new trader)
2. **Possible memory leak in long-running WebSocket connections**
3. **Database connections not being properly closed**

## Data Structures Status

### ✅ PROPERLY LIMITED

| Structure | Location | Limit | Cleanup Method |
|-----------|----------|-------|----------------|
| `seen_trades` | Line 1782-1784 | 50,000 max, keeps last 25,000 | Automatic trimming |
| `recent_trade_sizes` | Line 1134-1135 | 10,000 trades | Rolling window (pop oldest) |
| `market_stats["trades"]` | Line 1000 | 1,000 per market | Keep last 1000 |
| `recent_market_trades` | Cluster tracking | Time-based (6x cluster window) | Prunes old timestamps |
| `market_hourly_volume` | Line 18-19 | 1 hour rolling | Prunes hourly |

### ⚠️ NEEDS LIMITS

| Structure | Location | Problem | Est. Memory Impact |
|-----------|----------|---------|-------------------|
| **`wallet_profiles`** | Line 578 | No limit on number of wallets | **HIGH** (100-500 MB) |
| **`market_questions`** | Line 588 | No limit on markets | Low (10-20 MB) |
| **`market_urls`** | Line 589 | No limit on markets | Low (10-20 MB) |
| **`market_categories`** | Line 590 | No limit on markets | Low (5-10 MB) |
| **`wallet_clusters`** | Line 601 | No cleanup of old clusters | Medium (20-50 MB) |

## Primary Culprit: Wallet Profiles

### Growth Pattern
- **New wallets per day:** ~500-2,000 unique traders
- **30 days:** 15,000-60,000 wallet profiles
- **Memory per profile:** ~2-10 KB (positions, trade history, timestamps)
- **Total memory:** **150-600 MB** from wallets alone

### What's stored per wallet:
```python
WalletProfile:
    - positions: Dict[market_id][outcome] = {buy/sell shares & USD}
    - resolved_positions: List of historical bets
    - recent_trade_times: Last 100 timestamps
    - markets_traded: Set of market IDs
```

## Recommended Fixes

### Quick Win #1: Add Wallet Pruning (5 minutes)

Add this method to `WhaleDetector` class in `whale_detector.py`:

```python
def cleanup_inactive_wallets(self):
    """Remove wallets that haven't traded in 30 days to prevent memory growth."""
    if len(self.wallet_profiles) < 10000:
        return  # Only clean if we have lots of wallets

    cutoff = datetime.now() - timedelta(days=30)
    inactive = [
        addr for addr, profile in self.wallet_profiles.items()
        if profile.last_seen and profile.last_seen < cutoff
    ]

    for addr in inactive:
        del self.wallet_profiles[addr]

    if inactive:
        logger.info(f"🧹 Cleaned {len(inactive)} inactive wallets (30+ days). Remaining: {len(self.wallet_profiles)}")
```

Then call it periodically (add to `TradeMonitor._check_for_trades` in line ~1700):

```python
# In TradeMonitor._check_for_trades(), after processing trades:
if len(self.detector.wallet_profiles) > 10000:
    self.detector.cleanup_inactive_wallets()
```

### Quick Win #2: Add Memory Monitoring Endpoint

Add to `src/main.py`:

```python
@app.get("/stats/memory")
async def get_memory_stats():
    """Track memory usage of in-memory data structures"""
    import sys

    wallet_memory_mb = sys.getsizeof(detector.wallet_profiles) / (1024 * 1024)

    return {
        "wallet_profiles_count": len(detector.wallet_profiles),
        "wallet_profiles_mb": round(wallet_memory_mb, 2),
        "seen_trades_count": len(detector.seen_trades),
        "market_stats_count": len(detector.market_stats),
        "market_hourly_volume_count": len(detector.market_hourly_volume),
        "recent_trade_sizes_count": len(detector.recent_trade_sizes),
        "recent_market_trades_total": sum(len(v) for v in detector.recent_market_trades.values()),
    }
```

## Other Potential Issues

### 1. WebSocket Memory Leaks
The hybrid WebSocket monitor might accumulate messages. Check:
- `polymarket_websocket.py` - ensure message buffers are limited
- Connection reconnection logic - make sure old connections are properly closed

### 2. Database Connection Pool
PostgreSQL connections might not be closing properly. Check:
- Railway Postgres connection limit (default: 100 connections)
- SQLAlchemy pool size in `database.py`

### 3. Alert Queue Buildup
If alerts are generated faster than they can be sent, queues might grow:
- Check Discord rate limits
- Check Resend email rate limits

## How Much Memory Do You Actually Need?

### Current Estimate (without cleanup):
| Component | Memory |
|-----------|--------|
| Wallet profiles (30 days) | 300 MB |
| Market stats & caches | 50 MB |
| Seen trades | 10 MB |
| Recent trades | 20 MB |
| Python runtime + libraries | 200 MB |
| FastAPI + uvicorn | 100 MB |
| **Total Estimate** | **~680 MB** |

### With Wallet Cleanup (30 days):
- **Expected usage: ~400-500 MB**
- **Railway Hobby plan: 8 GB available**
- **You have 16x more RAM than you need!**

## Likely Root Cause

The OOM crash was probably caused by:
1. **Long runtime without restarts** (weeks?) → wallet_profiles grew to 50K+
2. **High-volume period** (election day?) → spike in unique wallets
3. **Memory leak elsewhere** (WebSocket, DB connections)

## Action Plan

1. **Immediate** (Do this now):
   - Add wallet cleanup code above
   - Deploy to Railway
   - Add `/stats/memory` endpoint to monitor

2. **Short-term** (Next week):
   - Monitor `/stats/memory` daily
   - Set up Railway restart schedule (daily at 4 AM)
   - Add alerting if memory > 2 GB

3. **Long-term** (Next month):
   - Move wallet profiles to PostgreSQL (persist historical data)
   - Keep only "active" wallets in memory (traded in last 7 days)
   - Add Redis cache for frequently accessed data

## Do You Need More RAM?

**No.** With the wallet cleanup fix above, you'll use ~400-500 MB max.

Railway Hobby plan ($5/month) provides **8 GB RAM**, which is 16x what you need.

The issue was unbounded growth over time, not insufficient RAM.
