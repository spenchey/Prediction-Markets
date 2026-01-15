# Prediction Market Whale Tracker - Claude Code Configuration

## Project Overview

A subscription-based service that identifies high-value signals in prediction markets by tracking whale trades, smart money, and new accounts making outsized bets in non-sports markets.

## Skills Integration

This project uses [Superpowers](https://github.com/obra/superpowers) for structured development workflows.

**Skills are located in:** `.superpowers/skills/`

### Required Workflows

Before implementing any feature:
1. **Brainstorming** - Refine requirements through questions
2. **Writing Plans** - Create detailed implementation plans
3. **TDD** - Write failing test → watch fail → implement → watch pass → refactor
4. **Code Review** - Review against plan before marking complete

### Key Skills to Use

| Skill | When to Use |
|-------|-------------|
| `@.superpowers/skills/test-driven-development/SKILL.md` | Before writing ANY implementation code |
| `@.superpowers/skills/writing-plans/SKILL.md` | When planning multi-step features |
| `@.superpowers/skills/brainstorming/SKILL.md` | When requirements are unclear |
| `@.superpowers/skills/systematic-debugging/SKILL.md` | When debugging issues |
| `@.superpowers/skills/subagent-driven-development/SKILL.md` | For parallel task execution |

## Project Structure

```
prediction-market-tracker/
├── src/                    # Python backend
│   ├── main.py            # FastAPI app entry point
│   ├── config.py          # Configuration settings
│   ├── database.py        # SQLAlchemy models
│   ├── polymarket_client.py # Polymarket API client
│   ├── kalshi_client.py     # Kalshi API client (with RSA auth for trades)
│   ├── whale_detector.py  # Core detection logic (6 alert types)
│   ├── alerter.py         # Multi-channel notifications
│   ├── scheduler.py       # Email digest scheduling
│   └── subscriptions.py   # Subscription tier management
├── tests/                  # Test suite (TDD)
│   ├── test_whale_detector.py
│   ├── test_alerter.py
│   └── ...
├── dashboard/             # React/Next.js frontend
├── docs/plans/            # Implementation plans (Superpowers format)
├── .superpowers/          # Superpowers skills library
└── PROJECT_MEMORY.md      # Session continuity file
```

## Core Business Logic

### Alert Types (6 total)
1. **WHALE_TRADE** - Trades >= $10,000
2. **UNUSUAL_SIZE** - Z-score > 3 std deviations
3. **MARKET_ANOMALY** - Unusual for specific market
4. **NEW_WALLET** - First-time traders with $1k+ bets
5. **FOCUSED_WALLET** - Wallets in <=3 markets with 5+ trades
6. **SMART_MONEY** - Wallets with >60% win rate

### Key Constraint: No Sports Markets
Sports markets (NFL, NBA, etc.) are filtered OUT. Focus is on political/crypto/events where insider information is more likely.

## Testing Requirements

**All tests must follow TDD (Red-Green-Refactor):**

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_whale_detector.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

**Test file naming:** `tests/test_<module_name>.py`

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run backend
uvicorn src.main:app --reload

# Run dashboard
cd dashboard && npm run dev

# Run tests
pytest tests/ -v
```

## Implementation Plans Location

Save all implementation plans to: `docs/plans/YYYY-MM-DD-<feature-name>.md`

Current planned features:
- [ ] Stripe billing integration
- [x] Kalshi market integration (full - markets + trades)
- [x] Kalshi authenticated API (RSA-PSS signing implemented)
- [ ] Automated trading module
- [ ] Mobile app (React Native)

## Code Quality Standards

- **TDD:** Write failing test first, ALWAYS
- **DRY:** Don't repeat yourself
- **YAGNI:** Don't add features until needed
- **Type hints:** Use Python type hints
- **Docstrings:** Document public functions
- **Frequent commits:** Small, focused commits

## API Keys Required

See `.env.example` for all required/optional API keys:
- Polymarket (public, no key needed)
- Resend (email alerts)
- Discord/Telegram/Slack webhooks
- Stripe (billing - planned)
- Kalshi (API key + RSA private key for trade data)

---

## Railway Deployment

The service is deployed on Railway with automatic deployments from GitHub.

### Project Details
- **Project Name**: shimmering-kindness
- **Service Name**: web
- **Public URL**: https://web-production-9d2d3.up.railway.app
- **Health Check**: https://web-production-9d2d3.up.railway.app/health

### Railway CLI Commands
```bash
# Check status
railway status

# View logs
railway logs -n 100

# Set environment variable
railway variables --set KEY=value

# Deploy current code
railway up --detach

# Redeploy last deployment
railway redeploy -y
```

### Environment Variables (Railway)
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (auto-set by Railway) |
| `DISCORD_WEBHOOK_URL` | Discord webhook for forum channel |
| `DISCORD_THREAD_ID` | Thread ID for posting alerts (see below) |
| `POLL_INTERVAL` | Trade polling interval in seconds (default: 30) |
| `WHALE_THRESHOLD_USDC` | Minimum USD for whale alerts (default: 10000) |
| `LOG_LEVEL` | Logging level (default: INFO) |
| `KALSHI_API_KEY` | Kalshi API key ID (UUID format) |
| `KALSHI_PRIVATE_KEY_B64` | Base64-encoded RSA private key for Kalshi |

---

## Discord Forum Channel Configuration

The Discord webhook points to a **forum channel**, which requires special handling.

### Category-Based Thread Routing (Added 2026-01-15)

Alerts are automatically routed to category-specific threads:

| Category | Thread ID | Thread Name |
|----------|-----------|-------------|
| Politics | `1461398615242313819` | 🏛️ Politics Alerts |
| Crypto | `1461399011373092884` | ₿ Crypto Alerts |
| Sports | `1461403481255579748` | ⚽ Sports Alerts |
| Finance | `1461400496379138271` | 📈 Finance Alerts |
| Entertainment | `1461400992028299447` | 🎬 Entertainment Alerts |
| World | `1461401409709674618` | 🌍 World Alerts |
| Other (fallback) | `1461073799905542420` | Whale Alerts |

**Environment Variables for Category Routing:**
```bash
DISCORD_THREAD_POLITICS=1461398615242313819
DISCORD_THREAD_CRYPTO=1461399011373092884
DISCORD_THREAD_SPORTS=1461403481255579748
DISCORD_THREAD_FINANCE=1461400496379138271
DISCORD_THREAD_ENTERTAINMENT=1461400992028299447
DISCORD_THREAD_WORLD=1461401409709674618
DISCORD_THREAD_OTHER=1461073799905542420
```

### Key Details
- **Webhook URL**: Stored in Railway as `DISCORD_WEBHOOK_URL`
- **Default Thread ID**: `1461073799905542420` (the "Whale Alerts" thread - fallback)
- **Thread Name**: "Whale Alerts"

### How Forum Channels Work
Discord forum channels require either:
1. `thread_id` as a **URL query parameter** (to post to existing thread)
2. `thread_name` in JSON body (to create new thread per message)

**IMPORTANT**: `thread_id` must be passed as a query param, NOT in the JSON body:
```python
# Correct
url = f"{webhook_url}?thread_id={thread_id}"
client.post(url, json=payload)

# Wrong - will fail with error 220001
payload["thread_id"] = thread_id  # Does NOT work!
```

### Testing Discord Webhook
```bash
cd prediction-market-tracker
python test_discord.py
```

The test script auto-detects forum channels and retries with `thread_name` if needed.

---

## Alert Types (14 total)

### Original (6)
1. **WHALE_TRADE** - Trades >= $10,000
2. **UNUSUAL_SIZE** - Z-score > 3 std deviations
3. **MARKET_ANOMALY** - Unusual for specific market
4. **NEW_WALLET** - First-time traders with $1k+ bets
5. **FOCUSED_WALLET** - Wallets in <=3 markets with 5+ trades
6. **SMART_MONEY** - Wallets with >60% win rate

### Added January 2026 (8)
7. **REPEAT_ACTOR** - 2+ trades in last hour
8. **HEAVY_ACTOR** - 5+ trades in last 24 hours
9. **EXTREME_CONFIDENCE** - Bets at 90%+ or 10%- odds
10. **WHALE_EXIT** - Large positions being unwound
11. **CONTRARIAN** - Betting against market consensus
12. **CLUSTER_ACTIVITY** - Coordinated multi-wallet trading
13. **HIGH_IMPACT** - Trade is large % of market's hourly volume
14. **ENTITY_ACTIVITY** - Multi-wallet entity detected

---

## Session Log (2026-01-14)

### Issue: Discord Alerts Not Posting

**Problem**: Alerts showing "sent to 1/2 channels" - Discord was failing silently.

**Root Cause**:
1. Discord webhook pointed to a **forum channel**
2. Forum channels require `thread_id` or `thread_name`
3. Initial fix passed `thread_id` in JSON body - **wrong!**
4. Discord API requires `thread_id` as URL query parameter

**Solution**:
1. Updated `src/alerter.py` to pass thread_id as query param:
   ```python
   url = f"{self.webhook_url}?thread_id={self.thread_id}"
   ```
2. Created "Whale Alerts" thread in forum channel
3. Set `DISCORD_THREAD_ID=1461073799905542420` on Railway

### Files Changed
- `src/alerter.py` - Discord forum channel support with thread_id as query param
- `src/config.py` - Added `DISCORD_THREAD_ID` and `DISCORD_THREAD_NAME` config options
- `test_discord.py` - New script to test Discord webhook connectivity

### Commits
- `700704c` - Add Discord forum channel support
- `70e8367` - Fix Discord forum channel: thread_id as query param
- `1d2e2eb` - Improve alert quality and clarity

### Result
Alerts now posting successfully to Discord:
```
🎮 Discord alert sent
📢 Alert sent to 2/2 channels
```

---

### Issue: Alert Quality Improvements (Same Session)

**Problems reported:**
1. No platform identification (Polymarket vs Kalshi vs PredictIt)
2. Market question not always shown (just saw "Down" outcome with no context)
3. Severity meaning unclear (what does HIGH mean?)

**Solution:**
Updated `alerter.py` and `polymarket_client.py`:

1. **Added `platform` field** to Trade dataclass (defaults to "Polymarket")
2. **Market question always shown** - Falls back to market ID if unavailable
3. **Position instead of Outcome** - Shows "Buy No" or "Sold Yes" instead of just "No"
4. **Severity explanation** - HIGH/MEDIUM/LOW now include descriptions

**New Alert Format (v2 - with links and categories):**
```
📊 Market: Will Elon Musk post 440-459 tweets...? [clickable link]
🏛️ Category: Entertainment
🏦 Platform: Polymarket
💰 Amount: $1,150.66
🎯 Position: Buy No
⚡ Severity: HIGH (Large trade size, unusual pattern, or high-confidence signal)
👤 Trader: 0x1234... [clickable link to profile]
```

**New Features (commit d9790c7):**
- **Market URL** - Clickable link to Polymarket market page
- **Trader URL** - Clickable link to trader's Polymarket profile
- **Category** - Auto-detected (Politics, Crypto, Sports, Finance, Entertainment, Science, World, Other)
- **Category emojis**: 🏛️ Politics, ₿ Crypto, ⚽ Sports, 📈 Finance, 🎬 Entertainment, 🔬 Science, 🌍 World

**Category Detection:**
1. First checks API tags field
2. Falls back to keyword matching in question text:
   - Politics: trump, biden, election, congress, senate, etc.
   - Crypto: bitcoin, ethereum, btc, eth, blockchain, etc.
   - Sports: nfl, nba, super bowl, championship, etc.
   - Finance: stock, fed, inflation, gdp, etc.
   - Entertainment: oscar, grammy, twitter, elon, etc.

**Severity Meanings:**
- **HIGH** - Large trade size, unusual pattern, or high-confidence signal
- **MEDIUM** - Notable activity worth monitoring
- **LOW** - Minor signal, may be noise

**Position Action (commit 5ca64bc):**
Tracks whether a trade is opening, adding to, or closing a position:
- 🆕 **OPENING** - First trade in this market/outcome (new position)
- ➕ **ADDING** - Adding to an existing position in same direction
- 🔚 **CLOSING** - Reducing/exiting an existing position

**How it works:**
- Tracks per-market positions for each wallet (buy_shares, sell_shares, USD amounts)
- Before each trade, checks wallet's existing position in that market/outcome
- Long position (bought > sold) + SELL = CLOSING
- Long position + BUY = ADDING
- No position + any trade = OPENING
- Note: Position data resets on service restart (no persistence yet)

---

## Kalshi Integration (Added 2026-01-14)

### Overview
Kalshi is a CFTC-regulated US prediction market exchange. Integration added to track both Polymarket and Kalshi markets.

### Current Status: FULL (with auth)
- ✅ Market data (prices, volume, open interest)
- ✅ Trade data (requires RSA authentication)

Note: Kalshi trades do NOT expose trader identities (unlike Polymarket's blockchain transparency).

### Files Added/Changed
- `src/kalshi_client.py` - KalshiClient with RSA-PSS authentication
- `src/whale_detector.py` - Multi-platform TradeMonitor, anonymous trader detection
- `src/alerter.py` - Platform-specific URLs, anonymous trader handling
- `src/main.py` - Initialize both Polymarket + Kalshi clients
- `src/config.py` - Added Kalshi settings

### New API Endpoints
- `GET /platforms` - Shows enabled platforms and capabilities
- `GET /markets/kalshi` - Lists active Kalshi markets
- `GET /health` - Now shows active platforms list

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `KALSHI_ENABLED` | `true` | Enable/disable Kalshi integration |
| `KALSHI_API_KEY` | `None` | API key ID from Kalshi dashboard |
| `KALSHI_PRIVATE_KEY_B64` | `None` | Base64-encoded RSA private key |

### Anonymous Trader Handling
Kalshi trades have `trader_address="KALSHI_ANON"`. The whale detector:
- **Skips** wallet-based alerts: NEW_WALLET, FOCUSED_WALLET, SMART_MONEY, REPEAT_ACTOR, HEAVY_ACTOR, WHALE_EXIT, CLUSTER_ACTIVITY, ENTITY_ACTIVITY
- **Still fires** trade-based alerts: WHALE_TRADE, UNUSUAL_SIZE, MARKET_ANOMALY, EXTREME_CONFIDENCE, HIGH_IMPACT

### How to Get Kalshi API Credentials
1. Sign up at https://kalshi.com
2. Go to Settings → API → Generate API Key
3. Download RSA private key file (.pem)
4. Base64 encode the key: `base64 -w 0 < kalshi_private_key.pem`
5. Set environment variables in Railway:
   - `KALSHI_API_KEY` - Your API key ID (UUID format)
   - `KALSHI_PRIVATE_KEY_B64` - Base64-encoded RSA private key

### Technical Details
- **API Base**: `https://api.elections.kalshi.com/trade-api/v2` (trading API deprecated)
- **Authentication**: RSA-PSS padding with SHA-256
- **Signature format**: `timestamp + method + path` (no query params)
- **Headers**: `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-TIMESTAMP`, `KALSHI-ACCESS-SIGNATURE`
- **Trade endpoint**: `/markets/trades` (global endpoint)

See: https://docs.kalshi.com/getting_started/api_keys

### Commits
- `790f661` - Add Kalshi prediction market integration
- `d87eb6b` - Add Kalshi authenticated API support for trade fetching
- `efec456` - Fix timezone-aware datetime comparison error
- `ccf6544` - Update CLAUDE.md with Kalshi auth documentation

---

## Session Log (2026-01-14) - Kalshi Authenticated API

### Task: Enable Kalshi Trade Data Fetching

**Problem**: Initial Kalshi integration only fetched market data. Trade data requires authenticated API access.

**Solution**: Implemented RSA-PSS authentication for Kalshi API.

### Implementation Steps

1. **User provided credentials**:
   - API Key ID: `18d0d054-c3fc-474d-a93d-7cefa8fa22f0`
   - RSA private key (downloaded from Kalshi dashboard)

2. **Set Railway environment variables**:
   ```bash
   railway variables --set KALSHI_API_KEY=18d0d054-c3fc-474d-a93d-7cefa8fa22f0
   railway variables --set KALSHI_PRIVATE_KEY_B64=<base64-encoded-key>
   ```

3. **Updated `src/kalshi_client.py`**:
   - Added RSA private key loading from base64 env var
   - Implemented `_sign_request()` with RSA-PSS padding + SHA-256
   - Sign message format: `timestamp + method + path` (no query params!)
   - Use elections API for all requests (trading API deprecated)
   - Changed trade endpoint from `/markets/{ticker}/trades` to `/markets/trades`

4. **Fixed timezone issue**:
   - Kalshi timestamps are timezone-aware (UTC)
   - Whale detector uses naive datetimes
   - Solution: Strip timezone info in `_convert_trade()` and `_convert_market()`

### Key Discoveries

1. **Trading API deprecated**: Kalshi moved everything to `api.elections.kalshi.com`
   - Old: `https://trading-api.kalshi.com/trade-api/v2` (returns 401 with migration message)
   - New: `https://api.elections.kalshi.com/trade-api/v2`

2. **Signature requirements** (from Kalshi docs):
   - Padding: RSA-PSS (not PKCS1v15!)
   - Hash: SHA-256
   - Salt length: digest length
   - Path: Must NOT include query parameters

3. **Trade endpoint**:
   - Per-market trades (`/markets/{ticker}/trades`) returns 404
   - Global trades (`/markets/trades`) works with optional `ticker` filter

### Files Changed
- `src/kalshi_client.py` - Full RSA auth implementation
- `src/config.py` - Added `KALSHI_PRIVATE_KEY_B64` setting

### Result
Both Polymarket and Kalshi trades now being monitored:
```
Fetched 100 trades (Polymarket)
Fetched 100 Kalshi trades
Analyzed 200 trades, generated X alerts
Platform: Kalshi (in Discord alerts)
```

### Testing Commands
```bash
# Test locally with Railway credentials
railway variables --json > kalshi_env.json
python test_kalshi_auth.py

# Check Railway logs for Kalshi activity
railway logs -n 100 | grep -i kalshi
```

---

## Session Log (2026-01-15) - Alert Filtering & Category Routing

### Changes Made

#### 1. Minimum Alert Threshold ($450)
**Problem**: Too many low-value alerts cluttering the feed.

**Solution**: Added `min_alert_threshold_usd` parameter to `WhaleDetector`:
- Default: $450 minimum for all alerts
- **Exceptions**: CLUSTER_ACTIVITY and WHALE_EXIT alerts bypass the minimum (valuable signals at any size)

**Files Changed**:
- `src/whale_detector.py` - Added `min_alert_threshold_usd` parameter and filter logic

**Code**:
```python
# Filter out low-value alerts (except cluster activity and exits)
alerts = [
    alert for alert in alerts
    if alert.trade.amount_usd >= self.min_alert_threshold_usd
    or alert.alert_type in self.exempt_alert_types
]
```

#### 2. Category-Based Discord Thread Routing
**Problem**: All alerts going to single "Whale Alerts" thread, making it hard to follow specific categories.

**Solution**: Created separate Discord threads per category and updated alerter to route automatically:

| Category | Thread ID |
|----------|-----------|
| Politics | `1461398615242313819` |
| Crypto | `1461399011373092884` |
| Finance | `1461400496379138271` |
| Entertainment | `1461400992028299447` |
| World | `1461401409709674618` |
| Other | `1461073799905542420` |

**Files Changed**:
- `src/config.py` - Added `DISCORD_THREAD_*` settings for each category
- `src/alerter.py` - Added `_get_thread_id_for_category()` method and category routing logic

**Railway Environment Variables to Set**:
```bash
railway variables --set DISCORD_THREAD_POLITICS=1461398615242313819
railway variables --set DISCORD_THREAD_CRYPTO=1461399011373092884
railway variables --set DISCORD_THREAD_SPORTS=1461403481255579748
railway variables --set DISCORD_THREAD_FINANCE=1461400496379138271
railway variables --set DISCORD_THREAD_ENTERTAINMENT=1461400992028299447
railway variables --set DISCORD_THREAD_WORLD=1461401409709674618
railway variables --set DISCORD_THREAD_OTHER=1461073799905542420
```

### Deployment
After setting environment variables, redeploy:
```bash
railway redeploy -y
```

---

## Session Log (2026-01-15) - Sports Filtering & Discord Fix

### Issues Fixed

#### 1. Sports Markets Not Being Filtered
**Problem**: Sports markets like "Grizzlies vs. Magic" and Kalshi NBA markets (KXNBATOTAL) were getting through.

**Root Causes**:
- SPORTS_KEYWORDS list didn't include team names or "vs" pattern
- Kalshi markets have `market_question=None`, only ticker has sport info

**Solution** (commits `5fe6d7a`, `cb7c948`):
- Added team names (NBA: grizzlies, magic, lakers, etc.)
- Added NFL team names (cowboys, eagles, chiefs, etc.)
- Added matchup patterns: ` vs `, ` vs. `, ` @ `
- `is_sports_market()` now checks BOTH market_question AND market_id/ticker
- Catches Kalshi tickers like KXNBATOTAL, KXNFL, etc.

#### 2. Discord Alerts Failing (1/2 channels)
**Problem**: Alerts were only going to Console, Discord was failing silently.

**Root Cause**: Category thread environment variables weren't set on Railway.

**Solution**: Set all category thread IDs on Railway:
```bash
DISCORD_THREAD_POLITICS=1461398615242313819
DISCORD_THREAD_CRYPTO=1461399011373092884
DISCORD_THREAD_SPORTS=1461403481255579748
DISCORD_THREAD_FINANCE=1461400496379138271
DISCORD_THREAD_ENTERTAINMENT=1461400992028299447
DISCORD_THREAD_WORLD=1461401409709674618
DISCORD_THREAD_OTHER=1461073799905542420
```

**Result**: Alerts now show "📢 Alert sent to 2/2 channels" with Discord working.

### Duplicate Discord Threads to Delete
Two accidental duplicate threads were created:
- **Politics Alerts duplicate**: `1461398614365569186` (DELETE this)
- **Sports Alerts duplicate**: `1461403481167368244` (DELETE this)

Keep the thread IDs listed in the category routing table above.

### Commits
- `106c3e7` - Add $450 min alert threshold and Sports category routing
- `5fe6d7a` - Improve sports filtering with team names and matchup patterns
- `cb7c948` - Fix sports filtering for Kalshi markets (check ticker too)
