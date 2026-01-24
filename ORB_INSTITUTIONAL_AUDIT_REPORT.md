# ORB Institutional Audit Report
**Date**: 2026-01-24
**Auditor**: Claude Sonnet 4.5
**Repository**: myprojectx2_cleanpush
**Branch**: recovery/working-app

---

## Executive Summary

**SAFE TO TRADE?** ⚠️ **CONDITIONAL YES - WITH CRITICAL ACTIONS REQUIRED**

The codebase demonstrates strong foundational design with UTC storage, explicit timezone conversions, and zero-lookahead architecture. However, several **CRITICAL GAPS** in temporal integrity testing, edge case handling, and out-of-sample validation must be addressed before live trading.

**Immediate Actions Required:**
1. Build temporal integrity test suite (DST boundaries, weekend gaps)
2. Create silent failure tests (missing bars, duplicates, out-of-order data)
3. Run determinism validation (two identical backtest runs)
4. Implement explicit out-of-sample validation framework
5. Document fill model and commission assumptions explicitly

---

## 1) System Truth Discovery

### Environment

| Component | Value | Status |
|-----------|-------|--------|
| Git Root | `C:/Users/sydne/OneDrive/myprojectx2_cleanpush` | ✅ |
| Git Status | `?? res2.txt` (clean working tree) | ✅ |
| Python Version | 3.10.9 | ✅ |
| Platform | Windows-10-10.0.19045-SP0 | ✅ |
| zoneinfo | Available | ✅ |
| DuckDB | 1.4.3 | ✅ |

**Finding**: Environment is stable and suitable for production.

---

## 2) Timezone Authority Inventory

### Single Source of Truth Policy

**Standard**: All timestamps stored in **UTC** in database. Conversion to `Australia/Brisbane` (UTC+10, no DST) happens at:
- Query boundaries (session window definitions)
- UI/execution boundaries (display, ORB detection)
- Feature building (daily aggregation)

### Data Flow Timeline Inventory

| Stage | Module/File | Column Name | Stored TZ | Conversion Point | Evidence |
|-------|-------------|-------------|-----------|------------------|----------|
| **1. Ingestion (Databento)** | `pipeline/backfill_databento_continuous.py` | `ts_event` (Databento) → `ts_utc` | UTC (tz-aware) | L240: Databento returns tz-aware UTC | `backfill_databento_continuous.py:240` |
| **2. Database Storage** | `bars_1m`, `bars_5m` tables | `ts_utc` | `TIMESTAMPTZ` (UTC) | Direct insert L86-87 | `backfill_databento_continuous.py:86` |
| **3. Feature Building** | `pipeline/build_daily_features_v2.py` | `ts_utc` | UTC | L71-72: `astimezone(TZ_UTC)` | `build_daily_features_v2.py:71` |
| **4. Session Windows** | `pipeline/build_daily_features_v2.py` | N/A (computed) | Brisbane local → UTC | L59-67: `_dt_local()` creates Brisbane-aware datetime, converts to UTC for queries | `build_daily_features_v2.py:59` |
| **5. ORB Detection** | `pipeline/build_daily_features_v2.py` | `ts_utc` | UTC | L100-113: `_fetch_1m_bars()` converts local→UTC for query | `build_daily_features_v2.py:100` |
| **6. Live Data (ProjectX)** | `trading_app/data_loader.py` | `ts_utc` | UTC | L84: `TIMESTAMPTZ` schema | `trading_app/data_loader.py:84` |
| **7. Trading App Config** | `trading_app/config.py` | N/A | Brisbane definitions | L32: `TZ_LOCAL = ZoneInfo("Australia/Brisbane")` | `trading_app/config.py:32` |
| **8. Backtest Engine** | `trading_app/backtest/engine.py` | N/A | Brisbane → UTC | L28-29: Uses pytz for conversion (LEGACY, should migrate to zoneinfo) | `trading_app/backtest/engine.py:28` |

### Critical Observations

**✅ STRENGTHS:**
1. **Consistent UTC Storage**: All database tables use `TIMESTAMPTZ` with UTC
2. **Explicit Conversions**: No naive timestamps in production pipeline
3. **Single Timezone Authority**: Australia/Brisbane consistently used across all modules
4. **ORB Window Alignment**: Trading day correctly defined as 09:00→09:00 Brisbane time

**⚠️ CONCERNS:**
1. **Mixed Timezone Libraries**: Some modules use `pytz` (legacy), others use `zoneinfo` (modern). This creates maintenance risk and potential conversion bugs.
   - `build_daily_features_v2.py` uses `zoneinfo` ✅
   - `backtest/engine.py` uses `pytz` ⚠️
   - **Recommendation**: Standardize on `zoneinfo` (Python 3.9+ builtin)

