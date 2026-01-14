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
- [ ] Kalshi market integration
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
- Kalshi (planned)

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

---

## Discord Forum Channel Configuration

The Discord webhook points to a **forum channel**, which requires special handling.

### Key Details
- **Webhook URL**: Stored in Railway as `DISCORD_WEBHOOK_URL`
- **Thread ID**: `1461073799905542420` (the "Whale Alerts" thread)
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

**New Alert Format:**
```
📊 Market: Will Elon Musk post 440-459 tweets...?
🏦 Platform: Polymarket
💰 Amount: $1,150.66
🎯 Position: Buy No
⚡ Severity: HIGH (Large trade size, unusual pattern, or high-confidence signal)
👤 Trader: 0x1234...
```

**Severity Meanings:**
- **HIGH** - Large trade size, unusual pattern, or high-confidence signal
- **MEDIUM** - Notable activity worth monitoring
- **LOW** - Minor signal, may be noise
