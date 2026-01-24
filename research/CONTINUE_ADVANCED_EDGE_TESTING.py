#!/usr/bin/env python3
"""
CONTINUE ADVANCED EDGE TESTING - Testing additional hypotheses

We now have 6 verified edges. Continue testing:
1. Low vol + double sweep cascade (stacking Edges #2 and #4)
2. Pre-ORB momentum (high travel vs low travel)
3. Liquidity spacing (tight levels vs wide levels)
4. Failed sweep rejection patterns
5. ATR expansion at ORB time
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data/db/gold.db"
con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 80)
print("ADVANCED EDGE TESTING - Discovering additional patterns")
print("=" * 80)
print("\nVerified Edges: 6")
print("  1. Direction Alignment (63% vs 33%)")
print("  2. Low Vol Boost (75% WR)")
print("  3. Liquidity Freshness (edge fades with time)")
print("  4. Double Sweep Cascade (60% WR)")
print("  5. Weekday Effect (58-73% WR)")
print("  6. ELITE Setup (77% WR)\n")

# ============================================================================
# TEST 13: Low Vol + Double Sweep Cascade (Stacking Edges #2 and #4)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 13: Low Vol + Double Sweep Cascade (2300 ORB)")
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

print("\nLow Vol + Double Sweep Cascade:")
print(f"{'Vol Regime':<15} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 50)
for row in result:
    vol, trades, wr, avg_r = row
    marker = " [STACKED EDGE]" if vol == 'LOW_VOL' and trades >= 10 else ""
    print(f"{vol:<15} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}{marker}")

# ============================================================================
# TEST 14: Pre-ORB Momentum (Travel Distance Analysis)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 14: Pre-ORB Momentum - Does high travel before ORB predict outcome?")
print("=" * 80)

# For UP breaks: measure from asia_low to orb_1800_low (how far price traveled before ORB)
# For DOWN breaks: measure from asia_high to orb_1800_high
result = con.execute("""
    SELECT
        CASE
            -- UP breaks: high momentum (traveled far from Asia low)
            WHEN orb_1800_break_dir = 'UP' AND (orb_1800_low - asia_low) > 2.0 THEN 'HIGH_MOMENTUM_UP'
            WHEN orb_1800_break_dir = 'UP' AND (orb_1800_low - asia_low) <= 2.0 THEN 'LOW_MOMENTUM_UP'
            -- DOWN breaks: high momentum (traveled far from Asia high)
            WHEN orb_1800_break_dir = 'DOWN' AND (asia_high - orb_1800_high) > 2.0 THEN 'HIGH_MOMENTUM_DOWN'
            WHEN orb_1800_break_dir = 'DOWN' AND (asia_high - orb_1800_high) <= 2.0 THEN 'LOW_MOMENTUM_DOWN'
            ELSE 'OTHER'
        END as momentum_pattern,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r,
        AVG(CASE
            WHEN orb_1800_break_dir = 'UP' THEN (orb_1800_low - asia_low)
            ELSE (asia_high - orb_1800_high)
        END) as avg_travel
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND orb_1800_break_dir IN ('UP', 'DOWN')
      AND asia_low IS NOT NULL
      AND asia_high IS NOT NULL
      AND orb_1800_low IS NOT NULL
      AND orb_1800_high IS NOT NULL
    GROUP BY momentum_pattern
    HAVING COUNT(*) >= 20
    ORDER BY avg_r DESC
""").fetchall()

print("\nPre-ORB Momentum (all setups):")
print(f"{'Momentum Pattern':<25} {'Trades':<10} {'WR%':<10} {'Avg R':<10} {'Avg Travel'}")
print("-" * 75)
for row in result:
    pattern, trades, wr, avg_r, avg_travel = row
    if pattern != 'OTHER':
        print(f"{pattern:<25} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}     ${avg_travel:.2f}")

# Now test momentum with direction alignment
result = con.execute("""
    SELECT
        CASE
            -- UP breaks: high momentum (traveled far from Asia low)
            WHEN orb_1800_break_dir = 'UP' AND (orb_1800_low - asia_low) > 2.0 THEN 'HIGH_MOMENTUM_UP'
            WHEN orb_1800_break_dir = 'UP' AND (orb_1800_low - asia_low) <= 2.0 THEN 'LOW_MOMENTUM_UP'
            -- DOWN breaks: high momentum (traveled far from Asia high)
            WHEN orb_1800_break_dir = 'DOWN' AND (asia_high - orb_1800_high) > 2.0 THEN 'HIGH_MOMENTUM_DOWN'
            WHEN orb_1800_break_dir = 'DOWN' AND (asia_high - orb_1800_high) <= 2.0 THEN 'LOW_MOMENTUM_DOWN'
            ELSE 'OTHER'
        END as momentum_pattern,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
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

