# Phase 3 Proper - Critical Findings

**Date**: 2026-01-21
**Status**: ⚠️ CRITICAL DISCREPANCY IDENTIFIED

---

## Executive Summary

Phase 3 backtest completed using the new candidate_backtest_engine.py with proper:
- Raw bars_1m data (not precomputed outcomes)
- Candidate-specific RR, SL mode, scan windows
- Fixed midnight-crossing window logic
- Zero-lookahead compliance

**However, results do NOT match Phase 2 expectations. Major discrepancy identified.**

---

## Results vs Expectations

### 2300 ORB Extended (RR=1.5, HALF SL)

| Source | Trades | Win Rate | Avg R | Notes |
|--------|--------|----------|-------|-------|
| **Expected (Phase 2)** | 522 | 56.1% | **+0.403R** | From validated_setups |
| **Baseline (daily_features_v2)** | 522 | 47.5% | **-0.026R** | RR=2.0, 85min window |
| **Phase 3 Proper (this run)** | 522 | 39.1% | **-0.023R** | RR=1.5, extended window |
| **Phase 4A (buggy)** | - | 15.5% | **-0.612R** | Midnight rollover bug |

### 0030 ORB Extended (RR=3.0, HALF SL)

| Source | Trades | Win Rate | Avg R | Notes |
|--------|--------|----------|-------|-------|
| **Expected (Phase 2)** | 520 | 31.3% | **+0.254R** | From validated_setups |
| **Baseline (daily_features_v2)** | 523 | 44.2% | **-0.027R** | RR=2.0, 85min window |
| **Phase 3 Proper (this run)** | 523 | 20.1% | **-0.170R** | RR=3.0, extended window |
| **Phase 4A (buggy)** | - | 3.5% | **-0.846R** | Midnight rollover bug |

---

## Critical Finding

**The promoted edge metrics (+0.403R, +0.254R) do not match ANY available backtest results:**

1. **Not from baseline precomputed outcomes** - those are NEGATIVE (-0.026R, -0.027R)
2. **Not from my proper backtest** - getting NEGATIVE results (-0.023R, -0.170R)
3. **Not from Phase 4A** - that was catastrophically buggy

**Conclusion: The source of the +0.403R and +0.254R metrics is UNKNOWN.**

---

## Diagnostic Verification

### ORB Calculation Accuracy

Verified that candidate_backtest_engine.py calculates ORBs **EXACTLY** matching daily_features_v2:

```
2300 ORB - 2024-01-02: high=2077.7, low=2075.7, size=2.0 ✓ MATCH
2300 ORB - 2024-01-03: high=2056.0, low=2053.4, size=2.6 ✓ MATCH
0030 ORB - 2024-01-02: high=2077.9, low=2074.2, size=3.7 ✓ MATCH
0030 ORB - 2024-01-03: high=2045.1, low=2042.9, size=2.2 ✓ MATCH
```

**ORB calculations are correct.** Issue must be in entry/exit logic or trade simulation.

---

## ORB Size Filters

Checked filter impact:
- **2300 filter (0.155)**: All 522 days pass (min ORB size = 0.7)
- **0030 filter (0.112)**: All 523 days pass (min ORB size = 0.5)

**Filters are essentially no-ops** - they don't exclude any trades in the dataset.

---

## Phase 3 Full Results

**Tested**: 50 DRAFT candidates
**Total trades across all candidates**: 12,550
**Average trades per candidate**: 251

### Top Performing Candidates

| Rank | Candidate | Trades | WR | Avg R | ORB | RR | SL |
|------|-----------|--------|----|----|-----|----|----|
| 1 | 1800 ORB Extended - RR3.0 | 522 | 28.2% | +0.126R | 1800 | 3.0 | HALF |
| 2 | 1100 ORB + Bias RR3.0 | 523 | 28.1% | +0.124R | 1100 | 3.0 | HALF |
| 3 | 1800 ORB Extended - RR2.0 | 522 | 37.0% | +0.109R | 1800 | 2.0 | HALF |
| 4 | 1800 ORB Extended - RR1.5 | 522 | 43.3% | +0.082R | 1800 | 1.5 | HALF |
| 5 | 1100 ORB + Directional Bias | 523 | 35.6% | +0.067R | 1100 | 2.0 | HALF |

