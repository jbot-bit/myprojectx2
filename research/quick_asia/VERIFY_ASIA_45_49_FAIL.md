# VERIFY ASIA CANDIDATES 45-49: FAIL REPORT

**Date**: 2026-01-21
**Status**: VERIFICATION FAILED - INCORRECT METRICS IN DATABASE
**Root Cause**: Metrics transcription error during import

---

## EXECUTIVE SUMMARY

Verification FAILED for candidates 45, 46, 48, and 49 due to **win_rate mismatch**.
However, investigation reveals that **my backtest reproduction is 100% CORRECT** and matches the original `asia_results_365d.csv` exactly.

**The problem**: Incorrect win_rate values were imported into edge_candidates (MotherDuck database) and specified in test16.txt target metrics.

---

## VERIFICATION RESULTS

| Candidate | Config | Computed WR | Target WR | CSV WR | Status |
|-----------|--------|-------------|-----------|--------|--------|
| 45 | 0900 RR2.0 HALF | 0.378 | 0.465 ❌ | 0.378 ✅ | **MISMATCH** |
| 46 | 0900 RR3.0 HALF | 0.299 | 0.382 ❌ | 0.299 ✅ | **MISMATCH** |
| 47 | 1000 RR1.0 FULL | 0.529 | 0.528 ✅ | 0.529 ✅ | **PASS** |
| 48 | 1000 RR2.0 HALF | 0.354 | 0.389 ❌ | 0.354 ✅ | **MISMATCH** |
| 49 | 1000 RR1.5 FULL | 0.444 | 0.493 ❌ | 0.444 ✅ | **MISMATCH** |

**Key**:
- **Computed WR** = My backtest reproduction
- **Target WR** = test16.txt / MotherDuck metrics
- **CSV WR** = Original `asia_results_365d.csv` results

---

## ROOT CAUSE ANALYSIS

### Source of Truth

The **correct metrics** are in:
```
research/quick_asia/research/quick_asia/asia_results_365d.csv
```

CSV excerpt (relevant rows):
```
orb_time,rr,sl_mode,mode,trades,win_rate,avg_r,total_r
0900,2.0,HALF,ISOLATION,254,0.377953,0.099302,25.222744
0900,3.0,HALF,ISOLATION,254,0.299213,0.096840,24.597322
1000,1.0,FULL,ISOLATION,257,0.529183,0.055065,14.151809
1000,2.0,HALF,ISOLATION,257,0.354086,0.053564,13.766069
1000,1.5,FULL,ISOLATION,257,0.443580,0.083578,21.479465
```

### Where The Error Occurred

When creating `research/asia_candidates_for_import.json`, win_rate values were **incorrectly transcribed**:

**Candidate 45 (0900 RR2.0 HALF)**:
- CSV: `win_rate=0.377953` (37.8%)
- JSON: `win_rate=0.465` (46.5%) ❌ WRONG
- Discrepancy: +0.087 (8.7 percentage points)

**Candidate 46 (0900 RR3.0 HALF)**:
- CSV: `win_rate=0.299213` (29.9%)
- JSON: `win_rate=0.382` (38.2%) ❌ WRONG
- Discrepancy: +0.083 (8.3 percentage points)

**Candidate 48 (1000 RR2.0 HALF)**:
- CSV: `win_rate=0.354086` (35.4%)
- JSON: `win_rate=0.389` (38.9%) ❌ WRONG
- Discrepancy: +0.035 (3.5 percentage points)

**Candidate 49 (1000 RR1.5 FULL)**:
- CSV: `win_rate=0.443580` (44.4%)
- JSON: `win_rate=0.493` (49.3%) ❌ WRONG
- Discrepancy: +0.050 (5.0 percentage points)

### Why Other Metrics Match

- **trades**: Matches exactly (copied correctly)
- **avg_r**: Matches within tolerance (copied correctly)
- **total_r**: Matches within tolerance (copied correctly)
- **win_rate**: WRONG (transcription error)

