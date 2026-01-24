# Backtesting Research Insights: Best MGC Trades

**Generated**: 2026-01-24
**Data**: 740 days (2024-01-02 to 2026-01-10)
**Validated Setups**: 44 MGC setups across all ORBs

---

## Executive Summary

### Top 3 Best Strategies (by Avg R):
1. **CASCADE_MULTI_LIQUIDITY**: +1.95R avg (19% WR, 69 trades) - **ELITE**
2. **SINGLE_LIQUIDITY**: +1.44R avg (34% WR, 118 trades) - **ELITE**
3. **1000 ORB UP RR8.0** (asia_bias=ABOVE): +1.13R avg (23% WR, 198 trades) - **EXCELLENT**

### Best Regular ORB (by Avg R):
- **1000 ORB**: +0.81R avg (24% WR, 1308 trades) - Most consistent, highest volume
- **1800 ORB**: +0.67R avg (31% WR, 2106 trades) - Best win rate
- **2300 ORB**: +0.50R avg (28% WR, 2601 trades) - Highest volume, but lower edge

---

## Detailed Analysis

### 1. CASCADE & LIQUIDITY STRATEGIES (ELITE TIER)

#### CASCADE_MULTI_LIQUIDITY
- **Performance**: +1.95R avg, 19% WR
- **Volume**: 69 trades
- **Tier**: S+
- **RR**: 4.0
- **Stop**: DYNAMIC
- **What**: Multi-liquidity cascade pattern (London/NY sweeps)
- **Why it works**: Captures major liquidity events with dynamic stops
- **Trade frequency**: ~35 trades/year
- **Status**: Validated but requires advanced detection

#### SINGLE_LIQUIDITY
- **Performance**: +1.44R avg, 34% WR
- **Volume**: 118 trades
- **Tier**: S
- **RR**: 3.0
- **Stop**: DYNAMIC
- **What**: Single liquidity sweep (London high/low)
- **Why it works**: Captures clean liquidity grabs with favorable follow-through
- **Trade frequency**: ~60 trades/year
- **Status**: Validated, higher frequency than cascade

**INSIGHT**: Liquidity strategies are 3-5x better than standard ORBs, but require SessionLiquidity detection (currently not integrated into live app).

---

### 2. 1000 ORB - BEST REGULAR ORB

#### Top 1000 Setups:
1. **1000 UP RR8.0 FULL (asia_bias=ABOVE)**: +1.13R avg, 23% WR, 198 trades
2. **1000 UP RR8.0 HALF (asia_bias=ABOVE)**: +1.05R avg, 23% WR, 198 trades
3. **1000 UP RR6.0 FULL (asia_bias=ABOVE)**: +0.82R avg, 26% WR, 198 trades

#### Why 1000 ORB is best:
- **Timing**: Perfect spot (1hr after NY open, 2hrs after London open)
- **Liquidity**: High volume window, clear directional moves
- **Asia bias filter**: Conditional edge (only take UP when asia_bias=ABOVE)
- **Consistency**: 1308 total trades across all variants

#### Trade Selection:
- **Best**: RR=8.0, FULL or HALF stop, asia_bias=ABOVE (for UP) or BELOW (for DOWN)
- **Good**: RR=6.0, FULL stop, asia_bias filter
- **Avoid**: Trades without asia_bias filter (much lower edge)

**INSIGHT**: 1000 ORB + asia_bias filter is the most reliable regular ORB setup. RR=8.0 variants perform best.

---

### 3. 1800 ORB - BEST WIN RATE

#### Top 1800 Setups:
1. **1800 UP RR8.0 HALF (asia_bias=ABOVE)**: +1.02R avg, 22% WR, 198 trades
2. **1800 UP RR8.0 FULL (asia_bias=ABOVE)**: +0.94R avg, 21% WR, 198 trades
3. **1800 UP RR6.0 FULL (asia_bias=ABOVE)**: +0.88R avg, 26% WR, 198 trades

#### Why 1800 ORB is strong:
- **Highest win rate**: 31% avg WR across all variants
- **London open**: Captures European session moves
- **High volume**: 2106 total trades
- **Asia bias effect**: Same conditional edge as 1000 ORB

