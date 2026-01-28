# 🐋 Prediction Whale - Improvement Plan

**Date:** 2026-01-28  
**Goal:** Reduce noise, increase signal quality for @predictionwhales Twitter

---

## Current State Analysis

### What's Posting to Twitter (is_twitter_worthy criteria):
1. **$10k+** trades — always post ❌ **PROBLEM: Size alone ≠ unusual**
2. **$1k+ with multi-trade patterns** (REPEAT_ACTOR, HEAVY_ACTOR, CLUSTER_ACTIVITY)
3. **$5k+ with SMART_MONEY or NEW_WALLET**
4. **4+ simultaneous triggers**

### Recent Tweets (Examples of Noise):
| Bet | Amount | Issue |
|-----|--------|-------|
| Sinner at 90¢ | $30k | Normal bet on heavy favorite |
| Suns -8.5 spread | $30k | Sports bet (should be filtered) |
| Arkansas to beat Oklahoma | $31k | Sports bet |
| S&P range bet | $37k | Normal hedging/arb |

### The Core Problem:
**Large dollar amount alone does NOT equal "whale" or "unusual"**

A $30k bet at 90¢ odds on a heavy favorite is:
- Expected behavior from any well-capitalized trader
- Low risk/reward ratio (betting $30k to win $3.3k)
- NOT indicative of "smart money" or special knowledge

---

## What ACTUALLY Makes a Bet Noteworthy

### Tier 1: Truly Unusual (Always Tweet-Worthy)
| Signal | Why It Matters |
|--------|----------------|
| **New wallet + large first bet** | Someone deploying fresh capital with conviction |
| **Contrarian** (betting longshots >3:1 underdog) | Information asymmetry signal |
| **Cluster activity** | Coordinated wallets = institutional or insider |
| **Smart money** (proven winners) making moves | Track record validates conviction |
| **High impact ratio** (>10% of market volume) | Moving the market |

### Tier 2: Context-Dependent
| Signal | Needs Context |
|--------|---------------|
| Large bet on favorite | Only if odds shift OR new wallet |
| Sports bets | Generally noise, but could track sharp bettors |
| Short-term markets (15-min BTC) | High volume but low information value |

### Tier 3: Noise (Filter Out)
| Signal | Why Filter |
|--------|------------|
| Large bet at fair odds on liquid market | Normal trading |
| Any sports spread/total bet | High volume, algorithmic |
| Arbitrage patterns | Not predictive |

---

## Proposed Changes

### 1. Fix Sports Filtering
**Issue:** Sports markets still posting despite `EXCLUDE_SPORTS_MARKETS: True`

**Check:** The Kalshi trades are coming through with sports tickers (KXNBATOTAL, etc.)

```python
# Current: is_sports_market() checks keywords
# Problem: Not catching all Kalshi sports tickers

# Fix: Add Kalshi sports ticker patterns
KALSHI_SPORTS_PATTERNS = [
    'KXNBA', 'KXNFL', 'KXMLB', 'KXNHL', 'KXMLS',  # Major leagues
    'KXNCAA', 'KXCFB',  # College
    'KXUFC', 'KXPGA', 'KXATP', 'KXWTA',  # Individual sports
]
```

### 2. Add "Odds Context" to Whale Detection

Current logic only looks at bet SIZE. Need to add:

```python
def is_significant_bet(self, trade: Trade, market_info: dict) -> bool:
    """
    A bet is significant when it shows conviction, not just size.
    """
    price = trade.price  # 0.0 to 1.0
    amount = trade.amount_usd
    
    # Betting on heavy favorite (>85% odds) = low signal
    if trade.side == "BUY" and price >= 0.85:
        # Only significant if VERY large or new wallet
        return amount >= 50_000 or self.is_new_wallet(trade.trader_address)
    
    # Betting on underdog (<30% odds) = high signal
    if trade.side == "BUY" and price <= 0.30:
        return amount >= 10_000  # Lower threshold for contrarian
    
    # Middle odds = standard threshold
    return amount >= 25_000
```

### 3. Revise Twitter Criteria

**Current `is_twitter_worthy()`:**
```python
if amount >= 10_000:
    return True  # ← Too permissive
```

**Proposed:**
```python
def is_twitter_worthy(cls, alert: AlertMessage) -> bool:
    amount = alert.trade_amount
    types = set(alert.alert_types)
    price = alert.trade_price  # Need to add this field
    
    # Tier 1: Always tweet (truly unusual)
    unusual_types = {"NEW_WALLET", "CLUSTER_ACTIVITY", "SMART_MONEY", "CONTRARIAN"}
    if amount >= 10_000 and types & unusual_types:
        return True
    
    # Tier 2: Large + longshot (betting against consensus)
    if amount >= 25_000 and price and price <= 0.30:
        return True
    
    # Tier 3: Massive bets (market-moving)
    if amount >= 100_000:
        return True
    
    # Tier 4: Multi-signal (coordinated/repeated)
    if amount >= 5_000 and len(types) >= 3:
        return True
    
    return False
```

### 4. Add "Risk-Adjusted Size" Metric

```python
def risk_adjusted_size(amount_usd: float, price: float) -> float:
    """
    Normalize bet size by risk taken.
    
    $30k at 90¢ = risking $30k to win $3.3k = risk_adjusted = $3,300
    $10k at 10¢ = risking $10k to win $90k = risk_adjusted = $90,000
    
    Use potential_payout as the signal, not amount risked.
    """
    if price >= 0.99 or price <= 0.01:
        return amount_usd  # Avoid division issues
    
    # Potential payout = shares * (1 - price) for buys
    shares = amount_usd / price
    potential_payout = shares * (1 - price)
    
    return potential_payout
```

### 5. Track & Display Wallet "Freshness"

For NEW_WALLET alerts, add context:
- **First bet ever** vs **First bet in 30 days**
- **Wallet age** (on-chain data)
- **Funding source** (if traceable)

---

## Implementation Priority

### Phase 1: Quick Wins (This Week)
1. [x] Fix Kalshi sports filtering (add ticker patterns) - DONE previously
2. [x] Raise Twitter threshold for "favorite" bets (price > 80%) - DONE 2026-01-28
3. [x] Add price/odds to alert format for context - DONE 2026-01-28

### Phase 2: Signal Improvement (COMPLETED 2026-01-28)
4. [x] Implement odds-aware filtering in whale_detector.py
5. [x] Revise `is_twitter_worthy()` with full odds context
6. [x] Add `trade_price` field to AlertMessage for direct access
7. [x] Discord embeds now show odds context

### Phase 3: Content Strategy
7. [ ] Add "why this matters" to tweets
8. [ ] Track whale accuracy (build credibility)
9. [ ] Weekly "Whale of the Week" recap

---

## Questions to Resolve

1. **What's the actual sports filter status?** Need to check if `EXCLUDE_SPORTS_MARKETS` is True in production .env

2. **Do we have price data in alerts?** Need to pass trade.price through to TwitterFormatter

3. **Kalshi API:** Does it expose odds/price at trade time?

4. **Wallet data:** For Polymarket, can we pull on-chain nonce/age?

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Tweets/day | ~20-50 | 5-15 |
| Sports tweets | Yes | 0 |
| Avg bet in tweets | ~$25k | ~$40k+ OR unusual signal |
| Engagement (likes/RTs) | ? | 2x baseline |

---

*Next step: Review with Spencer, then implement Phase 1.*
