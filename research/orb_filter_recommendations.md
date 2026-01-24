# ORB FILTER ANALYSIS - IMPROVING WIN RATES

**Date**: 2026-01-22
**Analysis**: Comparing winners vs losers to find high-probability conditions

---

## 🎯 KEY FINDING: FILTERS CAN DOUBLE YOUR WIN RATE

Using the right filters, we can increase win rates from:
- **9AM**: 11.7% → **19.1%** (63% improvement)
- **10AM**: 16.4% → **24.7%** (50% improvement)

**This means you take FEWER trades but with MUCH HIGHER success rates.**

---

## 🔥 BEST FILTERS (BY SETUP)

### 9AM 8R HALF Extended

**Baseline**: 523 trades, 11.7% WR, +0.058R avg, +30.3R total

| Filter | Trades | WR% | Avg R | Total R | Improvement |
|--------|--------|-----|-------|---------|-------------|
| **ORB size 0.15-0.35%** | **68** | **19.1%** | **+0.72R** | **+49R** | **+63% WR, +12x avg R** |
| Large ORB (>0.20%) | 51 | 15.7% | +0.50R | +25R | +34% WR, +8.6x avg R |
| Friday only | 104 | 15.4% | +0.38R | +40R | +32% WR, +6.6x avg R |
| Tuesday only | 106 | 14.2% | +0.27R | +29R | +21% WR |
| With pre-ORB trend | 228 | 13.2% | +0.20R | +46R | +13% WR |

**RECOMMENDED FILTER FOR 9AM:**
- **ORB size between 0.15% and 0.35% of price**
- This gives you 19.1% WR (vs 11.7% baseline)
- +0.72R per trade (vs +0.058R baseline)
- 68 trades over 5 years = 13 per year
- **49R total (vs 30R baseline) = 62% more profit with 87% fewer trades**

---

### 10AM 6R FULL Extended

**Baseline**: 523 trades, 16.4% WR, +0.194R avg, +101.5R total

| Filter | Trades | WR% | Avg R | Total R | Improvement |
|--------|--------|-----|-------|---------|-------------|
| **With pre-ORB trend** | **235** | **24.7%** | **+0.81R** | **+190R** | **+50% WR, +4.2x avg R** |
| ORB size 0.12-0.25% | 89 | 19.1% | +0.51R | +46R | +16% WR, +2.6x avg R |
| Monday only | 105 | 21.0% | +0.50R | +53R | +27% WR, +2.6x avg R |
| Wednesday only | 104 | 19.2% | +0.39R | +40R | +17% WR |

**RECOMMENDED FILTER FOR 10AM:**
- **Trade WITH pre-ORB trend** (if 9am-10am moved up, trade long breakouts; if down, trade short)
- This gives you 24.7% WR (vs 16.4% baseline)
- +0.81R per trade (vs +0.194R baseline)
- 235 trades over 5 years = 47 per year
- **190R total (vs 101R baseline) = 87% more profit with 55% fewer trades**

---

### 10AM 4R FULL Standard

**Baseline**: 523 trades, 20.8% WR, +0.143R avg, +74.6R total

| Filter | Trades | WR% | Avg R | Total R | Improvement |
|--------|--------|-----|-------|---------|-------------|
| ORB size 0.12-0.25% | 89 | 24.7% | +0.58R | +52R | +19% WR, +4.1x avg R |
| ORB size 0.10-0.30% | 139 | 21.6% | +0.35R | +48R | +4% WR, +2.4x avg R |
| Monday only | 105 | 21.9% | +0.27R | +28R | +5% WR |
| With pre-ORB trend | 199 | 22.1% | +0.23R | +46R | +6% WR |

**RECOMMENDED FILTER FOR 10AM 4R:**
- **ORB size between 0.12% and 0.25%**
- This gives you 24.7% WR (vs 20.8% baseline)
- +0.58R per trade (vs +0.143R baseline)
- 89 trades over 5 years = 18 per year

---

## 📊 WHAT THESE FILTERS MEAN

### 1. ORB Size Filter (% of Price)

**Best range: 0.12% - 0.35% of price**

**Why it works:**
- **Too small (<0.12%)**: Choppy, no real move, whipsaws
- **Sweet spot (0.12-0.35%)**: Enough movement to show intent, not exhausted
- **Too large (>0.35%)**: Already moved too much, likely to reverse

**How to calculate:**
```
ORB size % = (ORB high - ORB low) / ORB midpoint × 100

Example:
ORB high: 2530.5
ORB low: 2529.0
ORB mid: 2529.75
ORB size: 1.5 pts
ORB size %: 1.5 / 2529.75 × 100 = 0.059% (TOO SMALL - skip)

Example 2:
ORB high: 2534.0
ORB low: 2529.0
ORB size: 5.0 pts
ORB size %: 5.0 / 2531.5 × 100 = 0.198% (GOOD - take trade)
```

### 2. Pre-ORB Trend Filter (CRITICAL FOR 10AM)

**Definition**: Did price move in a direction BEFORE the ORB?

**How to identify:**
- Look at 9:00-10:00 price action (the hour before 10am ORB)
- If close is in **upper 40%** of that range → **upward bias** → trade LONG breakouts
- If close is in **lower 40%** of that range → **downward bias** → trade SHORT breakouts
- If close is **middle 20%** → **no bias** → skip or take both sides