---

## IMPACT ANALYSIS

### Database State

**MotherDuck edge_candidates (IDs 45-49)** contains incorrect win_rate values:
- These were imported from `research/asia_candidates_for_import.json`
- The JSON file contains transcription errors from the source CSV
- Currently stored metrics are **MISLEADING**

### Consequences

1. **Misleading Performance**: Win rates appear 3-9% higher than actual
2. **Incorrect Risk Assessment**: Higher WR suggests more stable edges than reality
3. **Portfolio Decisions**: May lead to over-allocation or incorrect prioritization
4. **Production Risk**: If promoted with wrong metrics, traders will have false expectations

---

## CORRECTIVE ACTIONS REQUIRED

### Immediate (Before Promotion)

1. **Update `research/asia_candidates_for_import.json`** with correct win_rates from CSV:
   - Candidate 45: `0.378` (not 0.465)
   - Candidate 46: `0.299` (not 0.382)
   - Candidate 48: `0.354` (not 0.389)
   - Candidate 49: `0.444` (not 0.493)

2. **Update MotherDuck edge_candidates** metrics_json for IDs 45-49:
   ```sql
   UPDATE edge_candidates
   SET metrics_json = '<corrected_json>'
   WHERE candidate_id IN (45, 46, 48, 49);
   ```

3. **Re-run verification**: After fixing, run `verify_asia_candidates_45_49_backtest.py` again

### Test16.txt Update

Update target metrics in test16.txt to match CSV:
```python
TARGET_METRICS = {
    45: {"trades": 254, "win_rate": 0.378, "avg_r": 0.099, "total_r": 25.2},  # Was 0.465
    46: {"trades": 254, "win_rate": 0.299, "avg_r": 0.097, "total_r": 24.6},  # Was 0.382
    47: {"trades": 257, "win_rate": 0.529, "avg_r": 0.055, "total_r": 14.2},  # OK
    48: {"trades": 257, "win_rate": 0.354, "avg_r": 0.054, "total_r": 13.8},  # Was 0.389
    49: {"trades": 257, "win_rate": 0.444, "avg_r": 0.084, "total_r": 21.5},  # Was 0.493
}
```

---

## BACKTEST ENGINE VALIDATION

**My backtest reproduction is CORRECT and DETERMINISTIC**:

✅ Matches original `asia_results_365d.csv` exactly (5/5 configs)
✅ Trades count matches (254/257 as expected)
✅ Avg R matches within 0.001R
✅ Total R matches within 0.1R
✅ Win rate matches within 0.001 (when compared to CSV, not incorrect JSON)

**Engine used**: `research/quick_asia/asia_backtest_core.py`
**Data source**: Local `data/db/gold.db` (bars_1m)
**Date range**: 2025-01-11 to 2026-01-10 (365 trading days)

---

## RECOMMENDATIONS

### DO NOT PROCEED with current database state

The candidates 45-49 in MotherDuck have **incorrect performance metrics** and should NOT be approved/promoted until corrected.

### Required Before Approval

1. Fix win_rate values in MotherDuck edge_candidates
2. Re-run verification to confirm PASS
3. Update ASIA_READY_FOR_REVIEW.md with correct metrics
4. Only then proceed with approval/promotion workflow

### Long-term Prevention

- **Automated import validation**: Add checks to compare JSON vs source CSV
- **Verification step**: Always run backtest verification before import
- **Double-check transcription**: Manual review of performance metrics during import

---

## CONCLUSION

**Verification Status**: FAIL (due to incorrect database metrics, not backtest error)
**Backtest Quality**: PASS (100% match with original CSV)
**Next Step**: Fix metrics in database, then re-verify

**DO NOT APPROVE OR PROMOTE** any candidates until metrics are corrected.

---

**Report Generated**: 2026-01-21
**Author**: Claude (verification backtest)
**Contact**: Review `research/quick_asia/VERIFY_ASIA_45_49.md` for detailed comparison
