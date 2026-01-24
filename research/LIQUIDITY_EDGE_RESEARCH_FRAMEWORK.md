# Liquidity-Driven Edge Research Framework

**Created**: 2026-01-24
**Authority**: CLAUDE.md, res.txt (research-only, no production changes)
**Status**: Research conceptual framework + testable workflow

---

## Executive Summary

This document provides a systematic framework for discovering new statistically valid edges by analyzing how **liquidity events** (session sweeps, cascades) interact with **ORB outcomes** across different timing windows.

**Core Insight**: The best MGC strategies are liquidity-driven (CASCADE: +1.95R, SINGLE_LIQ: +1.44R), significantly outperforming standard ORBs (+0.40-0.81R). This suggests **untapped edge potential** in liquidity event timing and sequence patterns.

---

## Part 1: Liquidity Classification System (Existing)

### Current Session Type Codes

Your codebase already classifies liquidity events using session type codes in `daily_features_v2` table:

#### Asia Session Types (relative to pre-Asia session):
- **A0_NORMAL**: Normal range session (172 days)
- **A2_EXPANDED**: Expanded range session (331 days)
- **None**: Weekend/holiday (237 days)

#### London Session Types (relative to Asia session):
- **L1_SWEEP_HIGH**: London high > Asia high (232 days) ← **Liquidity event**
- **L2_SWEEP_LOW**: London low < Asia low (165 days) ← **Liquidity event**
- **L3_EXPANSION**: Both highs AND lows taken (34 days) ← **Strong liquidity event**
- **L4_CONSOLIDATION**: Neither high nor low taken (90 days)
- **None**: Weekend/holiday (219 days)

#### Pre-NY Session Types (relative to London + Asia):
- **N1_SWEEP_HIGH**: Pre-NY high > max(London, Asia) (counted days)
- **N2_SWEEP_LOW**: Pre-NY low < min(London, Asia) (counted days)
- **N3_CONSOLIDATION**: Range < 0.25 ATR (tight)
- **N4_EXPANSION**: Range > 0.8 ATR (volatile)
- **N0_NORMAL**: Everything else

### Classification Logic (from `pipeline/build_daily_features_v2.py`):

```python
# London liquidity classification
def classify_london_code(london_high, london_low, asia_high, asia_low):
    took_high = london_high > asia_high
    took_low = london_low < asia_low
    if took_high and took_low:
        return "L3_EXPANSION"
    if took_high:
        return "L1_SWEEP_HIGH"
    if took_low:
        return "L2_SWEEP_LOW"
    return "L4_CONSOLIDATION"

# Pre-NY liquidity classification
def classify_pre_ny_code(pre_ny_high, pre_ny_low, london_high, london_low, asia_high, asia_low, atr_20):
    ref_high = max(london_high, asia_high)
    ref_low = min(london_low, asia_low)

    if pre_ny_high > ref_high and pre_ny_low >= ref_low:
        return "N1_SWEEP_HIGH"
    if pre_ny_low < ref_low and pre_ny_high <= ref_high:
        return "N2_SWEEP_LOW"
    # ... consolidation/expansion logic
    return "N0_NORMAL"
```

---

## Part 2: Validated Liquidity Edges (Existing)

### CASCADE_MULTI_LIQUIDITY (+1.95R avg, S+ tier)
- **Pattern**: London sweeps Asia → NY sweeps London (cascading accumulation)
- **Performance**: 19% WR, 69 trades, ~35 trades/year
- **RR**: 4.0
- **Stop**: DYNAMIC
- **Key insight**: **Sequential liquidity events** create strong directional bias

### SINGLE_LIQUIDITY (+1.44R avg, S tier)
- **Pattern**: Single London level swept at NY open (23:00 ORB)
- **Performance**: 34% WR, 118 trades, ~60 trades/year
- **RR**: 3.0
- **Stop**: DYNAMIC
- **Key insight**: **Clean single sweep** with favorable follow-through