2. **No Explicit DST Testing**: While Brisbane has no DST, data sources (GLBX.MDP3, CME) and US markets DO observe DST. No tests validate correct handling during:
   - US DST start (March, 2nd Sunday 2am)
   - US DST end (November, 1st Sunday 2am)
   - **Blocker**: Could cause 1-hour offset in session windows during DST transitions

---

## 3) Temporal Integrity Tests

### Current State: **CRITICAL GAP**

**Gate Status**: ❌ **FAILED - NO AUTOMATED TESTS EXIST**

No automated tests currently validate:
- ORB window alignment across DST regimes
- Correct timestamp interpretation during DST transitions
- Session boundary accuracy (09:00 Asia, 18:00 London, 23:00 NY, 00:30 NY)

### Required Tests (NOT IMPLEMENTED)

```python
# REQUIRED: test_temporal_integrity.py (DOES NOT EXIST)

def test_orb_window_aest_period():
    """Verify ORB windows during AEST (Brisbane standard time)."""
    # Test date: 2025-06-15 (winter, no US DST active)
    # Assert: 09:00 Brisbane ORB = 23:00 UTC (prev day)
    pass

def test_orb_window_us_dst_start():
    """Verify ORB windows during US DST start (March 2nd Sunday)."""
    # Test date: 2025-03-09 (US DST starts)
    # Assert: 09:00 Brisbane ORB maps correctly despite US clock change
    pass

def test_orb_window_us_dst_end():
    """Verify ORB windows during US DST end (November 1st Sunday)."""
    # Test date: 2025-11-02 (US DST ends)
    # Assert: ORB boundaries remain aligned to Brisbane time
    pass

def test_midnight_crossing_windows():
    """Verify NY session (23:00→00:30) correctly crosses midnight."""
    # Assert: No off-by-one errors in bar fetching
    pass
```

### Timestamp Probe Script (NOT IMPLEMENTED)

**Required**: `scripts/timestamp_probe.py`
- Read 1 day of 1m bars
- Print first 20 timestamps in raw DB, UTC, and Brisbane
- Print computed ORB start/end for all 6 ORBs
- Validate against expected local times

**Action Item**: Create this script to enable manual validation.

---

## 4) Lookahead Bias Audit

### Methodology

Searched for red flags:
```bash
rg -n "shift\(-|lead\(|future|lookahead|mfe|mae|outcome|label|target|profit|pnl" *.py
rg -n "rolling\(|expanding\(|resample\(" *.py
```

### Findings

**✅ ZERO LOOKAHEAD ARCHITECTURE CONFIRMED**

**Evidence**:

1. **Feature/Outcome Separation** (`build_daily_features_v2.py:1-40`)
   - Header explicitly states: "ZERO LOOKAHEAD (FIXED) + CANONICAL EXECUTION ENGINE"
   - Entry logic uses ONLY data available at time `t` (L172-184)
   - ORB computed from first 5 minutes ONLY (L154-162)
   - Outcome computed AFTER entry using subsequent bars (L230-270)

2. **Entry Definition** (`build_daily_features_v2.py:172-184`)
   ```python
   # Entry = first 1m close outside ORB
   for ts_utc, h, l, c in bars:  # bars AFTER ORB end
       c = float(c)
       if c > orb_high:
           break_dir = "UP"
           entry_price = c  # CLOSE price, not high/low
           break
   ```
   - Uses CLOSE (not intrabar high/low) ✅
   - Only considers bars AFTER ORB window ends ✅
   - No future data accessed ✅

3. **Guardrail Assertions** (`build_daily_features_v2.py:186-189`)
   ```python
   assert entry_price != orb_high, "FATAL: Entry at ORB high (should be at close)"
   assert entry_price != orb_low, "FATAL: Entry at ORB low (should be at close)"
   ```
   - Prevents accidental lookahead at ORB edge ✅

4. **MAE/MFE Computation** (`build_daily_features_v2.py:226-270`)
   - Computed AFTER entry using subsequent bars ✅
   - Measured from ORB edge (not entry) for consistency ✅
   - No future aggregates used ✅

5. **No Negative Shift Operations**
   - No `.shift(-1)` found in production code ✅
   - No `.lead()` operations ✅
   - No "future window" aggregates ✅

**⚠️ MINOR CONCERNS:**

