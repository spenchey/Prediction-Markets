# Project Memory - Prediction Market Whale Tracker

> This file helps AI assistants understand the project context and continue work from previous sessions.
> **Last Updated:** January 13, 2026 - **LIVE ON RAILWAY WITH DISCORD ALERTS**

## Project Overview

**Goal:** Build a subscription-based service that identifies high-value signals in prediction markets by tracking:
1. Large bets ("whale" trades) in real-time
2. New accounts making outsized bets (potential insider knowledge)
3. Accounts with high historical win rates ("smart money")
4. Accounts focused on specific markets (potential informed traders)

**Target Markets:** Non-sports prediction markets (politics, crypto, economics, events)
- Polymarket (primary)
- Kalshi (planned)
- Other platforms (future)

**Business Model:** Subscription service with:
- Free tier: Delayed alerts, basic access
- Pro tier ($29/month): Real-time alerts, smart money access, API
- Enterprise tier ($99/month): Unlimited, webhooks, priority support

## Project History

### Initial Development (ChatGPT + Sonnet)
Two separate implementations were created:
1. **Main Project (Sonnet):** Full-featured FastAPI app with React dashboard, multi-channel notifications
2. **MVP Project (ChatGPT):** Lightweight detector with focused wallet detection and granular severity

### Combined Implementation (Opus - January 2026)
Merged best features from both codebases:
- **From Sonnet:** Async architecture, comprehensive alerter, React dashboard, database persistence
- **From ChatGPT:** FOCUSED_WALLET detection, granular 1-10 severity scores, market anomaly detection
- **New additions:** Sports filtering, subscription management, email digests, smart money tracking

## Architecture

```
prediction-market-tracker/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration (env vars, settings)
│   ├── database.py          # SQLAlchemy models and DB operations
│   ├── polymarket_client.py # Polymarket API client
│   ├── kalshi_client.py     # Kalshi API client (partial)
│   ├── whale_detector.py    # Core detection logic (14 alert types)
│   ├── alerter.py           # Multi-channel notifications
│   ├── scheduler.py         # Email digest scheduling
│   ├── subscriptions.py     # Subscription management
│   ├── entity_engine.py     # Union-Find wallet clustering (NEW - ChatGPT v5)
│   ├── wallet_profiler.py   # On-chain wallet profiling (NEW - ChatGPT v5)
│   └── websocket_client.py  # WebSocket real-time client
├── dashboard/               # React/Next.js frontend
│   └── src/
│       ├── app/            # Next.js pages
│       └── components/     # React components
├── requirements.txt
├── .env.example
└── PROJECT_MEMORY.md       # This file
```

## Key Features

### Alert Types (14 total - Enhanced January 2026)

**ORIGINAL DETECTORS (6):**
1. **WHALE_TRADE** - Trades >= $10,000 (configurable)
2. **UNUSUAL_SIZE** - Statistically abnormal (z-score based)
3. **MARKET_ANOMALY** - Unusual for specific market
4. **NEW_WALLET** - First-time traders with large bets
5. **FOCUSED_WALLET** - Wallets concentrated in few markets
6. **SMART_MONEY** - Wallets with >60% historical win rate

**VELOCITY DETECTORS (6) - Inspired by Polymaster, PredictOS, PolyTrack:**
7. **REPEAT_ACTOR** - Wallets with 2+ trades in last hour (velocity detection)
8. **HEAVY_ACTOR** - Wallets with 5+ trades in last 24 hours
9. **EXTREME_CONFIDENCE** - Bets on >95% or <5% probability outcomes
10. **WHALE_EXIT** - Tracking when whales sell/unwind positions
11. **CONTRARIAN** - Large bets against market consensus (<15% probability)
12. **CLUSTER_ACTIVITY** - Coordinated wallet detection (same market, similar timing)