### Asia Bias Filter (discovered conditional edge)
- **Impact**: Increases edge by 50-100% when applied to standard ORBs
- **Example**: 1000 ORB: +0.40R → +1.13R with asia_bias filter
- **Rule**: UP trades when price above Asia high, DOWN trades when price below Asia low
- **Key insight**: **Price position relative to session liquidity** matters enormously

---

## Part 3: Research Questions (Untested)

### Category A: Liquidity Event Timing Relative to ORBs

**Q1: Does liquidity event TIMING relative to ORB window matter?**
- Hypothesis: Sweeps BEFORE ORB formation create different edge than sweeps DURING or AFTER
- Test cases:
  - London sweep → 1800 ORB (sweep happens AS ORB forms)
  - London sweep → 2300 ORB (sweep 5 hours before ORB)
  - London sweep → 0030 ORB (sweep 6.5 hours before ORB)

**Q2: Do "fresh" liquidity events create stronger edges?**
- Hypothesis: Recently swept levels (within 1-2 hours) create stronger directional bias
- Test: Compare ORB outcomes when liquidity event is <1hr old vs 2-4hr old vs >4hr old

**Q3: Does liquidity event RECENCY cascade?**
- Hypothesis: Multiple recent sweeps (within 30-60 min) amplify edge
- Test: Compare single sweep vs dual sweep (both within 1hr of ORB)

### Category B: Liquidity Event Sequence Patterns

**Q4: What other CASCADE patterns exist beyond the validated one?**
- Validated: London sweeps Asia → NY sweeps London
- Untested variants:
  - Asia sweeps pre-Asia → London sweeps Asia → ORB
  - London consolidates → NY sweeps both Asia + London
  - Asia + London both expand (L3) → ORB

**Q5: Does sweep DIRECTION matter?**
- Hypothesis: Sweep direction (high vs low) interacts with ORB direction
- Test cases:
  - L1_SWEEP_HIGH → 1800 ORB UP (aligned)
  - L1_SWEEP_HIGH → 1800 ORB DOWN (counter-trend)
  - L2_SWEEP_LOW → 1800 ORB UP (counter-trend)
  - L2_SWEEP_LOW → 1800 ORB DOWN (aligned)

**Q6: Does consolidation AFTER sweep create edge?**
- Hypothesis: Sweep → consolidate → ORB breakout is stronger than sweep → immediate move
- Test: Compare L1/L2 → L4_CONSOLIDATION (Pre-NY) → ORB outcomes

### Category C: Multi-Level Liquidity Zones

**Q7: Do "stacked" liquidity levels (Asia + London converge) create stronger edges?**
- Hypothesis: When Asia high ≈ London high (within small range), sweeping both creates amplified edge
- Test: Compare standard sweep vs "stacked level" sweep

**Q8: Does liquidity DISTANCE matter?**
- Hypothesis: Large gap between Asia/London highs creates different edge than small gap
- Test: Measure distance (in ATR or points), correlate with ORB outcome

**Q9: Do "untested" levels create better ORB setups?**
- Hypothesis: If London consolidates (L4), leaving Asia highs/lows untested, ORB may target those levels
- Test: L4_CONSOLIDATION → ORB targeting Asia high/low

### Category D: Volatility Context

**Q10: Does session range SIZE interact with liquidity events?**
- Hypothesis: Expanded sessions (A2, L3, N4) + liquidity events create different edge
- Test: Compare standard liquidity events vs expanded-session liquidity events

**Q11: Does ATR context modulate liquidity edge?**
- Hypothesis: Liquidity events in low-volatility environments create stronger ORB edges
- Test: Stratify liquidity events by ATR_20 quintiles, compare ORB outcomes

**Q12: Does pre-ORB travel distance predict liquidity-driven ORB success?**
- Hypothesis: Large travel before ORB (already moving) + liquidity alignment = stronger edge
- Test: pre_orb_travel > threshold + liquidity event vs no travel

### Category E: Time-of-Day Interactions

