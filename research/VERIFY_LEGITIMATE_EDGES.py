#!/usr/bin/env python3
"""
VERIFICATION SCRIPT: Test if claimed edges are REAL or fake

DO NOT TRUST OLD FILES. Test robustness and honesty ourselves.

Authority: CLAUDE.md (daily_features_v2 is canonical)
"""

import duckdb
from pathlib import Path
from scipy import stats
import numpy as np

DB_PATH = Path(__file__).parent.parent / "data/db/gold.db"
con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 80)
print("EDGE VERIFICATION: Testing if claimed edges are LEGITIMATE")
print("=" * 80)

# ============================================================================
# TEST 1: Verify we're using daily_features_v2 (NOT v1)
# ============================================================================
print("\n[TEST 1] Verify canonical table is daily_features_v2:")

tables = con.execute("SHOW TABLES").fetchall()
table_names = [t[0] for t in tables]

if 'daily_features_v2' in table_names:
    print("  [OK] daily_features_v2 EXISTS")
else:
    print("  [FAIL] daily_features_v2 MISSING - CRITICAL ERROR")
    exit(1)

if 'daily_features' in table_names:
    row_count = con.execute("SELECT COUNT(*) FROM daily_features").fetchone()[0]
    print(f"  [WARN] daily_features EXISTS with {row_count} rows (should be deleted)")
else:
    print("  [OK] daily_features does NOT exist (correct)")

# Check v2 has data
v2_count = con.execute("SELECT COUNT(*) FROM daily_features_v2 WHERE instrument='MGC'").fetchone()[0]
print(f"  [OK] daily_features_v2 has {v2_count} MGC rows")

# ============================================================================
# TEST 2: Verify session type codes exist and are populated
# ============================================================================
print("\n[TEST 2] Verify session type codes are populated:")

type_code_counts = con.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(asia_type_code) as asia_populated,
        COUNT(london_type_code) as london_populated,
        COUNT(pre_ny_type_code) as pre_ny_populated
    FROM daily_features_v2
    WHERE instrument = 'MGC'
""").fetchone()

total, asia_pop, london_pop, pre_ny_pop = type_code_counts
print(f"  Total MGC rows: {total}")
print(f"  Asia type codes populated: {asia_pop} ({asia_pop/total*100:.1f}%)")
print(f"  London type codes populated: {london_pop} ({london_pop/total*100:.1f}%)")
print(f"  Pre-NY type codes populated: {pre_ny_pop} ({pre_ny_pop/total*100:.1f}%)")

if asia_pop / total < 0.6:
    print("  [WARN] WARNING: Low asia_type_code coverage")

# ============================================================================
# TEST 3: Verify CASCADE/SINGLE_LIQ setups exist in validated_setups
# ============================================================================
print("\n[TEST 3] Verify CASCADE/SINGLE_LIQ setups exist:")

cascade_setup = con.execute("""
    SELECT setup_id, win_rate, avg_r, trades, tier, notes
    FROM validated_setups
    WHERE instrument = 'MGC'
      AND setup_id LIKE '%CASCADE%'
""").fetchall()

if cascade_setup:
    for row in cascade_setup:
        print(f"  [OK] {row[0]}: WR={row[1]:.0f}%, AvgR={row[2]:+.2f}R, trades={row[3]}, tier={row[4]}")
else:
    print("  [FAIL] NO CASCADE SETUP FOUND in validated_setups")

single_liq_setup = con.execute("""
    SELECT setup_id, win_rate, avg_r, trades, tier, notes
    FROM validated_setups
    WHERE instrument = 'MGC'
      AND setup_id LIKE '%SINGLE_LIQUIDITY%'
""").fetchall()

if single_liq_setup:
    for row in single_liq_setup:
        print(f"  [OK] {row[0]}: WR={row[1]:.0f}%, AvgR={row[2]:+.2f}R, trades={row[3]}, tier={row[4]}")
else:
    print("  [FAIL] NO SINGLE_LIQUIDITY SETUP FOUND in validated_setups")

# ============================================================================
# TEST 4: VERIFY CASCADE EDGE IS REAL (not just claimed)
# ============================================================================
print("\n[TEST 4] VERIFY CASCADE EDGE: Test if multi-liquidity pattern is REAL:")

# We can't directly test CASCADE since it's not a simple column
# But we can test if the PATTERN (London sweep → Pre-NY sweep) actually correlates with better outcomes

# Test: Do sequential sweeps (L1/L2 → N1/N2) perform better than no sweeps?
sequential_sweeps = con.execute("""
    SELECT
        AVG(orb_2300_r_multiple) as avg_r,
        STDDEV(orb_2300_r_multiple) as std_r,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_2300_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND pre_ny_type_code IN ('N1_SWEEP_HIGH', 'N2_SWEEP_LOW')
      AND orb_2300_outcome IS NOT NULL
