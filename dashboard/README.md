# 🐋 Whale Tracker Dashboard

A real-time React dashboard for monitoring prediction market whale activity.

## Features

- **Live Alert Feed** - Real-time whale trade alerts via Server-Sent Events
- **Stats Overview** - Track total alerts, trades, and unique wallets
- **Whale Leaderboard** - Top traders by volume
- **Market Overview** - Active markets with prices and volume
- **Sound Alerts** - Audio notification for high-severity alerts
- **Filter Controls** - Filter by severity (HIGH/MEDIUM/LOW)

## Setup

### Prerequisites
- Node.js 18+ 
- The Python backend running on port 8000

### Installation

```bash
# Navigate to dashboard folder
cd dashboard

# Install dependencies
npm install

# Start development server
npm run dev
```

The dashboard will be available at **http://localhost:3000**

### Production Build

```bash
npm run build
npm start
```

## Configuration

The dashboard connects to the backend API at `http://localhost:8000` by default.

To change this, set the environment variable:

```bash
NEXT_PUBLIC_API_URL=http://your-backend-url:8000
```

Or create a `.env.local` file:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Architecture

```
dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx      # Root layout
│   │   ├── page.tsx        # Main dashboard page
│   │   └── globals.css     # Global styles
│   └── components/
│       ├── Header.tsx          # Navigation header
│       ├── StatsCards.tsx      # Statistics overview
│       ├── AlertFeed.tsx       # Real-time alerts
│       ├── WhaleLeaderboard.tsx # Top wallets
│       ├── MarketsList.tsx     # Active markets
│       └── NotificationBanner.tsx
├── tailwind.config.js
├── next.config.js
└── package.json
```

## Real-Time Updates

The dashboard uses two methods for updates:

1. **Server-Sent Events (SSE)** - Connects to `/alerts/stream` for instant alert notifications
2. **Polling** - Refreshes stats every 30 seconds

## Customization

### Colors
Edit `tailwind.config.js` to change the color scheme:

```js
colors: {
  whale: {
    500: '#0ea5e9', // Primary color
    // ...
  }
}
```

### Alert Sounds
The dashboard plays a beep sound for HIGH severity alerts. Modify `playAlertSound()` in `page.tsx` to change or disable this.

## Deploying with Backend

### Option 1: Same Server
Deploy both on the same server, with Next.js proxying to the FastAPI backend.

### Option 2: Separate Servers
Deploy the dashboard to Vercel/Netlify and backend to Railway/Render. Update `NEXT_PUBLIC_API_URL` accordingly.

### Vercel Deployment
```bash
npm install -g vercel
vercel
```

## Screenshots

Coming soon!

---

Part of the [Prediction Market Whale Tracker](../) project.
