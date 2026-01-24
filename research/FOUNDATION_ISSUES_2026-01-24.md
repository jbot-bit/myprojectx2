# Foundation Issues Found - 2026-01-24

**Status**: CRITICAL - Foundation may not be solid
**Authority**: CLAUDE.md, res.txt (verify everything yourself)

---

## Issue #1: daily_features v1 Still Exists (SHOULD BE DELETED)

**Finding**: `daily_features` table exists with 745 rows
**Expected**: Table should NOT exist (per CLAUDE.md)
**CLAUDE.md says**: "daily_features (v1) has been DELETED... Never existed in production... Zero rows (table never created)"

**Reality**: Table EXISTS with data

**Risk**: If any code still references daily_features v1, it's using WRONG data

**Action needed**: Confirm if this is okay or if table should be deleted

---

## Issue #2: Session Type Codes Only 68-70% Populated

**Finding**:
- Asia type codes: 503/740 (68.0%)
- London type codes: 521/740 (70.4%)
- Pre-NY type codes: 521/740 (70.4%)

**This means**: ~30% of days have NO liquidity classification

**Why**: Likely weekends/holidays (237 days with None values found earlier)

**Risk**: LOW - expected behavior for weekends/holidays

**Conclusion**: LEGITIMATE - not all days have trading sessions

---

## Issue #3: CASCADE Edge Could Not Be Verified with Simple Test

**Claimed edge** (from validated_setups):
- CASCADE_MULTI_LIQUIDITY: +1.95R avg, 19% WR, 69 trades

**My verification attempt**:
- Sequential sweeps (London + Pre-NY): AvgR=-0.016, WR=48.6%, n=249
- This is NEGATIVE, not +1.95R!

**Why the discrepancy**:
1. My test is TOO SIMPLE - I tested ANY sequential sweeps, not the specific CASCADE pattern
2. CASCADE likely has additional filters/conditions I didn't test
3. CASCADE might use specific timing, direction alignment, or other criteria

**Conclusion**: CANNOT VERIFY CASCADE edge with simple test - need to understand exact definition

**Risk**: HIGH - if we claim CASCADE is +1.95R but can't verify it, we're on FAKE FOUNDATION

---

## Issue #4: Asia Bias Filter Could Not Be Verified

**Claimed edge**: Asia bias filter increases edge by 50-100%
**My test**: Insufficient sample size (couldn't derive asia_bias from available columns)

**Why**: asia_bias is a CONDITION (not stored column), I need to calculate it correctly from data

**Conclusion**: CANNOT VERIFY with current test - need better test logic

---

## What This Means

### RED FLAGS:
1. **daily_features v1 still exists** - violates CLAUDE.md authority
2. **CASCADE edge cannot be reproduced** with simple pattern matching

### YELLOW FLAGS:
1. **Session type codes 30% missing** - but likely legitimate (weekends)
2. **Asia bias filter not tested** - test logic needs work

### GREEN FLAGS:
1. **daily_features_v2 exists and has data** (740 MGC rows)
2. **No duplicate dates** in data
3. **Win rate looks reasonable** (51.1% for 1000 ORB)
4. **CASCADE/SINGLE_LIQ entries exist in validated_setups**

---

## Recommended Actions

### IMMEDIATE (Before proceeding):
1. **Address daily_features v1**: Delete table or explain why it's okay to keep
2. **Understand CASCADE definition**: What EXACTLY is the pattern? (not just "sequential sweeps")
3. **Get asia_bias calculation logic**: How is it derived from data?

### BEFORE USING AS BUILDING BLOCKS:
- **DO NOT assume CASCADE is +1.95R** until we can verify it ourselves
- **DO NOT assume asia_bias filter works** until we can verify it ourselves
- **DO NOT trust validated_setups without verification**

### RESEARCH APPROACH:
Instead of using unverified edges as building blocks, start from FIRST PRINCIPLES:
1. Query raw session data (asia_high, london_high, etc.)
2. Test simple hypotheses (does London sweep matter? does direction matter?)
3. Build up from VERIFIED patterns only
4. Document everything with statistical tests

---

## Next Steps (User Decision)

### Option A: Fix Foundation Issues First
1. Delete or explain daily_features v1
2. Get exact CASCADE definition
3. Verify asia_bias logic
4. Re-run verification with correct logic

### Option B: Start from Scratch (Safer)
1. Ignore validated_setups claims
2. Start with raw session data
3. Test liquidity patterns ourselves
4. Build up VERIFIED edges only

### Option C: Trust but Verify
1. Use validated_setups as HYPOTHESES (not facts)
2. Test each claim independently
3. Document which edges are verified vs claimed

---

**Recommendation**: Option B (Start from Scratch) is safest for ensuring LEGITIMATE foundation.

We have the data, we have the session type codes, we can test everything ourselves.

**Authority**: CLAUDE.md (daily_features_v2 is canonical)
**Constraint**: res.txt (verify robustness and honesty yourself)
**Status**: Foundation questionable - verification needed before proceeding

---

**Generated**: 2026-01-24
**Next**: User decision on how to proceed