""").fetchone()

no_sweeps = con.execute("""
    SELECT
        AVG(orb_2300_r_multiple) as avg_r,
        STDDEV(orb_2300_r_multiple) as std_r,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_2300_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND london_type_code = 'L4_CONSOLIDATION'
      AND pre_ny_type_code = 'N0_NORMAL'
      AND orb_2300_outcome IS NOT NULL
""").fetchone()

print(f"  Sequential sweeps (London + Pre-NY): AvgR={sequential_sweeps[0]:+.3f}, WR={sequential_sweeps[3]*100:.1f}%, n={sequential_sweeps[2]}")
print(f"  No sweeps (consolidation): AvgR={no_sweeps[0]:+.3f}, WR={no_sweeps[3]*100:.1f}%, n={no_sweeps[2]}")

# Statistical test
if sequential_sweeps[2] >= 20 and no_sweeps[2] >= 20:
    # Get individual r_multiples for t-test
    sweep_r = con.execute("""
        SELECT orb_2300_r_multiple
        FROM daily_features_v2
        WHERE instrument = 'MGC'
          AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
          AND pre_ny_type_code IN ('N1_SWEEP_HIGH', 'N2_SWEEP_LOW')
          AND orb_2300_outcome IS NOT NULL
    """).fetchdf()['orb_2300_r_multiple'].values

    no_sweep_r = con.execute("""
        SELECT orb_2300_r_multiple
        FROM daily_features_v2
        WHERE instrument = 'MGC'
          AND london_type_code = 'L4_CONSOLIDATION'
          AND pre_ny_type_code = 'N0_NORMAL'
          AND orb_2300_outcome IS NOT NULL
    """).fetchdf()['orb_2300_r_multiple'].values

    t_stat, p_value = stats.ttest_ind(sweep_r, no_sweep_r)
    print(f"  t-test: t={t_stat:.2f}, p={p_value:.4f}")

    if p_value < 0.05 and sequential_sweeps[0] > no_sweeps[0]:
        print("  [OK] LEGITIMATE EDGE: Sequential sweeps significantly better (p<0.05)")
    elif p_value < 0.10:
        print("  [WEAK] WEAK EDGE: Marginal significance (p<0.10)")
    else:
        print("  [FAIL] NOT SIGNIFICANT: Sequential sweeps not reliably better (p>=0.05)")
else:
    print("  [WARN] Sample size too small for statistical test")

# ============================================================================
# TEST 5: VERIFY ASIA BIAS FILTER IS REAL
# ============================================================================
print("\n[TEST 5] VERIFY ASIA BIAS FILTER: Test if asia_bias=ABOVE/BELOW is REAL:")

# We can't directly test asia_bias column (it's a condition, not stored)
# But we can test if the PATTERN (price position relative to Asia) matters

# Test: Does 1000 ORB UP work better when price is above Asia high?
# First, need to derive asia_bias from data

# For simplicity, test if ORB outcomes differ by whether ORB happened after price was above/below Asia range
# We'll use orb_1000 as test case (best regular ORB according to research)

print("  Testing 1000 ORB outcomes...")

# Get all 1000 ORB trades
orb_1000_data = con.execute("""
    SELECT
        date_local,
        orb_1000_break_dir,
        orb_1000_outcome,
        orb_1000_r_multiple,
        asia_high,
        asia_low,
        orb_1000_high,
        orb_1000_low
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1000_outcome IS NOT NULL
      AND orb_1000_break_dir IN ('UP', 'DOWN')
      AND asia_high IS NOT NULL
      AND asia_low IS NOT NULL