**Example:**
```
9:00-10:00 range:
High: 2535.0
Low: 2528.0
Range: 7.0 pts
Close at 9:59: 2533.5

Position in range: (2533.5 - 2528.0) / 7.0 = 78.6% (upper end)

ACTION: Trade LONG breakouts only (skip short breakouts)
```

**This filter alone improves 10am from 16.4% to 24.7% WR!**

### 3. Day of Week Patterns

**Best days:**
- **Monday**: Fresh week, clean moves (good for 10am)
- **Friday**: Week-end positioning (good for 9am)

**Weaker days:**
- Thursday tends to be choppier
- Wednesday is mixed

---

## 💰 PROFIT COMPARISON: BASELINE VS FILTERED

### 9AM 8R HALF Extended

| Strategy | Trades/Year | WR% | Avg R | Annual R | 5-Year R |
|----------|-------------|-----|-------|----------|----------|
| **Baseline (all trades)** | 103 | 11.7% | +0.058R | +6.0R | +30.3R |
| **Filtered (0.15-0.35% ORB)** | 13 | 19.1% | +0.72R | +9.8R | **+49R** |

**Result**: Make 62% MORE profit by taking 87% FEWER trades

---

### 10AM 6R FULL Extended

| Strategy | Trades/Year | WR% | Avg R | Annual R | 5-Year R |
|----------|-------------|-----|-------|----------|----------|
| **Baseline (all trades)** | 103 | 16.4% | +0.194R | +20.1R | +101.5R |
| **Filtered (with trend)** | 47 | 24.7% | +0.81R | +38.0R | **+190R** |

**Result**: Make 87% MORE profit by taking 55% FEWER trades

---

## ✅ IMPLEMENTATION STRATEGY

### For 9AM Setup:

**Entry Rules:**
1. Wait for 9am ORB (09:00-09:05)
2. Calculate ORB size as % of price
3. **ONLY take trade if ORB is 0.15% - 0.35%**
4. If too small or too large, **SKIP**
5. Enter on first 1-min close outside ORB
6. Stop: ORB midpoint (HALF mode)
7. Target: 8R

**Expected Results:**
- ~13 trades per year (1 per month)
- 19% win rate
- +0.72R per trade
- ~10R profit per year

---

### For 10AM Setup (BETTER):

**Entry Rules:**
1. Observe 9:00-10:00 price action
2. Identify if price is trending up or down
3. Wait for 10am ORB (10:00-10:05)
4. **ONLY take breakouts in direction of pre-ORB trend**
   - If 9-10am was up → take LONG breakouts only
   - If 9-10am was down → take SHORT breakouts only
   - If sideways → skip
5. Enter on first 1-min close outside ORB
6. Stop: ORB low/high (FULL mode)
7. Target: 6R

**Expected Results:**
- ~47 trades per year (4 per month)
- 25% win rate (1 in 4)
- +0.81R per trade
- ~38R profit per year

---

## 🎯 RECOMMENDED TRADING PLAN

**Best approach: Use BOTH setups with filters**

**9AM**: Take 13 filtered trades per year
- Filter: ORB size 0.15-0.35%
- Expected: +10R per year

**10AM**: Take 47 filtered trades per year
- Filter: With pre-ORB trend
- Expected: +38R per year

**TOTAL**: 60 trades per year, +48R annual profit

**This is HIGH QUALITY over quantity.**

---

## 📝 HOW TO ADD TO YOUR TRADING APP

**Required additions:**

1. **ORB Size Calculator**
   - Show ORB size in pts
   - Show ORB size as % of price
   - **Alert if size is in optimal range (0.12-0.35%)**

2. **Pre-ORB Trend Detector**
   - Track 9:00-10:00 range
   - Calculate where close sits in range
   - **Show directional bias: UP / DOWN / NEUTRAL**
   - **Only show 10am trades that match bias**

3. **Setup Filter Display**
   - Show "FILTERED" or "SKIP" based on conditions
   - Reason for skip: "ORB too small", "Wrong direction", etc.

4. **Trade Counter**
   - Show how many filtered trades taken this year
   - Expected vs actual

---

## 🚨 CRITICAL REMINDER

**The 10am setup with pre-ORB trend filter:**
- 24.7% win rate = **1 in 4 trades wins**
- 6R reward = when you win, you make **6 times your risk**
- **You WILL have losing streaks of 5-10 trades**
- **This is NORMAL and EXPECTED**

**Required for success:**
1. Follow the filter rules (don't override)
2. Accept the losses (they're part of the edge)
3. Risk the same amount every trade
4. Track results over 50+ trades minimum

**The math works over time, not on any single trade.**

---

## CONCLUSION

**Filters are CRITICAL for low win-rate, high RR strategies.**

Without filters:
- 9am: 11.7% WR, +30R total
- 10am: 16.4% WR, +101R total

With filters:
- 9am: 19.1% WR, +49R total
- 10am: 24.7% WR, +190R total

**Filters improve results by 50-87% while reducing trade count.**

**Next step: Implement these filters in your trading app.**
