# TIER 1 FILTER OPPORTUNITIES - ANALYSIS COMPLETE
**Date**: 2026-01-24
**Focus**: 4 robust ORBs (1800, 1100, 2300, 0030)
**Goal**: Improve edge while maintaining frequency

---

## KEY FINDINGS

### 1. DIRECTIONAL BIAS IS STRONGEST SIGNAL ✅

**Major opportunities found**:

| ORB  | UP Breaks   | DOWN Breaks | Difference | Recommendation           |
|------|-------------|-------------|------------|--------------------------|
| 1100 | +0.086R (269t) | **-0.009R** (257t) | **+0.095R** | Trade ONLY UP breaks ✅ |
| 0030 | **-0.031R** (286t) | +0.085R (239t) | **+0.116R** | Trade ONLY DOWN breaks ✅ |
| 1800 | +0.016R (289t) | +0.084R (236t) | +0.067R    | Prefer DOWN breaks       |
| 2300 | +0.039R (278t) | +0.042R (247t) | +0.003R    | Both similar, keep both  |

**Biggest win**:
- **0030 ORB - DOWN only**: Improves from +0.022R → +0.085R (+0.063R improvement!)
- **1100 ORB - UP only**: Improves from +0.040R → +0.086R (+0.046R improvement!)

**Trade-off**: Cuts frequency in half (but still 120-135 trades/year each - acceptable!)

---

## RECOMMENDED FILTERS (IMMEDIATE IMPLEMENTATION)

### Priority 1: 0030 ORB - DOWN Breaks Only

**Current baseline**:
- All breaks: 525 trades/year, 56.2% WR, +0.022R avg

**With DOWN filter**:
- DOWN only: **239 trades/year, 59.4% WR, +0.085R avg**
- **Improvement: +0.063R per trade (+186%!)**

**Frequency check**: 239 trades ≈ **120 trades/year** ✅ (above 100 minimum)

**Implementation**:
```python
# In validated_setups or strategy filter
if orb_time == '0030' and break_direction == 'UP':
    skip_trade = True  # Only trade DOWN breaks
```

**Rationale**:
- DOWN breaks at 00:30 (overnight NY session) have strong edge
- UP breaks at 00:30 are actually NEGATIVE (-0.031R) - avoid these!

---

### Priority 2: 1100 ORB - UP Breaks Only

**Current baseline**:
- All breaks: 526 trades/year, 59.7% WR, +0.040R avg

**With UP filter**:
- UP only: **269 trades/year, 62.1% WR, +0.086R avg**
- **Improvement: +0.046R per trade (+115%!)**

**Frequency check**: 269 trades ≈ **135 trades/year** ✅ (well above minimum)

**Implementation**:
```python
# In validated_setups or strategy filter
if orb_time == '1100' and break_direction == 'DOWN':
    skip_trade = True  # Only trade UP breaks
```

**Rationale**:
- UP breaks at 11:00 (late Asia session) perform well
- DOWN breaks at 11:00 are breakeven (-0.009R) - avoid these!

---

### Priority 3: 1800 ORB - Prefer DOWN Breaks (Optional)

**Current baseline**:
- All breaks: 525 trades/year, 61.9% WR, +0.046R avg

**With DOWN filter**:
- DOWN only: **236 trades/year, 64.0% WR, +0.084R avg**
- **Improvement: +0.038R per trade (+83%!)**

**Trade-off**: Larger frequency cut (236 trades ≈ **118 trades/year**)

**Recommendation**: TEST, but maybe keep both directions
- DOWN is significantly better
- But 1800 ORB is already strong with both directions
- Consider this filter only if you need to be more selective

---

### Priority 4: 2300 ORB - NO FILTER (Keep Both)

**Finding**: UP and DOWN breaks perform identically (+0.039R vs +0.042R)

**Recommendation**: Keep trading both directions
- No edge in filtering
- Maximizes frequency (525 trades/year)
- Good profitability already (+0.041R)

---

## IMPACT SUMMARY

### Before Filters (Current)

| ORB  | Trades/Year | Net R   | Annual Expectancy |
|------|-------------|---------|-------------------|
| 1800 | 525         | +0.046  | +24.2R            |
| 1100 | 526         | +0.040  | +21.0R            |
| 2300 | 525         | +0.041  | +21.5R            |
| 0030 | 525         | +0.022  | +11.6R            |
| **Total** | **2,101** | **+0.037** | **+78.3R/year** |

### After Filters (Recommended)

| ORB  | Trades/Year | Net R    | Annual Expectancy | Filter           |
|------|-------------|----------|-------------------|------------------|
| 1800 | 525         | +0.046   | +24.2R            | None (keep both) |
| 1100 | **269**     | **+0.086** | **+23.1R**      | **UP only** ✅   |
| 2300 | 525         | +0.041   | +21.5R            | None (keep both) |
| 0030 | **239**     | **+0.085** | **+20.3R**      | **DOWN only** ✅ |
| **Total** | **1,558** | **+0.057** | **+89.1R/year** |

**Impact**:
- Trades reduced: -543 trades/year (-26%)
- Net R improved: +0.037R → +0.057R (+54%!)
- **Annual expectancy improved: +78.3R → +89.1R (+14%!)**

**Conclusion**: Trade fewer, but **WAY better** trades ✅

---

## FREQUENCY BALANCE CHECK

### With Recommended Filters

| ORB  | Trades/Year | Trades/Week | Status          |
|------|-------------|-------------|-----------------|
| 1800 | 525         | ~10         | ✅ Excellent    |
| 2300 | 525         | ~10         | ✅ Excellent    |
| 1100 | 269         | ~5          | ✅ Good         |
| 0030 | 239         | ~5          | ✅ Good         |

