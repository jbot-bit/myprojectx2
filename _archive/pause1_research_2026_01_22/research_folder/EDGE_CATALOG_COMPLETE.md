# Complete Edge Catalog - All Discovered Setups & Conditions
**Date**: 2026-01-22
**Status**: Comprehensive collection of all tested edges

---

## Meta-Parameters (Being Tested Now)

### ORB Window Size
- **Current assumption**: 5 minutes
- **Testing**: 5, 10, 15, 30 minutes
- **Hypothesis**: Larger windows may capture more significant ranges

### Entry Confirmation
- **Current assumption**: 1-minute close
- **Testing**: 1-minute vs 5-minute close confirmation
- **Hypothesis**: 5-minute confirmation may reduce whipsaws

---

## ORB Time Edges (From Completed Research)

### 0900 ORB (Asia Open)
**From 9am_best_strategies_report.md**:
- **BEST**: RR=1.0, HALF SL, standard window
  - 52.9% WR, +0.061R avg, +31.7R total (5yr)
  - Quick scalps, 16min avg hold
- **Alternative**: RR=8.0, HALF SL, extended window
  - 11.7% WR, +0.058R avg, +30.3R total (5yr)
  - Asymmetric, rare big wins
- **AVOID**: RR=6.0, FULL SL (tests NEGATIVE)

### 1000 ORB (Mid-Asia)
**From 10am_best_strategies_report.md**:
- **BEST**: RR=6.0, FULL SL, extended window
  - 16.4% WR, +0.194R avg, +101.5R total (5yr)
  - 3x better than 9am!
  - FULL stops work here (opposite of 9am)
- **Alternative**: RR=6.0, FULL SL, standard window
  - 12.2% WR, +0.185R avg, +96.6R total (5yr)
  - 25% lower drawdown
- **Conservative**: RR=4.0, FULL SL
  - 21% WR, +0.143R avg
  - Lower risk profile

### 1100 ORB (Late Asia)
**From UNICORN_SETUPS_CORRECTED.md**:
- **Setup**: RR=3.0, FULL SL, extended
  - 30.4% WR, +0.215R avg
  - +56R/year claimed
- **Status**: Needs verification with detailed backtest

### 1800 ORB (London Open)
**From UNICORN_SETUPS_CORRECTED.md**:
- **Setup**: RR=1.5, FULL SL, extended
  - 51.0% WR, +0.274R avg
  - +72R/year claimed
  - Captures NY session moves
- **Status**: Needs verification

### 2300 ORB (NY Futures Open)
**From UNICORN_SETUPS_CORRECTED.md**:
- **Setup**: RR=1.5, HALF SL, extended
  - 56.1% WR, +0.403R avg
  - +105R/year claimed
  - "Best overall" - high frequency
  - Filter: Skip if ORB size > 0.155 × ATR(20)
- **Status**: Needs verification

### 0030 ORB (NY Cash Open)
**From UNICORN_SETUPS_CORRECTED.md**:
- **Setup**: RR=3.0, HALF SL, extended
  - 31.3% WR, +0.254R avg
  - +66R/year claimed
  - Filter: Skip if ORB size > 0.112 × ATR(20)
- **Status**: Needs verification

---

## Condition Filters (From phase1B_condition_edges.csv)

### 1. Asia Bias Filter
**Type**: Directional bias based on session positioning
**Implementation**: Compare entry price to Asia session midpoint

**UP trades with asia_bias=ABOVE**:
- MGC 1000 UP 8.0R FULL: +0.756R improvement
  - Baseline: 0.375R (14.96% WR)
  - Filtered: 1.131R (23.23% WR)
  - Retention: 40.6% of trades
- MGC 1800 UP 8.0R HALF: +0.769R improvement
  - Baseline: 0.251R (13.79% WR)
  - Filtered: 1.020R (22.22% WR)

**DOWN trades with asia_bias=BELOW**:
- MGC 2300 DOWN 8.0R HALF: +1.113R improvement
  - Baseline: -0.164R (8.83% WR)
  - Filtered: 0.950R (21.01% WR)
