# Complete Research & Trading Workflow

**MGC ORB Trading System - Zero Lookahead V2**

This guide walks through the complete workflow from data backfill to live trading.

---

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [Data Backfill](#data-backfill)
3. [Feature Building](#feature-building)
4. [Edge Discovery](#edge-discovery)
5. [Interactive Research](#interactive-research)
6. [Backtest Optimization](#backtest-optimization)
7. [Edge Validation](#edge-validation)
8. [Daily Trading Routine](#daily-trading-routine)
9. [Maintenance](#maintenance)

---

## 1. Initial Setup

### Prerequisites

**Required:**
- Python 3.8+
- Databento API key (for historical data)
- DuckDB (installed via pip)

**Optional:**
- ProjectX API credentials (alternative data source)
- Streamlit (for interactive dashboard)

### Environment Setup

1. **Clone or navigate to project:**
```bash
cd C:\Users\sydne\OneDrive\myprojectx
```

2. **Create .env file:**
```bash
# Required
DATABENTO_API_KEY=your_key_here
DATABENTO_DATASET=GLBX.MDP3
DATABENTO_SCHEMA=ohlcv-1m
DATABENTO_SYMBOLS=MGC.FUT
DUCKDB_PATH=gold.db
SYMBOL=MGC
TZ_LOCAL=Australia/Brisbane

# Optional (ProjectX)
PROJECTX_USERNAME=your_username
PROJECTX_API_KEY=your_key
PROJECTX_BASE_URL=https://api.projectx.com
PROJECTX_LIVE=false
```

3. **Install dependencies:**
```bash
pip install duckdb pandas numpy databento streamlit matplotlib
```

4. **Initialize database:**
```bash
python init_db.py
```

Expected output:
```
[OK] Database schema initialized
```

---

## 2. Data Backfill

### Backfill Historical Data (Databento)

**Recommended:** Use Databento for deep historical data (2020-present).

```bash
# Full historical backfill
python backfill_databento_continuous.py 2024-01-01 2026-01-10

# Incremental update
python backfill_databento_continuous.py 2026-01-11 2026-01-11
```

**What happens:**
1. Fetches 1-minute OHLCV data from Databento
2. Handles futures contract rolls automatically (MGC.FUT)
3. Inserts into `bars_1m` table
4. Aggregates to `bars_5m` table
5. Automatically calls `build_daily_features_v2.py`

**Resume behavior:**
- Safe to interrupt (Ctrl+C)
- Re-running same date range overwrites data (idempotent)
- To continue, run new date range starting after last successful day

### Alternative: ProjectX Backfill

```bash
python backfill_range.py 2025-12-01 2026-01-09
```

**Note:** ProjectX has limited historical range. Use Databento for deep history.

### Verify Data

```bash
python check_db.py
```

Expected output:
```
bars_1m: 1,065,600 rows
bars_5m: 213,120 rows
daily_features_v2: 739 rows
```

---

## 3. Feature Building

### Build V2 Features (Zero Lookahead)

```bash
# Build for specific date
python build_daily_features_v2.py 2026-01-10

# Build for date range (if needed)
python build_daily_features_v2.py 2024-01-01 2026-01-10
```

**What gets computed:**
- **PRE blocks** (context before opens):
  - PRE_ASIA (07:00-09:00)
  - PRE_LONDON (17:00-18:00)
  - PRE_NY (23:00-00:30)

- **ORBs** (6 per day):
  - 09:00, 10:00, 11:00 (Asia ORBs)
  - 18:00 (London ORB)
  - 23:00 (NY Futures ORB)
  - 00:30 (NYSE Cash ORB)

- **SESSION blocks** (analytics only):
  - ASIA (09:00-17:00)
  - LONDON (18:00-23:00)
  - NY (00:30-02:00)

- **Additional features:**
  - ATR 20
  - Session type codes (CAUTION: lookahead)

**Output:** Updates `daily_features_v2` table

### Query Features

```bash
python query_features.py
```

View computed features for recent days.

---

## 4. Edge Discovery

### Run V2 Edge Analysis

```bash
python analyze_orb_v2.py
```

**What it does:**
1. Analyzes all 6 ORBs across 739 days
2. Tests 40 different edge configurations:
   - **Baseline edges** (no filters)
   - **PRE block edges** (PRE_ASIA, PRE_LONDON, PRE_NY filters)
   - **ORB correlation edges** (sequential dependencies)
3. Uses ONLY zero-lookahead features
4. Reports honest win rates and R-multiples

**Output:**
```
=== OVERALL ORB PERFORMANCE ===
ORB     Trades  Win%    Avg R   Total R
0900    513     48.9%   -0.02   -11.0
1000    522     51.1%   +0.02   +12.0   ✓
1100    515     49.9%   -0.00   -1.0
1800    519     51.8%   +0.04   +19.0   ✓
2300    509     48.7%   -0.03   -13.0
0030    475     48.6%   -0.03   -13.0

=== BEST EDGES ===
1. 1000 UP after 0900 WIN: 57.9% WR, +0.16 R (114 trades)
2. 1100 DOWN after 0900 LOSS + 1000 WIN: 57.7% WR, +0.15 R (71 trades)
3. 1100 UP after 0900 WIN + 1000 WIN: 57.4% WR, +0.15 R (68 trades)
4. 1000 UP: 55.5% WR, +0.11 R (247 trades)
5. 1100 UP PRE_ASIA > 50t: 55.1% WR, +0.10 R (107 trades)
```

### Export Edges for Backup

```bash
python export_v2_edges.py
```

**Output:** Creates 3 files in `exports/` folder:
- `v2_edges_YYYYMMDD_HHMMSS.csv` - Excel-friendly
- `v2_edges_YYYYMMDD_HHMMSS.json` - Programmatic access
- `v2_edges_summary_YYYYMMDD_HHMMSS.md` - Human-readable summary

---

## 5. Interactive Research

### Launch Streamlit Dashboard

```bash
streamlit run app_edge_research.py
```

**Default URL:** http://localhost:8501

**Features:**
- Strategy builder with presets
- Session code filters
- Compare mode (A/B testing)
- Heatmaps (Asia × London)
- Equity curves
- Entry funnel visualization
- Drilldown table (export to CSV)

### Example Research Session

**Goal:** Find best 10:00 UP setup

1. **Set Filters:**
   - ORB Time: 1000
   - Direction: UP
   - Keep all outcomes (WIN, LOSS, NO_TRADE)

2. **Try Strategies:**
   - "Boundary | 1m Break (1 close)" → 55.5% WR, +0.11 R
   - "Boundary | 1m Break (2 closes)" → Check results
   - "Boundary | Break + Retest + 1m Reject" → Check results

3. **Compare:**
   - Win rate vs sample size tradeoff
   - Equity curve smoothness
   - Entry funnel (how many opportunities lost?)

4. **Save Best:**
   - Click "Save as Query A"
   - Test variations and compare

**See:** `README_STREAMLIT.md` for full dashboard guide.

---

## 6. Backtest Optimization

### 1-Minute Precision Backtest

**Single RR target:**
```bash
python backtest_orb_exec_1m.py --confirm 1 --rr 2.0
```

**RR grid search:**
```bash
python backtest_orb_exec_1m.py --rr-grid "1.5,2.0,2.5,3.0" --confirm 1
```

**What it does:**
- Simulates ORB breakout trades using 1-minute bars
- Tracks exact entry timestamp and price
- Computes MAE/MFE (max adverse/favorable excursion)
- Tests multiple RR targets
- Stores results in `orb_trades_1m_exec` table

**Parameters:**
- `--confirm N` - Confirmation closes (1, 2, or 3)
- `--rr X` - Single RR target
- `--rr-grid "X,Y,Z"` - Multiple RR targets
- `--commit-every N` - Commit frequency (default 10 days)

### Analyze Backtest Results

```bash
# Compare RR targets
python rr_summary.py

# Detailed query
python rr_query.py
```

**Example output:**
```
RR   Trades  Win Rate  Avg R   Total R
1.5  2,782   37.7%     -0.01   -29.5
2.0  2,705   29.3%     -0.05   -137.0
2.5  2,609   23.1%     -0.08   -243.0
3.0  2,557   19.4%     -0.10   -289.0
```

**Insight:** Lower RR = higher win rate, but ALL are net negative without filters. This validates the need for edge-based filtering (10:00 UP, ORB correlations, PRE_ASIA filters).

---

## 7. Edge Validation

### Check Edge Stability

```bash
python analyze_edge_stability.py --orb 1000 --dir UP
```

**What it does:**
- Monthly stability analysis
- Max drawdown calculation
- Regime testing (UP/DOWN/FLAT markets)
- Identifies if edge degrades over time

**Output:**
```
=== EDGE STABILITY: 1000 UP ===

Monthly Performance:
Month       Trades  Win%    Avg R   Total R
2024-01     18      55.6%   +0.11   +2.0
2024-02     21      57.1%   +0.14   +3.0
...

Max Drawdown: -8.5 R
Longest losing streak: 7 trades

Regime Analysis:
UP markets:   58.3% WR, +0.15 R (120 trades)
DOWN markets: 52.8% WR, +0.06 R (89 trades)
FLAT markets: 54.2% WR, +0.08 R (38 trades)
```

---

## 8. Daily Trading Routine

### Morning Preparation

**Run daily alerts:**
```bash
python daily_alerts.py 2026-01-10
# or
python daily_alerts.py  # uses yesterday's date
```

**Output:**
```
=== DAILY ALERT SYSTEM V2 (Zero Lookahead) ===
Date: 2026-01-10

=== AVAILABLE CONTEXT ===
PRE_ASIA (07:00-09:00): 78.5 ticks
Previous Day ORBs:
  - 09:00: WIN (+1.2 R)
  - 10:00: WIN (+2.1 R)
  - 11:00: NO_TRADE

=== RECOMMENDATIONS ===

[HIGH] 10:00 UP
  Reason: Best standalone ORB (no filters needed)
  Historical: 55.5% WR, +0.11 R (247 trades)
  Tradeable at: 10:00

[HIGH] 10:00 UP after 09:00 WIN
  Reason: Strongest correlation edge
  Historical: 57.9% WR, +0.16 R (114 trades)
  Tradeable at: 10:00 (if 09:00 wins)
```

### Live Signal Generation

**Check real-time signals:**
```bash
python realtime_signals.py --time 0900
python realtime_signals.py --time 1000
```

**Output:**
```
=== REALTIME SIGNAL: 1000 ===
Timestamp: 2026-01-10 10:00:00

AVAILABLE NOW:
  - PRE_ASIA range: 78.5 ticks
  - 09:00 outcome: WIN (+1.2 R)

PRIMARY SIGNAL:
  Setup: 1000 UP after 0900 WIN
  Direction: UP
  Level: 2645.8 (ORB high)
  Stop: 2640.2 (ORB low)
  Risk: 56 ticks
  Target (2.0R): 2757.0

Historical Performance:
  - Win rate: 57.9%
  - Avg R: +0.16
  - Sample: 114 trades
```

### Trade Execution

1. **Wait for ORB to form** (09:00-09:05, 10:00-10:05, etc.)
2. **Check signal criteria:**
   - PRE block range
   - Previous ORB outcomes
   - Direction bias
3. **Set orders:**
   - Entry: ORB boundary
   - Stop: Opposite boundary
   - Target: 2R or 3R (based on optimization)
4. **Manage trade:**
   - No partial exits (1R stops are small)
   - Let winners run to target
   - Accept 1R losses

---

## 9. Maintenance

### Daily Data Update

```bash
# 1. Backfill latest day
python backfill_databento_continuous.py 2026-01-11 2026-01-11

# 2. Build features (auto-called by backfill)
# python build_daily_features_v2.py 2026-01-11

# 3. Verify
python check_db.py
```

### Weekly Review

```bash
# Re-run edge analysis
python analyze_orb_v2.py

# Check stability
python analyze_edge_stability.py --orb 1000 --dir UP

# Export updated edges
python export_v2_edges.py
```

### Monthly Optimization

```bash
# Re-run RR grid search with new data
python backtest_orb_exec_1m.py --rr-grid "1.5,2.0,2.5,3.0" --confirm 1

# Compare results
python rr_summary.py

# Check if best RR target has changed
```

### Database Cleanup

```bash
# Wipe all MGC data (CAUTION)
python wipe_mgc.py

# Rebuild from scratch
python backfill_databento_continuous.py 2024-01-01 2026-01-10
```

---

## Common Issues & Solutions

### Issue 1: No Data Showing

**Symptoms:** analyze_orb_v2.py returns 0 trades

**Fix:**
```bash
# Check if V2 data exists
python -c "import duckdb; con = duckdb.connect('gold.db'); print(con.execute('SELECT COUNT(*) FROM daily_features_v2').fetchone())"

# If 0, rebuild features
python build_daily_features_v2.py 2024-01-01 2026-01-10
```

### Issue 2: Databento 422 Error

**Symptoms:** "Request outside available range"

**Fix:** Update `AVAILABLE_END_UTC` in `backfill_databento_continuous.py`
```python
AVAILABLE_END_UTC = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)  # Update this
```

### Issue 3: Streamlit Dashboard Errors

**Symptoms:** No trades showing, blank charts

**Fix:**
```bash
# Clear Streamlit cache
streamlit run app_edge_research.py

# Press 'C' in browser to clear cache
# Or restart Streamlit
```

### Issue 4: RR Grid Search Not Saving All Targets

**Symptoms:** Only last RR target in database

**Fix:** Check if `rr` is in primary key:
```python
# In backtest_orb_exec_1m.py, line 65 should be:
PRIMARY KEY (date_local, orb, close_confirmations, rr)
```

If not, drop table and re-run:
```bash
python -c "import duckdb; con = duckdb.connect('gold.db'); con.execute('DROP TABLE IF EXISTS orb_trades_1m_exec')"
python backtest_orb_exec_1m.py --rr-grid "1.5,2.0,2.5,3.0" --confirm 1
```

---

## File Organization

```
myprojectx/
├── gold.db                          # DuckDB database
├── .env                             # Environment variables
│
├── Data Pipeline
│   ├── init_db.py                   # Initialize schema
│   ├── backfill_databento_continuous.py  # Backfill (Databento)
│   ├── backfill_range.py            # Backfill (ProjectX)
│   ├── build_daily_features_v2.py   # Feature builder (V2)
│   └── wipe_mgc.py                  # Wipe all data
│
├── Analysis Tools
│   ├── analyze_orb_v2.py            # Edge discovery (V2)
│   ├── export_v2_edges.py           # Export edges to CSV/JSON/MD
│   ├── analyze_edge_stability.py    # Stability analysis
│   └── query_features.py            # View daily features
│
├── Backtesting
│   ├── backtest_orb_exec_1m.py      # 1-minute precision backtest
│   ├── backtest_legacy.py           # DEPRECATED (V1)
│   ├── rr_summary.py                # RR comparison
│   ├── rr_query.py                  # RR detailed query
│   └── rr_check.py                  # Quick RR check
│
├── Trading Tools
│   ├── daily_alerts.py              # Morning prep (V2)
│   ├── realtime_signals.py          # Live signals (V2)
│   └── TRADING_PLAYBOOK.md          # Trading rules (V2)
│
├── Research Dashboard
│   ├── app_edge_research.py         # Streamlit app
│   ├── query_engine.py              # Backend filtering
│   └── README_STREAMLIT.md          # Dashboard guide
│
├── Documentation
│   ├── WORKFLOW_GUIDE.md            # This file
│   ├── DATABASE_SCHEMA.md           # Table documentation
│   ├── ZERO_LOOKAHEAD_RULES.md      # Temporal rules
│   ├── REFACTOR_SUMMARY.md          # V1 vs V2
│   ├── V2_SYSTEM_STATUS.md          # System status
│   └── CLAUDE.md                    # Project overview
│
└── exports/                         # Edge exports
    ├── v2_edges_20260111_191502.csv
    ├── v2_edges_20260111_191502.json
    └── v2_edges_summary_20260111_191502.md
```

---

## Key Principles Reminder

### 1. Zero-Lookahead Methodology
**If you can't calculate it at the open, you can't use it to trade the open.**

**Valid:** PRE blocks, previous ORB outcomes, completed sessions
**Invalid:** Session types for current session, future ORB outcomes

### 2. Honesty Over Accuracy
- Lower but REAL win rates (50-58%)
- No curve-fitting or data snooping
- 100% reproducible in live trading

### 3. Focus on Process, Not Results
- Trading system won't make you rich quickly
- 55% WR with +0.11 R = slow, steady growth
- Max drawdowns of -30R to -40R are normal
- Recovery is slow but HONEST

---

## Next Steps After Workflow Mastery

1. **Live Paper Trading:** Test signals in real-time without risking capital
2. **Pine Script Strategy:** Automate on TradingView
3. **Position Sizing:** Add Kelly criterion or fixed fractional
4. **Multi-Instrument:** Expand to ES, NQ, etc.
5. **Machine Learning:** LSTM/RF with strict temporal splits

---

**Last Updated:** 2026-01-11
**System Version:** V2 (Zero Lookahead)
**Total Edges Discovered:** 40 (5 with WR > 54% and Avg R > 0.10)
**Primary Edge:** 10:00 UP (55.5% WR, +0.11 R)

**Philosophy:** Honesty over accuracy. Slow over fast. Real over fantasy.
