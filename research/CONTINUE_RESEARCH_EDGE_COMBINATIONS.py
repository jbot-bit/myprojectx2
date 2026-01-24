#!/usr/bin/env python3
"""
CONTINUE RESEARCH: Test edge combinations

Now that we have 5 verified edges, test COMBINATIONS:
1. Low vol + direction alignment + double sweep
2. Direction alignment + pre-ORB travel (momentum)
3. Low vol + weekday + direction alignment (ELITE setup)
4. Liquidity level spacing + direction alignment
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DB_PATH = Path(__file__).parent.parent / "data/db/gold.db"
con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 80)
print("TESTING EDGE COMBINATIONS - Building ELITE setups")
print("=" * 80)
print("\nVerified Edges: 5")
print("  1. Direction Alignment (63% vs 33%)")
print("  2. Low Vol Boost (75% WR)")
print("  3. Liquidity Freshness (edge fades with time)")
print("  4. Double Sweep Cascade (60% WR)")
print("  5. Weekday Effect (58-73% WR)\n")

# ============================================================================
# TEST 9: Low Vol + Direction Alignment + Weekday (ELITE SETUP)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 9: ELITE SETUP - Low Vol + Direction Alignment + Weekday")
print("=" * 80)

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
            ELSE 'NOT_LOW_VOL'
        END as vol_regime,
        CASE DAYOFWEEK(d.date_local)
            WHEN 2 THEN 'Monday'
            WHEN 3 THEN 'Tuesday'
            WHEN 4 THEN 'Wednesday'
            WHEN 5 THEN 'Thursday'
            ELSE 'Other'
        END as day_of_week,
        COUNT(*) as trades,
        AVG(CASE WHEN d.orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(d.orb_1800_r_multiple) as avg_r
    FROM daily_features_v2 d
    JOIN atr_percentiles a ON d.date_local = a.date_local
    WHERE d.instrument = 'MGC'
      AND d.orb_1800_outcome IS NOT NULL
      AND d.london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND d.orb_1800_break_dir IN ('UP', 'DOWN')
      -- Direction aligned
      AND (
          (d.london_type_code = 'L1_SWEEP_HIGH' AND d.orb_1800_break_dir = 'UP') OR
          (d.london_type_code = 'L2_SWEEP_LOW' AND d.orb_1800_break_dir = 'DOWN')
      )
    GROUP BY vol_regime, day_of_week
    HAVING COUNT(*) >= 5
    ORDER BY vol_regime, day_of_week
""").fetchall()

