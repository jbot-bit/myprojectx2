# Phase 3 Testing - Completion Report

**Date**: 2026-01-21
**Status**: ✅ COMPLETE (with critical findings)

---

## Executive Summary

Phase 3 testing was completed on all 50 DRAFT candidates from Phase 2.5. All candidates were backtested using precomputed ORB outcomes from daily_features_v2 table.

**Result**: **0 candidates passed hard gates**

**Critical Finding**: The current backtest infrastructure uses baseline ORB outcomes (RR=2.0, SL=HALF) and does not account for candidate-specific parameters (varying RR values, filters, scan windows). This limits the validity of the results.

---

## Test Parameters

**Test Period**: 2020-12-20 to 2026-01-10 (5.05 years)

**Candidates Tested**: 50 (all DRAFT from Phase 2.5)

**Hard Gates Applied**:
- Minimum trades: 200
- Minimum avg_r: +0.15R
- Maximum drawdown: 50R
- Time-split validation: 2/3 periods positive

---

## Results Summary

| Metric | Value |
|--------|-------|
| Candidates tested | 50 |
| Candidates backtested | 50 |
| Candidates skipped | 0 |
| Passed hard gates | **0** |
| Passed stress tests | **0** |
| Final shortlist | **0** |

---

## Performance Distribution

### By ORB Session

| Session | Candidates | Avg R (mean) | Best Avg R | Worst Avg R | Trades (typical) |
|---------|-----------|--------------|------------|-------------|------------------|
| 1800 | 12 | +0.037R | +0.037R | +0.037R | 519 |
| 1000 | 6 | +0.023R | +0.023R | +0.023R | 522 |
| 1100 | 7 | -0.002R | -0.002R | -0.002R | 515 |
| 0900 | 6 | -0.021R | -0.021R | -0.021R | 513 |
| 2300 | 11 | -0.026R | -0.026R | -0.026R | 509 |
| 0030 | 8 | -0.027R | -0.027R | -0.027R | 475 |

**Key Observation**: All candidates within the same ORB session have **identical performance** because they're using the same baseline precomputed outcomes.

---

## Top Performers (by avg_r)

| Rank | ID | Name | ORB | Trades | WR% | Avg R | Total R | Max DD | Status |
|------|----|----|-----|--------|-----|-------|---------|--------|--------|
| 1 | 2-6, 25, 28-29, 35, 38, 43, 46 | 1800 ORB variants (all) | 1800 | 519 | 51.8% | +0.037R | +19R | 17R | FAIL |
| 13-18 | 18, 21-22, 34, 41, 48 | 1000 ORB variants (all) | 1000 | 522 | 51.1% | +0.023R | +12R | 23R | FAIL |
| 19-25 | 15-16, 23-24, 32, 42, 49 | 1100 ORB variants (all) | 1100 | 515 | 49.9% | -0.002R | -1R | 31R | FAIL |
| 26-31 | 17, 19-20, 33, 40, 47 | 0900 ORB variants (all) | 0900 | 513 | 48.9% | -0.021R | -11R | 48R | FAIL |
| 32-42 | 7-10, 26, 30, 36, 39, 44, 50 | 2300 ORB variants (all) | 2300 | 509 | 48.7% | -0.026R | -13R | 37R | FAIL |
| 43-50 | 11-14, 27, 31, 37, 45, 51 | 0030 ORB variants (all) | 0030 | 475 | 48.6% | -0.027R | -13R | 21R | FAIL |

---

## Gate Failures

All 50 candidates failed due to:

1. **Low avg_r** (50/50 candidates failed)
   - Threshold: +0.15R minimum
   - Best actual: +0.037R (1800 ORB)
   - Worst actual: -0.027R (0030 ORB)

2. **Time-split validation** (50/50 candidates failed)
   - Requirement: 2/3 periods positive
   - Actual: 0-1/3 periods positive for all candidates

3. **No failures on**:
   - Minimum trades (all had 200+ trades)
   - Maximum drawdown (all under 50R cap)

---

## Critical Limitation: Baseline Outcomes Only

### The Problem

The backtest used precomputed ORB outcomes from `daily_features_v2` table, which stores **baseline** results for:
- **RR = 2.0** (fixed)
- **SL mode = HALF** (ORB midpoint)
- **No filters applied**