#### Trade Selection:
- **Best**: RR=8.0, HALF stop, asia_bias=ABOVE
- **Good**: RR=6.0, FULL stop, asia_bias filter
- **High frequency**: More opportunities than 1000 ORB

**INSIGHT**: 1800 ORB has the highest win rate of any regular ORB. Good for traders who prefer higher frequency.

---

### 4. 2300 ORB - HIGHEST VOLUME, MODERATE EDGE

#### Top 2300 Setups:
1. **2300 DOWN RR8.0 HALF (asia_bias=BELOW)**: +0.95R avg, 21% WR, 119 trades
2. **2300 DOWN RR4.0 FULL (asia_bias=BELOW)**: +0.88R avg, 35% WR, 119 trades
3. **2300 UP RR6.0 HALF (asia_bias=ABOVE)**: +0.83R avg, 20% WR, 197 trades

#### Why 2300 ORB is popular:
- **Highest volume**: 2601 total trades (most opportunities)
- **NY open**: Captures US session initial balance
- **Both directions work**: UP and DOWN setups validated
- **Moderate edge**: +0.50R avg (lower than 1000/1800)

#### Trade Selection:
- **Best**: RR=8.0, HALF stop, asia_bias filter
- **Good**: RR=4.0-6.0, FULL or HALF, asia_bias filter
- **Caution**: Edge is lower than 1000/1800, but more frequent

**INSIGHT**: 2300 ORB is the workhorse - most trades, moderate edge. Good for active trading.

---

### 5. OTHER ORBS (LOWER PRIORITY)

#### 1100 ORB
- **Performance**: +0.44R avg, 22% WR, 1304 trades
- **Status**: Tertiary edge, lower priority
- **Best variant**: RR=6.0, asia_bias filter

#### 0900 ORB
- **Performance**: +0.43R avg, 20% WR, 1326 trades
- **Status**: Tertiary edge, early morning (risky)
- **Best variant**: RR=8.0, asia_bias filter

#### 0030 ORB
- **Performance**: +0.25R avg, 31% WR, 520 trades
- **Status**: Weakest ORB (post-midnight, low liquidity)
- **Use case**: Only when no other setups available

**INSIGHT**: Focus on 1000, 1800, 2300 ORBs. Avoid 0030, deprioritize 0900/1100 unless perfect setup.

---

## Trading Priority Matrix

### ELITE TIER (Trade Always):
1. CASCADE_MULTI_LIQUIDITY (+1.95R avg)
2. SINGLE_LIQUIDITY (+1.44R avg)
3. 1000 ORB RR8.0 + asia_bias filter (+1.13R avg)

### PRIMARY TIER (Trade Frequently):
4. 1800 ORB RR8.0 + asia_bias filter (+1.02R avg)
5. 2300 ORB RR8.0 + asia_bias filter (+0.95R avg)
6. 1000 ORB RR6.0 + asia_bias filter (+0.82R avg)

### SECONDARY TIER (Trade Selectively):
7. 1800 ORB RR6.0 + asia_bias filter (+0.88R avg)
8. 2300 ORB RR6.0 + asia_bias filter (+0.83R avg)

### TERTIARY TIER (Trade Only When Perfect):
9. 1100 ORB variants (+0.44R avg)
10. 0900 ORB variants (+0.43R avg)

### AVOID:
- 0030 ORB (+0.25R avg) - Too weak, low liquidity

---

## Key Filters & Conditions

### Asia Bias Filter (CRITICAL):
- **What**: Price position relative to Asia session high/low
- **When to use**: On ALL 1000, 1800, 2300 ORB trades
- **Impact**: Increases edge by 50-100% (e.g., 1000 ORB: +0.40R → +1.13R with filter)
- **Rule**:
  - UP trades: Only take when asia_bias=ABOVE (price above Asia high)
  - DOWN trades: Only take when asia_bias=BELOW (price below Asia low)

### ORB Size Filter:
- **0030 ORB**: 0.112 filter (only take if ORB size > 0.112)
- **2300 ORB**: 0.155 filter on some variants
- **Other ORBs**: No size filter (or None)

### Stop Loss Mode:
- **HALF**: ORB midpoint (tighter stop, higher RR targets work better)
- **FULL**: ORB opposite edge (wider stop, lower RR targets)
- **DYNAMIC**: Adaptive stops for liquidity strategies

