# PRODUCTION READINESS CHECKLIST
**MGC Live Edge Identification System**
**Date**: 2026-01-24
**Status**: ⚠️ CONDITIONAL GO - CRITICAL ACTIONS REQUIRED

---

## EXECUTIVE SUMMARY

Your system has **strong foundations** with zero-lookahead architecture, proper timezone handling, and 9 verified profitable edges. However, before going live, you must complete **4 critical validation steps** to ensure the system is bulletproof.

**Current State**:
- ✅ 21/24 tests passing (3 skipped - expected)
- ✅ Database/config synchronization verified
- ✅ Timezone handling validated (Brisbane UTC+10)
- ✅ 9 verified edges discovered (77%+ WR on elite setups)
- ⚠️ Missing: Out-of-sample validation + commission modeling

---

## QUICK STATUS CHECK

Run this to verify system health:

```bash
# 1. Test synchronization (CRITICAL)
python test_app_sync.py

# 2. Run temporal integrity tests
python -m pytest tests/test_temporal_integrity.py -v

# 3. Run edge case tests
python -m pytest tests/test_edge_cases.py -v

# 4. Run determinism tests
python -m pytest tests/test_determinism.py -v

# 5. Validate timezone handling
python scripts/timestamp_probe.py 2025-06-15
```

**Expected**: All tests PASS, all validation checks PASS

---

## CRITICAL BLOCKERS (Must Fix Before Live Trading)

### ✅ BLOCKER #1: Database/Config Sync - RESOLVED
**Status**: PASS (2026-01-24)

```
[PASS] ALL TESTS PASSED!
Your apps are now synchronized:
  - config.py matches validated_setups database (55 setups)
  - setup_detector.py works with all instruments
  - All components load without errors
```

**Evidence**: `test_app_sync.py` passes successfully

---

### ✅ BLOCKER #2: Temporal Integrity Tests - RESOLVED
**Status**: PASS (2026-01-24)

**Tests Created**:
- `tests/test_temporal_integrity.py` (6 tests + 1 skip)
  - ✅ AEST winter timezone handling
  - ✅ US DST start (March) - no offset errors
  - ✅ US DST end (November) - no offset errors
  - ✅ Midnight crossing (23:00→00:30)
  - ✅ All 6 ORB alignment
  - [Skipped: Requires actual bar data]

**Validation Script**:
- `scripts/timestamp_probe.py` - Validates ORB alignment on actual data
- All 4 validation checks PASS on 2025-06-15 data

**Evidence**:
```
[OK] PASS: Brisbane timezone is UTC+10 (no DST)
[OK] PASS: 09:00 Brisbane = 23:00 UTC (previous day)
[OK] PASS: All 6 ORBs are exactly 5 minutes duration
[OK] PASS: NY session (23:00->00:30) spans 90 minutes
```

---

### ✅ BLOCKER #3: Edge Case Tests - RESOLVED
**Status**: PASS (2026-01-24)

**Tests Created**:
- `tests/test_edge_cases.py` (8 tests + 2 skip)
  - ✅ Missing bars in ORB window handled
  - ✅ Completely missing ORB window (holidays)
  - ✅ Duplicate timestamps rejected by database
  - ✅ Out-of-order bars handled correctly
  - ✅ Weekend (no data) handled gracefully
  - ✅ DST boundary day - no offset errors
  - ✅ ORB window with gap in middle
  - ✅ Partial trading day (early close)

**Result**: System handles edge cases gracefully (returns None, no crashes)

---

### ❌ BLOCKER #4: Out-of-Sample Validation - NOT IMPLEMENTED

**Status**: CRITICAL - Must complete before live trading

**Required**:
1. **Define Research Cutoff Date**
   - Recommendation: 2025-12-31
   - Lock ALL parameters before this date
   - No optimization on data after cutoff

2. **Split Data**
   - In-Sample: 2024-01-01 → 2025-12-31 (parameter development)
   - Out-of-Sample: 2026-01-01 → present (validation only)

