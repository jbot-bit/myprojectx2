#!/usr/bin/env python3
"""
TEST LIQUIDITY PATTERNS FROM SCRATCH

Option B: Start from first principles
- NO trust in validated_setups
- NO trust in unverified edges
- TEST everything ourselves with statistical rigor

Authority: CLAUDE.md (daily_features_v2 canonical)
Constraint: res.txt (verify robustness and honesty)
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DB_PATH = Path(__file__).parent.parent / "data/db/gold.db"
con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 80)
print("LIQUIDITY PATTERN TESTING - FROM FIRST PRINCIPLES")
print("=" * 80)
print("\nTesting simple hypotheses with statistical rigor")
print("Building up from VERIFIED patterns only\n")

# ============================================================================
# TEST 1: Does ANY London liquidity event matter?
# ============================================================================
print("\n" + "=" * 80)
print("TEST 1: Does London sweep (ANY direction) improve ORB outcomes?")
print("=" * 80)

# Hypothesis: Days when London sweeps Asia levels (L1 or L2) have better ORB outcomes

# Test on 1800 ORB (London sweep happens AS ORB forms)
result = con.execute("""
    SELECT
        CASE
            WHEN london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW') THEN 'SWEEP'
            WHEN london_type_code = 'L4_CONSOLIDATION' THEN 'CONSOLIDATION'
            ELSE 'OTHER'
        END as pattern,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r,
        STDDEV(orb_1800_r_multiple) as std_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IS NOT NULL
    GROUP BY pattern
    ORDER BY avg_r DESC
""").fetchall()

print("\n1800 ORB outcomes by London pattern:")
print(f"{'Pattern':<20} {'Trades':<10} {'Win Rate':<12} {'Avg R':<10} {'Std R'}")
print("-" * 70)
for row in result:
    pattern, trades, wr, avg_r, std_r = row
    print(f"{pattern:<20} {trades:<10} {wr*100:<12.1f} {avg_r:<10.3f} {std_r:.3f}")

# Statistical test: SWEEP vs CONSOLIDATION
sweep_data = con.execute("""
    SELECT orb_1800_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
""").fetchdf()['orb_1800_r_multiple'].values

consolidation_data = con.execute("""
    SELECT orb_1800_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code = 'L4_CONSOLIDATION'
""").fetchdf()['orb_1800_r_multiple'].values

if len(sweep_data) >= 20 and len(consolidation_data) >= 20:
    t_stat, p_value = stats.ttest_ind(sweep_data, consolidation_data)
    effect_size = (np.mean(sweep_data) - np.mean(consolidation_data)) / np.sqrt((np.var(sweep_data) + np.var(consolidation_data)) / 2)

    print(f"\nStatistical test (SWEEP vs CONSOLIDATION):")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value: {p_value:.4f}")
    print(f"  Effect size (Cohen's d): {effect_size:.3f}")

    if p_value < 0.05:
        print(f"  [SIGNIFICANT] Edge is real (p < 0.05)")
        if effect_size > 0.3:
            print(f"  [STRONG EFFECT] Effect size > 0.3 (meaningful)")
        else:
            print(f"  [WEAK EFFECT] Effect size < 0.3 (marginal)")
    elif p_value < 0.10:
        print(f"  [MARGINAL] Weak evidence (0.05 <= p < 0.10)")
    else:
        print(f"  [NOT SIGNIFICANT] No evidence of edge (p >= 0.10)")
else:
    print(f"\n[SKIP] Insufficient sample size for statistical test")

# ============================================================================
# TEST 2: Does London sweep DIRECTION matter?
# ============================================================================
print("\n" + "=" * 80)
print("TEST 2: Does London sweep DIRECTION (high vs low) matter?")
print("=" * 80)

# Hypothesis: L1_SWEEP_HIGH creates bullish bias, L2_SWEEP_LOW creates bearish bias

result = con.execute("""
    SELECT
        london_type_code,
        orb_1800_break_dir,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND orb_1800_break_dir IN ('UP', 'DOWN')
    GROUP BY london_type_code, orb_1800_break_dir
    ORDER BY london_type_code, orb_1800_break_dir
""").fetchall()

print("\n1800 ORB outcomes by sweep direction:")
print(f"{'Sweep Type':<20} {'ORB Dir':<10} {'Trades':<10} {'Win Rate':<12} {'Avg R'}")
print("-" * 70)
for row in result:
    sweep, orb_dir, trades, wr, avg_r = row
    print(f"{sweep:<20} {orb_dir:<10} {trades:<10} {wr*100:<12.1f} {avg_r:+.3f}")

# Test alignment: L1_SWEEP_HIGH + UP vs L1_SWEEP_HIGH + DOWN
l1_up = con.execute("""
    SELECT orb_1800_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code = 'L1_SWEEP_HIGH'
      AND orb_1800_break_dir = 'UP'
      AND orb_1800_outcome IS NOT NULL
""").fetchdf()['orb_1800_r_multiple'].values

l1_down = con.execute("""
    SELECT orb_1800_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code = 'L1_SWEEP_HIGH'
      AND orb_1800_break_dir = 'DOWN'
      AND orb_1800_outcome IS NOT NULL