### Expected "Winners" (Based on validated_setups)

| Candidate | Expected | Actual | Delta |
|-----------|----------|--------|-------|
| 2300 ORB Extended - RR1.5 | +0.403R | **-0.023R** | -0.426R ❌ |
| 0030 ORB Extended - RR3.0 | +0.254R | **-0.170R** | -0.424R ❌ |

**Both expected winners FAILED in Phase 3 proper backtest.**

---

## Possible Explanations

### 1. Different Entry Logic

Phase 2 might have used different entry detection:
- Different confirmation rules?
- Different close vs high/low logic?
- Different scan window boundaries?

### 2. Different Exit Logic

Phase 2 might have used different exit simulation:
- Different TP/SL intra-bar ordering?
- Different time-exit rules?
- Different max hold periods?

### 3. Different Data Range

Phase 2 might have used:
- Different date range (not 2024-01-02 to 2026-01-10)?
- Different data source?
- Different timezone handling?

### 4. Manual Adjustments

The +0.403R and +0.254R values might have been:
- Manually entered estimates?
- From a different analysis tool?
- From selective period testing?

### 5. Implementation Bug in My Code

Despite ORB calculations matching, there could be a bug in:
- Entry detection (detect_breakout_entry)
- Trade simulation (simulate_trade)
- Risk/target calculation

---

## What Works Correctly

✅ ORB calculations match daily_features_v2 exactly
✅ Midnight-crossing window logic fixed (0030 now finds trades)
✅ Candidate-specific RR values applied
✅ Zero-lookahead compliance enforced
✅ Different candidates produce different results (not collapsed)

---

## What Doesn't Work

❌ 2300 Extended results don't match Phase 2 expectations (-0.426R delta)
❌ 0030 Extended results don't match Phase 2 expectations (-0.424R delta)
❌ No positive avg_r candidates that pass min_trades >= 200 gate
❌ Cannot reproduce the metrics in validated_setups

---

## Recommended Next Steps

### Option 1: Investigate Phase 2 Methodology

- Find the actual Phase 2 backtest script/code
- Determine what methodology produced +0.403R / +0.254R
- Reverse engineer the logic

### Option 2: Debug Current Implementation

- Add detailed trade-by-trade logging
- Compare specific trades against expected outcomes
- Identify where divergence occurs

### Option 3: Accept Current Results

- Acknowledge that Phase 2 metrics cannot be reproduced
- Use Phase 3 proper results as new baseline
- Re-evaluate edge viability based on -0.023R / -0.170R

### Option 4: Query Data Source

- Check if there's documentation about how validated_setups was populated
- Look for Phase 2 CSV files or analysis notes
- Confirm the +0.403R / +0.254R values are trustworthy

---

## Critical Questions

1. **Where did the +0.403R and +0.254R metrics originate?**
   - Not from daily_features_v2 precomputed outcomes
   - Not from any backtest I can reproduce

2. **Are the promoted edges actually profitable?**
   - My backtest shows NEGATIVE expectancy
   - Baseline precomputed shows NEGATIVE expectancy
   - Only the unverifiable "Phase 2" shows POSITIVE

3. **Should we trust validated_setups metrics?**
   - No reproducible source found
   - Major discrepancy with all backtest methods

4. **What is the correct backtest methodology?**
   - Need to establish ground truth for entry/exit rules
   - Need to verify against manual trade replay

---

## Data Files

- `phase3_proper_results.csv`: Full results for all 50 candidates
- `diagnose_orb_calculation.py`: ORB calculation verification script
- `candidate_backtest_engine.py`: New backtest engine (v1)
- `run_phase3_proper.py`: Phase 3 runner script

---

## Status

**BLOCKED**: Cannot proceed with promotion or Phase 4 until discrepancy is resolved.

**Required**: Determine source of +0.403R / +0.254R metrics or accept that they are not reproducible.

---

**Report Date**: 2026-01-21
**Phase**: 3 Proper (Fixed Backtest Engine)
**Outcome**: ⚠️ CRITICAL DISCREPANCY - Expected metrics not reproducible