**Total**: 1,558 trades/year = **30 trades/week** on average

**Verdict**: Excellent balance between quality and frequency ✅
- Not over-filtered (30 trades/week is plenty)
- Significantly improved edge (+54% better per trade)
- Still regular opportunities (2-3 setups per day on average)

---

## OTHER POTENTIAL FILTERS (LOWER PRIORITY)

### Pre-NY Range

**Weak signal** - differences are small:
- 1800: Winners 19.7 vs Losers 19.6 (0.5% difference)
- 2300: Winners 20.0 vs Losers 19.3 (3.5% difference)
- 0030: Winners 19.6 vs Losers 19.8 (1.0% difference)

**Recommendation**: Don't filter on this yet
- Directional bias is much stronger signal
- Pre-NY range adds complexity without clear benefit

### Session Context

**1800 ORB - Asia range**:
- Winners: 25.4 | Losers: 24.4
- Small difference, not actionable

**2300 ORB - London range**:
- Winners: 19.8 | Losers: 21.8
- **Winners had SMALLER London range** (interesting!)
- **Potential filter**: London range < 21.0 points

**Recommendation**: Test 2300 ORB with London range filter (lower priority)

### ORB Size

**No clear pattern** in any ORB:
- Winners and losers have similar average ORB sizes
- Not a good discriminator

**Recommendation**: Don't filter on ORB size
- Larger ORBs have lower cost impact (already accounted for)
- Size alone doesn't predict outcome

### ATR / Volatility

**No clear pattern** in any ORB:
- Winners and losers have similar ATR values
- Volatility doesn't discriminate winners/losers

**Recommendation**: Don't filter on ATR for now

---

## IMPLEMENTATION PLAN

### Phase 1: Directional Filters (THIS WEEK)

**Add to validated_setups table**:

```sql
-- Add direction_filter column
ALTER TABLE validated_setups ADD COLUMN direction_filter VARCHAR;

-- Update 1100 setups
UPDATE validated_setups
SET direction_filter = 'UP'
WHERE orb_time = '1100';

-- Update 0030 setups
UPDATE validated_setups
SET direction_filter = 'DOWN'
WHERE orb_time = '0030';

-- Keep 1800 and 2300 as NULL (trade both)
```

**Update strategy engine**:
```python
# In setup_detector or strategy_engine
if setup.direction_filter:
    if orb_break_direction != setup.direction_filter:
        return None  # Skip this trade
```

### Phase 2: Backtest Validation (BEFORE LIVE)

**Run backtest with new filters**:
1. Rebuild daily_features_v2 (already done with costs)
2. Apply directional filters
3. Confirm metrics match analysis
4. Verify 1,558 trades/year total

**Expected results**:
- 1100 UP only: 269 trades, +0.086R, 62.1% WR
- 0030 DOWN only: 239 trades, +0.085R, 59.4% WR
- Total system: +89.1R/year expectancy

### Phase 3: Paper Trade (30 DAYS)

**Track actual vs expected**:
- Directional accuracy (does UP/DOWN filter actually help?)
- Trade frequency (getting 30 trades/week?)
- Net R per ORB (matching backtested values?)

**Adjust if needed**:
- If 1100 DOWN breaks start working in paper trading, remove filter
- If 0030 UP breaks show edge, remove filter

---

## VALIDATED SETUPS IMPACT

### From LEGITIMATE_EDGES_CATALOG.md

**Need to re-classify setups by direction**:

1. **Elite Setup (77% WR, RR=8.0)**:
   - Check ORB time
   - If 1100 or 0030, verify direction matches filter
   - If direction is wrong, may need to exclude

2. **All 1100 ORB setups**:
   - Mark as "UP BREAKS ONLY"
   - Remove or flag any DOWN break setups

3. **All 0030 ORB setups**:
   - Mark as "DOWN BREAKS ONLY"
   - Remove or flag any UP break setups

4. **All 1800 and 2300 setups**:
   - Keep both directions (no filter)

---

## MONITORING & REFINEMENT

### After 100 Trades

**Review actual directional performance**:
```
ORB | Direction | Trades | Net R   | Expected | Match?
1100 | UP       | XX     | +X.XXX  | +0.086   | ✅/❌
1100 | DOWN     | 0      | N/A     | (skip)   | ✅
0030 | UP       | 0      | N/A     | (skip)   | ✅
0030 | DOWN     | XX     | +X.XXX  | +0.085   | ✅/❌
```

**If mismatch**:
- Remove filter if "skip" direction becomes profitable
- Strengthen filter if included direction underperforms

### Long-term Optimization

**After 6 months live trading**:
- Re-analyze with new data
- Check if directional bias holds
- Consider adding secondary filters (session context, etc.)
- Balance between over-optimization and edge improvement

---

## SUMMARY

**IMMEDIATE ACTION**: Implement directional filters on 1100 (UP) and 0030 (DOWN)

**Expected Impact**: +14% annual expectancy (+10.8R/year more profit)

**Trade-off**: -26% fewer trades (but still 30/week - plenty!)

**Confidence**: HIGH - directional bias is strong and consistent signal

**Next Steps**:
1. Update validated_setups table with direction_filter
2. Modify strategy engine to apply filters
3. Backtest to validate
4. Paper trade for 30 days
5. Go live if metrics hold

**Files to update**:
- `data/db/gold.db` - validated_setups table
- `trading_app/setup_detector.py` - add direction filter logic
- `trading_app/strategy_engine.py` - apply filters

---

**Analysis Complete**: 2026-01-24
**Status**: Ready for implementation ✅
**Priority**: HIGH - significant edge improvement with minimal complexity
