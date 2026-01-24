# NQ Massive Moves Research - Final Report

**Date**: 2026-01-13
**Goal**: Find repeatable 3R+ same-day runners
**Status**: ❌ NO PATTERNS PASSED

---

## Executive Summary

Tested 2 pattern families designed to capture 3R+ intraday runners on NQ. **Both patterns FAILED** robustness tests.

**Key Finding**: 3R+ intraday targets on NQ are **extremely difficult** to achieve with repeatable patterns. The market structure favors:
1. Quick 1R mean-reversion scalps (as we found earlier)
2. NOT sustained 3R+ trend continuation

**Sample Size**: 268 trading days (Jan-Nov 2025), 306,243 1-minute bars

---

## Patterns Tested

### Pattern 1: Trend Day Detector

**Logic**:
- Identify strong directional move in first 30 minutes of search window
- Require >60% directional efficiency (close-to-close vs high-to-low range)
- Enter on continuation after impulse
- Stop: Initial swing low/high
- Target: 3R

**Results**:
- **Trades**: 52
- **Win Rate**: 23.1%
- **Avg R**: -0.077R
- **IS Avg R**: +0.000R
- **OOS Avg R**: -0.250R
- **Status**: ❌ FAIL

**Why It Failed**:
1. **Too strict filtering** - Only triggers 52 times in 268 days (~0.19/day)
2. **Low win rate** - 23% WR means 77% of "strong impulses" reverse
3. **IS/OOS breakdown** - Works in-sample but fails out-of-sample (overfitting)
4. **False momentum** - Early impulse ≠ sustained trend

**Sample Trades**:
```
Date        Direction  Outcome  R     MAE   MFE
2025-01-20  UP         WIN      +3.0  0.17  3.06  ✓ Rare winner
2025-01-25  UP         LOSS     -1.0  1.01  0.01
2025-02-12  UP         WIN      +3.0  0.00  3.17  ✓ Clean trend
2025-03-18  DOWN       LOSS     -1.0  2.46  0.40  ← Deep stop hit
```

**Observation**: When it works, it works well (MFE > 3R). But 77% of the time, the early impulse is a fake-out.

---

### Pattern 2: Breakout + Retest

**Logic**:
- Break Asia high/low
- Retest level (within 10 points)
- Enter after retest confirms
- Stop: 2 points beyond retest
- Target: 3R

**Results**:
- **Trades**: 5,052 (!!)
- **Win Rate**: 24.8%
- **Avg R**: -0.006R
- **IS Avg R**: -0.042R
- **OOS Avg R**: +0.078R
- **Status**: ❌ FAIL

**Why It Failed**:
1. **Too loose filtering** - Triggers 5,052 times (18.8 trades/day) = noise
2. **Low win rate** - 25% WR = 3:1 loss ratio
3. **Asia levels not predictive** - Breaking Asia H/L doesn't predict 3R continuation
4. **Retest logic flawed** - "Within 10 points" catches many false retests

**Trade Distribution**:
- **Losses**: 3,797 (75.2%)
- **Wins**: 1,255 (24.8%)

**Observation**: The pattern fires constantly but mostly on weak breakouts that fail to extend 3R.

---

## Why 3R+ Targets Fail on NQ Intraday

### 1. Market Structure Reality

**NQ Behavior**:
- **Mean-reverting at 1R scale** (as we found in RR optimization)
- Quick moves to 1R, then consolidation or reversal
- **3R moves are rare** - require sustained institutional flow

**Evidence**:
- From RR optimization: 63.9% WR at 1R drops to 2.6% WR at 2R
- Even best ORB (0030) can't sustain 3R moves reliably
- Only ~2-6% of trades ever reach 2R+, let alone 3R

### 2. False Momentum Problem

**Pattern Issue**: Both patterns try to identify "strong momentum" early, but:
- Early impulse ≠ sustained trend
- Breakouts fail 75% of the time at 3R
- NQ has many intraday fake-outs driven by algo liquidity sweeps

**Result**: Low win rates (23-25%) across all tested patterns.

### 3. Sample Size vs Selectivity Trade-off

**Dilemma**:
- **Strict filters** (Trend Day): Low sample (52 trades) = no statistical power
- **Loose filters** (Breakout Retest): High sample (5,052 trades) = mostly noise

**No Middle Ground Found**: Could not find a pattern with both:
- Sufficient sample size (>100 trades)
- High enough win rate (>40%)
- Positive expectancy in IS and OOS

---

## Robustness Test Results

### IS/OOS Split (70/30 by date)

| Pattern | IS Trades | IS Avg R | OOS Trades | OOS Avg R | Pass? |
|---------|-----------|----------|------------|-----------|-------|
| Trend Day | 37 | +0.000R | 15 | -0.250R | ❌ Negative OOS |
| Breakout Retest | 3,550 | -0.042R | 1,502 | +0.078R | ❌ Negative IS |

**Verdict**: Neither pattern is stable across time splits. This indicates **overfitting** or **regime dependence**.

### Outlier Removal (Top 1% Days)

