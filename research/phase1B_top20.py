#!/usr/bin/env python3
"""
PHASE 1B - CONDITION DISCOVERY (TOP 20 FAMILIES ONLY)

Tests conditions on ONLY the top 20 families from Phase 1A.
Much faster: ~20 families × 7 conditions × ~2.5 values = ~350 tests vs 2500+
"""

import duckdb
import pandas as pd
import numpy as np
import pytz
import sys
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# Paths
ROOT = Path(__file__).parent.parent
DB_PATH = str(ROOT / "data" / "db" / "gold.db")
OUTPUT_DIR = ROOT / "research"

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")
TZ_UTC = pytz.utc

INSTRUMENT = 'MGC'

# Load top 20 from Phase 1A
phase1a = pd.read_csv(OUTPUT_DIR / 'phase1A_baseline_families.csv')
top20 = phase1a.head(20)

print("=" * 80)
print("PHASE 1B - CONDITION DISCOVERY (TOP 20 FAMILIES)")
print("=" * 80)
sys.stdout.flush()
print()
print("Testing conditions on top 20 baseline families only")
print(f"Estimated tests: ~350 (vs ~2500+ for all families)")
print()
sys.stdout.flush()

print("Top 20 families to test:")
for i, row in enumerate(top20.itertuples(), 1):
    print(f"  {i:2d}. {row.family_id:35s} {row.avg_r:+.3f}R")
sys.stdout.flush()

print()
print("Starting Phase 1B testing...")
print()
sys.stdout.flush()

# Import the rest of the functions from the full script
exec(open('research/phase1B_condition_discovery.py').read().split('def main():')[0])

def main():
    """Run Phase 1B on top 20 families only."""

    CONDITIONS = [
        ('orb_size', ['SMALL', 'MEDIUM', 'LARGE']),
        ('pre_orb_trend', ['BULLISH', 'BEARISH', 'NEUTRAL']),
        ('asia_bias', ['ABOVE', 'BELOW', 'INSIDE']),
        ('london_sweep', ['SWEPT_HIGH', 'SWEPT_LOW', 'NO_SWEEP']),
        ('day_group', ['MON_TUE', 'WED_THU', 'FRI']),
        ('pre_volatility', ['CALM', 'VOLATILE']),
    ]

    # Connect to database
    conn = duckdb.connect(DB_PATH, read_only=True)

    # Get data range
    result = conn.execute("""
        SELECT MIN(DATE(ts_utc AT TIME ZONE 'Australia/Brisbane')) as min_date,
               MAX(DATE(ts_utc AT TIME ZONE 'Australia/Brisbane')) as max_date
        FROM bars_1m
        WHERE symbol = ?
    """, [INSTRUMENT]).fetchone()

    start_date, end_date = result[0], result[1]
    print(f"Data range: {start_date} to {end_date}")
    sys.stdout.flush()

    # Load data
    print("Loading bars and features...")
    sys.stdout.flush()
    bars_df = load_bars_for_date_range(conn, start_date, end_date)
    features_df = load_daily_features(conn)
    print(f"Loaded {len(bars_df):,} bars and {len(features_df):,} feature rows")
    print()
    sys.stdout.flush()

    # Test only top 20 families
    results = []
    total_tests = 0

    for _, family_row in top20.iterrows():
        family_id = family_row['family_id']
        orb_time = family_row['orb_time']
        direction = family_row['direction']
        rr = family_row['rr']
        sl_mode = family_row['sl_mode']

        print(f"Testing {family_id}...")
        sys.stdout.flush()

        for condition_name, condition_values in CONDITIONS:
            for condition_value in condition_values:
                total_tests += 1

                if total_tests % 20 == 0:
                    print(f"  Progress: {total_tests}/~350 tests...")
                    sys.stdout.flush()

                result = test_condition(
                    bars_df, features_df,
                    orb_time, direction, rr, sl_mode,
                    condition_name, condition_value,
                    start_date, end_date
                )

                if result is not None:
                    results.append(result)
                    print(f"  [FOUND] {condition_name}={condition_value}: {result.filtered_avg_r:+.3f}R (baseline: {result.baseline_avg_r:+.3f}R, delta: {result.delta_avg_r:+.3f}R)")
                    sys.stdout.flush()

    conn.close()

    print()
    print("=" * 80)
    print("PHASE 1B COMPLETE")
    print("=" * 80)
    print()
    sys.stdout.flush()

    if len(results) == 0:
        print("No condition-dependent edges found.")
        print()
        return

    # Convert to DataFrame
    df = pd.DataFrame([asdict(r) for r in results])
    df = df.sort_values('filtered_avg_r', ascending=False)

    # Save CSV
    output_csv = OUTPUT_DIR / 'phase1B_condition_edges.csv'
    df.to_csv(output_csv, index=False)
    print(f"[OK] Saved CSV: {output_csv}")

    # Generate markdown
    output_md = OUTPUT_DIR / 'phase1B_condition_edges.md'

    with open(output_md, 'w') as f:
        f.write("# PHASE 1B - CONDITION-DEPENDENT EDGES (TOP 20 FAMILIES)\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Tested**: Top 20 families from Phase 1A\n\n")
        f.write(f"**Edges Found**: {len(df)}\n\n")
        f.write("---\n\n")

        # Top 20 edges
        f.write("## TOP 20 CONDITION-DEPENDENT EDGES\n\n")
        f.write("| Rank | Family | Condition | Baseline AvgR | Filtered AvgR | Delta | WR% | Trades | Retention% |\n")
        f.write("|------|--------|-----------|---------------|---------------|-------|-----|--------|------------|\n")

        for i, row in enumerate(df.head(20).itertuples(), 1):
            f.write(f"| {i} | {row.family_id} | {row.condition_name}={row.condition_value} | {row.baseline_avg_r:+.3f}R | {row.filtered_avg_r:+.3f}R | {row.delta_avg_r:+.3f}R | {row.filtered_win_rate:.1f}% | {row.filtered_trades} | {row.trade_retention_pct:.0f}% |\n")

        f.write("\n")

    print(f"[OK] Saved report: {output_md}")
    print()

    # Display top 10
    print("TOP 10 CONDITION-DEPENDENT EDGES:")
    print()
    for i, row in enumerate(df.head(10).itertuples(), 1):
        print(f"{i}. {row.family_id} + {row.condition_name}={row.condition_value}")
        print(f"   Filtered: {row.filtered_avg_r:+.3f}R ({row.filtered_trades} trades, {row.filtered_win_rate:.1f}% WR)")
        print(f"   Baseline: {row.baseline_avg_r:+.3f}R | Delta: {row.delta_avg_r:+.3f}R")
        print()

    print("=" * 80)
    print("PHASE 1B COMPLETE - STOP")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