1. **MAE/MFE Storage** (`daily_features_v2` table)
   - `mae` and `mfe` columns stored in same row as ORB features
   - **Risk**: Could accidentally use MAE/MFE in filters (would be lookahead)
   - **Mitigation**: Code review shows filters only use `orb_size`, `rsi`, `session_range` (all pre-entry) ✅
   - **Recommendation**: Consider separate `trade_outcomes` table to enforce separation

2. **Rolling/Expanding Operations** (5 files found)
   - `ml/training/prepare_training_data.py`: Uses rolling for feature engineering ⚠️
   - **Need Manual Review**: Verify ML features don't leak future data
   - Other files are in `_archive/` (not production)

**Gate Status**: ✅ **PASSED - Production code is zero-lookahead compliant**

---

## 5) Execution Realism Validation

### Entry Definition

**Current Implementation** (`build_daily_features_v2.py:172-184`):
- Entry trigger: "First 1-minute CLOSE outside ORB after ORB window ends"
- Entry price: Close price of triggering bar
- **Realistic?** ✅ YES - Close price is observable and executable

### Fill Model

**Current Implementation**:
- Entry at close of triggering bar
- Assumes fill at close price (no slippage modeling)

**Concerns**:
- ❌ **NO SLIPPAGE MODEL DOCUMENTED**
- ❌ **NO COMMISSION COST DOCUMENTED**
- **Reality Check**: Micro Gold (MGC) tick size = $0.10, commission ~$1/side
  - At RR=2.0, typical risk = 2-5 ticks ($2-5)
  - Commission = $2 round-trip = ~40-100% of risk
  - **CRITICAL**: Without commission modeling, profitability claims are INFLATED

### Stop/Target Ordering

**Current Implementation** (`build_daily_features_v2.py:237-265`):
```python
hit_stop = l <= stop
hit_target = h >= target

if hit_stop and hit_target:
    outcome = "LOSS"  # Conservative: both hit = LOSS
elif hit_stop:
    outcome = "LOSS"
elif hit_target:
    outcome = "WIN"
```

**Realistic?** ✅ YES - Conservative assumption (stop-first on same bar)

### Gate Status

⚠️ **CONDITIONAL PASS - MUST ADD EXPLICIT COSTS**

**Required Actions**:
1. Document commission assumption (e.g., $2 round-trip)
2. Document slippage assumption (e.g., 0.5 ticks = $0.05)
3. Add costs to R calculation: `net_R = gross_R - (commission + slippage) / risk`
4. Re-run all profitability reports with costs included

**Example**:
```python
COMMISSION_RT = 2.0  # $2 round-trip
SLIPPAGE_TICKS = 0.5  # 0.5 ticks avg
TICK_VALUE = 0.10

def apply_costs(gross_r, risk_ticks):
    cost = COMMISSION_RT + (SLIPPAGE_TICKS * TICK_VALUE * 2)  # entry + exit
    risk_dollars = risk_ticks * TICK_VALUE
    cost_in_r = cost / risk_dollars
    return gross_r - cost_in_r
```

---

## 6) Determinism / Recreatability

### Current State: **NOT TESTED**

**Gate Status**: ❌ **FAILED - NO VALIDATION EXISTS**

**Required Test**:
```bash
# Run backtest twice
python build_daily_features_v2.py 2024-01-01 2026-01-10 > run1.txt
python build_daily_features_v2.py 2024-01-01 2026-01-10 > run2.txt
diff run1.txt run2.txt
```

**Expected**: Byte-for-byte identical (or within floating-point tolerance)

**Potential Nondeterminism Sources**:
1. ✅ No `random` module usage found in production code
2. ✅ No `datetime.now()` in feature building
3. ⚠️ Dictionary iteration order (Python 3.7+ is ordered, should be fine)
4. ⚠️ No explicit random seed management for research scripts

**Action Required**: Run determinism test and document results.

---

## 7) Silent Failure Points + Targeted Test Cases

### Current State: **CRITICAL GAP**

**Gate Status**: ❌ **FAILED - NO EDGE CASE TESTS**

The system should "fail loudly" on data quality issues, but no tests validate this behavior.

### Required Test Cases (NOT IMPLEMENTED)

```python
# REQUIRED: test_edge_cases.py (DOES NOT EXIST)

def test_missing_bars_in_orb_window():
    """Inject missing bar at 09:02 - ORB should return None or raise."""
    pass

def test_duplicate_timestamps():
    """Inject duplicate timestamp - should raise or warn."""
    pass

def test_out_of_order_bars():
    """Inject bar with ts < previous bar - should raise."""
    pass

def test_holiday_no_data():
    """Test 2025-12-25 (Christmas) - should handle gracefully."""
    pass

def test_dst_boundary_day():
    """Test 2025-03-09 (US DST start) - no off-by-one errors."""
    pass

def test_orb_window_with_gap():
    """ORB window 09:00-09:05 with missing 09:03 bar - behavior?"""
    pass
```