**ADVANCED ENTITY DETECTORS (2) - ChatGPT v5 Integration:**
13. **HIGH_IMPACT** - Trade volume >= 8% of market's hourly volume
14. **ENTITY_ACTIVITY** - Wallet belongs to detected multi-wallet entity

### Severity System
- **Categorical:** LOW, MEDIUM, HIGH (for display)
- **Granular:** 1-10 score (for filtering/sorting)

### Sports Filtering
Markets are classified as sports/non-sports using keyword detection. Sports markets are filtered OUT by default since the focus is on political/crypto/event markets where insider information is more likely.

### Notification Channels
- Console (always on)
- Email (via Resend.com)
- Discord (webhook)
- Telegram (bot)
- Slack (webhook)
- Push (Expo for mobile)
- Webhook (Enterprise only)

### Scheduled Reports
- Daily digest at 8 AM UTC
- Weekly report on Mondays at 9 AM UTC

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check |
| `GET /health` | Railway health check |
| `GET /markets` | List active markets |
| `GET /trades` | Recent trades |
| `GET /trades/whales` | Whale trades only |
| `GET /trades/wallet/{address}` | Trades by wallet |
| `GET /alerts` | Recent alerts |
| `GET /alerts/stream` | SSE real-time alerts |
| `GET /alerts/types` | Alert counts by type |
| `GET /stats` | Overall statistics |
| `GET /stats/wallets` | Wallet leaderboard (with velocity flags) |
| `GET /stats/detection` | All 14 detection type counts |
| `GET /stats/velocity` | Repeat actors & heavy actors |
| `GET /stats/clusters` | Detected wallet clusters |
| `GET /stats/exits` | Whales exiting positions |
| `GET /stats/entities` | All detected multi-wallet entities (NEW) |
| `GET /entity/{wallet}` | Entity membership for a wallet (NEW) |
| `POST /scan` | Manual scan trigger |

## Configuration (.env)

Key settings to configure:
```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./trades.db

# Detection thresholds
WHALE_THRESHOLD_USDC=10000
EXCLUDE_SPORTS_MARKETS=true

# Notifications (configure at least one)
RESEND_API_KEY=re_xxxxx
ALERT_EMAIL=your@email.com
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Digests
DAILY_DIGEST_HOUR=8
WEEKLY_DIGEST_DAY=mon
```

## Current Status

### Completed
- [x] Core whale detection with 6 alert types
- [x] Sports market filtering
- [x] Multi-channel notifications
- [x] Database persistence
- [x] REST API with SSE streaming
- [x] React dashboard scaffolding
- [x] Subscription management module
- [x] Email digest scheduler
- [x] Configuration system
- [x] **Pushed to GitHub** - https://github.com/spenchey/Prediction-Markets
- [x] **Fixed Polymarket API client** (see API Fixes section below)
- [x] **Created deployment files** (Dockerfile, railway.toml, nixpacks.toml, Procfile)
- [x] **Added PostgreSQL support** to database.py
- [x] **Removed pandas/numpy** from requirements (caused build failures)
- [x] **DEPLOYED TO RAILWAY** - Using Nixpacks (not Dockerfile) - January 13, 2026

### LIVE DEPLOYMENT (January 13, 2026)
**Status:** ✅ **LIVE AND SENDING DISCORD ALERTS**

**Live URL:** https://web-production-9d2d3.up.railway.app

**Railway Project:** shimmering-kindness
- Service: web (the app)
- Service: Postgres (database)

**Configured Alerts:**
- ✅ Discord webhook connected
- Whale threshold: $10,000
- Poll interval: 30 seconds

---

### Railway CLI Setup (for future management)

The project is linked to Railway CLI. To manage:

```bash
cd "C:\Users\Spencer H\Desktop\Predicition Markets\prediction-market-tracker\prediction-market-tracker"

# View logs
railway logs

# Check status
railway status

# Set environment variables
railway variables --set "KEY=value"

# View all variables
railway variables

# Deploy manually (usually auto-deploys on git push)
railway up
```