- MGC 2300 DOWN 4.0R FULL: +0.903R improvement
  - Baseline: -0.021R (17.92% WR)
  - Filtered: 0.882R (35.29% WR)

**Logic**: Trade WITH the Asia session bias
- If Asia was bullish → take LONG breakouts
- If Asia was bearish → take SHORT breakouts

### 2. Pre-ORB Trend Filter
**Type**: Momentum filter based on pre-ORB price action
**Implementation**: Measure price trend in X bars before ORB

**Bullish pre_orb_trend for UP trades**:
- MGC 1000 UP 8.0R FULL: +0.274R improvement
  - Baseline: 0.375R
  - Filtered: 0.649R
- Modest improvements across most setups
- 42% retention rate

**Logic**: Trade WITH the pre-ORB momentum
- Pre-ORB trending up → favor LONG
- Pre-ORB trending down → favor SHORT

### 3. ORB Size Filter
**Type**: Volatility filter to avoid exhaustion
**Implementation**: Skip if ORB size is too large (exhaustion) or too small (noise)

**Small ORB filter (below median)**:
- MGC 1000 UP 8.0R FULL: +0.072R improvement
  - Baseline: 0.375R
  - Filtered: 0.447R
  - 88.9% retention (high frequency maintained)

**ATR-based filter**:
- Skip if ORB size > threshold × ATR(20)
- 2300 ORB: threshold = 0.155
- 0030 ORB: threshold = 0.112
- Prevents exhaustion setups

### 4. Gap Filter (From GAP_RESEARCH_COMPLETE.md)
**Type**: Opening gap size filter
**Implementation**: Measure gap between prev_close and current_open

**Small gap fade (< 1.0 tick)**:
- 74% win rate (228/308 trades)
- Immediate fade back to prev_close
- Only works for tiny gaps

**Large gap continuation (> 1.0 tick)**:
- 25.3% WR, +0.52R avg
- Gaps can run 20-400+ ticks before filling
- 94.6% eventually fill, but NOT immediately

**Caution**: "Eventual fill" ≠ "immediate fill"

---

## Stop Loss Mode Insights

### HALF vs FULL by ORB Time

**9am (Asia Open) → HALF is superior**:
- HALF mode dominates top 10
- FULL mode tests negative
- Reason: Opening whipsaws, need tighter stops

**10am (Mid-Asia) → FULL is superior**:
- FULL mode 2.5x better than HALF
- Reason: Established moves, more conviction

**Night ORBs (2300, 0030) → HALF preferred**:
- Tighter ranges, better with HALF
- From UNICORN doc (needs verification)

**Hypothesis**: Stop mode depends on market phase
- Early (uncertain) → HALF
- Established (trending) → FULL

---

## RR Target Patterns

### By ORB Time

**0900** (from detailed report):
- RR=1.0 is optimal (+0.061R)
- RR=8.0 also works (+0.058R)
- RR=6.0 NEGATIVE

**1000** (from detailed report):
- RR=6.0 is optimal (+0.194R)
- RR=4.0 also works (+0.143R)
- Higher RR targets work better

**Night ORBs** (from UNICORN):
- RR=1.5 for 2300
- RR=3.0 for 0030
- Moderate targets

**Pattern**: ORB time determines optimal RR
- Early Asia: Low targets (1R) or asymmetric (8R)
- Mid Asia: Medium-high targets (6R)
- Night: Low-medium targets (1.5-3R)

---

## Scan Window Insights

### Standard vs Extended

**Standard window** (ORB end → 17:00 same day):
- Better for quick-hit setups (1R-2R)
- Lower drawdowns
- Shorter hold times

**Extended window** (ORB end → 09:00 next day):
- Better for asymmetric setups (6R-8R)
- Captures overnight moves
- Higher drawdowns
- CRITICAL for night ORBs!

**From UNICORN discovery**:
- Old bug: Night ORBs scanned only 85 minutes
- Real moves take 3-8 hours overnight
- Extending to next Asia open added +200R/year

---

## Indicators to Test (Not Yet Implemented)

