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

### Filtered High-Frequency Markets (added 2026-01-16)
The following market types are also filtered out to reduce noise:
- **15-minute Bitcoin up/down markets** - These generate massive trade volume but are mostly noise
- **5-minute markets** - Similar high-frequency noise
- **Hourly BTC markets** - Also filtered

### Trade Fetching Improvements (2026-01-16)
To prevent missing large trades during high-volume periods:
1. **Increased fetch limit**: 500 trades per poll (up from 100)
2. **Time-based queries**: Uses `after_timestamp` to prevent gaps between polls
3. **Secondary whale check**: Additional query specifically for trades >= whale threshold
4. **Kalshi pagination**: Now fetches up to 500 trades by paginating through API

### Hybrid WebSocket + Polling Monitor (2026-01-16)
Real-time trade detection using WebSocket with polling as backup:

**Architecture:**
- **WebSocket (primary)**: Connects to `wss://ws-live-data.polymarket.com` for real-time Polymarket trades (~100ms latency)
- **Polling (backup)**: Runs every 30 seconds to catch any missed trades and handle Kalshi

**Files:**
- `src/polymarket_websocket.py` - WebSocket client and HybridTradeMonitor class
- `src/config.py` - `USE_HYBRID_MONITOR=True` enables hybrid mode

**Configuration:**
| Variable | Default | Description |
|----------|---------|-------------|
| `USE_HYBRID_MONITOR` | `True` | Enable WebSocket + polling hybrid |
| `POLL_INTERVAL` | `30` | Backup polling interval (seconds) |
| `POLYMARKET_WS_URL` | `wss://ws-live-data.polymarket.com` | WebSocket endpoint |

**Health endpoint** now shows WebSocket stats:
```json
{
  "monitor": "hybrid",
  "websocket": {"connected": true, "trades_received": 1234},
  "polling": {"trades_received": 56}
}
```

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
- **Plan**: Hobby ($5/month) - upgraded 2026-01-16 (up to 8 GB RAM / 8 vCPU per service)
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
| `POLL_INTERVAL` | Trade polling interval in seconds (default: 15, reduced from 60 on 2026-01-16) |
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

## Daily Email Digest (Added 2026-01-15)

Automated daily summary email sent at **5 AM Eastern Time** with a modern Robinhood/Coinbase style design.

### Features
- **Database-backed compilation** - Survives service restarts
- **Modern HTML template** - Dark header, card-based trades, pill badges
- **APScheduler** - Runs daily at 5 AM ET, weekly on Monday 9 AM ET

### Environment Variables
```bash
DAILY_DIGEST_HOUR=5          # Hour to send (24h format)
DIGEST_TIMEZONE=America/New_York
RESEND_API_KEY=re_xxxxx      # Required for email sending
ALERT_EMAIL=you@example.com  # Recipient email
```

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/digest/preview` | GET | Preview digest data (JSON) |
| `/digest/preview/html` | GET | Preview HTML email template |
| `/digest/daily` | POST | Manually trigger daily digest |
| `/digest/weekly` | POST | Manually trigger weekly digest |

### Testing
```bash
# Preview digest data
curl https://web-production-9d2d3.up.railway.app/digest/preview

# Preview HTML template in browser
open https://web-production-9d2d3.up.railway.app/digest/preview/html

