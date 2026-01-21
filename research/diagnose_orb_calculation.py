#!/usr/bin/env python3
"""
Diagnostic: Compare candidate_backtest_engine ORB calculations
with precomputed values in daily_features_v2.
"""

import duckdb
import pandas as pd
from pathlib import Path
from candidate_backtest_engine import (
    parse_candidate_spec,
    load_bars_for_trading_day,
    calculate_orb,
    TZ_LOCAL,
    TZ_UTC
)
from datetime import date, time as dt_time

ROOT = Path(__file__).parent.parent
DB_PATH = str(ROOT / "data" / "db" / "gold.db")

# Test a few specific days
test_dates = [
    date(2024, 1, 2),
    date(2024, 1, 3),
    date(2024, 1, 4),
    date(2024, 1, 5),
]

# Create dummy candidate specs for 2300 and 0030
candidate_2300_dict = {
    'candidate_id': 999,
    'name': 'Diagnostic 2300',
    'test_config_json': '''{"orb_time": "2300", "entry_rule": "breakout"}''',
    'filter_spec_json': None
}

candidate_0030_dict = {
    'candidate_id': 998,
    'name': 'Diagnostic 0030',
    'test_config_json': '''{"orb_time": "0030", "entry_rule": "breakout"}''',
    'filter_spec_json': None
}

conn = duckdb.connect(DB_PATH, read_only=True)

print("=" * 100)
print("2300 ORB Calculation Comparison")
print("=" * 100)
print()

spec_2300 = parse_candidate_spec(candidate_2300_dict)

for test_date in test_dates:
    # Get precomputed from daily_features_v2
    precomputed = conn.execute("""
        SELECT orb_2300_high, orb_2300_low, orb_2300_size, orb_2300_break_dir
        FROM daily_features_v2
        WHERE instrument = 'MGC' AND date_local = ?
    """, [str(test_date)]).fetchone()

    # Calculate using candidate_backtest_engine
    bars = load_bars_for_trading_day(conn, test_date, spec_2300)
    orb_calc = calculate_orb(bars, spec_2300) if len(bars) > 0 else None

    print(f"Date: {test_date}")
    if precomputed and precomputed[0] is not None:
        print(f"  Precomputed: high={precomputed[0]:.1f}, low={precomputed[1]:.1f}, size={precomputed[2]:.1f}")
    else:
        print(f"  Precomputed: None")

    if orb_calc:
        print(f"  Calculated:  high={orb_calc['high']:.1f}, low={orb_calc['low']:.1f}, size={orb_calc['size']:.1f}")

        if precomputed and precomputed[0] is not None:
            match = (
                abs(orb_calc['high'] - precomputed[0]) < 0.1 and
                abs(orb_calc['low'] - precomputed[1]) < 0.1
            )
            print(f"  Match: {'YES' if match else 'NO'}")
    else:
        print(f"  Calculated:  None (no bars)")
    print()

print("=" * 100)
print("0030 ORB Calculation Comparison")
print("=" * 100)
print()

spec_0030 = parse_candidate_spec(candidate_0030_dict)

for test_date in test_dates:
    # Get precomputed from daily_features_v2
    precomputed = conn.execute("""
        SELECT orb_0030_high, orb_0030_low, orb_0030_size, orb_0030_break_dir
        FROM daily_features_v2
        WHERE instrument = 'MGC' AND date_local = ?
    """, [str(test_date)]).fetchone()

    # Calculate using candidate_backtest_engine
    bars = load_bars_for_trading_day(conn, test_date, spec_0030)
    orb_calc = calculate_orb(bars, spec_0030) if len(bars) > 0 else None

    print(f"Date: {test_date}")
    if precomputed and precomputed[0] is not None:
        print(f"  Precomputed: high={precomputed[0]:.1f}, low={precomputed[1]:.1f}, size={precomputed[2]:.1f}")
    else:
        print(f"  Precomputed: None")

    if orb_calc:
        print(f"  Calculated:  high={orb_calc['high']:.1f}, low={orb_calc['low']:.1f}, size={orb_calc['size']:.1f}")

        if precomputed and precomputed[0] is not None:
            match = (
                abs(orb_calc['high'] - precomputed[0]) < 0.1 and
                abs(orb_calc['low'] - precomputed[1]) < 0.1
            )
            print(f"  Match: {'YES' if match else 'NO'}")
    else:
        print(f"  Calculated:  None (no bars)")
    print()

conn.close()