### Volume Analysis
- Heavy volume at ORB formation
- Volume confirmation on breakout
- Volume exhaustion signals

### RSI
- Currently calculated for 0030 ORB
- Could filter overbought/oversold
- RSI divergence at ORB?

### ATR-based Filters
- Already used for ORB size filters
- Could use for position sizing
- ATR expansion/contraction signals

### Session Type Codes
- Already in daily_features_v2
- asia_type_code: sweep/expansion/consolidation
- Could filter by session character

### Price Action Patterns
- Inside bars before ORB
- Engulfing patterns
- Failed breakouts (trap setups)

---

## Multi-Instrument Edges (NQ, MPL)

### NQ (E-mini Nasdaq)
**From validated_setups**:
- 5 setups validated
- Different characteristics than MGC
- Needs separate analysis

### MPL (Micro Platinum)
**From validated_setups**:
- 6 setups validated
- Precious metal correlation with MGC
- Potential portfolio diversification

---

## Advanced Setups (Manual/Discretionary)

### Multi-Liquidity Cascades
**From UNICORN**:
- London sweeps Asia 23:00 level
- Second sweep occurs
- Acceptance failure within 3 bars
- Gap >9.5 points MANDATORY
- 19% WR, +1.95R avg, ~+68R/year
- Only 69 trades in 2 years (rare)

### Single Liquidity Reactions
**From UNICORN**:
- Level rejection setups
- 33.7% WR, +1.44R avg
- ~+86R/year
- 120 trades (16% of days)

**Status**: Manual setups, hard to automate

---

## Research Priorities

### Phase 1: Meta-Parameters (In Progress)
- [ ] ORB window size (5/10/15/30 min)
- [ ] Entry confirmation (1m vs 5m)
- [ ] Results: meta_parameter_scan_results.csv

### Phase 2: Condition Testing
- [ ] Asia bias filter on all ORBs
- [ ] Pre-ORB trend filter
- [ ] ORB size filters
- [ ] Gap filters

### Phase 3: Indicator Integration
- [ ] Volume confirmation
- [ ] RSI filters
- [ ] Session type filtering

### Phase 4: Multi-Instrument
- [ ] NQ comprehensive analysis
- [ ] MPL comprehensive analysis
- [ ] Cross-instrument signals

---

## Implementation Notes

### Data Source
- **Canonical**: daily_features_v2
- **Zero-lookahead**: Entry at 1m close outside ORB
- **Timezone**: Australia/Brisbane (UTC+10)
- **Trading day**: 09:00 → next 09:00

### Execution Rules
- Entry: First close outside ORB (NOT edge touch)
- Stop: FULL (opposite edge) or HALF (midpoint)
- Target: Entry ± (RR × risk)
- Resolution: Conservative (stop-first if both hit same bar)

### Filters Applied Pre-Entry
- ORB size vs ATR thresholds
- Asia bias alignment
- Pre-ORB trend alignment
- Gap size constraints

---

## Conflicts & Unresolved Questions

1. **0900 ORB**: UNICORN says RR=6.0 FULL works, detailed report says it's negative
   - **Resolution needed**: Full 5-year retest

2. **1000 ORB**: UNICORN says RR=8.0 best, detailed report says RR=6.0 best
   - **Possible**: Both true on different timeframes (2yr vs 5yr)

3. **ORB window size**: Assuming 5 minutes, never tested alternatives
   - **Resolution in progress**: meta_parameter_scan.py

4. **Entry timing**: Assuming 1-minute, never tested 5-minute confirmation
   - **Resolution in progress**: meta_parameter_scan.py

5. **Night ORB filters**: UNICORN has ATR filters, not yet verified
   - **Resolution needed**: Separate night ORB analysis

---

## Next Steps

1. ✅ Complete meta-parameter scan
2. Create condition-testing framework
3. Resolve 0900/1000 conflicts with full retests
4. Verify UNICORN night ORB claims
5. Test indicator combinations
6. Build automated research pipeline

---

**Status**: Catalog complete. Ready for systematic testing.
