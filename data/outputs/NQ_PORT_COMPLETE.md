# NQ PORT TO FRAMEWORK - COMPLETE

**Date**: 2026-01-13
**Status**: ✅ PHASE 1 COMPLETE (Ingestion + Features)
**Next**: Backtesting + Dashboard Integration

---

## 📊 SUMMARY

Successfully ported the entire Gold (MGC) research stack to NQ (Nasdaq futures):
- ✅ DBN ingestion with continuous contract logic
- ✅ Data integrity audit (PASSED)
- ✅ Feature pipeline with all 6 ORBs
- ✅ Initial findings: NQ shows different patterns than MGC

**Data Coverage**: Jan 13 - Nov 21, 2025 (~10.5 months, 268 trading days)

---

## 🎯 DELIVERABLES COMPLETED

### 1. ✅ DBN Ingestion (`scripts/ingest_databento_dbn_nq.py`)

**Features**:
- Reads Databento DBN files with symbology mapping
- Selects front contract by volume (NQH5, NQM5, NQU5, NQZ5)
- Aggregates to 1-minute bars
- Converts prices from fixed-point (÷1e9)
- Builds 5-minute bars deterministically
- Uses INSERT OR REPLACE (idempotent)

**Results**:
- **306,243** 1-minute bars
- **61,252** 5-minute bars
- 4 contracts: NQH5 (Mar), NQM5 (Jun), NQU5 (Sep), NQZ5 (Dec)

**Command**:
```bash
python scripts/ingest_databento_dbn_nq.py NQ
```

---

### 2. ✅ Data Integrity Audit (`scripts/audit_nq_data_integrity.py`)

**Checks**:
- ✅ No duplicate timestamps
- ✅ No invalid prices (all in 16,460-26,399 range)
- ✅ Timezone conversion correct (UTC → UTC+10 Brisbane)
- ✅ 5m aggregation matches 1m data
- ⚠️ Gaps expected (weekends/holidays)
- ⚠️ Coverage 70.9% (normal for futures, no overnight on weekends)

**Output**: `outputs/NQ_DATA_AUDIT.md`

**Verdict**: ✅ DATA INTEGRITY VERIFIED - Ready for feature engineering

**Command**:
```bash
python scripts/audit_nq_data_integrity.py
```

---

### 3. ✅ Feature Pipeline (`scripts/build_daily_features_nq.py`)

**Features Implemented**:
- Session stats: PRE_ASIA, ASIA, PRE_LONDON, LONDON, PRE_NY, NY_CASH
- 6 ORBs: 0900, 1000, 1100, 1800, 2300, 0030
- ORB execution: Entry on first close outside, FULL/HALF SL, RR targets
- MAE/MFE tracking (ORB-anchored, normalized by R)
- RSI(14) at 0030 ORB

**Session Windows (Brisbane UTC+10 - SAME AS MGC)**:
- ASIA: 09:00-17:00
- LONDON: 18:00-23:00
- NY_FUTURES: 23:00-00:30 (next day)
- NY_CASH: 00:30-02:00 (next day)

**Output Table**: `daily_features_v2_nq` (268 rows)

**Command**:
```bash
python scripts/build_daily_features_nq.py 2025-01-13 2025-11-21 --sl-mode full
```

---

## 📈 INITIAL NQ ORB FINDINGS

**Performance (268 trading days, Jan-Nov 2025, FULL SL mode)**:

| Rank | ORB | Trades | Win Rate | Avg R | Notes |
|------|-----|--------|----------|-------|-------|
| 🥇 1st | **0030** | 208 | **63.9%** | **+0.279R** | NYSE open - BEST for NQ |
| 🥈 2nd | **1800** | 221 | 62.0% | +0.240R | London open |
| 🥉 3rd | **1100** | 219 | 61.6% | +0.233R | Asia mid-day |
| 4th | **1000** | 221 | 57.9% | +0.158R | Asia early |
| 5th | **0900** | 223 | 52.9% | +0.058R | Asia open - weak |
| 6th | **2300** | 222 | 50.0% | +0.000R | NY Futures - breakeven |

**Key Insights**:
1. **0030 ORB is strongest** - Makes sense: Nasdaq = US equity index, NYSE open drives it
2. **Different pattern than MGC** - Gold favored Asia ORBs; NQ favors NYSE open
3. **All profitable except 2300** - 5 of 6 ORBs show positive expectancy
4. **High trade frequency** - ~220 trades per ORB (~0.8/day each)

---

## 🔧 TECHNICAL IMPLEMENTATION

### NQ-Specific Parameters

```python
SYMBOL = "NQ"
TICK_SIZE = 0.25  # vs 0.1 for MGC
BARS_1M_TABLE = "bars_1m_nq"
BARS_5M_TABLE = "bars_5m_nq"
OUTPUT_TABLE = "daily_features_v2_nq"
```

### Continuous Contract Logic

Same as MGC:
- Front contract = highest volume per minute
- Exclude spreads (symbol contains '-')
- Only NQ outrights (NQH5, NQM5, NQU5, NQZ5)
- Automatic roll detection

### Session Windows

**Kept SAME as MGC** (per user requirement):
- Asia: 09:00-17:00 (Brisbane)
- London: 18:00-23:00
- NY Futures: 23:00-00:30 (next day)
- NYSE: 00:30-02:00 (next day)

These are NOT traditional NQ RTH hours (09:30-16:00 ET) but allow comparison with MGC framework.

---

## 📁 FILES CREATED

### Scripts
1. `scripts/ingest_databento_dbn_nq.py` - DBN ingestion for NQ
2. `scripts/audit_nq_data_integrity.py` - Data validation
3. `scripts/build_daily_features_nq.py` - Feature pipeline for NQ