""").fetchdf()['orb_1800_r_multiple'].values

if len(l1_up) >= 10 and len(l1_down) >= 10:
    t_stat, p_value = stats.ttest_ind(l1_up, l1_down)
    print(f"\nStatistical test (L1_SWEEP_HIGH: UP vs DOWN):")
    print(f"  UP (aligned): n={len(l1_up)}, mean={np.mean(l1_up):.3f}R")
    print(f"  DOWN (counter): n={len(l1_down)}, mean={np.mean(l1_down):.3f}R")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value: {p_value:.4f}")

    if p_value < 0.05:
        print(f"  [SIGNIFICANT] Direction alignment matters (p < 0.05)")
    else:
        print(f"  [NOT SIGNIFICANT] No evidence direction matters (p >= 0.05)")

# ============================================================================
# TEST 3: Does liquidity event TIMING matter? (1800 vs 2300 ORB)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 3: Does liquidity TIMING matter? (fresh vs aged)")
print("=" * 80)

# Hypothesis: London sweep at 1800 ORB (0 min old) > London sweep at 2300 ORB (5 hrs old)

result = con.execute("""
    SELECT
        'orb_1800' as orb_time,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')

    UNION ALL

    SELECT
        'orb_2300' as orb_time,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_2300_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_2300_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_2300_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
""").fetchall()

print("\nLondon sweep outcomes by ORB time (liquidity age):")
print(f"{'ORB Time':<15} {'Liquidity Age':<20} {'Trades':<10} {'Win Rate':<12} {'Avg R'}")
print("-" * 75)
for row in result:
    orb_time, trades, wr, avg_r = row
    age = "FRESH (0-5 min)" if orb_time == 'orb_1800' else "AGED (5 hours)"
    print(f"{orb_time:<15} {age:<20} {trades:<10} {wr*100:<12.1f} {avg_r:+.3f}")

# Statistical test
orb_1800_sweep = con.execute("""
    SELECT orb_1800_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND orb_1800_outcome IS NOT NULL
""").fetchdf()['orb_1800_r_multiple'].values

orb_2300_sweep = con.execute("""
    SELECT orb_2300_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND orb_2300_outcome IS NOT NULL
""").fetchdf()['orb_2300_r_multiple'].values

if len(orb_1800_sweep) >= 20 and len(orb_2300_sweep) >= 20:
    t_stat, p_value = stats.ttest_ind(orb_1800_sweep, orb_2300_sweep)
    print(f"\nStatistical test (1800 FRESH vs 2300 AGED):")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value: {p_value:.4f}")

    if p_value < 0.05:
        print(f"  [SIGNIFICANT] Liquidity freshness matters (p < 0.05)")
    else:
        print(f"  [NOT SIGNIFICANT] No evidence freshness matters (p >= 0.05)")

# ============================================================================
# TEST 4: Do SEQUENTIAL sweeps (cascade) work better?
# ============================================================================
print("\n" + "=" * 80)
print("TEST 4: Do SEQUENTIAL sweeps (cascade pattern) work better?")
print("=" * 80)

# Hypothesis: London sweep → Pre-NY sweep (sequential) > single sweep

result = con.execute("""
    SELECT
        CASE
            WHEN london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
                 AND pre_ny_type_code IN ('N1_SWEEP_HIGH', 'N2_SWEEP_LOW')
                THEN 'SEQUENTIAL_SWEEPS'
            WHEN london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
                 AND pre_ny_type_code = 'N0_NORMAL'
                THEN 'SINGLE_SWEEP'
            ELSE 'NO_SWEEP'
        END as pattern,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_2300_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_2300_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_2300_outcome IS NOT NULL
      AND london_type_code IS NOT NULL
      AND pre_ny_type_code IS NOT NULL
    GROUP BY pattern
    ORDER BY avg_r DESC
""").fetchall()

print("\n2300 ORB outcomes by cascade pattern:")
print(f"{'Pattern':<25} {'Trades':<10} {'Win Rate':<12} {'Avg R'}")
print("-" * 60)
for row in result:
    pattern, trades, wr, avg_r = row
    print(f"{pattern:<25} {trades:<10} {wr*100:<12.1f} {avg_r:+.3f}")

# Statistical test: SEQUENTIAL vs SINGLE
sequential = con.execute("""
    SELECT orb_2300_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND pre_ny_type_code IN ('N1_SWEEP_HIGH', 'N2_SWEEP_LOW')
      AND orb_2300_outcome IS NOT NULL
""").fetchdf()['orb_2300_r_multiple'].values

single = con.execute("""
    SELECT orb_2300_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND pre_ny_type_code = 'N0_NORMAL'
      AND orb_2300_outcome IS NOT NULL
""").fetchdf()['orb_2300_r_multiple'].values

if len(sequential) >= 20 and len(single) >= 20:
    t_stat, p_value = stats.ttest_ind(sequential, single)
    print(f"\nStatistical test (SEQUENTIAL vs SINGLE sweep):")
    print(f"  Sequential: n={len(sequential)}, mean={np.mean(sequential):.3f}R")
    print(f"  Single: n={len(single)}, mean={np.mean(single):.3f}R")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value: {p_value:.4f}")

    if p_value < 0.05 and np.mean(sequential) > np.mean(single):
        print(f"  [SIGNIFICANT] CASCADE pattern is REAL (p < 0.05)")
    else:
        print(f"  [NOT SIGNIFICANT] No evidence cascade works better (p >= 0.05)")

con.close()

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY: Which patterns are LEGITIMATE?")
print("=" * 80)
print("""
A pattern is LEGITIMATE if:
1. Statistical significance: p < 0.05 (t-test)
2. Effect size > 0.3 (Cohen's d)
3. Sample size >= 20 per group
4. Makes logical sense (market microstructure)

Only VERIFIED patterns should be used as building blocks for further research.

Next steps:
1. Review results above
2. Document VERIFIED edges in LEGITIMATE_EDGES_CATALOG.md
3. Test more specific hypotheses (direction alignment, spacing, etc.)
4. Build up from solid foundation
""")
print("=" * 80)
