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
│   ├── whale_detector.py    # Core detection logic (ENHANCED)
│   ├── alerter.py           # Multi-channel notifications
│   ├── scheduler.py         # Email digest scheduling (NEW)
│   └── subscriptions.py     # Subscription management (NEW)
├── dashboard/               # React/Next.js frontend
│   └── src/
│       ├── app/            # Next.js pages
│       └── components/     # React components
├── requirements.txt
├── .env.example
└── PROJECT_MEMORY.md       # This file
```

## Key Features

### Alert Types (12 total - Enhanced January 2026)

**ORIGINAL DETECTORS (6):**
1. **WHALE_TRADE** - Trades >= $10,000 (configurable)
2. **UNUSUAL_SIZE** - Statistically abnormal (z-score based)
3. **MARKET_ANOMALY** - Unusual for specific market
4. **NEW_WALLET** - First-time traders with large bets
5. **FOCUSED_WALLET** - Wallets concentrated in few markets
6. **SMART_MONEY** - Wallets with >60% historical win rate

**NEW DETECTORS (6) - Inspired by Polymaster, PredictOS, PolyTrack:**
7. **REPEAT_ACTOR** - Wallets with 2+ trades in last hour (velocity detection)
8. **HEAVY_ACTOR** - Wallets with 5+ trades in last 24 hours
9. **EXTREME_CONFIDENCE** - Bets on >95% or <5% probability outcomes
10. **WHALE_EXIT** - Tracking when whales sell/unwind positions
11. **CONTRARIAN** - Large bets against market consensus (<15% probability)
12. **CLUSTER_ACTIVITY** - Coordinated wallet detection (same market, similar timing)

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
| `GET /stats/detection` | All 12 detection type counts |
| `GET /stats/velocity` | Repeat actors & heavy actors |
| `GET /stats/clusters` | Detected wallet clusters |
| `GET /stats/exits` | Whales exiting positions |
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

## Contact

Project Owner: Spencer H
Location: `C:\Users\Spencer H\Desktop\Predicition Markets\prediction-market-tracker\prediction-market-tracker`
