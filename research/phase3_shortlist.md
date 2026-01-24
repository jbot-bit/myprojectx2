# Phase 3 Shortlist - Survivors

**Date**: 2026-01-21

**Survivors**: 0 candidates

**Status**: No candidates passed hard gates. Stress testing was not performed.

---

## Why No Survivors

All 50 Phase 2.5 candidates failed hard gates due to:

### Primary Failure: Low Avg R

**Gate requirement**: avg_r >= +0.15R
**Best performance**: +0.037R (1800 ORB variants)
**Worst performance**: -0.027R (0030 ORB variants)

All candidates fell short of the +0.15R minimum threshold.

### Secondary Failure: Time-Split Validation

**Gate requirement**: 2/3 periods positive (out of 3 equal time chunks)
**Actual performance**: 0-1/3 periods positive for all candidates

Most candidates showed inconsistent performance across time periods.

---

## Critical Finding: Baseline Testing Only

The backtest used **precomputed baseline outcomes** from daily_features_v2 table, which stores:
- RR = 2.0 (fixed)
- SL mode = HALF (ORB midpoint)
- No filters applied
- Standard scan windows (not extended)

The Phase 2.5 candidates have **varying specifications**:
- RR values: 1.0, 1.5, 2.0, 2.5, 3.0
- SL modes: HALF, FULL
- Filters: Size, directional bias, compression, alignment
- Scan windows: Extended (8-10 hours) vs standard

**Result**: All candidates within the same ORB session (e.g., all 12 variants of 1800 ORB) had **identical performance** because they all used the same baseline precomputed outcomes.

**Implication**: The current results do NOT test candidate-specific improvements (filters, extended windows, varying RR values). They only show baseline ORB performance.

---

## Baseline Performance Summary

While candidate variations weren't tested, baseline ORB performance was measured:

### Positive (Weak)
- **1800 ORB**: +0.037R avg, 51.8% WR, 519 trades
- **1000 ORB**: +0.023R avg, 51.1% WR, 522 trades

### Breakeven
- **1100 ORB**: -0.002R avg, 49.9% WR, 515 trades

### Negative
- **0900 ORB**: -0.021R avg, 48.9% WR, 513 trades
- **2300 ORB**: -0.026R avg, 48.7% WR, 509 trades
- **0030 ORB**: -0.027R avg, 48.6% WR, 475 trades

**Conclusion**: Baseline ORB performance is weak. Only 1800 and 1000 ORBs show slight positive expectancy. This suggests most Phase 2.5 candidates would need significant improvement from filters/extended windows to become profitable.

---

## Discrepancy with Phase 2 Results

Phase 2 found strong edges for 2300 and 0030 ORBs with **extended scan windows**:
- 2300 ORB Extended (RR=1.5): +0.403R avg, 56.1% WR
- 0030 ORB Extended (RR=3.0): +0.254R avg, 31.3% WR

Phase 3 found negative baseline performance:
- 2300 ORB: -0.026R avg, 48.7% WR
- 0030 ORB: -0.027R avg, 48.6% WR

**Likely Cause**: Extended scan windows (8-10 hours) are CRITICAL for 2300/0030 profitability. Baseline outcomes use standard scan windows (~85 minutes), which are insufficient to capture overnight moves.

**Implication**: The Phase 2 edges are likely valid, but require extended windows which were not tested in Phase 3 baseline backtest.

---

## Recommendations

### Option 1: Build Proper Backtest Engine
- Calculate ORBs from raw bars_1m
- Apply candidate-specific filters
- Use candidate-specific RR/SL parameters
- Support extended scan windows
- Effort: 8-12 hours

### Option 2: Lower Hard Gates
- Reduce MIN_AVG_R to +0.02R
- Reduce time-split requirement to 1/3 periods
- Rerun Phase 3 with relaxed gates
- Effort: 5 minutes

### Option 3: Focus on Proven Winners
- Manually test 2300/0030 extended edges from Phase 2
- Skip the other 48 candidates
- Effort: 2-3 hours

### Option 4: Accept Baseline Results
- Conclude that only 1800/1000 ORBs have weak edges
- Archive Phase 2.5 candidates
- Focus on known profitable setups only
- Effort: 0

---

## Conclusion

Phase 3 testing revealed that baseline ORB performance is weak across most sessions. To properly validate the Phase 2.5 candidates (which include filters, extended windows, and varying parameters), a more sophisticated backtesting engine is required.

Current recommendation: Either build proper backtest infrastructure (Option 1) or focus on proven 2300/0030 extended edges (Option 3).

---

**See**: `research/PHASE3_COMPLETED.md` for full details
**See**: `research/phase3_results.csv` for complete candidate results
