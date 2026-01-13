# Project Memory - Prediction Market Whale Tracker

> This file helps AI assistants understand the project context and continue work from previous sessions.
> **Last Updated:** January 13, 2026 - **DEPLOYED SUCCESSFULLY TO RAILWAY**

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

### Alert Types (6 total)
1. **WHALE_TRADE** - Trades >= $10,000 (configurable)
2. **UNUSUAL_SIZE** - Statistically abnormal (z-score based)
3. **MARKET_ANOMALY** - Unusual for specific market (from ChatGPT MVP)
4. **NEW_WALLET** - First-time traders with large bets
5. **FOCUSED_WALLET** - Wallets concentrated in few markets (from ChatGPT MVP)
6. **SMART_MONEY** - Wallets with >60% historical win rate

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
| `GET /markets` | List active markets |
| `GET /trades` | Recent trades |
| `GET /trades/whales` | Whale trades only |
| `GET /trades/wallet/{address}` | Trades by wallet |
| `GET /alerts` | Recent alerts |
| `GET /alerts/stream` | SSE real-time alerts |
| `GET /stats` | Overall statistics |
| `GET /stats/wallets` | Wallet leaderboard |
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

### COMPLETED - Railway Deployment (January 13, 2026)
**Status:** ✅ **DEPLOYED AND RUNNING**

**Critical Learning - USE NIXPACKS, NOT DOCKERFILE:**
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

**Environment Variables (set in Railway dashboard):**
- `DATABASE_URL` = (auto-set by PostgreSQL addon)
- `WHALE_THRESHOLD_USDC` = 10000
- `POLL_INTERVAL` = 30
- `LOG_LEVEL` = INFO
- `RESEND_API_KEY` = (if using email alerts)
- `DISCORD_WEBHOOK_URL` = (if using Discord)
- `ALERT_EMAIL` = your@email.com

### Future Work
- [ ] Win rate tracking (needs market resolution data)
- [ ] Stripe payment integration
- [ ] Automated trading module
- [ ] Mobile app (React Native)
- [ ] Kalshi integration
- [ ] WebSocket support for real-time updates
- [ ] Machine learning for pattern detection
- [ ] Portfolio management/copy trading

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

## Contact

Project Owner: Spencer H
Location: `C:\Users\Spencer H\Desktop\Predicition Markets\prediction-market-tracker\prediction-market-tracker`