The Phase 2.5 candidates have **varying parameters**:
- RR values: 1.0, 1.5, 2.0, 2.5, 3.0
- SL modes: HALF, FULL
- Filters: Size, directional bias, compression, alignment, sweep+rejection
- Scan windows: Extended (8-10 hours) vs standard (85 minutes)

### Why Results Are Identical

All candidates within the same ORB session (e.g., all 1800 ORB candidates) have **identical results** because:
1. They all query the same `orb_1800_outcome` and `orb_1800_r_multiple` columns
2. Those columns contain baseline outcomes (RR=2.0, no filters)
3. Candidate-specific variations (filters, RR) are not applied

### Impact

The current backtest results represent:
- ✅ **Valid baseline performance** for each ORB session (useful benchmark)
- ❌ **NOT valid testing** of candidate-specific variations

---

## What Would Be Required for Proper Testing

To properly test the Phase 2.5 candidates, a full ORB backtesting engine would need to:

### 1. Load Raw Intraday Data
- Query `bars_1m` table for each trading day
- Convert UTC to local timezone (Brisbane)
- Identify ORB windows (e.g., 18:00-18:05 for 1800 ORB)

### 2. Apply Filters at Decision Time
- **Size filters**: Check if ORB size is within specified range (e.g., 0.2-0.5% of price)
- **Directional bias**: Compute bias signal at decision time (uses production directional_bias.py)
- **Session dependencies**: Check prior session conditions (e.g., compression, expansion)
- **Sweep detection**: Identify if ORB swept prior session high/low

### 3. Detect Entry Signals
- Scan bars within candidate-specific scan window
- Detect first 1m close outside ORB (or alternative entry logic for sweep+rejection)
- Apply candidate-specific confirmations

### 4. Calculate Candidate-Specific Outcomes
- Compute stop price based on candidate SL mode (HALF vs FULL)
- Compute target price based on candidate RR value (1.0-3.0)
- Track bar-by-bar until stop or target hit
- Calculate actual R multiple for this candidate's parameters

### 5. Infrastructure Required
- Timezone-aware bar processing
- ORB calculation from raw bars (not using precomputed values)
- Filter evaluation logic (needs directional_bias.py, session stats)
- Entry/exit simulation with proper slippage assumptions
- Time complexity: ~5-10 minutes per candidate for 5+ years of data

**Estimated Development Time**: 8-12 hours to build + test robust engine

---

## Baseline Performance Findings (Valid)

While candidate variations weren't tested, the baseline ORB performance IS valid and shows:

### Positive Expectancy Sessions
1. **1800 ORB**: +0.037R avg, 51.8% WR, 519 trades
   - Total: +19R over 5 years
   - Annual: ~+4R/year, ~103 trades/year
   - **Finding**: Barely positive, likely not robust to slippage

2. **1000 ORB**: +0.023R avg, 51.1% WR, 522 trades
   - Total: +12R over 5 years
   - Annual: ~+2R/year, ~103 trades/year
   - **Finding**: Very weak edge, high risk of failure under stress

### Negative Expectancy Sessions
3. **1100 ORB**: -0.002R avg, 49.9% WR, 515 trades
   - **Finding**: Breakeven (not usable)

4. **0900 ORB**: -0.021R avg, 48.9% WR, 513 trades
   - **Finding**: Losing baseline (filters might help)

5. **2300 ORB**: -0.026R avg, 48.7% WR, 509 trades
   - **Finding**: Losing baseline (contradicts Phase 2.5 CSV results from Jan 16!)

6. **0030 ORB**: -0.027R avg, 48.6% WR, 475 trades
   - **Finding**: Losing baseline

### Discrepancy with Phase 2 NY Session Results

**CRITICAL**: Phase 2 found:
- 2300 ORB Extended (RR=1.5): +0.403R avg, 56.1% WR (from NIGHT_ORB_2300_half_EXTENDED.csv)
- 0030 ORB Extended (RR=3.0): +0.254R avg, 31.3% WR (from NIGHT_ORB_0030_half_EXTENDED.csv)

**Phase 3 found**:
- 2300 ORB: -0.026R avg, 48.7% WR
- 0030 ORB: -0.027R avg, 48.6% WR

**Possible Causes**:
1. Phase 2 used **extended scan windows** (23:05 → 09:00, ~10 hours)
2. Phase 3 uses baseline outcomes which may have **standard scan windows** (85 minutes)
3. The extended window is CRITICAL to capturing overnight moves
4. daily_features_v2 may store standard-window outcomes, not extended