### Outputs
4. `outputs/NQ_DATA_AUDIT.md` - Comprehensive data audit report
5. `outputs/NQ_PORT_COMPLETE.md` - This document
6. `check_nq_features.py` - Quick feature stats checker

### Database Tables
7. `bars_1m_nq` - 1-minute OHLCV bars (306,243 rows)
8. `bars_5m_nq` - 5-minute aggregated bars (61,252 rows)
9. `daily_features_v2_nq` - Daily features with all 6 ORBs (268 rows)

---

## 🎯 WHAT'S READY

✅ **Data Pipeline**: Complete and validated
✅ **Feature Engineering**: All 6 ORBs calculated
✅ **Initial Findings**: NQ behaves differently than MGC
✅ **Zero Lookahead**: All features use only available-at-time data
✅ **Execution Engine**: Same conservative model as MGC (entry on close, ORB-anchored)

---

## 📋 WHAT'S PENDING

### High Priority (Next Steps)
1. **Port Backtests** - Adapt MGC backtest scripts to use NQ tables/config
2. **Market Config** - Create `configs/market_nq.yaml` with NQ-specific parameters
3. **Dashboard Integration** - Add symbol selector (MGC vs NQ)

### Medium Priority
4. **RR Optimization** - Test RR 1.0, 1.5, 2.0, 2.5, 3.0 for each ORB
5. **SL Mode Comparison** - Compare FULL vs HALF stop modes
6. **Size Filter Discovery** - Test if ORB size filters help NQ (they helped MGC night sessions)
7. **Entry Timing Variants** - Test 1/2/3 close confirmations

### Low Priority
8. **Pre-2024 Data** - Backfill 2020-2023 for longer history
9. **IS/OOS Validation** - Proper in-sample / out-of-sample split
10. **Advanced Features** - Volume profiles, tick imbalances, etc.

---

## 💡 KEY LEARNINGS

### NQ vs MGC Differences

**MGC (Gold)**:
- Best ORBs: Asia sessions (0900, 1100)
- Gold trades globally 24/5
- Lower volatility, tighter ranges

**NQ (Nasdaq)**:
- Best ORB: NYSE open (0030)
- Equity index driven by US market hours
- Higher volatility, wider ranges

**Implication**: Can't blindly apply MGC strategies to NQ - each instrument has its own personality.

### Framework Flexibility

The framework successfully ported because:
- Session windows are configurable
- ORB logic is instrument-agnostic
- Tables are separated (bars_1m_nq vs bars_1m)
- Tick size is parameterized

This proves the architecture is sound and can scale to more instruments (ES, CL, GC, etc).

---

## 🚀 HOW TO RUN THE FULL PIPELINE

### 1. Ingest Data
```bash
# Place DBN files in NQ/ folder
python scripts/ingest_databento_dbn_nq.py NQ
```

### 2. Audit Data
```bash
python scripts/audit_nq_data_integrity.py
# Check outputs/NQ_DATA_AUDIT.md
```

### 3. Build Features
```bash
# For FULL SL mode (default)
python scripts/build_daily_features_nq.py 2025-01-13 2025-11-21 --sl-mode full

# For HALF SL mode
python scripts/build_daily_features_nq.py 2025-01-13 2025-11-21 --sl-mode half
```

### 4. Check Results
```bash
python check_nq_features.py
```

---

## 🧪 NEXT EXPERIMENT: "TRIAL EVERYTHING" ON NQ

Per user's mission: **Run the same trial-everything framework on NQ**.

**What to test**:
1. All 6 ORBs (done - 0030 is best)
2. RR variations (1.0, 1.5, 2.0, 2.5, 3.0)
3. SL modes (FULL vs HALF)
4. Entry confirmations (1, 2, 3 closes)
5. Size filters (ORB size vs ATR)
6. Buffer zones (entry X points away from ORB edge)
7. Liquidity states (volume, spread, MA distance)
8. Session conditions (Asia type, London type, etc.)

**Expected Approach**:
- Systematic grid search
- Conservative execution assumptions
- Zero lookahead enforcement
- IS/OOS validation when more data available

---

## 📊 COMPARISON: NQ vs MGC ORBs

| Metric | MGC 0900 | NQ 0030 | Notes |
|--------|----------|---------|-------|
| Win Rate | 71.7% | 63.9% | MGC Asia ORB stronger |
| Avg R | +0.431R | +0.279R | MGC higher expectancy |
| Frequency | ~daily | ~daily | Similar trade frequency |
| Best Time | Asia open | NYSE open | Different market drivers |

**Conclusion**: Both instruments have profitable ORBs, but optimal times differ based on market structure.

---

## ✅ DELIVERABLES SUMMARY

**Completed**:
1. ✅ Ingest NQ DBN → DuckDB (306k bars)
2. ✅ Validate data integrity (PASSED)
3. ✅ Port feature pipeline (268 days)
4. ✅ Calculate all 6 ORBs
5. ✅ Initial findings documented

**Commands to reproduce**:
```bash
# Full pipeline
python scripts/ingest_databento_dbn_nq.py NQ
python scripts/audit_nq_data_integrity.py
python scripts/build_daily_features_nq.py 2025-01-13 2025-11-21 --sl-mode full
python check_nq_features.py
```

**Next Phase**: Backtesting framework + market config + dashboard integration

---

**Status**: ✅ NQ PORT PHASE 1 COMPLETE - Ready for systematic testing

**Date**: 2026-01-13
**Data Coverage**: Jan 13 - Nov 21, 2025 (268 trading days)
**Total Bars**: 306,243 (1m) + 61,252 (5m)
**Features**: 268 daily rows with 6 ORBs each
