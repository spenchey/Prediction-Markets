# Memory Optimization Deployment Guide

**Date:** January 26, 2026
**Status:** ✅ Ready to Deploy
**Commit:** `fe5e0c3` - Merged memory fixes with latest changes

---

## What Was Fixed

### The Problem
Railway deployment crashed with OOM (out-of-memory) error. Primary cause: **unbounded growth of `wallet_profiles` dictionary**.

### The Solution
Added automatic cleanup that prunes inactive wallets every time the monitor checks for trades:
- Removes wallets inactive for 30+ days when count > 10,000
- Keeps only "hot" wallet profiles in memory
- Added `/stats/memory` endpoint to monitor memory usage

---

## Changes Made

### 1. Added Wallet Cleanup Method
**File:** `src/whale_detector.py`

```python
def cleanup_inactive_wallets(self, max_inactive_days=30, min_wallets_before_cleanup=10000):
    """Remove wallets that haven't traded in X days to prevent memory growth."""
    # Only runs if wallet count > 10,000
    # Removes wallets with no trades in last 30 days
```

### 2. Automatic Cleanup in Monitor
**File:** `src/whale_detector.py` (TradeMonitor class)

Cleanup runs automatically after processing trades:
```python
# Periodic wallet cleanup to prevent memory growth (runs when > 10K wallets)
self.detector.cleanup_inactive_wallets()
```

### 3. Memory Monitoring Endpoint
**File:** `src/main.py`

New endpoint: `GET /stats/memory`

Returns:
```json
{
  "wallet_profiles_count": 8234,
  "wallet_profiles_mb_estimate": 45.2,
  "seen_trades_count": 12500,
  "market_stats_count": 423,
  "recent_trade_sizes_count": 10000,
  "warning": "Normal"
}
```

---

## Deployment Steps

### Option 1: Automatic Deployment (Recommended)
Railway auto-deploys from the `main` branch. Your changes are already pushed.

1. **Monitor the deployment:**
   ```bash
   railway logs --tail
   ```

2. **Wait for deployment to complete** (2-3 minutes)

3. **Verify the fix:**
   ```bash
   curl https://web-production-9d2d3.up.railway.app/stats/memory
   ```

4. **Check health:**
   ```bash
   curl https://web-production-9d2d3.up.railway.app/health
   ```

### Option 2: Manual Deployment
If auto-deploy doesn't trigger:

```bash
cd "C:\Users\Spencer H\Desktop\Predicition Markets\prediction-market-tracker\prediction-market-tracker"
railway redeploy -y
```

---

## Monitoring After Deployment

### 1. Check Memory Usage (Every Few Days)
```bash
curl https://web-production-9d2d3.up.railway.app/stats/memory
```

**What to look for:**
- `wallet_profiles_count` should stay under 20,000
- `warning` should show "Normal" or "Low"
- If `warning` shows "High", the cleanup is working (it'll prune on next poll)

### 2. Check Railway Metrics
Visit: https://railway.app/project/shimmering-kindness

Monitor:
- **Memory usage** - Should stay under 1 GB
- **CPU usage** - Should be low (< 20%)
- **No crashes** - Uptime should be continuous

### 3. Test the Cleanup
After a few days, check if cleanup is running:

```bash
railway logs | grep "Memory cleanup"
```

Should show logs like:
```
🧹 Memory cleanup: Removed 234 inactive wallets (>30 days). Remaining: 8923
```

---

## Expected Results

### Before Fix
- **Wallet profiles:** Growing unbounded (could reach 50K+)
- **Memory usage:** 600 MB - 2 GB+
- **Result:** OOM crash after several weeks

### After Fix
- **Wallet profiles:** Stays under 20,000 (auto-pruned)
- **Memory usage:** 400-500 MB steady state
- **Result:** Stable, no crashes

---

## Troubleshooting

### If Memory Still High After 1 Week

Check current wallet count:
```bash
curl https://web-production-9d2d3.up.railway.app/stats/memory | jq '.wallet_profiles_count'
```

If still > 20,000, manually trigger cleanup:
1. Add a cleanup endpoint (temporary):
   ```python
   @app.post("/admin/cleanup")
   async def manual_cleanup():
       if detector:
           detector.cleanup_inactive_wallets(max_inactive_days=30, min_wallets_before_cleanup=0)
       return {"status": "cleaned"}
   ```

2. Call it:
   ```bash
   curl -X POST https://web-production-9d2d3.up.railway.app/admin/cleanup
   ```

### If Still Getting OOM

Consider:
1. **Lower the cleanup threshold:**
   - Change `min_wallets_before_cleanup` from 10,000 to 5,000
   - Change `max_inactive_days` from 30 to 14

2. **Upgrade Railway plan:**
   - Current: Hobby ($5/mo) - 8 GB RAM
   - Next: Pro ($20/mo) - 32 GB RAM
   - But this shouldn't be necessary with the fix!

---

## Files Changed

| File | Changes |
|------|---------|
| `src/whale_detector.py` | Added `cleanup_inactive_wallets()` method + automatic call in monitor |
| `src/main.py` | Added `/stats/memory` endpoint |
| `MEMORY_ANALYSIS_RESULTS.md` | Detailed analysis and findings |
| `MEMORY_OPTIMIZATION.md` | Implementation plan and strategy |

---

## Next Steps

1. ✅ **Deployed** - Changes pushed to main branch
2. ⏳ **Monitor** - Check memory usage daily for first week
3. 📊 **Verify** - Confirm wallet count stays under 20K
4. 🎉 **Done** - Should be stable with no more OOM crashes!

## Questions?

- **Where's the cleanup code?** → `src/whale_detector.py` line ~1492
- **How often does it run?** → Every time the monitor checks for trades (30-60s)
- **Can I adjust the thresholds?** → Yes, edit the parameters in `cleanup_inactive_wallets()`
- **Will this affect alerts?** → No, only removes wallets with no activity for 30+ days
