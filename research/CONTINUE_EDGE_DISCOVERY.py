#!/usr/bin/env python3
"""
CONTINUE EDGE DISCOVERY - Building from verified foundation

We now have ONE verified edge: Direction Alignment (63% WR when aligned)

Next questions:
1. Does direction alignment work on OTHER ORBs?
2. Does it work better in low/high volatility?
3. What are the best specific cascade conditions?
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DB_PATH = Path(__file__).parent.parent / "data/db/gold.db"
con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 80)
print("CONTINUING EDGE DISCOVERY - Building from Verified Edge #1")
print("=" * 80)
print("\nVerified Edge #1: Direction Alignment (63% WR aligned, 33% counter)\n")

# ============================================================================
# TEST 5: Does direction alignment work on OTHER ORBs?
# ============================================================================
print("\n" + "=" * 80)
print("TEST 5: Does direction alignment work on OTHER ORBs?")
print("=" * 80)

# Test on 1000, 2300, 0030 ORBs
orbs_to_test = [
    ('orb_1000', '1000 ORB (2hrs after London)'),
    ('orb_2300', '2300 ORB (5hrs after London)'),
    ('orb_0030', '0030 ORB (6.5hrs after London)')
]

for orb_col, orb_name in orbs_to_test:
    print(f"\n{orb_name}:")
    print("-" * 60)

    result = con.execute(f"""
        SELECT
            london_type_code,
            {orb_col}_break_dir as orb_dir,
            COUNT(*) as trades,
            AVG(CASE WHEN {orb_col}_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
            AVG({orb_col}_r_multiple) as avg_r
        FROM daily_features_v2
        WHERE instrument = 'MGC'
          AND {orb_col}_outcome IS NOT NULL
          AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
          AND {orb_col}_break_dir IN ('UP', 'DOWN')
        GROUP BY london_type_code, orb_dir
        ORDER BY london_type_code, orb_dir
    """).fetchall()

    if result:
        print(f"{'Sweep':<20} {'ORB Dir':<10} {'Trades':<10} {'WR%':<10} {'Avg R'}")
        for row in result:
            sweep, orb_dir, trades, wr, avg_r = row
            # Determine if aligned
            aligned = (sweep == 'L1_SWEEP_HIGH' and orb_dir == 'UP') or \
                     (sweep == 'L2_SWEEP_LOW' and orb_dir == 'DOWN')
            marker = " [ALIGNED]" if aligned else " [COUNTER]"
            print(f"{sweep:<20} {orb_dir:<10} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}{marker}")

        # Calculate aligned vs counter averages
        aligned_wr = []
        counter_wr = []
        for row in result:
            sweep, orb_dir, trades, wr, avg_r = row
            if (sweep == 'L1_SWEEP_HIGH' and orb_dir == 'UP') or \
               (sweep == 'L2_SWEEP_LOW' and orb_dir == 'DOWN'):
                aligned_wr.append(wr)
            else:
                counter_wr.append(wr)

        if aligned_wr and counter_wr:
            print(f"  Summary: Aligned avg WR = {np.mean(aligned_wr)*100:.1f}%, Counter avg WR = {np.mean(counter_wr)*100:.1f}%")
            diff = (np.mean(aligned_wr) - np.mean(counter_wr)) * 100
            print(f"  Difference: {diff:+.1f} percentage points")
    else:
        print("  Insufficient data")

# ============================================================================
# TEST 6: Does direction alignment work better in specific volatility regimes?
# ============================================================================
print("\n" + "=" * 80)
print("TEST 6: Does direction alignment + volatility regime matter?")
print("=" * 80)

# Classify days by ATR percentile
result = con.execute("""
    WITH atr_percentiles AS (
        SELECT
            date_local,
            atr_20,
            NTILE(3) OVER (ORDER BY atr_20) as vol_tercile
        FROM daily_features_v2
        WHERE instrument = 'MGC'
          AND atr_20 IS NOT NULL
    )
    SELECT
        CASE
            WHEN a.vol_tercile = 1 THEN 'LOW_VOL'
            WHEN a.vol_tercile = 2 THEN 'MED_VOL'
            ELSE 'HIGH_VOL'
        END as vol_regime,
        CASE
            WHEN (d.london_type_code = 'L1_SWEEP_HIGH' AND d.orb_1800_break_dir = 'UP') OR
                 (d.london_type_code = 'L2_SWEEP_LOW' AND d.orb_1800_break_dir = 'DOWN')
                THEN 'ALIGNED'
            ELSE 'COUNTER'
        END as alignment,
        COUNT(*) as trades,
        AVG(CASE WHEN d.orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(d.orb_1800_r_multiple) as avg_r
    FROM daily_features_v2 d
    JOIN atr_percentiles a ON d.date_local = a.date_local
    WHERE d.instrument = 'MGC'
      AND d.orb_1800_outcome IS NOT NULL
      AND d.london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND d.orb_1800_break_dir IN ('UP', 'DOWN')
    GROUP BY vol_regime, alignment
    ORDER BY vol_regime, alignment
""").fetchall()

print("\n1800 ORB: Direction alignment by volatility regime:")
print(f"{'Vol Regime':<15} {'Alignment':<12} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 65)
for row in result:
    vol_regime, alignment, trades, wr, avg_r = row
    print(f"{vol_regime:<15} {alignment:<12} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}")

# ============================================================================
# TEST 7: Specific cascade conditions (aligned sweeps only)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 7: What specific CASCADE conditions work? (aligned sweeps only)")
print("=" * 80)

# Test: Does ALIGNED London sweep → ALIGNED Pre-NY sweep create stronger edge?
result = con.execute("""
    SELECT
        CASE
            -- Both sweeps aligned high
            WHEN london_type_code = 'L1_SWEEP_HIGH' AND pre_ny_type_code = 'N1_SWEEP_HIGH' AND orb_2300_break_dir = 'UP'
                THEN 'DOUBLE_SWEEP_HIGH_UP'
            -- Both sweeps aligned low
            WHEN london_type_code = 'L2_SWEEP_LOW' AND pre_ny_type_code = 'N2_SWEEP_LOW' AND orb_2300_break_dir = 'DOWN'
                THEN 'DOUBLE_SWEEP_LOW_DOWN'
            -- Single aligned sweep (London only)
            WHEN london_type_code = 'L1_SWEEP_HIGH' AND pre_ny_type_code IN ('N0_NORMAL', 'N3_CONSOLIDATION') AND orb_2300_break_dir = 'UP'
                THEN 'SINGLE_SWEEP_HIGH_UP'
            WHEN london_type_code = 'L2_SWEEP_LOW' AND pre_ny_type_code IN ('N0_NORMAL', 'N3_CONSOLIDATION') AND orb_2300_break_dir = 'DOWN'
                THEN 'SINGLE_SWEEP_LOW_DOWN'
            ELSE 'OTHER'
        END as pattern,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_2300_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_2300_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_2300_outcome IS NOT NULL
      AND orb_2300_break_dir IN ('UP', 'DOWN')
    GROUP BY pattern
    HAVING COUNT(*) >= 10
    ORDER BY avg_r DESC
""").fetchall()

print("\n2300 ORB: Specific aligned cascade patterns:")
print(f"{'Pattern':<30} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 60)
for row in result:
    pattern, trades, wr, avg_r = row
    if pattern != 'OTHER':
        print(f"{pattern:<30} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}")

# ============================================================================
# TEST 8: Day of week effect on direction alignment
# ============================================================================
print("\n" + "=" * 80)
print("TEST 8: Does day of week affect direction alignment edge?")
print("=" * 80)

result = con.execute("""
    SELECT
        CASE DAYOFWEEK(date_local)
            WHEN 1 THEN 'Sunday'
            WHEN 2 THEN 'Monday'
            WHEN 3 THEN 'Tuesday'
            WHEN 4 THEN 'Wednesday'
            WHEN 5 THEN 'Thursday'
            WHEN 6 THEN 'Friday'
            WHEN 7 THEN 'Saturday'
        END as day_of_week,
        CASE
            WHEN (london_type_code = 'L1_SWEEP_HIGH' AND orb_1800_break_dir = 'UP') OR
                 (london_type_code = 'L2_SWEEP_LOW' AND orb_1800_break_dir = 'DOWN')
                THEN 'ALIGNED'
            ELSE 'COUNTER'
        END as alignment,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND orb_1800_break_dir IN ('UP', 'DOWN')
    GROUP BY day_of_week, alignment
    HAVING COUNT(*) >= 5
    ORDER BY day_of_week, alignment
""").fetchall()

print("\n1800 ORB: Direction alignment by day of week:")
print(f"{'Day':<15} {'Alignment':<12} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 65)
for row in result:
    day, alignment, trades, wr, avg_r = row
    print(f"{day:<15} {alignment:<12} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}")

con.close()

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("DISCOVERY SUMMARY")
print("=" * 80)
print("""
Questions answered:
1. Does direction alignment work on other ORBs? → See results above
2. Does it work better in specific volatility regimes? → See results above
3. What specific cascade conditions work best? → See results above
4. Does day of week matter? → See results above

Next steps:
1. Document any NEW verified edges in LEGITIMATE_EDGES_CATALOG.md
2. Only add edges with:
   - Clear win rate difference (>10 percentage points)
   - Adequate sample size (>=30 trades)
   - Logical market explanation
3. Build up from verified edges only
""")
print("=" * 80)