# Trigger manual daily digest
curl -X POST https://web-production-9d2d3.up.railway.app/digest/daily
```

### Email Design
- **Header**: Dark (#1a1a1a) with whale emoji
- **Stats Bar**: Alerts count, Volume ($), Smart Money count
- **Alert Breakdown**: Pill badges by type
- **Top Trades**: Card-based with green accent ($00d395)
- **Footer**: Dark with unsubscribe links

---

## Twitter Queue (Added 2026-01-15)

Semi-automated Twitter/X posting via a private Discord channel. High-value alerts are posted in the **same full format** as the main Discord channels so potential X followers see exactly what subscribers receive.

### Why Semi-Automated?
- X API costs $200/month for write access
- This approach is free and gives you control over what gets posted
- Rate-limited to ~4 posts/hour to avoid spam
- Shows real product to potential customers

### Features
- **Full alert format** - Same rich embeds as main Discord channels
- **Hashtags in footer** - Copy entire alert and hashtags come with it
- **High-value filtering** - Only best alerts are queued
- **Rate limiting** - Max 4 posts per hour (configurable)

### Filtering Criteria (must meet at least one)
- Trade amount >= $1,000
- HIGH severity
- 3+ trigger signals (multi-signal alert)
- Contains HIGH_IMPACT, SMART_MONEY, WHALE_TRADE, or CLUSTER_ACTIVITY

### Environment Variables
```bash
DISCORD_TWITTER_WEBHOOK_URL=https://discord.com/api/webhooks/...  # Webhook for #for-twitter
TWITTER_MIN_AMOUNT=1000        # Minimum USD for Twitter-worthy alerts
TWITTER_MAX_PER_HOUR=4         # Rate limit
```

### Hashtag Strategy (in footer)
**Evergreen tags** (always included):
- `#PredictionMarkets` `#WhaleAlert`

**Category tags** (up to 2):
- Politics: `#Politics` `#Election`
- Crypto: `#Crypto` `#Bitcoin` `#Ethereum`
- Finance: `#Stocks` `#Finance` `#Markets`
- Entertainment: `#Entertainment` `#Showbiz`
- World: `#WorldNews` `#Geopolitics`

**Topic tags** (up to 3, based on market question):
- `#Trump` `#Biden` `#Elon` `#Tesla` `#SpaceX` `#BTC` `#ETH` `#AI` `#OpenAI` etc.

### Alert Format in #for-twitter
```
🐋 High Impact

💥 HIGH IMPACT: $4,184 is 100% of market's hourly volume

📊 Market: Will Trump win the 2028 election?
🏛️ Category: Politics | 🏦 Platform: Polymarket | 💰 Amount: $4,184.00
🎯 Position: Buy Yes ➕ ADDING
⚡ Severity: 🔴 HIGH - Large trade size, unusual pattern, or high-confidence signal
👤 Trader: 0x1234abcd...

#PredictionMarkets #WhaleAlert #Politics #Election #Trump
```

### Workflow
1. Check #for-twitter channel for high-value alerts
2. Highlight entire alert → Copy
3. Paste to X (hashtags included in footer)
4. Post with optional commentary

### Discord Channel
- **Channel**: #for-twitter (private)
- **Channel ID**: 1461428003056652339
- **Webhook ID**: 1461428485083107550
- Only visible to server owner

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

---

## Session Log (2026-01-15) - Daily Email Digest

### Task: Daily Summary Email at 5 AM ET

**Request**: Create daily summary email with modern design (Robinhood/Coinbase style) using Resend, sent at 5 AM ET.

### Implementation

#### Files Changed
- `src/database.py` - Added `get_alerts_by_date_range()`, `get_digest_summary()`
- `src/alerter.py` - Added `send_digest()` method to Alerter class
- `src/scheduler.py` - Modern HTML template, `_compile_digest_from_db()` method
- `src/config.py` - `DAILY_DIGEST_HOUR=5`, `DIGEST_TIMEZONE=America/New_York`
- `src/main.py` - Initialize scheduler, add `/digest/*` endpoints