### Current Behavior (Code Review)

**`build_daily_features_v2.py` Handling**:
- Missing data: Returns `None` from `_window_stats_1m()` (L88-89)
- Downstream: `None` values stored as NULL in database (silent handling) ✅
- **Concern**: No logging of missing data events ⚠️

**Recommendation**: Add logging for data quality issues:
```python
if not row or row[0] is None:
    logger.warning(f"Missing data for window {start_local} - {end_local}")
    return None
```

---

## 8) Profitability Framework Honesty Checks

### Current State: **MAJOR GAPS**

**Gate Status**: ⚠️ **CONDITIONAL FAIL - NO OUT-OF-SAMPLE FRAMEWORK**

### Walk-Forward / Holdout Split

**Required**: Explicit train/test split with NO optimization on test set

**Current Practice** (from CLAUDE.md and code review):
- Features built on full dataset (2024-01-01 to 2026-01-10)
- No documented train/test split
- `validated_setups` table contains 17 setups (6 MGC, 5 NQ, 6 MPL)
- **Unclear**: Were these optimized on full sample or validated out-of-sample?

**Evidence Needed**:
1. Clear timestamp of "research cutoff" (e.g., 2025-12-31)
2. All parameter choices locked BEFORE this date
3. 2026-01-01+ used ONLY for validation (no re-optimization)

### Required Metrics Report Format

**Missing**: No standardized report with in-sample vs out-of-sample metrics

**Required Format**:
```
=== Profitability Report ===
Date Range: 2024-01-01 to 2026-01-10
Research Cutoff: 2025-12-31 (NO PARAMS CHANGED AFTER THIS DATE)

IN-SAMPLE (2024-01-01 to 2025-12-31):
  Trade Count: XXX
  Win Rate: XX%
  Avg R: X.XX
  Max Drawdown: XX R
  Worst Streak: X losses

OUT-OF-SAMPLE (2026-01-01 to 2026-01-10):
  Trade Count: XX
  Win Rate: XX%
  Avg R: X.XX
  Max Drawdown: XX R
  Worst Streak: X losses

MOST RECENT QUARTER (2025-10-01 to 2025-12-31):
  Trade Count: XX
  Win Rate: XX%
  Avg R: X.XX
```

**Action Required**: Implement walk-forward validation framework before claiming profitability.

---

## 9) Deliverables

### Findings Summary

| # | Severity | Finding | Evidence | Status |
|---|----------|---------|----------|--------|
| 1 | **BLOCKER** | No temporal integrity tests (DST boundaries) | Section 3 | ❌ Not Fixed |
| 2 | **BLOCKER** | No silent failure tests (missing bars, duplicates) | Section 7 | ❌ Not Fixed |
| 3 | **BLOCKER** | No out-of-sample validation framework | Section 8 | ❌ Not Fixed |
| 4 | **MAJOR** | No commission/slippage modeling | Section 5 | ❌ Not Fixed |
| 5 | **MAJOR** | Mixed timezone libraries (pytz vs zoneinfo) | Section 2 | ⚠️ Partial (backtest engine uses pytz) |
| 6 | **MAJOR** | No determinism validation (two identical runs) | Section 6 | ❌ Not Tested |
| 7 | MINOR | No data quality logging (missing bars) | Section 7 | ⚠️ Recommendation |
| 8 | MINOR | MAE/MFE in same table as features (risk of leakage) | Section 4 | ✅ Mitigated by code review |

### Fix Plan (Ordered by Dependency)

#### Phase 1: Critical Infrastructure (1-2 days)
**MUST COMPLETE BEFORE LIVE TRADING**

1. **Create Temporal Integrity Test Suite** (`tests/test_temporal_integrity.py`)
   - Test DST boundary handling (US March/November transitions)
   - Test midnight-crossing windows (NY 23:00→00:30)
   - Test ORB window alignment (all 6 ORBs)
   - **Dependency**: None
   - **Blocks**: Live trading approval

2. **Create Silent Failure Test Suite** (`tests/test_edge_cases.py`)
   - Test missing bars in ORB window
   - Test duplicate timestamps
   - Test out-of-order bars
   - Test holiday/weekend handling
   - **Dependency**: None
   - **Blocks**: Live trading approval

3. **Run Determinism Validation**
   ```bash
   python build_daily_features_v2.py 2024-01-01 2026-01-10 > run1.txt
   python build_daily_features_v2.py 2024-01-01 2026-01-10 > run2.txt
   diff run1.txt run2.txt  # Must be identical
   ```
   - **Dependency**: None
   - **Blocks**: Trust in backtest results