**Q13: Which ORB times capture liquidity events best?**
- Hypothesis: Different ORBs have different optimal liquidity patterns
- Test matrix:
  - 0900 ORB: Best after Asia liquidity events?
  - 1000 ORB: Best after Asia + early London events?
  - 1100 ORB: Best after Asia + London consolidation?
  - 1800 ORB: Captures London open liquidity directly
  - 2300 ORB: Best after London sweep + consolidation?
  - 0030 ORB: Best after full cascade pattern?

**Q14: Does day-of-week interact with liquidity patterns?**
- Hypothesis: Monday/Friday liquidity events behave differently (week start/end effects)
- Test: Stratify liquidity events by day of week

---

## Part 4: Research Workflow (Incremental, Safe)

### Phase 1: Liquidity Event Inventory (Data Exploration)

**Goal**: Understand what liquidity patterns exist in the data

**Method**:
1. Query `daily_features_v2` for all session type codes
2. Build frequency distributions:
   - Single events (L1, L2, N1, N2)
   - Combinations (L1 + N1, L2 + N0, etc.)
   - Cascade patterns (L1 → N1, L2 → N2)
3. Visualize timing patterns (heatmaps, sequence diagrams)

**Output**: Liquidity event catalog (CSV or JSON)

**Code sketch**:
```python
# research/liquidity_event_inventory.py
import duckdb
import pandas as pd

con = duckdb.connect("data/db/gold.db", read_only=True)

# Get all session patterns
df = con.execute("""
    SELECT
        date_local,
        asia_type_code,
        london_type_code,
        pre_ny_type_code,
        asia_high, asia_low,
        london_high, london_low,
        pre_ny_high, pre_ny_low,
        -- All ORB outcomes
        orb_0900_break_dir, orb_0900_outcome, orb_0900_r_multiple,
        orb_1000_break_dir, orb_1000_outcome, orb_1000_r_multiple,
        orb_1800_break_dir, orb_1800_outcome, orb_1800_r_multiple,
        orb_2300_break_dir, orb_2300_outcome, orb_2300_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND asia_type_code IS NOT NULL
    ORDER BY date_local
""").df()

# Derive composite patterns
df['london_sweep'] = df['london_type_code'].apply(lambda x: 'SWEEP' if x in ['L1_SWEEP_HIGH', 'L2_SWEEP_LOW'] else 'NO_SWEEP')
df['pre_ny_sweep'] = df['pre_ny_type_code'].apply(lambda x: 'SWEEP' if x in ['N1_SWEEP_HIGH', 'N2_SWEEP_LOW'] else 'NO_SWEEP')
df['cascade_pattern'] = df['london_sweep'] + '_' + df['pre_ny_sweep']

# Frequency analysis
print("Cascade pattern distribution:")
print(df['cascade_pattern'].value_counts())

# Save for later analysis
df.to_csv("research/outputs/liquidity_event_inventory.csv", index=False)
```

**Safety**: Read-only queries, no database modifications

---

### Phase 2: Liquidity-ORB Association (Statistical Testing)

**Goal**: Test which liquidity patterns correlate with better ORB outcomes

**Method**:
1. For each liquidity pattern, compute ORB outcome statistics:
   - Win rate
   - Average R
   - Trade count
   - Break direction bias
2. Compare to baseline (no liquidity event)
3. Rank patterns by edge magnitude
4. Apply statistical significance tests (t-test, bootstrap)

**Output**: Ranked liquidity patterns with statistical confidence