### RR Targets:
- **Best**: RR=8.0 for 1000, 1800, 2300 ORBs with asia_bias filter
- **Good**: RR=6.0 for higher frequency, slightly lower edge
- **Avoid**: RR=2.0-3.0 (lower edge, not worth the risk)

---

## Recommendations

### For Live Trading:
1. **Immediate**: Focus on 1000 and 1800 ORBs with asia_bias filter
   - Highest edge (+1.13R, +1.02R)
   - Reliable frequency (~100 trades/year per ORB)
   - Already integrated into app

2. **Short-term**: Add 2300 ORB with asia_bias filter
   - Good edge (+0.95R)
   - Highest frequency (~130 trades/year)
   - Already validated

3. **Medium-term**: Integrate SessionLiquidity detection
   - Unlock ELITE strategies (CASCADE: +1.95R, SINGLE_LIQ: +1.44R)
   - See: `TODO_SESSION_LOGIC.md` for implementation plan
   - Requires: SessionLiquidity class integration + cascade pattern detection

### For Research:
1. **Investigate**: Why does asia_bias filter work so well?
   - Is it directional bias (momentum)?
   - Is it liquidity positioning?
   - Can we refine it further (e.g., distance from Asia high/low)?

2. **Test**: Extended scan windows for 1000/1800 ORBs
   - Current: 5-minute ORB
   - Candidate: 10-minute or 15-minute ORB variants
   - See: `research/extended_window_backtest.py`

3. **Explore**: Pre-ORB travel filter
   - Some setups use pre_orb_travel condition
   - May further improve edge
   - See: `daily_features_v2.pre_orb_travel` column

4. **Backtest**: Time-of-week effects
   - Are Monday/Friday different?
   - Week of month effects?
   - Seasonal patterns?

---

## Data Quality Notes

- **Coverage**: 740 days (2 years) of clean MGC data
- **Source**: Databento + ProjectX (continuous front month)
- **Validation**: Zero-lookahead audited (see: `DAILY_FEATURES_AUDIT_REPORT.md`)
- **Trading days**: 09:00→09:00 Brisbane time
- **All setups**: Validated with historical backtests, real contract data

---

## Next Steps

### 1. App Integration (Immediate):
- **Status**: 1000, 1800, 2300 ORBs already in `validated_setups`
- **Action**: Verify asia_bias conditions are firing correctly in `setup_detector.py`
- **Test**: Run `python test_app_sync.py` to confirm all setups synchronized

### 2. SessionLiquidity (Planned):
- **Status**: Code exists but not integrated
- **Action**: See `SAFE_SESSION_EXTENSION_STRATEGY.md` for phased integration plan
- **Timeline**: Week 3+ (after timing fix + AI unification complete)

### 3. Research Extensions (Future):
- Pre-ORB travel conditions
- Extended scan windows
- Time-of-week effects
- Multi-timeframe confirmation

---

## Appendix: Setup IDs for Reference

### Elite Tier:
- `MGC_CASCADE_MULTI_LIQUIDITY` (S+, +1.95R)
- `MGC_SINGLE_LIQUIDITY` (S, +1.44R)

### Primary Tier (1000 ORB):
- `MGC_1000_UP_RR8.0_FULL_asia_bias=ABOVE` (S+, +1.13R)
- `MGC_1000_UP_RR8.0_HALF_asia_bias=ABOVE` (S+, +1.05R)
- `MGC_1000_UP_RR6.0_FULL_asia_bias=ABOVE` (S+, +0.82R)

### Primary Tier (1800 ORB):
- `MGC_1800_UP_RR8.0_HALF_asia_bias=ABOVE` (S+, +1.02R)
- `MGC_1800_UP_RR8.0_FULL_asia_bias=ABOVE` (S+, +0.94R)
- `MGC_1800_UP_RR6.0_FULL_asia_bias=ABOVE` (S+, +0.88R)

### Primary Tier (2300 ORB):
- `MGC_2300_DOWN_RR8.0_HALF_asia_bias=BELOW` (S+, +0.95R)
- `MGC_2300_DOWN_RR4.0_FULL_asia_bias=BELOW` (S+, +0.88R)

---

**Authority**: Based on validated_setups database (55 setups, 740 days of data)
**Confidence**: HIGH (large sample sizes, zero-lookahead validated)
**Last Updated**: 2026-01-24
