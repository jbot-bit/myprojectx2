# Daily Features V2: Current Columns + Proposed Additions for Edge Research

**Date**: 2026-01-24
**Status**: daily_features v1 DELETED - only v2 remains (canonical)
**Purpose**: Document what we have + propose additions for liquidity research

---

## Current Columns in daily_features_v2 (86 total)

### Core Identification (2 columns)
- `date_local` - Trading day date
- `instrument` - MGC, NQ, MPL

### Pre-Session Data (9 columns)
- `pre_asia_high`, `pre_asia_low`, `pre_asia_range`
- `pre_london_high`, `pre_london_low`, `pre_london_range`
- `pre_ny_high`, `pre_ny_low`, `pre_ny_range`

### Session Data (9 columns)
- `asia_high`, `asia_low`, `asia_range`
- `london_high`, `london_low`, `london_range`
- `ny_high`, `ny_low`, `ny_range`

### Session Type Codes (3 columns) ← **KEY FOR LIQUIDITY RESEARCH**
- `asia_type_code` - A0_NORMAL, A2_EXPANDED
- `london_type_code` - L1_SWEEP_HIGH, L2_SWEEP_LOW, L3_EXPANSION, L4_CONSOLIDATION
- `pre_ny_type_code` - N0_NORMAL, N1_SWEEP_HIGH, N2_SWEEP_LOW, N3_CONSOLIDATION, N4_EXPANSION

### ORB Data (ALL 6 ORBs, ~12 columns each = 72 columns)
For each ORB (0900, 1000, 1100, 1800, 2300, 0030):
- `orb_XXXX_high`, `orb_XXXX_low`, `orb_XXXX_size`
- `orb_XXXX_break_dir` - UP, DOWN, NONE
- `orb_XXXX_outcome` - WIN, LOSS, TIME_EXIT, NO_TRADE
- `orb_XXXX_r_multiple` - Return in R (risk units)
- `orb_XXXX_mae` - Max Adverse Excursion
- `orb_XXXX_mfe` - Max Favorable Excursion
- `orb_XXXX_risk_ticks` - Risk in ticks
- `orb_XXXX_stop_price` - Stop loss price
- Additional columns for each ORB

### Indicators (2 columns)
- `rsi_14_at_0030` - RSI at 00:30 ORB
- `atr_20` - 20-period ATR

**TOTAL: 86 columns**

---

## What's MISSING for Liquidity Research?

### Category A: Liquidity Event Timing

**Problem**: We know LONDON sweeps ASIA (L1/L2), but when exactly?
**Missing**:
- `london_sweep_time` - Timestamp when London high/low was set
- `pre_ny_sweep_time` - Timestamp when Pre-NY high/low was set
- `time_since_asia_close` - Minutes from Asia close to sweep event

**Why useful**: Test if liquidity event RECENCY matters (fresh sweep vs old sweep)

**Example research question**:
- Does London sweep at 18:05 (0 min old) create better 1800 ORB edge than Asia sweep at 15:00 (3 hrs old)?

---

### Category B: Liquidity Level Spacing

**Problem**: We know levels were swept, but how far apart were they?
**Missing**:
- `asia_london_high_gap` - Distance between Asia high and London high (if London swept)
- `asia_london_low_gap` - Distance between Asia low and London low
- `london_preny_high_gap` - Distance between London high and Pre-NY high
- `london_preny_low_gap` - Distance between London low and Pre-NY low

**Why useful**: Test if "stacked levels" (converging highs/lows) create stronger edges

**Example research question**:
- Do close levels (gap < 0.5 ATR) create more explosive ORB breakouts than wide levels (gap > 2.0 ATR)?

---

### Category C: Price Position Relative to Levels

**Problem**: We have asia_bias in validated_setups, but it's not stored in features table
**Missing**:
- `price_at_orb_start` - Price at each ORB start (0900, 1000, 1100, 1800, 2300, 0030)
- `asia_bias_at_XXXX` - Was price ABOVE/BELOW/INSIDE Asia range at each ORB time?
- `london_bias_at_XXXX` - Was price ABOVE/BELOW/INSIDE London range at each ORB time?

**Why useful**: Directly test asia_bias and london_bias filters without deriving them

**Example research question**:
- Does london_bias=ABOVE at 2300 ORB create better edge than asia_bias=ABOVE?

---

### Category D: Cascade Pattern Flags

**Problem**: We claim CASCADE works (+1.95R), but pattern is not stored
**Missing**:
- `is_cascade_london_ny` - Boolean: London swept Asia AND Pre-NY swept London?
- `is_double_sweep_high` - Boolean: Both London and Pre-NY swept high?
- `is_double_sweep_low` - Boolean: Both London and Pre-NY swept low?
- `is_reversal_pattern` - Boolean: London swept high, Pre-NY swept low (or vice versa)?

**Why useful**: Directly test cascade patterns without complex queries

**Example research question**:
- Is cascade (London → NY sequential sweeps) better than simultaneous sweeps (L3_EXPANSION)?

---

### Category E: Volatility Context

**Problem**: We have ATR_20, but no volatility STATE at key times
**Missing**:
- `volatility_percentile` - Where is current ATR vs 90-day distribution? (0-100)
- `is_low_vol_regime` - Boolean: ATR < 25th percentile?
- `is_high_vol_regime` - Boolean: ATR > 75th percentile?
- `range_efficiency` - (Asia range) / (Asia high - Asia low traveled distance)

**Why useful**: Test if liquidity patterns work differently in different volatility regimes