**Code sketch**:
```python
# research/liquidity_orb_association.py
import duckdb
import pandas as pd
from scipy import stats

con = duckdb.connect("data/db/gold.db", read_only=True)

# Test: Does L1_SWEEP_HIGH improve 1800 ORB outcomes?
result = con.execute("""
    SELECT
        london_type_code,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r,
        STDDEV(orb_1800_r_multiple) as std_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW', 'L4_CONSOLIDATION')
    GROUP BY london_type_code
""").fetchall()

for row in result:
    print(f"{row[0]}: WR={row[2]:.1%}, AvgR={row[3]:+.3f}, n={row[1]}")

# Statistical test: Is L1_SWEEP_HIGH different from baseline?
sweep_high_r = con.execute("""
    SELECT orb_1800_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code = 'L1_SWEEP_HIGH'
      AND orb_1800_outcome IS NOT NULL
""").fetchdf()['orb_1800_r_multiple'].values

baseline_r = con.execute("""
    SELECT orb_1800_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code = 'L4_CONSOLIDATION'
      AND orb_1800_outcome IS NOT NULL
""").fetchdf()['orb_1800_r_multiple'].values

t_stat, p_value = stats.ttest_ind(sweep_high_r, baseline_r)
print(f"\nt-test: t={t_stat:.2f}, p={p_value:.4f}")
if p_value < 0.05:
    print("✓ Statistically significant edge")
else:
    print("✗ Not statistically significant")
```

**Safety**: Read-only analysis, results saved to CSV

---

### Phase 3: Timing Window Analysis (Liquidity Event Age)

**Goal**: Determine if liquidity event RECENCY matters

**Method**:
1. Calculate time delta between liquidity event and ORB start
   - London session ends ~18:00, 1800 ORB is 18:00-18:05 (0-5 min old)
   - London session ends ~18:00, 2300 ORB is 23:00-23:05 (5 hours old)
2. Stratify ORB outcomes by liquidity event "age"
3. Test hypothesis: fresher liquidity = stronger edge

**Output**: Optimal timing windows for each liquidity pattern

**Code sketch**:
```python
# research/liquidity_timing_analysis.py

# Define approximate session end times (Brisbane local)
SESSION_ENDS = {
    'asia': 17,      # 17:00
    'london': 23,    # 23:00 (end of London session relative to Brisbane)
    'pre_ny': 23     # 23:00 (NY cash open)
}

ORB_TIMES = {
    'orb_0900': 9,
    'orb_1000': 10,
    'orb_1100': 11,
    'orb_1800': 18,
    'orb_2300': 23,
    'orb_0030': 0.5
}

# Compute "liquidity event age" for each ORB
# Example: London sweep at 18:00 → 2300 ORB at 23:00 → 5 hours old
def compute_liquidity_age(session_end_hour, orb_hour):
    delta = orb_hour - session_end_hour
    if delta < 0:
        delta += 24  # Handle overnight
    return delta

# Test: 1800 ORB after London sweep (0-5 min old) vs 2300 ORB after London sweep (5 hrs old)
# Expected: 1800 ORB should have stronger edge (fresher liquidity)

result = con.execute("""
    SELECT
        'orb_1800' as orb_name,
        london_type_code,
        AVG(orb_1800_r_multiple) as avg_r,
        COUNT(*) as trades
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
    GROUP BY london_type_code

    UNION ALL

    SELECT
        'orb_2300' as orb_name,
        london_type_code,
        AVG(orb_2300_r_multiple) as avg_r,
        COUNT(*) as trades
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_2300_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
    GROUP BY london_type_code
""").fetchall()

for row in result:
    print(f"{row[0]} + {row[1]}: AvgR={row[2]:+.3f}, n={row[3]}")
```

**Safety**: Read-only analysis

---

### Phase 4: Cascade Pattern Discovery (Sequence Mining)

**Goal**: Find new multi-stage liquidity patterns beyond the validated CASCADE

**Method**:
1. Enumerate all 2-stage and 3-stage patterns:
   - 2-stage: (Asia type, London type)
   - 3-stage: (Asia type, London type, Pre-NY type)
2. For each pattern, compute ORB outcomes across all ORBs
3. Rank by edge magnitude
4. Filter for statistical significance + minimum trade count

**Output**: Candidate cascade patterns for validation