**Implication**: Extended scan windows are ESSENTIAL for 2300/0030 ORB profitability. Baseline (short window) performance is negative.

---

## Stress Test Results

**Not performed** - No candidates passed hard gates, so stress testing was skipped (as designed).

---

## Output Files

1. **research/phase3_results.csv**
   - 50 rows (one per candidate)
   - Columns: candidate_id, name, orb_time, rr, sl_mode, trades, win_rate, avg_r, total_r, max_dd_r, gate_failures
   - Sorted by avg_r descending

2. **research/phase3_results.md**
   - Summary statistics
   - Top 20 performers table
   - Gate failure details

3. **research/phase3_shortlist.md**
   - Empty (0 survivors)
   - Note explaining why no candidates passed

4. **research/phase3_for_import.json**
   - Empty array (0 survivors)
   - No candidates to promote

---

## Recommendations

### Option 1: Build Proper Backtest Engine (Recommended)

**Action**: Develop full ORB backtesting engine that:
- Calculates ORBs from raw bars_1m
- Applies candidate-specific filters
- Uses candidate-specific RR/SL parameters
- Supports extended scan windows

**Effort**: 8-12 hours development + testing
**Benefit**: Proper validation of all 50 candidates with their actual specifications
**Risk**: May still find 0 survivors if baseline performance is weak

### Option 2: Lower Hard Gates (Quick Test)

**Action**: Rerun Phase 3 with relaxed gates:
- MIN_AVG_R = 0.02 (instead of 0.15)
- TIME_SPLIT_MIN_POSITIVE = 1/3 (instead of 2/3)

**Effort**: 5 minutes (change constants, rerun)
**Benefit**: See if any baseline ORBs would pass relaxed gates
**Risk**: May promote weak edges that fail in live trading

### Option 3: Focus on Known Winners (Pragmatic)

**Action**: Manually test only the edges from Phase 2 that showed strong results:
- 2300 ORB Extended (RR=1.5, extended window)
- 0030 ORB Extended (RR=3.0, extended window)

**Effort**: 2-3 hours (build targeted backtest for these 2 edges)
**Benefit**: Validate proven edges with proper parameters
**Risk**: Ignores 48 other candidates

### Option 4: Accept Baseline Results (Conservative)

**Action**: Use Phase 3 baseline results to conclude:
- Only 1800 and 1000 ORBs have weak positive edges
- Other sessions (0900, 1100, 2300, 0030) have no edge at baseline
- Filters/extended windows may improve, but baseline is weak

**Effort**: 0 (accept current findings)
**Benefit**: Honest assessment based on available data
**Risk**: May miss edges that exist with proper testing

---

## Conclusion

Phase 3 testing successfully:
- ✅ Backtested all 50 candidates
- ✅ Applied hard gates
- ✅ Generated comprehensive results files
- ✅ Identified critical baseline performance metrics

Phase 3 limitations:
- ❌ Did not test candidate-specific variations (RR, filters, windows)
- ❌ Used baseline precomputed outcomes only
- ❌ Cannot validate if Phase 2.5 improvements (filters, extended windows) add value

**Bottom Line**: The infrastructure completed the task as designed, but revealed that proper candidate testing requires a more sophisticated backtesting engine. Current results show baseline ORB performance is weak (only 1800/1000 slightly positive), suggesting most Phase 2.5 candidates will likely fail even with proper testing unless filters/windows add significant value.

---

## Next Steps (DO NOT PERFORM - OUT OF SCOPE)

1. **Decision Required**: Choose one of the 4 options above
2. **If Option 1 chosen**: Build proper backtest engine (8-12 hours)
3. **If Option 2 chosen**: Lower gates and rerun (5 minutes)
4. **If Option 3 chosen**: Focus on 2300/0030 extended winners (2-3 hours)
5. **If Option 4 chosen**: Archive Phase 2.5 candidates, focus on proven edges only

---

**Phase 3 Status**: ✅ COMPLETE
**Deliverables**: All 4 output files generated
**Survivors**: 0 candidates
**Recommendation**: Build proper backtest engine (Option 1) or focus on proven 2300/0030 extended edges (Option 3)

---

**Report Date**: 2026-01-21
**Report Author**: Phase 3 Backtest Runner