**Project IDs (for CLI linking):**
- Project: `5c4be819-17ea-4113-b986-8462c2f7454a`
- Environment: `ffd50b3e-b07a-436a-b0b7-be3bfad2760d`
- Web Service: `ee7eafaf-33fe-4566-8109-ca6e719cbc34`

To re-link if needed:
```bash
railway link --project 5c4be819-17ea-4113-b986-8462c2f7454a --environment ffd50b3e-b07a-436a-b0b7-be3bfad2760d --service ee7eafaf-33fe-4566-8109-ca6e719cbc34
```

---

### Critical Learning - USE NIXPACKS, NOT DOCKERFILE:
After many failed attempts with Dockerfile-based deployment, the solution was simple:
1. **Rename/remove Dockerfile** → `Dockerfile.bak`
2. **Let Railway use Nixpacks** (its default builder)
3. **Add `.python-version`** file with `3.11`
4. **Use `startCommand` in railway.toml**

**Why Dockerfile Failed:**
- Railway's healthcheck never saw any output from the container
- Multiple CMD formats tried (shell form, exec form, inline commands)
- Multi-stage and single-stage builds both failed
- The container would start but uvicorn never seemed to run
- Likely a Railway-specific issue with Dockerfile CMD handling

**What Worked:**
```toml
# railway.toml
[build]
# Let Railway auto-detect (Nixpacks) - NO builder specified

[deploy]
startCommand = "uvicorn src.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 60
```

**Key Files for Deployment:**
- `railway.toml` - Railway configuration (Nixpacks + startCommand)
- `.python-version` - Specifies Python 3.11
- `Procfile` - Backup start command
- `requirements.txt` - Dependencies (NO pandas/numpy)
- `Dockerfile.bak` - Backed up, not used

**Environment Variables (configured via Railway CLI):**
| Variable | Status |
|----------|--------|
| `DATABASE_URL` | ✅ Connected to Railway Postgres |
| `DISCORD_WEBHOOK_URL` | ✅ Configured |
| `WHALE_THRESHOLD_USDC` | ✅ Set to 10000 |
| `POLL_INTERVAL` | ✅ Set to 30 |
| `LOG_LEVEL` | ✅ Set to INFO |
| `RESEND_API_KEY` | ❌ Not configured (email alerts disabled) |
| `TELEGRAM_BOT_TOKEN` | ❌ Not configured |
| `SLACK_WEBHOOK_URL` | ❌ Not configured |

To add more notification channels, use:
```bash
railway variables --set "RESEND_API_KEY=re_xxxxx" --set "ALERT_EMAIL=you@email.com"
```

### Enhanced Detection (January 13, 2026)
Added 6 new detection algorithms inspired by competitors:
- **Polymaster** (github.com/neur0map/polymaster) - Repeat/heavy actor detection
- **PredictOS** (github.com/PredictionXBT/PredictOS) - Multi-agent AI, WebSocket
- **PolyTrack** (polytrackhq.app) - Cluster detection concept

New features:
- [x] Velocity tracking (trades/hour, trades/day per wallet)
- [x] Extreme confidence detection (>95% or <5% bets)
- [x] Exit detection (whale position unwinding)
- [x] Contrarian detection (bets against consensus)
- [x] Basic cluster detection (coordinated wallets)
- [x] WebSocket client module (src/websocket_client.py)

### Entity Clustering System (January 13, 2026 - ChatGPT v5 + v6)
Integrated advanced entity clustering from ChatGPT's pm_whale_tracker_v5 and v6:

**New Files:**
- `src/entity_engine.py` - Union-Find clustering with edge decay
- `src/wallet_profiler.py` - On-chain wallet profiling