**Example research question**:
- Do liquidity sweeps in low-vol regimes create stronger ORB edges (coiled spring effect)?

---

### Category F: Day-of-Week & Time Context

**Problem**: No day-of-week or time patterns captured
**Missing**:
- `day_of_week` - Monday, Tuesday, etc.
- `week_of_month` - 1, 2, 3, 4, 5
- `is_first_trading_day_of_week` - Boolean
- `is_last_trading_day_of_week` - Boolean
- `days_since_last_holiday` - Count

**Why useful**: Test if liquidity patterns work differently on Mondays vs Fridays

**Example research question**:
- Does Monday liquidity (week start) behave differently than Friday liquidity (week end)?

---

### Category G: Price Travel Metrics

**Problem**: We have pre_orb_travel columns (OLD, from v1), but not in v2
**Missing**:
- `pre_orb_travel_XXXX` - Price distance traveled before each ORB start
- `travel_direction_XXXX` - UP/DOWN/FLAT before ORB
- `momentum_at_orb_XXXX` - Is price accelerating into ORB? (rate of travel)

**Why useful**: Test if "already moving" setups work better than "stagnant" setups

**Example research question**:
- Does large pre-ORB travel (already moving) + liquidity alignment = strongest edge?

---

### Category H: Failed Sweep Attempts

**Problem**: We track successful sweeps (L1, L2, N1, N2), but not failed attempts
**Missing**:
- `london_tested_asia_high` - Boolean: Did London test (but not break) Asia high?
- `london_tested_asia_low` - Boolean: Did London test (but not break) Asia low?
- `num_tests_before_break` - How many times was level tested before breaking?

**Why useful**: Test if "multiple test rejections" create better ORB reversal setups

**Example research question**:
- Does 3x test rejection at Asia high → ORB breakdown create stronger edge than untested level?

---

### Category I: Multi-Timeframe Context

**Problem**: We only have 1m and 5m data, but no hourly/daily context
**Missing**:
- `daily_trend` - Is price in uptrend/downtrend/sideways on daily chart?
- `4h_trend` - 4-hour trend direction
- `previous_day_close_vs_current` - Gap up/down from previous day?

**Why useful**: Test if ORB edges work differently with/against larger timeframe trends

**Example research question**:
- Do ORB breakouts WITH daily trend have higher win rate than counter-trend?

---

## Proposed Additions (Prioritized)

### TIER 1: Must-Have for Liquidity Research (implement first)
1. **Cascade flags** (`is_cascade_london_ny`, `is_double_sweep_high/low`)
2. **Price position** (`asia_bias_at_XXXX`, `london_bias_at_XXXX`)
3. **Liquidity spacing** (`asia_london_high_gap`, `asia_london_low_gap`)
4. **Pre-ORB travel** (`pre_orb_travel_XXXX`, `travel_direction_XXXX`)

### TIER 2: High-Value for Pattern Discovery
5. **Liquidity timing** (`london_sweep_time`, `time_since_asia_close`)
6. **Volatility context** (`volatility_percentile`, `is_low_vol_regime`)
7. **Day-of-week** (`day_of_week`, `is_first_trading_day_of_week`)

### TIER 3: Nice-to-Have for Advanced Research
8. **Failed sweep attempts** (`london_tested_asia_high`, `num_tests_before_break`)
9. **Multi-timeframe** (`daily_trend`, `4h_trend`)
10. **Range efficiency** (`range_efficiency`)

---

## Implementation Strategy

### Option A: Extend daily_features_v2 (Safest)
- Add new columns to existing table
- Backfill historical data
- Keep all existing columns (86 → 110+ columns)
- **Pros**: No breaking changes, gradual addition
- **Cons**: Table gets wider

### Option B: Create daily_features_v3 (Clean Slate)
- Build new table with ALL useful columns
- Keep v2 as read-only archive
- Fresh start with better organization
- **Pros**: Clean design, well-organized
- **Cons**: Migration effort, dual tables during transition

### Option C: Add Research-Specific Table (Modular)
- Keep daily_features_v2 as-is (production)
- Create `liquidity_research_features` table (research only)
- Join when needed for research
- **Pros**: No impact on production, research freedom
- **Cons**: Requires joins, more complex queries

**Recommendation**: **Option A** (extend v2) for Tier 1 additions, **Option C** (research table) for experimental Tier 2/3 features

---

## Next Steps

### Immediate (Before liquidity research):
1. ✅ Delete daily_features v1 (DONE)
2. Add Tier 1 columns to daily_features_v2:
   - `is_cascade_london_ny`
   - `is_double_sweep_high`, `is_double_sweep_low`
   - `asia_bias_at_0900`, `asia_bias_at_1000`, `asia_bias_at_1100`, `asia_bias_at_1800`, `asia_bias_at_2300`, `asia_bias_at_0030`
   - `pre_orb_travel_0900`, `pre_orb_travel_1000`, etc.
3. Backfill these columns for historical data

### Then (Start fresh liquidity research):
1. Test simple patterns (does cascade flag actually predict better outcomes?)
2. Verify asia_bias with stored columns (not derived)
3. Test liquidity spacing (do close levels create stronger breakouts?)
4. Build up from VERIFIED edges only

---

**Authority**: CLAUDE.md (daily_features_v2 canonical)
**Constraint**: res.txt (research only, verify everything)
**Status**: daily_features v1 deleted, v2 remains, ready for extensions
**Next**: User decides which columns to add for liquidity research

---

**Generated**: 2026-01-24