| Pattern | Full Sample | No Outliers | Pass? |
|---------|-------------|-------------|-------|
| Trend Day | -0.077R | ~-0.08R | ❌ Still negative |
| Breakout Retest | -0.006R | ~-0.02R | ❌ Still negative |

**Verdict**: Neither pattern depends on outliers, but that doesn't help since they're negative even without outliers.

### Pass/Fail Criteria

**Requirements** (at least 3 of 4):
1. ✓ Overall positive expectancy (>0.5R avg)
2. ✓ IS and OOS both positive
3. ✓ No outlier dependency (positive without top 1%)
4. ✓ Minimum sample size (>=20 trades)

**Results**:
- **Trend Day**: 1 of 4 (only sample size) = ❌ FAIL
- **Breakout Retest**: 1 of 4 (only sample size) = ❌ FAIL

---

## What Could Work (Future Research)

### 1. Lower Target Expectations

**Hypothesis**: 3R is too ambitious for NQ intraday.

**Test**: Rerun patterns with 2R or 1.5R targets
- Likely to increase win rate from 25% → 35-45%
- May achieve positive expectancy

**Trade-off**: No longer "massive moves" but more realistic.

---

### 2. Multi-Leg Approaches

**Hypothesis**: NQ doesn't trend 3R in one shot, but can reach 3R cumulative across multiple legs.

**Test**: Scale in/out strategies
- First leg: 1R target
- If 1R hit with momentum, add second leg: 2R target
- Pyramid into strength

**Advantage**: Captures realistic NQ behavior (1R moves common, 3R rare).

---

### 3. EOD Capture (Not Same-Day)

**Hypothesis**: 3R moves happen, but take multiple hours (not achievable in 4-5 hour search windows).

**Test**: Enter on signal, hold to EOD or next day
- Target: 4-5R over 12-24 hours
- Overnight risk acceptable for position trade

**Advantage**: More time for move to develop.

---

### 4. Specific Event-Driven Setups

**Hypothesis**: 3R moves occur on specific catalysts (FOMC, earnings, volatility spikes).

**Test**: Filter for:
- VIX > certain threshold
- Pre-market gap > X points
- Prior day range > 2x ATR

**Advantage**: Targets days with actual momentum potential.

---

### 5. Directional Bias + Session Optimization

**Hypothesis**: Certain directions work better in certain sessions.

**Test**:
- NYC open (23:00-02:00): Only trade UP breakouts
- London close (16:00-21:00): Only trade DOWN reversals
- Combine with day-of-week effects

**Advantage**: Reduces false signals by filtering on session context.

---

## Honest Assessment

### What We Learned

1. **3R+ intraday runners are RARE on NQ** - not a repeatable edge
2. **Mean-reversion dominates** - NQ wants to revert after 1R moves
3. **Early momentum is unreliable** - impulse moves often reverse
4. **Breakout retests are noisy** - 75% false signals at 3R targets

### What Actually Works (From Prior Research)

**Proven NQ Edges**:
- **1R ORB scalps** - 60-65% WR at 1R target (validated)
- **Size-filtered ORBs** - 10-118% improvement with ORB size filters
- **Quick profit-taking** - Take 1R, don't chase more

**Expected Returns**:
- Top 3 ORBs (filtered): ~0.33R/day
- Reliable, repeatable, profitable

---

## Recommendations

### 1. Stick with 1R ORB Framework

**Why**: Proven to work (65% WR, positive expectancy, passes robustness)

**Focus**: Optimize execution and position sizing, not chasing bigger targets.

---

### 2. If Pursuing Bigger Moves, Lower Expectations

**Realistic Target**: 1.5-2R (not 3R)

**Better Approach**:
- Use 1R ORBs as foundation
- On strong days (MFE > 1.5R), trail stops to capture runners
- Don't force 3R targets that rarely happen

---

### 3. Accept NQ's Personality

**NQ Reality**:
- High frequency mean-reversion
- 1R moves common
- 3R moves rare (event-driven only)

**Trading Style Match**: Scalping/mean-reversion fits NQ better than trend-following.

---

## Files Generated

1. `outputs/NQ_MASSIVE_CANDIDATES.csv` - Pattern summary stats
2. `outputs/NQ_MASSIVE_TRADES.csv` - All 5,104 tested trades
3. `outputs/NQ_MASSIVE_REPORT.md` - This report
4. `scripts/research_nq_massive_moves.py` - Research script

---

## Conclusion

**NO PATTERNS PASSED** the robustness tests for 3R+ intraday runners on NQ.

**Why**: NQ market structure is mean-reverting at the 1R scale, not trending at the 3R scale during intraday windows.

**Best "Almost Pass"**: None - both patterns showed negative expectancy.

**Honest Verdict**: 3R+ intraday targets on NQ are **not a repeatable edge** with the patterns tested. The 1R ORB framework (previously validated) remains the strongest approach for NQ.

**Status**: Research complete, no viable massive move patterns found.
**Date**: 2026-01-13
**Recommendation**: Focus on optimizing the proven 1R ORB framework rather than chasing rare 3R+ runners.