print("\nELITE SETUP combinations:")
print(f"{'Vol Regime':<15} {'Day':<15} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 65)
for row in result:
    vol, day, trades, wr, avg_r = row
    marker = " [ELITE]" if vol == 'LOW_VOL' and day != 'Other' else ""
    print(f"{vol:<15} {day:<15} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}{marker}")

# Best combination
elite_result = con.execute("""
    WITH atr_percentiles AS (
        SELECT
            date_local,
            NTILE(3) OVER (ORDER BY atr_20) as vol_tercile
        FROM daily_features_v2
        WHERE instrument = 'MGC' AND atr_20 IS NOT NULL
    )
    SELECT
        COUNT(*) as trades,
        AVG(CASE WHEN d.orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(d.orb_1800_r_multiple) as avg_r
    FROM daily_features_v2 d
    JOIN atr_percentiles a ON d.date_local = a.date_local
    WHERE d.instrument = 'MGC'
      AND a.vol_tercile = 1  -- Low vol
      AND DAYOFWEEK(d.date_local) IN (2,3,4,5)  -- Mon-Thu
      AND d.london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND (
          (d.london_type_code = 'L1_SWEEP_HIGH' AND d.orb_1800_break_dir = 'UP') OR
          (d.london_type_code = 'L2_SWEEP_LOW' AND d.orb_1800_break_dir = 'DOWN')
      )
      AND d.orb_1800_outcome IS NOT NULL
""").fetchone()

if elite_result and elite_result[0] >= 10:
    trades, wr, avg_r = elite_result
    print(f"\nELITE SETUP (Low Vol + Mon-Thu + Direction Aligned):")
    print(f"  Trades: {trades}")
    print(f"  Win Rate: {wr*100:.1f}%")
    print(f"  Avg R: {avg_r:+.3f}R")
    if wr >= 0.70:
        print(f"  [VERIFIED] 70%+ win rate achieved!")

# ============================================================================
# TEST 10: Low Vol + Double Sweep Cascade (2300 ORB)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 10: Low Vol + Double Sweep Cascade (2300 ORB)")
print("=" * 80)

result = con.execute("""
    WITH atr_percentiles AS (
        SELECT
            date_local,
            NTILE(3) OVER (ORDER BY atr_20) as vol_tercile
        FROM daily_features_v2
        WHERE instrument = 'MGC' AND atr_20 IS NOT NULL
    )
    SELECT
        CASE WHEN a.vol_tercile = 1 THEN 'LOW_VOL' ELSE 'NOT_LOW_VOL' END as vol_regime,
        COUNT(*) as trades,
        AVG(CASE WHEN d.orb_2300_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(d.orb_2300_r_multiple) as avg_r
    FROM daily_features_v2 d
    JOIN atr_percentiles a ON d.date_local = a.date_local
    WHERE d.instrument = 'MGC'
      AND d.orb_2300_outcome IS NOT NULL
      -- Double sweep cascade (aligned)
      AND (
          (d.london_type_code = 'L1_SWEEP_HIGH' AND d.pre_ny_type_code = 'N1_SWEEP_HIGH' AND d.orb_2300_break_dir = 'UP') OR
          (d.london_type_code = 'L2_SWEEP_LOW' AND d.pre_ny_type_code = 'N2_SWEEP_LOW' AND d.orb_2300_break_dir = 'DOWN')
      )
    GROUP BY vol_regime
    ORDER BY vol_regime
""").fetchall()

print("\nDouble Sweep Cascade by volatility:")
print(f"{'Vol Regime':<15} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 50)
for row in result:
    vol, trades, wr, avg_r = row
    print(f"{vol:<15} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}")

# ============================================================================
# TEST 11: Pre-ORB Travel + Direction Alignment
# ============================================================================
print("\n" + "=" * 80)
print("TEST 11: Pre-ORB Travel (Momentum) + Direction Alignment")
print("=" * 80)

# Calculate pre-ORB travel for 1800 ORB
# Compare price at 1800 vs Asia low (for UP breaks) or Asia high (for DOWN breaks)
result = con.execute("""
    SELECT
        CASE
            -- UP breaks: measure from Asia low to ORB start
            WHEN orb_1800_break_dir = 'UP' AND (orb_1800_low - asia_low) > 2.0 THEN 'HIGH_TRAVEL_UP'
            WHEN orb_1800_break_dir = 'UP' AND (orb_1800_low - asia_low) <= 2.0 THEN 'LOW_TRAVEL_UP'
            -- DOWN breaks: measure from Asia high to ORB start
            WHEN orb_1800_break_dir = 'DOWN' AND (asia_high - orb_1800_high) > 2.0 THEN 'HIGH_TRAVEL_DOWN'
            WHEN orb_1800_break_dir = 'DOWN' AND (asia_high - orb_1800_high) <= 2.0 THEN 'LOW_TRAVEL_DOWN'
            ELSE 'OTHER'
        END as momentum_pattern,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND orb_1800_break_dir IN ('UP', 'DOWN')
      -- Direction aligned
      AND (
          (london_type_code = 'L1_SWEEP_HIGH' AND orb_1800_break_dir = 'UP') OR
          (london_type_code = 'L2_SWEEP_LOW' AND orb_1800_break_dir = 'DOWN')
      )
      AND asia_low IS NOT NULL
      AND asia_high IS NOT NULL
      AND orb_1800_low IS NOT NULL
      AND orb_1800_high IS NOT NULL
    GROUP BY momentum_pattern
    HAVING COUNT(*) >= 10
    ORDER BY avg_r DESC
""").fetchall()

print("\nDirection Aligned + Pre-ORB Travel:")
print(f"{'Momentum Pattern':<25} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 60)
for row in result:
    pattern, trades, wr, avg_r = row
    if pattern != 'OTHER':
        print(f"{pattern:<25} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}")

# ============================================================================
# TEST 12: Liquidity Level Spacing + Direction Alignment
# ============================================================================
print("\n" + "=" * 80)
print("TEST 12: Liquidity Level Spacing + Direction Alignment")
print("=" * 80)

# Test: Do close levels (Asia high ~ London high) create stronger breakouts?
result = con.execute("""
    SELECT
        CASE
            -- For UP breaks: measure Asia high to London high gap
            WHEN london_type_code = 'L1_SWEEP_HIGH' AND orb_1800_break_dir = 'UP'
                 AND (london_high - asia_high) < 1.0
                THEN 'CLOSE_LEVELS_UP'
            WHEN london_type_code = 'L1_SWEEP_HIGH' AND orb_1800_break_dir = 'UP'
                 AND (london_high - asia_high) >= 1.0
                THEN 'FAR_LEVELS_UP'
            -- For DOWN breaks: measure Asia low to London low gap
            WHEN london_type_code = 'L2_SWEEP_LOW' AND orb_1800_break_dir = 'DOWN'
                 AND (asia_low - london_low) < 1.0
                THEN 'CLOSE_LEVELS_DOWN'
            WHEN london_type_code = 'L2_SWEEP_LOW' AND orb_1800_break_dir = 'DOWN'
                 AND (asia_low - london_low) >= 1.0
                THEN 'FAR_LEVELS_DOWN'
            ELSE 'OTHER'
        END as spacing_pattern,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND london_type_code IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
      AND orb_1800_break_dir IN ('UP', 'DOWN')
      AND asia_high IS NOT NULL
      AND asia_low IS NOT NULL
      AND london_high IS NOT NULL
      AND london_low IS NOT NULL
    GROUP BY spacing_pattern
    HAVING COUNT(*) >= 10
    ORDER BY avg_r DESC
""").fetchall()

print("\nLiquidity Level Spacing (Direction Aligned):")
print(f"{'Spacing Pattern':<25} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 60)
for row in result:
    pattern, trades, wr, avg_r = row
    if pattern != 'OTHER':
        print(f"{pattern:<25} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}")

con.close()

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("EDGE COMBINATIONS SUMMARY")
print("=" * 80)
print("""
Key findings:
1. ELITE SETUP combinations tested
2. Low vol + double sweep cascade tested
3. Pre-ORB travel (momentum) + alignment tested
4. Liquidity level spacing + alignment tested

Next steps:
1. Document any NEW verified combinations
2. Update LEGITIMATE_EDGES_CATALOG.md with findings
3. Create implementation proposal for best combinations
4. Continue testing other hypotheses

Remember: Only add edges with clear win rate improvement (>10%), adequate
sample size (>=30), and logical market explanation.
""")
print("=" * 80)