**Code sketch**:
```python
# research/cascade_pattern_discovery.py
import duckdb
import pandas as pd
from itertools import product

con = duckdb.connect("data/db/gold.db", read_only=True)

# Get all unique type codes
asia_types = ['A0_NORMAL', 'A2_EXPANDED']
london_types = ['L1_SWEEP_HIGH', 'L2_SWEEP_LOW', 'L3_EXPANSION', 'L4_CONSOLIDATION']
pre_ny_types = ['N0_NORMAL', 'N1_SWEEP_HIGH', 'N2_SWEEP_LOW', 'N3_CONSOLIDATION', 'N4_EXPANSION']

# Test all 3-stage combinations
results = []
for asia, london, pre_ny in product(asia_types, london_types, pre_ny_types):
    # Test pattern against 2300 ORB (most common)
    result = con.execute("""
        SELECT
            COUNT(*) as trades,
            AVG(CASE WHEN orb_2300_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
            AVG(orb_2300_r_multiple) as avg_r
        FROM daily_features_v2
        WHERE instrument = 'MGC'
          AND asia_type_code = ?
          AND london_type_code = ?
          AND pre_ny_type_code = ?
          AND orb_2300_outcome IS NOT NULL
    """, [asia, london, pre_ny]).fetchone()

    trades, wr, avg_r = result
    if trades >= 20:  # Minimum sample size
        results.append({
            'pattern': f"{asia} → {london} → {pre_ny}",
            'trades': trades,
            'win_rate': wr,
            'avg_r': avg_r
        })

# Rank by avg_r
df_results = pd.DataFrame(results)
df_results = df_results.sort_values('avg_r', ascending=False)

print("Top 10 cascade patterns (2300 ORB):")
print(df_results.head(10))

df_results.to_csv("research/outputs/cascade_patterns_2300.csv", index=False)
```

**Safety**: Read-only, results saved to CSV for review

---

### Phase 5: Direction Alignment Testing

**Goal**: Test if liquidity sweep direction (high vs low) interacts with ORB break direction

**Method**:
1. For each liquidity pattern, stratify by ORB direction:
   - L1_SWEEP_HIGH → ORB breaks UP (aligned)
   - L1_SWEEP_HIGH → ORB breaks DOWN (counter-trend)
2. Compute edge for each alignment scenario
3. Test hypothesis: aligned patterns have stronger edges

**Output**: Direction alignment matrix (liquidity direction × ORB direction)

**Code sketch**:
```python
# research/direction_alignment_analysis.py

# Test: Does L1_SWEEP_HIGH (bullish) improve UP breaks more than DOWN breaks?
result = con.execute("""
    SELECT
        london_type_code,
        orb_1800_break_dir,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND orb_1800_break_dir IN ('UP', 'DOWN')
      AND orb_1800_outcome IS NOT NULL
    GROUP BY london_type_code, orb_1800_break_dir
    ORDER BY london_type_code, orb_1800_break_dir
""").fetchall()

print("Direction alignment matrix (1800 ORB):")
print(f"{'Liquidity':<20} {'ORB Dir':<10} {'Trades':<10} {'WR%':<10} {'AvgR'}")
print("-" * 60)
for row in result:
    liq, dir_, trades, wr, avg_r = row
    print(f"{liq:<20} {dir_:<10} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}")

# Expected: L1_SWEEP_HIGH + UP should be stronger than L1_SWEEP_HIGH + DOWN
```

**Safety**: Read-only analysis

---

## Part 5: Edge Ranking & Promotion Criteria

### Criteria for "Strong Edge" (Legitimate Pattern Worth Remembering)

To avoid overfitting and ensure discovered patterns are tradeable:

#### 1. Statistical Significance
- **p-value < 0.05** (t-test vs baseline)
- **Effect size > 0.3** (Cohen's d)
- **Confidence interval** excludes zero

#### 2. Sample Size
- **Minimum 30 trades** (preferably 50+)
- **At least 1 year of data** (avoid seasonal flukes)
- **Consistent across years** (not just 2024 anomaly)

#### 3. Economic Significance
- **AvgR > +0.50R** (meaningful edge over baseline)
- **Win rate ≥ 18%** (for RR=4-6 setups) or ≥ 25% (for RR=2-3 setups)
- **Annual trade frequency ≥ 15** (enough opportunities to matter)

#### 4. Robustness Checks
- **Out-of-sample validation**: Test on different time periods
- **Instrument validation**: Does edge exist in NQ or MPL?
- **Parameter sensitivity**: Edge holds with small parameter variations

#### 5. Logical Coherence
- **Market microstructure explanation**: Why would this pattern work?
- **Liquidity narrative**: Does the pattern align with known liquidity dynamics?
- **No data mining artifacts**: Pattern makes intuitive sense

### Promotion Process

When a pattern meets ALL criteria above:

1. **Document the edge**:
   - Pattern description (plain English)
   - Statistical evidence (metrics, p-values)
   - Sample trades (show 5-10 real examples)
   - Market logic explanation

2. **Create research report**:
   - `research/outputs/EDGE_DISCOVERY_[pattern_name]_[date].md`
   - Include all supporting data
   - Add to `LEGITIMATE_EDGES_CATALOG.md` (create if doesn't exist)

3. **Backtest with zero-lookahead engine**:
   - Use `research/candidate_backtest_engine.py`
   - Verify edge with strict no-lookahead enforcement
   - Confirm results match exploratory analysis

4. **Add to edge_candidates table** (research database, NOT production):
   - Store as candidate for future validation
   - Track performance over time (forward-testing)

5. **ONLY IF edge proves durable over 3-6 months**:
   - Consider promoting to `validated_setups` (production)
   - Update `trading_app/config.py`
   - Run `python test_app_sync.py`

**IMPORTANT**: Do NOT shortcut to production. Research → Validation → Production is a one-way gate.

---

## Part 6: Legitimate Edges Discovered (Running Log)

### Edge #1: Asia Bias Filter (VALIDATED, IN PRODUCTION)

**Pattern**: ORB direction aligned with price position relative to Asia session
- **Rule**: UP trades only when price > Asia high; DOWN trades only when price < Asia low
- **Impact**: +50-100% edge improvement (e.g., 1000 ORB: +0.40R → +1.13R)
- **Statistical significance**: p < 0.001
- **Sample size**: 198+ trades per variant
- **Status**: ✅ Integrated into validated_setups (condition_type='asia_bias')
- **Market logic**: Price above Asia range indicates bullish liquidity positioning; breakouts aligned with this bias have higher follow-through

### Edge #2: CASCADE_MULTI_LIQUIDITY (VALIDATED, NOT INTEGRATED)

**Pattern**: London sweeps Asia levels → NY sweeps London levels (cascading liquidity accumulation)
- **Performance**: +1.95R avg, 19% WR, 69 trades
- **Statistical significance**: p < 0.01 (vs baseline ORBs)
- **Sample size**: 69 trades (~35/year)
- **Status**: ✅ Validated in database, ⏸️ Awaiting SessionLiquidity integration
- **Market logic**: Sequential liquidity grabs indicate strong directional intent; cascading sweeps amplify momentum

### Edge #3: SINGLE_LIQUIDITY (VALIDATED, NOT INTEGRATED)

**Pattern**: Single London level swept at NY open (23:00 ORB entry)
- **Performance**: +1.44R avg, 34% WR, 118 trades
- **Statistical significance**: p < 0.01
- **Sample size**: 118 trades (~60/year)
- **Status**: ✅ Validated in database, ⏸️ Awaiting SessionLiquidity integration
- **Market logic**: Clean single-side liquidity grab with no counter-sweep indicates one-sided auction; ORB captures continuation

### Edge #4: [To be discovered]

**Pattern**: TBD
- Use this framework to discover and document new edges
- Follow promotion criteria rigorously
- Add to this log when validated

---

## Part 7: Research Execution Plan (Incremental)

### Week 1: Data Exploration
- ✅ Run `research/liquidity_event_inventory.py`
- ✅ Review liquidity pattern distributions
- ✅ Visualize cascade sequences (optional: matplotlib heatmaps)

### Week 2: Statistical Testing
- ✅ Run `research/liquidity_orb_association.py` for all ORBs
- ✅ Rank patterns by AvgR
- ✅ Filter for statistical significance (p < 0.05)
- ✅ Document top 10 patterns

### Week 3: Timing Analysis
- ✅ Run `research/liquidity_timing_analysis.py`
- ✅ Test "liquidity freshness" hypothesis
- ✅ Identify optimal ORB times for each liquidity pattern

### Week 4: Cascade Discovery
- ✅ Run `research/cascade_pattern_discovery.py`
- ✅ Enumerate all 3-stage patterns
- ✅ Compare to validated CASCADE pattern
- ✅ Document promising candidates

### Week 5: Direction Alignment
- ✅ Run `research/direction_alignment_analysis.py`
- ✅ Test sweep direction × ORB direction interaction
- ✅ Quantify "aligned" vs "counter-trend" edges

### Week 6: Validation & Reporting
- ✅ Select top 3-5 candidates from weeks 1-5
- ✅ Run zero-lookahead backtests
- ✅ Write research reports
- ✅ Add to LEGITIMATE_EDGES_CATALOG.md

---

## Part 8: Important Constraints & Reminders

### DO NOT:
- ❌ Modify `validated_setups` table (production)
- ❌ Change `trading_app/config.py` (production)
- ❌ Touch `daily_features_v2` schema (canonical data)
- ❌ Add columns to production tables
- ❌ Assume patterns are real without statistical tests
- ❌ Promote edges to production without 3-6 month validation

### DO:
- ✅ Use read-only database connections
- ✅ Save research outputs to `research/outputs/` folder
- ✅ Write analysis scripts in `research/` directory
- ✅ Test statistical significance (p-values, effect sizes)
- ✅ Document all edges in markdown format
- ✅ Use existing `candidate_backtest_engine.py` for validation
- ✅ Think incrementally: explore → test → validate → promote
- ✅ Keep RR target flexible (don't lock into RR=8.0 prematurely)

### On RR Targets:
The backtest research showed RR=8.0 variants perform well, BUT:
- This is ONE observation from ONE dataset
- RR=6.0 also performs well (sometimes better win rate)
- RR=4.0 works for CASCADE strategies
- **DO NOT recommend RR=8.0 as "optimal" without more research**
- Instead: "RR=6-8 show promise; test which works best for YOUR edge"

---

## Part 9: Next Steps (Your Choice)

### Option A: Run Phase 1 (Data Exploration)
Create and run `research/liquidity_event_inventory.py` to see what liquidity patterns exist.

### Option B: Jump to Specific Question
Pick any research question from Part 3, write a quick analysis script, test it.

### Option C: Cascade Discovery
Focus on finding new cascade patterns (Phase 4) since validated CASCADE has best edge.

### Option D: Direction Alignment
Test if liquidity direction (sweep high vs low) matters for ORB outcomes.

### Option E: Custom Research
You know the framework—explore your own hypothesis!

---

## Summary

**What you have**:
- Session type classification system (already in data)
- 2 validated liquidity edges (CASCADE: +1.95R, SINGLE_LIQ: +1.44R)
- 1 validated conditional edge (asia_bias filter: +50-100% improvement)
- 740 days of clean MGC data ready for analysis

**What you can discover**:
- New cascade patterns beyond the validated one
- Optimal timing windows for liquidity events
- Direction alignment effects (sweep high vs low)
- Stacked level patterns (converging session highs/lows)
- Volatility-modulated liquidity edges

**How to discover safely**:
- Read-only queries on existing data
- Statistical testing (t-tests, bootstrap, effect sizes)
- Promotion criteria (significance + sample size + robustness + logic)
- Document everything in `LEGITIMATE_EDGES_CATALOG.md`
- Validate with zero-lookahead backtests before production

**Key insight**:
Liquidity-driven edges are 3-5x stronger than standard ORBs. Your data already classifies liquidity events—you just need to mine it systematically.

---

**Authority**: CLAUDE.md (canonical data model), res.txt (research-only constraints)
**Status**: Framework ready, execution pending
**Risk**: LOW (read-only analysis, no production changes)
