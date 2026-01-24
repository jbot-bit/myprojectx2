# Ready for Promotion - Summary

**Date**: 2026-01-21
**Status**: AWAITING USER DECISION

---

## Edges Ready for Production

Following Phase 2 validation, these edges are ready for promotion to validated_setups:

### 1. 2300 ORB Extended Window

```
Name: MGC 2300 ORB Extended
ORB Time: 2300 (23:00-23:05 Brisbane)
Entry: First 1m close outside ORB
Scan Window: 23:05 → 09:00 (10 hours)
Stop: ORB midpoint (HALF mode)
Target: 1.5R
Filter: None (baseline extended window)

Performance:
- Trades: 522 (2 years) = ~261/year
- Win Rate: 56.1%
- Avg R: +0.403R
- Annual R: ~+105R/year
- Max Risk per Trade: Varies with ORB size

Zero-Lookahead: ✅ COMPLIANT
Data Availability: ✅ CONFIRMED (bars_1m, daily_features_v2)
```

---

### 2. 0030 ORB Extended Window

```
Name: MGC 0030 ORB Extended
ORB Time: 0030 (00:30-00:35 Brisbane)
Entry: First 1m close outside ORB
Scan Window: 00:35 → 09:00 (8.5 hours)
Stop: ORB midpoint (HALF mode)
Target: 3.0R
Filter: None (baseline extended window)

Performance:
- Trades: 475 (2 years) = ~238/year
- Win Rate: 31.3%
- Avg R: +0.254R
- Annual R: ~+60R/year
- Max Risk per Trade: Varies with ORB size

Zero-Lookahead: ✅ COMPLIANT
Data Availability: ✅ CONFIRMED (bars_1m, daily_features_v2)
```

---

## Combined Impact

If both edges promoted:
- **Annual R**: +165R/year combined
- **Annual Trades**: ~499 trades/year combined
- **Sessions Covered**: Late NY futures (2300) + Post-midnight (0030)
- **Diversification**: Overnight holding periods (different from daytime ORBs)

---

## Promotion Workflow

If approved, the promotion process is:

### Step 1: Update validated_setups Database

Run SQL INSERT for each edge:

```sql
-- 2300 ORB Extended
INSERT INTO validated_setups (
    setup_id, instrument, orb_time, rr, sl_mode,
    close_confirmations, buffer_ticks, orb_size_filter,
    atr_filter, min_gap_filter,
    trades, win_rate, avg_r, annual_trades, tier,
    notes, validated_date, data_source
) VALUES (
    'MGC_2300_EXT',
    'MGC',
    '2300',
    1.5,
    'HALF',
    1,
    0.0,
    NULL,  -- No size filter for baseline extended
    NULL,
    NULL,
    522,
    56.1,
    0.403,
    261,
    'A',  -- High performance
    'Extended scan window 23:05→09:00. Phase 2 validated. Overnight compression→Asia expansion.',
    '2026-01-21',
    'Phase2_CSV_Analysis'
);

-- 0030 ORB Extended
INSERT INTO validated_setups (
    setup_id, instrument, orb_time, rr, sl_mode,
    close_confirmations, buffer_ticks, orb_size_filter,
    atr_filter, min_gap_filter,
    trades, win_rate, avg_r, annual_trades, tier,
    notes, validated_date, data_source
) VALUES (
    'MGC_0030_EXT',
    'MGC',
    '0030',
    3.0,
    'HALF',
    1,
    0.0,
    NULL,
    NULL,
    NULL,
    475,
    31.3,
    0.254,
    238,
    'B',  -- Good performance, lower WR
    'Extended scan window 00:35→09:00. Phase 2 validated. Higher RR compensates for lower WR.',
    '2026-01-21',
    'Phase2_CSV_Analysis'
);
```

### Step 2: Update config.py

Add entries to MGC_ORB_SIZE_FILTERS (if size filters used - none for these baseline extended edges):

```python
# In trading_app/config.py
MGC_ORB_SIZE_FILTERS = {
    '0900': 0.05,  # existing
    '1000': 0.05,  # existing
    '1100': 0.05,  # existing
    '1800': None,  # existing
    '2300': None,  # NEW - no filter for extended baseline
    '0030': None,  # NEW - no filter for extended baseline
}
```

**Note**: If size filters are NOT used in config.py, no changes needed here. Just ensure setup_detector.py can load these edges.

### Step 3: Verify Synchronization

```bash
python test_app_sync.py
```

Expected output:
```
ALL TESTS PASSED!

Your apps are now synchronized:
- config.py has MGC filters (6 sessions)
- validated_setups database has 19 setups (8 MGC, 5 NQ, 6 MPL)
- setup_detector.py works with all instruments
- All components load without errors

Your apps are SAFE TO USE!
```