3. **Generate Metrics Report**
   ```
   === PROFITABILITY REPORT ===
   Research Cutoff: 2025-12-31 (LOCKED)

   IN-SAMPLE (2024-01-01 to 2025-12-31):
     Trades: XXX
     Win Rate: XX%
     Avg R: X.XX
     Max DD: XX R
     Worst Streak: X

   OUT-OF-SAMPLE (2026-01-01 to present):
     Trades: XX
     Win Rate: XX%
     Avg R: X.XX
     Max DD: XX R
     Worst Streak: X
   ```

4. **Acceptance Criteria**
   - Out-of-sample WR within ±10% of in-sample
   - Out-of-sample Avg R within ±20% of in-sample
   - No catastrophic drawdowns (>5R) in OOS period
   - Edge still exists (OOS > random)

**Action**: Create `scripts/generate_oos_validation.py`

---

## MAJOR ISSUES (Fix Before Live)

### ❌ ISSUE #1: No Commission/Slippage Modeling

**Status**: NOT IMPLEMENTED

**Impact**: Backtest results are INFLATED (transaction costs not included)

**Reality Check**:
- MGC tick value: $0.10
- Commission: ~$2 round-trip
- Slippage: ~0.5 ticks ($0.05 per fill)
- Total cost: ~$2.10 per round-trip

**Example Impact**:
- Setup with 2.5-tick (0.25 point) risk = $2.50 risk
- Cost of $2.10 = **84% of risk!**
- Gross R=+1.0 → Net R=+0.16 (tiny edge)
- Gross R=+2.0 → Net R=+1.16 (still profitable)

**Required Fix**:

Add to `pipeline/build_daily_features_v2.py`:

```python
# Near top of file (after imports)
COMMISSION_RT = 2.0  # $2 round-trip commission
SLIPPAGE_TICKS = 0.5  # 0.5 ticks average slippage
TICK_VALUE = 0.10  # MGC tick value

def apply_costs(gross_r: float, risk_ticks: float) -> float:
    """Apply commission and slippage to R multiple."""
    if risk_ticks == 0:
        return gross_r

    # Total cost in dollars
    cost_dollars = COMMISSION_RT + (SLIPPAGE_TICKS * TICK_VALUE * 2)  # entry + exit

    # Risk in dollars
    risk_dollars = risk_ticks * TICK_VALUE

    # Cost in R terms
    cost_in_r = cost_dollars / risk_dollars

    return gross_r - cost_in_r

# In calculate_orb_1m_exec(), after computing outcome:
if outcome == "WIN":
    r_multiple_gross = rr
elif outcome == "LOSS":
    r_multiple_gross = -1.0
else:
    r_multiple_gross = 0.0

# Apply costs
r_multiple = apply_costs(r_multiple_gross, risk_ticks)
```

**Then re-run**:
```bash
python build_daily_features_v2.py 2024-01-01 2026-01-10
```

**Priority**: HIGH (must have for accurate profitability)

---

### ⚠️ ISSUE #2: Mixed Timezone Libraries (pytz vs zoneinfo)

**Status**: MINOR - Quality improvement

**Files Using pytz** (legacy):
- `trading_app/backtest/engine.py:18` - `import pytz`

**Files Using zoneinfo** (modern):
- `pipeline/build_daily_features_v2.py` - `from zoneinfo import ZoneInfo` ✅
- `tests/test_temporal_integrity.py` - zoneinfo ✅
- `trading_app/config.py` - zoneinfo ✅

**Action**: Migrate `backtest/engine.py` to zoneinfo

**Priority**: MEDIUM (works fine, but cleaner to standardize)

---

## VERIFIED COMPONENTS ✅

### Data Pipeline
- ✅ Backfill scripts (Databento + ProjectX)
- ✅ Feature builder (build_daily_features_v2.py - 100% verified)
- ✅ 5-minute aggregation (deterministic)
- ✅ Contract selection (highest volume, excludes spreads)
- ✅ Idempotent operations (safe to re-run)

