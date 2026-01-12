# 🐋 Prediction Market Whale Tracker

Track large and unusual trades on prediction markets in real-time. Get instant alerts via email, Telegram, Discord, Slack, and push notifications!

## ✨ Features

### Core Tracking
- **Real-time monitoring** of Polymarket trades
- **Whale detection** - Large trades above threshold
- **Unusual activity** - Statistically abnormal trades  
- **New wallet tracking** - First-time traders making big bets
- **Smart money** - Wallets with high win rates

### 🔔 All Notification Channels
- **Console** - Always on for development
- **Email** - Via Resend.com (100 free/day)
- **Telegram** - Instant bot notifications
- **Discord** - Webhook integration
- **Slack** - Workspace notifications
- **Push** - Mobile via Expo (React Native)

### 📊 React Dashboard
- Live alert feed with real-time updates
- Whale leaderboard
- Market overview
- Sound alerts for high-severity trades
- Filter by severity

### 🏦 Multi-Platform (Coming Soon)
- Kalshi client ready (needs API credentials)
- Extensible adapter pattern for more markets

---

## 🚀 Quick Start

### 1. Start the Backend

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python run.py
```

Backend runs at **http://localhost:8000**

### 2. Start the Dashboard

```bash
# In a new terminal
cd dashboard

# Install Node dependencies
npm install

# Run dashboard
npm run dev
```

Dashboard runs at **http://localhost:3000**

### 3. Configure Notifications (Optional)

Copy `.env.example` to `.env` and add your credentials:

```bash
cp .env.example .env
```

---

## 📱 Setting Up Notifications

### Telegram (Recommended - Free & Instant)

1. Message **@BotFather** on Telegram
2. Send `/newbot` and follow prompts
3. Copy the bot token
4. Start a chat with your new bot
5. Get your chat ID: `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdef...
   TELEGRAM_CHAT_ID=123456789
   ```

### Discord

1. Server Settings → Integrations → Webhooks
2. Create New Webhook
3. Copy URL, add to `.env`:
   ```
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   ```

### Email (Resend)

1. Sign up at [resend.com](https://resend.com) (free tier: 100/day)
2. Get API key from dashboard
3. Add to `.env`:
   ```
   RESEND_API_KEY=re_xxxxx
   ALERT_EMAIL=you@example.com
   ```

### Slack

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Create app → Add Incoming Webhooks
3. Activate and add to workspace
4. Copy URL, add to `.env`:
   ```
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
   ```

### Push Notifications (Mobile)

Push notifications require a React Native mobile app. See the `/mobile` folder (coming soon) or use Expo:

1. Build your app with `expo-notifications`
2. Get push tokens from users
3. Store tokens in your database
4. The alerter sends to all registered tokens

---

## 📊 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check & stats |
| `GET /markets` | Active prediction markets |
| `GET /trades` | Recent trades |
| `GET /trades/whales` | Large trades only |
| `GET /trades/wallet/{address}` | Trades by wallet |
| `GET /alerts` | Whale alerts |
| `GET /alerts/stream` | Real-time SSE stream |
| `GET /stats` | Overall statistics |
| `GET /stats/wallets` | Wallet leaderboard |
| `POST /scan` | Manual scan trigger |

Interactive docs: **http://localhost:8000/docs**

---

## 🏗️ Project Structure

```
prediction-market-tracker/
├── src/
│   ├── main.py              # FastAPI app & endpoints
│   ├── config.py            # Settings from .env
│   ├── polymarket_client.py # Polymarket API
│   ├── kalshi_client.py     # Kalshi API (placeholder)
│   ├── whale_detector.py    # Detection logic
│   ├── database.py          # SQLAlchemy models
│   └── alerter.py           # All notification channels
├── dashboard/               # React frontend
│   ├── src/
│   │   ├── app/            # Next.js app
│   │   └── components/     # React components
│   └── package.json
├── requirements.txt
├── .env.example
├── run.py                   # Simple start script
└── README.md
```

---

## 🚢 Deployment

### Backend (Railway)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

### Dashboard (Vercel)

```bash
cd dashboard
npm install -g vercel
vercel
```

Set `NEXT_PUBLIC_API_URL` to your Railway backend URL.

---

## ⚙️ Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `WHALE_THRESHOLD_USDC` | 10000 | USD threshold for whale alerts |
| `WHALE_STD_MULTIPLIER` | 3.0 | Std devs above mean = unusual |
| `POLL_INTERVAL` | 60 | Seconds between API polls |
| `DATABASE_URL` | sqlite:///./trades.db | Database connection |
| `LOG_LEVEL` | INFO | DEBUG, INFO, WARNING, ERROR |

---

## 🔮 Roadmap

- [x] Polymarket integration
- [x] Whale detection algorithms
- [x] Email notifications (Resend)
- [x] Telegram bot
- [x] Discord webhook
- [x] Slack webhook
- [x] React dashboard
- [ ] Kalshi integration (need API key)
- [ ] React Native mobile app
- [ ] User accounts & subscriptions
- [ ] Stripe payment integration
- [ ] Automated copy-trading

---

## 🐛 Troubleshooting

### Backend won't start
```bash
# Make sure venv is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Dashboard can't connect to backend
- Check backend is running on port 8000
- Check CORS settings in `main.py`
- Try `http://127.0.0.1:8000` instead of `localhost`

### No alerts appearing
- Lower threshold: `WHALE_THRESHOLD_USDC=100`
- Check Polymarket API is accessible
- Look at console logs for errors

### Notifications not sending
- Check credentials in `.env`
- Run `python -m src.alerter` to test
- Check logs for error messages

---

## 📜 License

MIT License - do whatever you want!

---

Built with ❤️ for prediction market enthusiasts.