#### Key Features
1. **Database-backed compilation** - Alerts queried from PostgreSQL, survives restarts
2. **Modern HTML design** - Dark header, green accents (#00d395), card-based trades
3. **APScheduler integration** - CronTrigger at 5 AM ET daily
4. **Test endpoints** - `/digest/preview`, `/digest/preview/html`, `/digest/daily`

#### API Endpoints Added
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/digest/preview` | GET | JSON preview of digest data |
| `/digest/preview/html` | GET | HTML email preview (renders in browser) |
| `/digest/daily` | POST | Manually trigger daily digest |
| `/digest/weekly` | POST | Manually trigger weekly digest |

#### Environment Variables Required
```bash
RESEND_API_KEY=re_xxxxx
ALERT_EMAIL=you@example.com
DAILY_DIGEST_HOUR=5
DIGEST_TIMEZONE=America/New_York
```

### Commits
- `36559c6` - Add daily email digest with modern design (5 AM ET)

---

## Session Log (2026-01-15) - Consolidated Alert Notifications

### Task: Combine Multiple Alerts Per Trade into Single Message

**Problem**: A single trade could trigger 3+ separate Discord messages (e.g., HIGH_IMPACT, NEW_WALLET, UNUSUAL_SIZE), cluttering the feed.

**Solution**: Consolidated all triggered conditions into ONE alert showing all reasons.

### Implementation

#### Files Changed
- `src/whale_detector.py` - `WhaleAlert` dataclass updated:
  - `alert_type` → `alert_types: List[str]`
  - `message` → `messages: List[str]`
  - `analyze_trade()` now returns single consolidated alert
- `src/alerter.py` - `AlertMessage` and Discord formatting updated:
  - Shows trigger badges and bullet-pointed reasons
  - Title: "Multi-Signal Alert (3 triggers)" for multiple triggers

#### New Alert Format (Discord)
```
🐋 Multi-Signal Alert (3 triggers)

🔔 Triggered: `HIGH IMPACT` `NEW WALLET` `UNUSUAL SIZE`

• 💥 HIGH IMPACT: $1,060 is 100% of market's hourly volume
• 🆕 NEW WALLET: First-time trader placed $1,060 bet
• 📊 UNUSUAL TRADE: $1,060 is 13.0 std devs above average

📊 Market: Will Trump nominate...
🏛️ Category: Politics
...
```

#### Backwards Compatibility
- `alert_type` and `message` properties return first item for DB storage
- Alert ID prefix changed to `consolidated_{trade_id}`

### Commits
- `74497f3` - Consolidate multiple alerts per trade into single notification

---

## Session Log (2026-01-15) - Twitter Queue for X Posting

### Task: Semi-Automated Twitter/X Posting

**Request**: Post high-value alerts to X/Twitter without paying $200/month for API access. User wants to grow a following by showcasing whale alerts.

### Implementation

#### 1. Created Private Discord Channel
- **Channel**: #for-twitter (private, only owner can see)
- **Channel ID**: `1461428003056652339`
- **Webhook ID**: `1461428485083107550`
- Created via browser automation in Chrome

#### 2. Added TwitterFormatter Class
**File**: `src/alerter.py`

```python
class TwitterFormatter:
    EVERGREEN_TAGS = ["#PredictionMarkets", "#WhaleAlert"]
    CATEGORY_TAGS = {
        "Politics": ["#Politics", "#Election"],
        "Crypto": ["#Crypto", "#Bitcoin", "#Ethereum"],
        ...
    }
    TOPIC_TAGS = {
        "trump": "#Trump", "bitcoin": "#BTC", "elon": "#Elon", ...
    }

    @classmethod
    def get_hashtags(cls, alert) -> str:
        # Returns: "#PredictionMarkets #WhaleAlert #Politics #Trump"

    @classmethod
    def is_twitter_worthy(cls, alert, min_amount=1000.0) -> bool:
        # Returns True if: $1000+ OR HIGH severity OR 3+ triggers
        # OR contains HIGH_IMPACT, SMART_MONEY, WHALE_TRADE, CLUSTER_ACTIVITY
```

#### 3. Added TwitterQueueAlert Channel
**File**: `src/alerter.py`

- Posts to private #for-twitter channel
- Uses **same full format** as main Discord alerts (not simplified tweets)
- Hashtags in footer for easy copy/paste
- Rate limited to 4 posts/hour
- High-value filtering (only best alerts)

#### 4. Configuration Added
**File**: `src/config.py`

```python
DISCORD_TWITTER_WEBHOOK_URL: Optional[str] = None
TWITTER_MIN_AMOUNT: float = 1000.0
TWITTER_MAX_PER_HOUR: int = 4
```

### Workflow for User
1. Check #for-twitter channel for high-value alerts
2. Highlight entire alert → Copy (hashtags in footer come with it)
3. Paste to X with optional commentary
4. Post

### Key Design Decisions
- **Full alert format** (not simplified tweets) - Shows potential customers exactly what subscribers receive
- **Hashtags in footer** - User can copy entire alert naturally, hashtags included
- **Rate limiting** - Max ~4/hour prevents spam, ensures quality selection
- **High-value filtering** - Only alerts worth posting get queued

### Files Changed
- `src/config.py` - Added Twitter queue settings
- `src/alerter.py` - Added `TwitterFormatter`, `TwitterQueueAlert` classes
- `CLAUDE.md` - Documentation

### Environment Variables Set on Railway
```bash
DISCORD_TWITTER_WEBHOOK_URL=<set in Railway, do not commit>
```

### Commits
- `5998888` - Add Twitter Queue for semi-automated X posting
- `ff5264a` - Twitter Queue: Use same rich format as main Discord alerts
- `a1ee71a` - Add copy-friendly hashtags field to Twitter Queue alerts
- `a687bbc` - Move hashtags to footer for easy full-copy to X

---

## Session Log (2026-01-15) - LaunchPass Monetization & Security Fix

### Task: Set Up Payment Collection with LaunchPass

**Request**: Monetize the whale tracker service with subscription tiers using LaunchPass.

### LaunchPass Configuration

Created two subscription products:

| Plan | Price | Discord Role | Access |
|------|-------|--------------|--------|
| **WhaleWatch** | $29/month | `premium` | Main prediction-whale-alerts forum |
| **Sports Add-On** | $4.99/month | `sports` | Sports-alerts channel |

**LaunchPass URLs:**
- Main: `https://launchpass.com/predictionwhales/whalewatch`
- Sports: `https://launchpass.com/predictionwhales/sports`

### Discord Channel Permissions

Configured role-based access control:

| Channel | Type | Visibility | Required Role |
|---------|------|------------|---------------|
| `#prediction-whale-alerts` | Forum | Private | `premium` |
| `#sports-alerts` | Text | Private | `sports` |
| `#welcome`, `#general`, etc. | Text | Public | None |

**How it works:**
1. User subscribes via LaunchPass payment link
2. LaunchPass assigns Discord role automatically
3. User gains access to private channels based on role

### Security Fix: GitGuardian Alert

**Problem**: Discord webhook URL was exposed in CLAUDE.md and committed to public GitHub repo.

**Resolution:**
1. Removed webhook URL from CLAUDE.md (replaced with placeholder)
2. Installed `git-filter-repo` tool
3. Scrubbed webhook URL from entire git history (58 commits)
4. Force pushed cleaned history to GitHub

**Command used:**
```bash
git filter-repo --replace-text replacements.txt --force
git remote add origin https://github.com/spenchey/Prediction-Markets.git
git push --force origin master
```

**Important reminder:** Never commit secrets to git. Always use environment variables (Railway) for sensitive values like webhook URLs, API keys, etc.

### New Discord Channel

Created `#sports-alerts` text channel:
- **Channel ID**: `1461465320140312819`
- **Access**: Private, requires `sports` role
- **Purpose**: Dedicated channel for sports add-on subscribers ($4.99/mo)

---

## Session Log (2026-01-16) - Railway OOM & Hybrid WebSocket Monitor

### Issue 1: Railway Out-of-Memory Email

**Problem**: Received OOM email from Railway, but app continued running (auto-restart).

**Root Cause**: Trial plan limited to 512MB RAM. In-memory caches (`wallet_profiles`, `market_stats`, `wallet_clusters`) can grow unbounded.

**Solution**: Upgraded Railway plan from Trial to Hobby ($5/month, up to 8GB RAM).

### Issue 2: Missed $66k Greenland Trade

**Problem**: A $66,000 bet on Trump acquiring Greenland wasn't caught by alerts.

**Root Causes Identified**:
1. Trade fetch limit was only 100 per poll
2. Poll interval was 60 seconds (too slow)
3. High-frequency 15-minute Bitcoin markets creating noise

**Solution**: Implemented multiple improvements:
1. Increased fetch limit from 100 → 500 trades per poll
2. Added `after_timestamp` parameter for time-based queries (prevents gaps)
3. Added secondary whale check specifically for trades >= threshold
4. Reduced poll interval from 60s → 15s (when using polling only)
5. Added filtering for 15-minute Bitcoin markets

### Issue 3: Competition Analysis

**Research**: Investigated how competitors handle real-time trades:
- **Polywhaler**: Private tracker, unclear implementation
- **PolyTrack**: Uses WebSocket for real-time data
- **Oddpool**: Also uses WebSocket

**Finding**: WebSocket provides ~100ms latency vs 15-60s polling.

### Solution: Hybrid WebSocket + Polling Monitor

**Implementation**: Created `src/polymarket_websocket.py` with:

```python
class PolymarketWebSocket:
    """WebSocket client for real-time Polymarket trade data."""
    # Connects to wss://ws-live-data.polymarket.com
    # Subscribes to activity/trades topic
    # Parses trade messages and calls on_trade callback

class HybridTradeMonitor:
    """Combines WebSocket (primary) and polling (backup)."""
    # WebSocket for real-time Polymarket trades
    # Polling every 30s as backup for all platforms including Kalshi
```

**Configuration** (added to `src/config.py`):
```python
POLYMARKET_WS_URL: str = "wss://ws-live-data.polymarket.com"
USE_HYBRID_MONITOR: bool = True
POLL_INTERVAL: int = 30  # Backup polling (30s with hybrid, 15s otherwise)
WS_RECONNECT_DELAY: float = 5.0
```

### Deployment Issues & Fixes

1. **Wrong branch**: Pushed to `master` but Railway deploys from `main`
   - Fix: `git push origin master:main`

2. **Timestamp parsing error** ("year 58014 is out of range"):
   - Root cause: WebSocket timestamps in milliseconds, not seconds
   - Fix: Check if timestamp > 32503680000, divide by 1000

3. **Health endpoint error** ("'ClientConnection' object has no attribute 'open'"):
   - Root cause: websockets library uses `.closed`, not `.open`
   - Fix: Changed `self._ws.open` to `not self._ws.closed`

### Final Health Check Result
```json
{
  "status": "ok",
  "monitor": "hybrid",
  "websocket": {"connected": true, "trades_received": 6961},
  "polling": {"trades_received": 2505, "alerts_generated": 22}
}
```

### Files Changed
- `src/config.py` - Added WebSocket and hybrid monitor settings
- `src/polymarket_client.py` - Increased limit to 500, added `after_timestamp`
- `src/kalshi_client.py` - Added pagination for 500 trades, `after_timestamp`
- `src/whale_detector.py` - Added 15-min BTC filtering, secondary whale check
- `src/polymarket_websocket.py` - **NEW** - WebSocket client and HybridTradeMonitor
- `src/main.py` - Integrated hybrid monitor, updated health endpoint

### Commits
- `9b18bb7` - Improve trade fetching to prevent missing large trades
- `62a54fe` - Implement hybrid WebSocket + polling monitor for real-time trades
- `2561ae3` - Fix WebSocket timestamp parsing (milliseconds to seconds)
- `4084c0b` - Fix WebSocket is_connected to use .closed instead of .open

### Key Learnings
- WebSocket provides much faster trade detection (~100ms vs 15-60s)
- Hybrid approach gives best of both worlds (speed + reliability)
- Always check library documentation for attribute names (`.closed` vs `.open`)
- Railway deploys from `main` branch, not `master`

---

## Session Log (2026-01-16) - Category Detection Fix

### Issue: Alerts Going to Wrong Discord Threads

**Problem**: All alerts were showing "Category: Other" and going to the "Whale Alerts" thread instead of category-specific threads (Politics, Crypto, Finance, etc.).

**Root Causes**:
1. WebSocket trades include `_ws_title` but category wasn't being detected from it
2. Kalshi trades don't include market questions at all - only ticker IDs
3. The `market_categories` dict was only populated during market fetch, not during trade analysis

### Solution: Two-Part Fix

#### Part 1: Auto-detect category from question text (commit 7028d4b)
Added `_detect_category_from_text()` method to WhaleDetector that detects category using keyword matching when market_question is provided.

#### Part 2: Kalshi ticker pattern detection (commit ad1ea13)
Extended category detection to also work with Kalshi market tickers:

| Ticker Pattern | Category |
|---------------|----------|
| KXNBA, KXNFL, KXMLB, KXMVE, KXATP, KXLIGUE | Sports |
| KXBTC, KXETH, KXSOL | Crypto |
| KXEO, KXCPI, KXGDP, KXFED | Finance |
| KXTRUMP, KXDJTVO, KXPRES | Politics |

### Code Changes
**File**: `src/whale_detector.py`

```python
def _detect_category_from_text(self, text: str, market_id: str = None) -> str:
    """Detect category from question text OR Kalshi ticker patterns."""
    # First try keyword matching on text
    if text:
        # ... keyword matching ...

    # Then try Kalshi ticker patterns
    if market_id:
        if "KXNBA" in market_id or "KXNFL" in market_id:
            return "Sports"
        if "KXBTC" in market_id or "KXETH" in market_id:
            return "Crypto"
        # etc.
```

### Result
- Polymarket WebSocket alerts now route to correct category threads
- Kalshi alerts route based on ticker pattern
- Alerts should appear in Politics, Crypto, Finance, Sports threads instead of all going to "Other"

### Verification (2026-01-16)

Verified category routing is working correctly:

1. **Test alerts sent** to each category thread (Politics, Crypto, Finance, Other) - all returned HTTP 204 success
2. **User confirmed** test messages appeared in correct Discord threads
3. **Health endpoint** showed 25+ alerts generated since deployment

**Category Detection Flow:**
1. WebSocket trade arrives with `_ws_title` (market question)
2. `_detect_category_from_text()` checks keywords in question text
3. If no match, checks Kalshi ticker patterns (KXNBA, KXBTC, etc.)
4. Category cached in `market_categories` dict for future trades
5. Alert sent to category-specific Discord thread via `_get_thread_id_for_category()`

**Thread Routing Confirmed Working:**
| Category | Thread | Status |
|----------|--------|--------|
| Politics | 🏛️ Politics Alerts | ✅ Verified |
| Crypto | ₿ Crypto Alerts | ✅ Verified |
| Finance | 📈 Finance Alerts | ✅ Verified |
| Other | Whale Alerts | ✅ Verified |

---

## Session Log (2026-01-16) - VIP Wallet Alert System

### Feature: VIP Wallet Alerts

**Request**: Alert whenever VIP wallets make ANY trade, with dedicated Discord thread.

### VIP Wallet Criteria

A wallet qualifies as VIP if it meets ANY of these criteria:

| Criteria | Default Threshold | Config Variable |
|----------|-------------------|-----------------|
| High lifetime volume | $100,000+ | `VIP_MIN_TOTAL_VOLUME` |
| Good win rate | 55%+ (with 10+ resolved) | `VIP_MIN_WIN_RATE` |
| Large trade history | 5+ trades over $5k | `VIP_MIN_LARGE_TRADES` |

### Implementation

**Files Changed:**
- `src/config.py` - Added VIP settings and `DISCORD_THREAD_VIP`
- `src/whale_detector.py` - Added `VIP_WALLET` alert type, `is_vip()` method to WalletProfile
- `src/alerter.py` - Added VIP thread routing (overrides category routing)

**New Alert Type:**
```
⭐ VIP WALLET: $150,000 lifetime volume | 62% win rate - placed $2,500 bet
```

**Key Features:**
- VIP_WALLET alerts trigger for ANY trade from VIP wallets (no minimum amount)
- Bypasses both minimum threshold ($450) and crypto threshold ($974)
- Routes to dedicated VIP thread (overrides category-based routing)
- Shows VIP reason: volume, win rate, or large trade count

### Discord Thread

| Thread | ID | Description |
|--------|----|-----------  |
| ⭐ VIP Wallet Alerts | `1461798236506554551` | Trades from VIP wallets |

### Environment Variable
```bash
DISCORD_THREAD_VIP=1461798236506554551
```

### Commits
- `096f1c4` - Add VIP wallet alert system