**Entity Detection Features:**
- **Union-Find clustering** - Groups related wallets into entities
- **Edge signals with decay:**
  - `shared_funder` (0.90 weight) - Wallets funded from same source
  - `time_coupled` (0.18 weight) - Wallets trading same market within 5 min
  - `market_overlap` (0.40 weight) - Wallets trading similar markets (Jaccard similarity)
- **Edge decay** - Half-life of 86400 seconds (connections fade over time)
- **Saturation** - Diminishing returns per signal type (factor 0.55)
- **Impact ratio** - Trade cash / market hourly volume

**v6 Enhancements:**
- **Market liquidity scaling** - Edge weights scale based on market volume
  - High-volume markets need more evidence to link wallets
  - Low-volume markets need less evidence
  - Scale range: 0.35x to 1.25x (baseline $50k/hour)
- **Stable entity IDs** - Sequential IDs (ent_000001) that persist across rebuilds
  - Reuses entity IDs when wallet overlap detected
  - Better for tracking entities over time

**New API Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `GET /stats/entities` | All detected entities with wallet counts |
| `GET /entity/{wallet}` | Get entity membership for a wallet |

**Environment Variables (optional, for wallet profiling):**
```bash
POLYGON_RPC_URL=https://polygon-rpc.com
POLYGONSCAN_API_KEY=your_key_here
MARKET_LIQUIDITY_BASELINE=50000
MARKET_IMPORTANCE_MIN_SCALE=0.35
MARKET_IMPORTANCE_MAX_SCALE=1.25
```

### Future Work
- [ ] Win rate tracking (needs market resolution data)
- [ ] Stripe payment integration
- [ ] Automated trading module
- [ ] Mobile app (React Native)
- [ ] Kalshi integration
- [ ] Enable WebSocket mode in production (currently REST polling)
- [ ] Machine learning for pattern detection
- [ ] Portfolio management/copy trading
- [ ] Advanced cluster detection (behavioral similarity)

---

## API Fixes Applied (January 12, 2026)

The Polymarket APIs had changed since the original code was written. These fixes were applied:

### 1. Markets API - outcomePrices Format Change
**File:** `src/polymarket_client.py` - `get_active_markets()`
**Issue:** `outcomePrices` is now a JSON string like `'["0.65", "0.35"]'` instead of a list
**Fix:** Added JSON parsing:
```python
import json
outcome_prices_raw = item.get("outcomePrices", '["0.5", "0.5"]')
if isinstance(outcome_prices_raw, str):
    prices = json.loads(outcome_prices_raw)
else:
    prices = outcome_prices_raw
```

### 2. Trades API - Authentication Required
**File:** `src/polymarket_client.py` - `get_recent_trades()` and `get_trades_by_address()`
**Issue:** `clob.polymarket.com` now requires authentication (returns 401)
**Fix:** Changed to use `data-api.polymarket.com` which is public:
```python
# Old (broken): https://clob.polymarket.com/trades
# New (working): https://data-api.polymarket.com/trades
```

### 3. Database URL for PostgreSQL
**File:** `src/database.py`
**Added:** `get_async_database_url()` function to convert PostgreSQL URLs for asyncpg:
```python
def get_async_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url
```

---

## Deployment Files (Railway with Nixpacks)

| File | Purpose |
|------|---------|
| `railway.toml` | Railway config - Nixpacks builder, startCommand, health checks |
| `.python-version` | Specifies Python 3.11 for Nixpacks |
| `Procfile` | Heroku-style start command (backup) |
| `.dockerignore` | Excludes tests, docs, local DBs from container |
| `Dockerfile.bak` | **DISABLED** - Dockerfile didn't work with Railway, kept as backup |

**IMPORTANT:** Do NOT rename `Dockerfile.bak` back to `Dockerfile`. Railway's Dockerfile handling caused healthcheck failures. Nixpacks works correctly.

### GOTCHA: main.py Was Stripped During Debugging

During deployment debugging, `src/main.py` was replaced with an ultra-minimal version (just health endpoint). The full version was restored from git commit `266a97c`:

```bash
git checkout 266a97c -- src/main.py
```

If the app shows "minimal version running" or alerts aren't working, check that main.py has the full whale detection code (should be ~400+ lines, not ~25 lines).

---

## How to Continue Development

### Running Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Copy env file
cp .env.example .env
# Edit .env with your API keys

# Run the backend
uvicorn src.main:app --reload

# Run the dashboard (separate terminal)
cd dashboard
npm install
npm run dev
```

### Key Files to Understand
1. `src/whale_detector.py` - Core detection logic
2. `src/main.py` - API endpoints and app lifecycle
3. `src/config.py` - All configurable settings
4. `src/subscriptions.py` - Subscription tiers and limits

### Testing Detection
```bash
# Run the detector test
python -m src.whale_detector
```

## Notes for AI Assistants

When working on this project:
1. **Always filter sports markets** - This is a key differentiator
2. **Maintain both severity systems** - Categorical for display, numeric for filtering
3. **Test with real Polymarket data** - APIs are public, no auth needed
4. **Don't commit API keys** - Use .env file
5. **Keep subscriptions.py updated** - It defines business logic
6. **Railway CLI is linked** - Use `railway variables`, `railway logs`, etc.
7. **NEVER use Dockerfile** - Nixpacks works, Dockerfile doesn't on Railway
8. **Check main.py size** - If it's tiny (~25 lines), restore full version from git
9. **Discord alerts are live** - Changes to alerter.py will affect production immediately

## Session Log

### January 13, 2026 - ChatGPT v5 + v6 Integration Session

**What was done:**

1. **Analyzed ChatGPT's pm_whale_tracker_v5.zip**
   - Extracted and reviewed all Python modules
   - Identified key features: Union-Find clustering, edge decay, saturation, entity scoring

2. **Created new modules from v5:**
   - `src/entity_engine.py` (500+ lines) - Full entity clustering engine
   - `src/wallet_profiler.py` (200+ lines) - On-chain wallet profiling via Polygon RPC

3. **Updated whale_detector.py with 2 new alert types:**
   - HIGH_IMPACT - Trades >= 8% of market hourly volume
   - ENTITY_ACTIVITY - Wallet belongs to detected multi-wallet entity
   - Total alert types: 14

4. **Added API endpoints in main.py:**
   - `GET /stats/entities` - List all detected entities
   - `GET /entity/{wallet}` - Get entity for a wallet

5. **Integrated ChatGPT's pm_whale_tracker_v6.zip enhancements:**
   - Market liquidity scaling (edges weighted by market volume)
   - Stable entity IDs (sequential, persist across rebuilds)
   - New parameters for liquidity baseline and scale factors

6. **Deployed to Railway:**
   - All commits pushed to GitHub master and main branches
   - Railway auto-deployed successfully
   - Health endpoint confirmed working
   - Discord alerts confirmed working

**Commits made:**
```
57f15d2 Document v6 entity clustering features
8542613 Add v6 entity clustering features
75a330b Update PROJECT_MEMORY with entity clustering documentation
589fa68 Add entity clustering and impact ratio from ChatGPT v5
```

**Files modified/created:**
- `src/entity_engine.py` (NEW)
- `src/wallet_profiler.py` (NEW)
- `src/whale_detector.py` (MODIFIED)
- `src/main.py` (MODIFIED)
- `PROJECT_MEMORY.md` (MODIFIED)

**Live deployment verified:**
- URL: https://web-production-9d2d3.up.railway.app
- Health: ✅ OK
- Database: ✅ Connected
- Discord alerts: ✅ Working

---

### January 19, 2026 - Alert Threshold & WebSocket Fix Session

**What was done:**

1. **Raised minimum alert threshold from $450 to $1,000**
   - User requested fewer alerts
   - Updated `min_alert_threshold_usd` in `whale_detector.py`

2. **Updated exempt alert types**
   - Changed from: `CLUSTER_ACTIVITY`, `WHALE_EXIT`, `VIP_WALLET`
   - Changed to: `CLUSTER_ACTIVITY`, `REPEAT_ACTOR`, `HEAVY_ACTOR`
   - Reason: User wants cluster trading and multi-trade execution alerts at any amount

3. **Fixed market lookup for category detection**
   - **Problem**: World/Entertainment alerts all going to "Other" thread since 1/16
   - **Root cause**: `get_market_by_id()` used Gamma API `/markets/{id}` which expects numeric IDs, but trades have condition IDs (hex strings like `0x702e...`)
   - **Fix**: Changed to use CLOB API (`clob.polymarket.com/markets/{condition_id}`) which correctly accepts condition IDs
   - Now market questions are fetched properly → category detection works → alerts route to correct Discord threads

4. **Fixed WebSocket trade parsing (MAJOR BUG)**
   - **Problem**: WebSocket received 4,339 trades but generated 0 alerts, while polling generated 11 alerts
   - **Root cause**: WebSocket messages have wrapper structure:
     ```json
     {
       "connection_id": "...",
       "payload": { <actual trade data> },
       "timestamp": "...",
       "topic": "...",
       "type": "..."
     }
     ```
     Code was reading `size`/`price` from top level (got 0), not from `payload`
   - **Fix**: Updated `_handle_trade()` to extract from payload:
     ```python
     trade_data = data.get("payload") or data.get("data") or data
     ```
   - **Result**: WebSocket now generates alerts properly (7 alerts from 1,998 trades after fix)

5. **Updated Twitter-worthy criteria (stricter for-twitter highlights)**
   - **Problem**: for-twitter was getting too many alerts, rate limited at 4/hour first-come-first-served
   - **Solution**: Stricter criteria so only truly exceptional alerts make it to for-twitter
   - **New criteria** (must meet one):
     | Tier | Criteria | Why |
     |------|----------|-----|
     | 1 | $10,000+ | True whale territory |
     | 2 | $1,000+ with REPEAT_ACTOR, HEAVY_ACTOR, or CLUSTER | Multi-trade patterns |
     | 3 | $5,000+ with SMART_MONEY or NEW_WALLET | Quality signals |
     | 4 | 4+ triggers | Highly unusual activity |
   - **Rate limit**: Increased from 4/hour to 20/hour (strict criteria limits naturally)
   - **Alert flow**: ALL alerts → category thread; Exceptional alerts → ALSO to for-twitter

**Commits made:**
```
19534f1 Raise min alert threshold to $1000, exempt multi-trade alerts
e8cddf8 Fix market lookup to use CLOB API for category detection
e10ec3d Fix WebSocket trade parsing - extract data from 'payload' field
36dc7d9 Remove debug logging after fixing WebSocket trade parsing
0662740 Stricter Twitter-worthy criteria for for-twitter highlights
```

**Files modified:**
- `src/whale_detector.py` - Threshold and exempt types
- `src/polymarket_client.py` - CLOB API for market lookup
- `src/polymarket_websocket.py` - Payload extraction fix
- `src/alerter.py` - Stricter is_twitter_worthy() criteria
- `src/config.py` - Rate limit increase

**Key Configuration (current):**
| Setting | Value |
|---------|-------|
| `min_alert_threshold_usd` | $1,000 |
| Exempt types | CLUSTER_ACTIVITY, REPEAT_ACTOR, HEAVY_ACTOR |
| Market lookup API | CLOB (`clob.polymarket.com`) |
| Twitter rate limit | 20/hour |
| Twitter-worthy minimum | $10k (or $1k-$5k with quality signals) |

---

## Contact

Project Owner: Spencer H
Location: `C:\Users\Spencer H\Desktop\Predicition Markets\prediction-market-tracker\prediction-market-tracker`