### Step 4: Update Trading Apps

The apps will automatically:
- Load new 2300/0030 setups from validated_setups
- Apply extended scan windows (if setup_detector.py supports extended windows)
- Display in setup lists and dashboards

**CRITICAL**: Verify that setup_detector.py and strategy_engine.py support:
1. Extended scan windows (23:05→09:00, 00:35→09:00)
2. Overnight holding (positions open past midnight)
3. Proper trading day boundaries

If apps don't support extended windows, they'll need code updates before promotion.

---

## Pre-Promotion Checklist

Before promoting, verify:

### Data Availability ✅
- [x] bars_1m table has complete data (2020-12-20 → 2026-01-10)
- [x] daily_features_v2 has 2300/0030 ORB columns
- [x] Timezone handling correct (Brisbane local time)

### App Readiness ⚠️ **NEEDS VERIFICATION**
- [ ] setup_detector.py supports extended scan windows
- [ ] strategy_engine.py handles overnight positions
- [ ] Position management supports multi-day holds
- [ ] EOD processing preserves overnight positions

### Production Safety ✅
- [x] validated_setups schema confirmed
- [x] test_app_sync.py ready to verify
- [x] No accidental modifications to existing setups

### User Approval ⏳
- [ ] User approves 2300 ORB Extended for promotion
- [ ] User approves 0030 ORB Extended for promotion
- [ ] User confirms apps support extended windows

---

## Risks and Considerations

### Risk 1: Extended Window Implementation
**Risk**: Apps may not support extended scan windows (23:05→09:00)
**Mitigation**: Verify setup_detector.py and strategy_engine.py before promotion
**Impact if not supported**: Setups load but don't execute properly

### Risk 2: Overnight Position Holding
**Risk**: Position management may close trades at EOD (before target/stop hit)
**Mitigation**: Verify EOD processing preserves overnight positions
**Impact if not supported**: Premature exits, reduced profitability

### Risk 3: Execution Assumptions
**Risk**: Phase 2 results assume ideal execution (no slippage, no missed entries)
**Mitigation**: Apply conservative slippage assumptions (1-2 ticks entry/exit)
**Impact**: Expected performance degrades by ~0.05-0.10R

### Risk 4: Market Regime Change
**Risk**: Phase 2 results from 2024-2026 data may not hold in different regimes
**Mitigation**: Monitor performance after promotion, kill if avg_r drops below +0.15R
**Impact**: Potential underperformance vs backtested results

---

## Recommendation

**Promote 2300 ORB Extended immediately** (Option B - Conservative):
- Stronger edge (56% WR, +0.403R avg)
- Higher confidence
- ~+105R/year value

**Defer 0030 ORB Extended pending**:
- App capability verification (extended windows, overnight holds)
- Or stress testing (slippage, skip rates)
- Or 1-2 months of live validation with 2300 first

**Rationale**: Get highest-quality edge into production first, validate app infrastructure with one edge before adding second.

---

## Alternative: Stress Test First (Option C)

If user wants additional confidence, run attack harness on Phase 2 results:

### Stress Tests to Apply
1. **Slippage**: Degrade entry/exit by 1-3 ticks
2. **Skip Rate**: Simulate 10-30% missed entries
3. **Stop-First Bias**: Force ambiguous bars to hit stop first
4. **Spread Widening**: Apply 2-4 tick spread costs

### Acceptance Criteria
After stress testing, edges must maintain:
- **avg_r > +0.15R** (minimum viable edge)
- **Combined stress avg_r > 0** (profitable under adversity)

### Effort
- Load Phase 2 trade-by-trade data (from CSV if available)
- Apply attack harness functions (from audits/attack_harness.py)
- Generate stress test report
- **Estimated time**: 1-2 hours

---

## Decision Required

**User must choose**:

1. **Option A**: Promote both edges (2300 + 0030) → +165R/year
2. **Option B**: Promote 2300 only → +105R/year (conservative)
3. **Option C**: Stress test first → 1-2 hours additional work

**If no decision made**: System remains in current state (17 validated setups, 2 provisionally approved edges)

---

## Files for Reference

- `research/PHASE2_SOURCE_OF_TRUTH.md` - Full analysis
- `research/ny_quick_scan/summary_2300.md` - Original 2300 analysis
- `research/ny_quick_scan/summary_0030.md` - Original 0030 analysis
- `research/phase2_rewrites.md` - Edge 2/7 rewrites (different edges)
- `trading_app/config.py` - Config file to update
- `data/db/gold.db` → `validated_setups` table - Database to update
- `test_app_sync.py` - Verification script

---

**Status**: ✅ READY FOR PROMOTION
**Awaiting**: User decision (Option A, B, or C)
**Next Action**: User approval → Execute promotion workflow

---

**Report Date**: 2026-01-21