""").fetchdf()

# Derive asia_bias: Did ORB start above/below/inside Asia range?
# Use ORB low for UP breaks, ORB high for DOWN breaks as proxy for entry point
orb_1000_data['orb_entry_proxy'] = orb_1000_data.apply(
    lambda row: row['orb_1000_low'] if row['orb_1000_break_dir'] == 'UP' else row['orb_1000_high'],
    axis=1
)

orb_1000_data['asia_bias'] = orb_1000_data.apply(
    lambda row: 'ABOVE' if row['orb_entry_proxy'] > row['asia_high']
                else 'BELOW' if row['orb_entry_proxy'] < row['asia_low']
                else 'INSIDE',
    axis=1
)

# Test: UP breaks when ABOVE Asia vs INSIDE Asia
up_above = orb_1000_data[(orb_1000_data['orb_1000_break_dir'] == 'UP') & (orb_1000_data['asia_bias'] == 'ABOVE')]
up_inside = orb_1000_data[(orb_1000_data['orb_1000_break_dir'] == 'UP') & (orb_1000_data['asia_bias'] == 'INSIDE')]

if len(up_above) >= 10 and len(up_inside) >= 10:
    avg_r_above = up_above['orb_1000_r_multiple'].mean()
    avg_r_inside = up_inside['orb_1000_r_multiple'].mean()
    wr_above = (up_above['orb_1000_outcome'] == 'WIN').mean()
    wr_inside = (up_inside['orb_1000_outcome'] == 'WIN').mean()

    print(f"  1000 ORB UP + asia_bias=ABOVE: AvgR={avg_r_above:+.3f}, WR={wr_above*100:.1f}%, n={len(up_above)}")
    print(f"  1000 ORB UP + asia_bias=INSIDE: AvgR={avg_r_inside:+.3f}, WR={wr_inside*100:.1f}%, n={len(up_inside)}")

    # t-test
    t_stat, p_value = stats.ttest_ind(up_above['orb_1000_r_multiple'].values, up_inside['orb_1000_r_multiple'].values)
    print(f"  t-test: t={t_stat:.2f}, p={p_value:.4f}")

    if p_value < 0.05 and avg_r_above > avg_r_inside:
        print("  [OK] LEGITIMATE EDGE: Asia bias ABOVE significantly better for UP breaks (p<0.05)")
        improvement_pct = ((avg_r_above - avg_r_inside) / abs(avg_r_inside) * 100) if avg_r_inside != 0 else 0
        print(f"    Improvement: {improvement_pct:+.0f}%")
    elif p_value < 0.10:
        print("  [WEAK] WEAK EDGE: Marginal significance (p<0.10)")
    else:
        print("  [FAIL] NOT SIGNIFICANT: Asia bias filter not reliably better (p>=0.05)")
else:
    print("  [WARN] Insufficient sample size for asia_bias test")

# ============================================================================
# TEST 6: Check for data integrity issues
# ============================================================================
print("\n[TEST 6] Data integrity checks:")

# Check for suspicious patterns (all wins, all losses, etc.)
orb_1000_outcomes = con.execute("""
    SELECT
        orb_1000_outcome,
        COUNT(*) as cnt
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1000_outcome IS NOT NULL
    GROUP BY orb_1000_outcome
""").fetchall()

print("  1000 ORB outcome distribution:")
for outcome, cnt in orb_1000_outcomes:
    print(f"    {outcome}: {cnt}")

# Check if win rate is suspiciously high or low
win_count = sum(cnt for outcome, cnt in orb_1000_outcomes if outcome == 'WIN')
total_count = sum(cnt for outcome, cnt in orb_1000_outcomes)
win_rate = win_count / total_count if total_count > 0 else 0

if win_rate > 0.60:
    print(f"  [WARN] WARNING: Win rate ({win_rate*100:.1f}%) suspiciously high - check for lookahead bias")
elif win_rate < 0.10:
    print(f"  [WARN] WARNING: Win rate ({win_rate*100:.1f}%) suspiciously low - check for calculation errors")
else:
    print(f"  [OK] Win rate ({win_rate*100:.1f}%) seems reasonable")

# Check for duplicate dates
duplicates = con.execute("""
    SELECT date_local, COUNT(*) as cnt
    FROM daily_features_v2
    WHERE instrument = 'MGC'
    GROUP BY date_local
    HAVING COUNT(*) > 1
""").fetchall()

if duplicates:
    print(f"  [WARN] WARNING: {len(duplicates)} duplicate dates found")
    for date, cnt in duplicates[:5]:
        print(f"    {date}: {cnt} rows")
else:
    print("  [OK] No duplicate dates")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("VERIFICATION SUMMARY:")
print("=" * 80)
print("\nNext steps:")
print("1. Review results above - are claimed edges REAL or fake?")
print("2. If edges are NOT significant, DO NOT use them as building blocks")
print("3. If edges ARE significant, document exact parameters (sample size, p-value, effect size)")
print("4. Only use VERIFIED edges for future research")
print("\nAuthority: CLAUDE.md (daily_features_v2 canonical)")
print("Constraint: res.txt (research only, no production changes)")
print("=" * 80)

con.close()