print("\nPre-ORB Momentum (ALIGNED setups only):")
print(f"{'Momentum Pattern':<25} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 60)
for row in result:
    pattern, trades, wr, avg_r = row
    if pattern != 'OTHER':
        print(f"{pattern:<25} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}")

# ============================================================================
# TEST 15: Liquidity Level Spacing (Tight vs Wide)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 15: Liquidity Level Spacing - Do tight levels create stronger moves?")
print("=" * 80)

# Test: Do close levels (Asia high ~ London high) create stronger breakouts?
result = con.execute("""
    SELECT
        CASE
            -- For UP breaks: measure Asia high to London high gap
            WHEN london_type_code = 'L1_SWEEP_HIGH' AND orb_1800_break_dir = 'UP'
                 AND (london_high - asia_high) < 1.0
                THEN 'TIGHT_LEVELS_UP'
            WHEN london_type_code = 'L1_SWEEP_HIGH' AND orb_1800_break_dir = 'UP'
                 AND (london_high - asia_high) >= 1.0
                THEN 'WIDE_LEVELS_UP'
            -- For DOWN breaks: measure Asia low to London low gap
            WHEN london_type_code = 'L2_SWEEP_LOW' AND orb_1800_break_dir = 'DOWN'
                 AND (asia_low - london_low) < 1.0
                THEN 'TIGHT_LEVELS_DOWN'
            WHEN london_type_code = 'L2_SWEEP_LOW' AND orb_1800_break_dir = 'DOWN'
                 AND (asia_low - london_low) >= 1.0
                THEN 'WIDE_LEVELS_DOWN'
            ELSE 'OTHER'
        END as spacing_pattern,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r,
        AVG(CASE
            WHEN london_type_code = 'L1_SWEEP_HIGH' THEN (london_high - asia_high)
            ELSE (asia_low - london_low)
        END) as avg_spacing
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
print(f"{'Spacing Pattern':<25} {'Trades':<10} {'WR%':<10} {'Avg R':<10} {'Avg Gap'}")
print("-" * 75)
for row in result:
    pattern, trades, wr, avg_r, avg_spacing = row
    if pattern != 'OTHER':
        print(f"{pattern:<25} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}     ${avg_spacing:.2f}")

# ============================================================================
# TEST 16: Failed Sweep Rejection Patterns
# ============================================================================
print("\n" + "=" * 80)
print("TEST 16: Failed Sweep Rejections - Do failed sweeps predict reversals?")
print("=" * 80)

# Test: When London TRIES to sweep high but fails (sets high but doesn't qualify as sweep)
# Does this create a bearish bias?
result = con.execute("""
    SELECT
        CASE
            -- London tried to go high (high > asia_high) but didn't sweep
            WHEN london_type_code NOT IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
                 AND london_high > asia_high
                 AND (london_high - asia_high) >= 0.5
                THEN 'FAILED_HIGH'
            -- London tried to go low (low < asia_low) but didn't sweep
            WHEN london_type_code NOT IN ('L1_SWEEP_HIGH', 'L2_SWEEP_LOW')
                 AND london_low < asia_low
                 AND (asia_low - london_low) >= 0.5
                THEN 'FAILED_LOW'
            -- Normal (no attempt)
            WHEN london_type_code IN ('L3_EXPANSION', 'L4_CONSOLIDATION')
                THEN 'NO_ATTEMPT'
            ELSE 'OTHER'
        END as rejection_pattern,
        orb_1800_break_dir,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND orb_1800_break_dir IN ('UP', 'DOWN')
      AND asia_high IS NOT NULL
      AND asia_low IS NOT NULL
      AND london_high IS NOT NULL
      AND london_low IS NOT NULL
    GROUP BY rejection_pattern, orb_1800_break_dir
    HAVING COUNT(*) >= 10
    ORDER BY rejection_pattern, orb_1800_break_dir
""").fetchall()

print("\nFailed Sweep Rejection Patterns:")
print(f"{'Rejection Pattern':<20} {'ORB Dir':<10} {'Trades':<10} {'WR%':<10} {'Avg R'}")
print("-" * 70)
for row in result:
    pattern, orb_dir, trades, wr, avg_r = row
    if pattern != 'OTHER':
        # Check if reversal (FAILED_HIGH + DOWN = reversal)
        reversal = (pattern == 'FAILED_HIGH' and orb_dir == 'DOWN') or \
                   (pattern == 'FAILED_LOW' and orb_dir == 'UP')
        marker = " [REVERSAL]" if reversal else ""
        print(f"{pattern:<20} {orb_dir:<10} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}{marker}")

# ============================================================================
# TEST 17: ATR Expansion at ORB Time
# ============================================================================
print("\n" + "=" * 80)
print("TEST 17: ATR Expansion - Does expanding ATR at ORB predict follow-through?")
print("=" * 80)

# Calculate ATR_5 (5-period ATR on 5-minute bars) at ORB time
# Compare to ATR_20 (20-day ATR)
# If ATR_5 > ATR_20 average → expanding volatility
result = con.execute("""
    SELECT
        CASE
            WHEN atr_20 IS NULL THEN 'NO_ATR_DATA'
            -- Low ATR (compressed)
            WHEN atr_20 < 2.0 THEN 'VERY_LOW_ATR'
            WHEN atr_20 < 2.5 THEN 'LOW_ATR'
            WHEN atr_20 < 3.0 THEN 'MED_ATR'
            WHEN atr_20 < 3.5 THEN 'HIGH_ATR'
            ELSE 'VERY_HIGH_ATR'
        END as atr_regime,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r,
        AVG(atr_20) as avg_atr
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND orb_1800_break_dir IN ('UP', 'DOWN')
      -- Direction aligned
      AND (
          (london_type_code = 'L1_SWEEP_HIGH' AND orb_1800_break_dir = 'UP') OR
          (london_type_code = 'L2_SWEEP_LOW' AND orb_1800_break_dir = 'DOWN')
      )
    GROUP BY atr_regime
    HAVING COUNT(*) >= 10
    ORDER BY avg_atr
""").fetchall()

print("\nATR Regime Analysis (Direction Aligned):")
print(f"{'ATR Regime':<20} {'Trades':<10} {'WR%':<10} {'Avg R':<10} {'Avg ATR'}")
print("-" * 75)
for row in result:
    atr_regime, trades, wr, avg_r, avg_atr = row
    if atr_regime != 'NO_ATR_DATA':
        print(f"{atr_regime:<20} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}     ${avg_atr:.3f}")

# ============================================================================
# TEST 18: ORB Size Analysis (Does ORB size predict outcome?)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 18: ORB Size - Do larger ORBs have better follow-through?")
print("=" * 80)

result = con.execute("""
    SELECT
        CASE
            WHEN orb_1800_size IS NULL THEN 'NO_SIZE'
            WHEN orb_1800_size < 0.5 THEN 'TINY_ORB'
            WHEN orb_1800_size < 1.0 THEN 'SMALL_ORB'
            WHEN orb_1800_size < 1.5 THEN 'MEDIUM_ORB'
            WHEN orb_1800_size < 2.0 THEN 'LARGE_ORB'
            ELSE 'HUGE_ORB'
        END as orb_size_category,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r,
        AVG(orb_1800_size) as avg_orb_size
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1800_outcome IS NOT NULL
      AND orb_1800_break_dir IN ('UP', 'DOWN')
      -- Direction aligned
      AND (
          (london_type_code = 'L1_SWEEP_HIGH' AND orb_1800_break_dir = 'UP') OR
          (london_type_code = 'L2_SWEEP_LOW' AND orb_1800_break_dir = 'DOWN')
      )
    GROUP BY orb_size_category
    HAVING COUNT(*) >= 10
    ORDER BY avg_orb_size
""").fetchall()

print("\nORB Size Analysis (Direction Aligned):")
print(f"{'ORB Size Category':<20} {'Trades':<10} {'WR%':<10} {'Avg R':<10} {'Avg Size'}")
print("-" * 75)
for row in result:
    category, trades, wr, avg_r, avg_size = row
    if category != 'NO_SIZE':
        print(f"{category:<20} {trades:<10} {wr*100:<10.1f} {avg_r:+.3f}     ${avg_size:.3f}")

con.close()

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("ADVANCED EDGE TESTING SUMMARY")
print("=" * 80)
print("""
Tests completed:
1. Low vol + double sweep cascade (stacking edges)
2. Pre-ORB momentum (high travel vs low travel)
3. Liquidity level spacing (tight vs wide levels)
4. Failed sweep rejection patterns
5. ATR expansion at ORB time
6. ORB size impact on follow-through

Next steps:
1. Document any NEW verified edges in LEGITIMATE_EDGES_CATALOG.md
2. Update implementation proposal with new findings
3. Continue testing other hypotheses if needed

Remember: Only add edges with clear win rate improvement (>10%), adequate
sample size (>=20), and logical market explanation.
""")
print("=" * 80)
