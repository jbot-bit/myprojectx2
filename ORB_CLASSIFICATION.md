# ORB CLASSIFICATION - SLIPPAGE ROBUSTNESS
**Date**: 2026-01-24
**Criteria**: Profitable with 2.0 ticks slippage ($4.00 total cost)

---

## TIER 1: ROBUST (Focus Here) ✅

**These ORBs survive worst-case slippage - prioritize for development**

| ORB  | Net R (2.0t) | Win Rate | Trades/Year | Avg Risk | Status      |
|------|--------------|----------|-------------|----------|-------------|
| 1800 | **+0.046R**  | 61.9%    | ~252        | 30.3t    | BEST        |
| 2300 | +0.041R      | 58.1%    | ~252        | 44.9t    | EXCELLENT   |
| 1100 | +0.040R      | 59.7%    | ~252        | 44.9t    | EXCELLENT   |
| 0030 | +0.022R      | 56.2%    | ~252        | 49.0t    | GOOD        |

**Action**: Find filters to increase edge on these 4 ORBs
**Goal**: Boost net R while maintaining frequency (>150 trades/year minimum)

---

## TIER 2: MARGINAL (Flag, Revisit Later) ⚠️

**Only works with excellent execution (<1.0 tick slippage)**

| ORB  | Net R (0.5t) | Net R (2.0t) | Win Rate | Trades/Year | Status              |
|------|--------------|--------------|----------|-------------|---------------------|
| 1000 | +0.038R      | **-0.063R**  | 60.3%    | ~252        | Execution-dependent |

**Action**: Flag as "GOOD EXECUTION ONLY"
**Note**: Keep in database, revisit after improving Tier 1 ORBs
**Condition**: Only trade if proven slippage <1.0 ticks

---

## TIER 3: SKIP (Flag, Research Later) ❌

**Unprofitable even with good execution**

| ORB  | Net R (0.5t) | Net R (2.0t) | Win Rate | Trades/Year | Status            |
|------|--------------|--------------|----------|-------------|-------------------|
| 0900 | -0.019R      | -0.140R      | 58.9%    | ~252        | Needs major work  |

**Action**: Flag as "DO NOT TRADE"
**Note**: Keep data, but don't develop strategies here
**Future**: May investigate if others optimized

---

## DEVELOPMENT PRIORITY

### Phase 1: Optimize Tier 1 (Current Focus)

**Goal**: Increase edge on 4 robust ORBs through filters

**Approach**:
1. Analyze winning vs losing trades
2. Find common patterns in winners
3. Test filters that improve net R
4. Balance frequency vs profitability

**Target metrics** (per ORB):
- Net R: +0.050R minimum (with 2.0t slippage)
- Frequency: 150+ trades/year (3+ per week)
- Win rate: 60%+ preferred

### Phase 2: Recover Tier 2 (If Execution Good)

**Condition**: Only after proving <1.0 tick slippage for 100+ trades

**Goal**: Add 1000 ORB back to rotation
- Net R target: +0.080R (with 1.0t slippage)
- Frequency: 150+ trades/year

### Phase 3: Research Tier 3 (Long-term)

**Timeline**: After Tier 1 optimized and live trading proven

**Goal**: Understand why 0900 fails
- Different filters needed?
- Session characteristics?
- Fundamental issue with Asia open?

---

## FOCUS AREAS FOR TIER 1 OPTIMIZATION

### 1. Balance Frequency + Profitability

**Bad approach**:
- Filter so heavily that only 20 trades/year remain
- Accept any trade just to get frequency

**Good approach**:
- Target 150-250 trades/year per ORB
- Accept slightly lower profitability for consistency
- Quality > quantity, but quantity matters too

### 2. Scoring System

**Instead of just RR**:
```
Score = (Net_R * Frequency_Weight) + (Win_Rate_Bonus)

Where:
- Net_R = Profitability after $4.00 costs
- Frequency_Weight = 1.0 if >200 trades/year, 0.5 if 100-200, 0.2 if <100
- Win_Rate_Bonus = +0.1 if WR >60%, +0.2 if WR >65%
```