### Database
- ✅ Schema validated (35 tables)
- ✅ UTC storage (TIMESTAMPTZ)
- ✅ daily_features_v2 canonical (740 rows MGC)
- ✅ validated_setups (55 setups total: 44 MGC, 5 NQ, 6 MPL)
- ✅ Multi-instrument support (MGC, NQ, MPL)
- ✅ Zero-lookahead architecture (features ≠ outcomes)

### Trading Apps
- ✅ app_trading_hub.py (main production app)
- ✅ app_mobile.py (Streamlit Cloud deployed)
- ✅ MGC_NOW.py (quick helper)
- ✅ Strategy engine (5 strategies, priority-ordered)
- ✅ AI assistant (Claude Sonnet 4.5)
- ✅ Position tracker + risk manager

### Edge Discovery
- ✅ 9 verified edges (2 TIER S, 4 TIER 1, 3 TIER 2)
- ✅ Elite setup: 77.1% WR, +0.543R (70 trades)
- ✅ Direction alignment: 63% vs 33% (+30% edge)
- ✅ Implementation proposal ready (Edge #1)

### Testing
- ✅ 21/24 tests passing (3 skipped - expected)
- ✅ Temporal integrity validated
- ✅ Edge cases handled
- ✅ Determinism confirmed
- ✅ 38-test audit framework (separate from pytest)

---

## APPROVAL GATES

### Gate 1: Paper Trading Approval ⚠️

**Requirements**:
- [x] ✅ Database/config synchronization validated
- [x] ✅ Temporal integrity tests passing
- [x] ✅ Edge case tests passing
- [x] ✅ Determinism validated
- [ ] ❌ Commission/slippage modeling added
- [ ] ❌ Feature builder re-run with costs

**Status**: 4/6 COMPLETE - **Need commission modeling**

**Timeline**: 2-4 hours work

**Approval**: ⚠️ NOT READY - Complete commission modeling first

---

### Gate 2: Live Trading Approval ❌

**Requirements**:
- [ ] Paper trading approval granted
- [ ] Out-of-sample validation complete
- [ ] Research cutoff date documented
- [ ] In-sample vs OOS metrics match (within tolerance)
- [ ] Edge still exists in OOS data
- [ ] User acceptance testing complete
- [ ] Risk limits configured
- [ ] Emergency stop procedures documented

**Status**: 0/8 COMPLETE

**Timeline**: 2-3 days work after Gate 1

**Approval**: ❌ NOT READY - Complete Gate 1 first

---

## IMMEDIATE ACTION PLAN

### Today (2-4 hours)

**Task 1: Add Commission/Slippage Modeling**

1. Edit `pipeline/build_daily_features_v2.py`
2. Add cost constants and `apply_costs()` function
3. Apply costs to R calculations in `calculate_orb_1m_exec()`
4. Test on single day: `python build_daily_features_v2.py 2025-06-15`
5. Verify results make sense (R multiples slightly reduced)

**Task 2: Re-run Feature Builder with Costs**

```bash
python build_daily_features_v2.py 2024-01-01 2026-01-10
```

**Task 3: Validate Results**

```bash
python query_features.py  # Check R multiples look reasonable
python check_db.py        # Verify data integrity
```

**Checkpoint**: Gate 1 requirements complete → PAPER TRADING APPROVED ✅

---

### This Week (2-3 days)

**Task 4: Define Research Cutoff**

1. Review validated_setups table: When were parameters finalized?
2. Set cutoff date (recommend: 2025-12-31)
3. Document: "NO parameters changed after 2025-12-31"

**Task 5: Create OOS Validation Script**

File: `scripts/generate_oos_validation.py`

```python
"""
Out-of-Sample Validation Report Generator

Splits data at research cutoff and compares in-sample vs out-of-sample metrics.
"""

RESEARCH_CUTOFF = "2025-12-31"  # LOCKED - do not change

# Query daily_features_v2 split by date
# Generate metrics for each split
# Compare and report
```

**Task 6: Generate OOS Report**

```bash
python scripts/generate_oos_validation.py > OOS_VALIDATION_REPORT.md
```

**Task 7: Review OOS Results**

- Are OOS metrics within acceptable range?
- Does the edge still exist?
- Any red flags?

**Checkpoint**: Gate 2 requirements complete → LIVE TRADING APPROVED ✅

---

## RISK ASSESSMENT

### Current Risk Level: ⚠️ MEDIUM

**Strengths** (High Confidence):
- ✅ Zero-lookahead architecture verified
- ✅ Proper timezone handling (Brisbane UTC+10)
- ✅ 9 verified edges with statistical support
- ✅ Conservative execution model (close-based entry)
- ✅ Guardrail assertions prevent lookahead
- ✅ 21/24 tests passing
- ✅ Clean database schema

**Weaknesses** (Must Address):
- ❌ No commission modeling → inflated results
- ❌ No OOS validation → overfitting risk unknown
- ⚠️ Only 740 days of data → small sample for some setups

**Mitigation**:
1. Add commission modeling (TODAY)
2. Complete OOS validation (THIS WEEK)
3. Start with smallest position size (1 micro contract)
4. Paper trade for 30 days minimum
5. Verify edge holds in real-time

---

## SUCCESS CRITERIA

### Paper Trading (30 days minimum)

**Metrics to Track**:
- Setup detection accuracy (all setups found correctly)
- Entry timing accuracy (entries at correct prices)
- Exit timing accuracy (stops/targets hit as expected)
- System uptime (no crashes, no missed setups)
- Data quality (no missing bars, no gaps)

**Acceptance**: All metrics within expected ranges

---

### Live Trading (After Paper Trading)

**Start Small**:
- 1 micro contract (MGC) only
- Best setup only (Elite: 77% WR)
- Max 1 trade per day
- Hard stop loss always in place

**Scale Up**:
- After 20 successful trades → 2 contracts
- After 50 successful trades → 3 contracts
- After 100 successful trades → Review risk limits

---

## DOCUMENTATION

**Authority**: `CLAUDE.md` (single source of truth)

**Audit Reports**:
- `ORB_INSTITUTIONAL_AUDIT_REPORT.md` (2026-01-24)
- `DAILY_FEATURES_AUDIT_REPORT.md` (2026-01-22)
- `PRODUCTION_READINESS_CHECKLIST.md` (this file)

**Research**:
- `research/LEGITIMATE_EDGES_CATALOG.md` (9 verified edges)
- `research/RESEARCH_SESSION_COMPLETE_2026-01-24.md`
- `research/IMPLEMENTATION_PROPOSAL_DIRECTION_ALIGNMENT.md`

**Tests**:
- `tests/test_temporal_integrity.py`
- `tests/test_edge_cases.py`
- `tests/test_determinism.py`
- `scripts/timestamp_probe.py`

---

## CONTACT & SUPPORT

**Quick Health Check**:
```bash
python test_app_sync.py  # Should say "SAFE TO USE"
```

**If Issues**:
1. Check `CLAUDE.md` for guidance
2. Review audit reports for details
3. Run specific tests to isolate problem

**Emergency Stop**:
- Close all positions
- Stop all apps
- Review logs and database state
- Do NOT resume until issue understood

---

## FINAL VERDICT

**Safe to Trade?** ⚠️ **NOT YET - 2 BLOCKERS REMAIN**

**Blockers**:
1. ❌ Commission/slippage modeling not added
2. ❌ Out-of-sample validation not complete

**Timeline to Approval**:
- Gate 1 (Paper Trading): 2-4 hours (add costs, re-run features)
- Gate 2 (Live Trading): 2-3 days (OOS validation)

**After completing both gates**: ✅ **APPROVED FOR LIVE TRADING WITH POSITION LIMITS**

---

**Last Updated**: 2026-01-24
**Next Review**: After commission modeling complete
**Auditor**: Claude Sonnet 4.5