#### Phase 2: Execution Realism (0.5 days)

4. **Add Commission and Slippage Modeling**
   - Add constants to `config.py`: `COMMISSION_RT`, `SLIPPAGE_TICKS`
   - Modify `build_daily_features_v2.py` to apply costs to R calculations
   - Re-run feature building with costs
   - **Dependency**: None
   - **Blocks**: Accurate profitability claims

5. **Document Fill Model Explicitly**
   - Add docstring to entry logic explaining fill assumptions
   - Document in `CLAUDE.md` under "Execution Model"
   - **Dependency**: None
   - **Blocks**: User understanding

#### Phase 3: Out-of-Sample Validation (2-3 days)

6. **Implement Walk-Forward Framework**
   - Define research cutoff date (e.g., 2025-12-31)
   - Lock all parameters before cutoff
   - Generate in-sample vs out-of-sample metrics report
   - **Dependency**: Commission modeling (Phase 2)
   - **Blocks**: Profitability claims

7. **Generate Metrics Report**
   - Create `reports/profitability_report.md`
   - Include in-sample, out-of-sample, and recent quarter metrics
   - **Dependency**: Walk-forward framework
   - **Blocks**: Safe-to-trade decision

#### Phase 4: Code Quality (Optional, Post-Live)

8. **Standardize on zoneinfo** (eliminate pytz)
   - Migrate `backtest/engine.py` from pytz to zoneinfo
   - Test all timezone conversions
   - **Dependency**: Phase 1 tests (to catch regressions)
   - **Blocks**: None (quality improvement)

9. **Add Data Quality Logging**
   - Add `logger.warning()` for missing bars, gaps, etc.
   - **Dependency**: None
   - **Blocks**: None (quality improvement)

### Test Suite Additions

**New Files Required**:

1. `tests/test_temporal_integrity.py`
   - `test_orb_window_aest_period()`
   - `test_orb_window_us_dst_start()`
   - `test_orb_window_us_dst_end()`
   - `test_midnight_crossing_windows()`
   - `test_all_six_orb_alignment()`

2. `tests/test_edge_cases.py`
   - `test_missing_bars_in_orb_window()`
   - `test_duplicate_timestamps()`
   - `test_out_of_order_bars()`
   - `test_holiday_no_data()`
   - `test_dst_boundary_day()`
   - `test_orb_window_with_gap()`

3. `tests/test_determinism.py`
   - `test_identical_backtest_runs()`
   - `test_feature_build_determinism()`

4. `scripts/timestamp_probe.py`
   - Manual validation script for ORB alignment
   - Prints raw DB timestamps, UTC, and Brisbane conversions

5. `scripts/generate_profitability_report.py`
   - Generates in-sample vs out-of-sample metrics
   - Includes recent quarter performance

---

## Final Verdict

### Safe to Trade?

**❌ NO - NOT YET**

**Reason**: Critical gaps in temporal integrity testing, edge case handling, and out-of-sample validation create unacceptable risk.

### Conditional Approval Path

Complete **Phase 1** (temporal integrity + silent failure tests) and **Phase 2** (commission modeling) within 1-2 days, then:

**✅ YES - SAFE FOR PAPER TRADING**

After completing **Phase 3** (out-of-sample validation):

**✅ YES - SAFE FOR LIVE TRADING WITH POSITION LIMITS**

### Strengths to Build On

1. ✅ **Zero-lookahead architecture** - Excellent foundation
2. ✅ **UTC storage + explicit conversions** - Correct timezone model
3. ✅ **Conservative execution model** - Realistic entry logic
4. ✅ **Guardrail assertions** - Prevents accidental lookahead

### Critical Weaknesses

1. ❌ **No temporal integrity tests** - High risk of DST bugs
2. ❌ **No edge case tests** - Silent failures possible
3. ❌ **No out-of-sample validation** - Profitability unproven
4. ❌ **No commission/slippage modeling** - Results inflated

---

## Recommended Next Steps

1. **Immediate** (Today): Create `tests/test_temporal_integrity.py` and run DST tests
2. **Today**: Create `tests/test_edge_cases.py` and test missing bar handling
3. **Today**: Run determinism validation (two identical backtest runs)
4. **Tomorrow**: Add commission/slippage modeling to `build_daily_features_v2.py`
5. **Next Week**: Implement walk-forward validation framework
6. **Before Live**: Generate profitability report with in-sample vs out-of-sample metrics

**Only then**: Safe to trade with real capital.

---

**End of Audit Report**