**Example**:
- Setup A: +0.150R, 50 trades/year, 70% WR → Score = 0.030 + 0.2 = 0.230
- Setup B: +0.080R, 200 trades/year, 62% WR → Score = 0.080 + 0.1 = 0.180

**Setup A has better RR but Setup B might be preferred** (more consistent edge)

### 3. Filter Candidates to Test

**For each Tier 1 ORB, analyze**:
1. ORB size ranges (find sweet spot)
2. Pre-ORB conditions (travel, gap, overnight range)
3. Session context (Asia/London/NY ranges)
4. Volatility filters (ATR bands)
5. Directional alignment (trend, session direction)
6. Time-based patterns (day of week, month)

**Metric to optimize**: Net R × Trade Frequency

---

## VALIDATED SETUPS REVIEW

### Current Catalog (from LEGITIMATE_EDGES_CATALOG.md)

**Need to re-classify all setups**:
1. Which ORB time? (1800, 1100, 2300, 0030, 1000, 0900)
2. Net R with 2.0t slippage?
3. Trade frequency?
4. Robust score?

**Action items**:
- Mark all 0900 setups as "TIER 3 - DO NOT TRADE"
- Mark all 1000 setups as "TIER 2 - GOOD EXECUTION ONLY"
- Focus development on 1800/1100/2300/0030 setups

---

## IMMEDIATE NEXT STEPS

### 1. Analyze Tier 1 ORBs for Filter Opportunities

Create script: `analyze_tier1_filters.py`

**For each robust ORB** (1800, 1100, 2300, 0030):
- Compare winning vs losing trades
- Find discriminating features
- Test candidate filters
- Report net R improvement + frequency impact

### 2. Create Robust Setup Catalog

File: `research/TIER1_ROBUST_SETUPS.md`

**Contents**:
- Only setups using Tier 1 ORBs
- Net R with 2.0t slippage
- Trade frequency
- Balanced score (frequency + profitability)

### 3. Update Master TODO

**Prioritize**:
1. Optimize 1800 ORB (best performer)
2. Optimize 2300 ORB (high frequency, large ORBs)
3. Optimize 1100 ORB (large ORBs)
4. Optimize 0030 ORB (largest ORBs, lowest cost impact)

**Deprioritize** (but keep):
- 1000 ORB setups (execution-dependent)
- 0900 ORB setups (unprofitable)

---

## DOCUMENTATION CONVENTION

### Flag in validated_setups Table

**Add column**: `slippage_tier` (VARCHAR)

**Values**:
- `TIER1_ROBUST` - Survives 2.0t slippage (1800, 1100, 2300, 0030)
- `TIER2_MARGINAL` - Needs <1.0t slippage (1000)
- `TIER3_SKIP` - Unprofitable (0900)

### Flag in Research Files

**Header notation**:
```markdown
## Setup: 1800 ORB - London Open Breakout [TIER1_ROBUST]

## Setup: 1000 ORB - Mid-Morning [TIER2_MARGINAL - Good Execution Only]

## Setup: 0900 ORB - Asia Open [TIER3_SKIP - Do Not Trade]
```

---

## REMEMBER

**Don't forget about Tier 2/3**:
- Keep all data and analysis
- Revisit after Tier 1 optimized
- May find filters that make them work
- Execution quality may improve over time

**Focus on Tier 1**:
- 4 robust ORBs that survive worst-case
- Balance frequency + profitability
- Don't over-optimize for RR alone
- Aim for consistent, frequent edge

**Target outcome**:
- 600-1000 trades/year across 4 ORBs (150-250 each)
- Average net R: +0.060R (with 2.0t slippage)
- Overall expectancy: +36R to +60R per year
- Win rate: 60%+ average

---

**Created**: 2026-01-24
**Status**: Classification complete, ready for Tier 1 optimization
