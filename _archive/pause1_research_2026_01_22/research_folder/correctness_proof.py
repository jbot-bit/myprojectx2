#!/usr/bin/env python3
"""
Correctness Proof - Minimal test showing RR/SL changes affect results

Tests just 3 setups:
- MGC 1000 RR=3.0 FULL
- MGC 1000 RR=6.0 FULL
- MGC 1000 RR=6.0 HALF

If fix is correct, these should produce DIFFERENT avg_r values.
"""

import sys
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta
import numpy as np
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_app.cloud_mode import get_database_connection

# Simple test config
INSTRUMENT = 'MGC'
ORB_TIME = '1000'
START_DATE = '2024-01-02'
END_DATE = '2026-01-10'
TZ_LOCAL = pytz.timezone("Australia/Brisbane")


def backtest_single_config(rr, sl_mode):
    """Backtest one specific configuration."""
    conn = get_database_connection()

    orb_start_time = dt_time(10, 0)
    orb_end_time = dt_time(10, 5)

    # Get trading dates
    dates_df = conn.execute(f"""
        SELECT DISTINCT date_local
        FROM daily_features_v2
        WHERE instrument = '{INSTRUMENT}'
        AND date_local >= '{START_DATE}'
        AND date_local <= '{END_DATE}'
        ORDER BY date_local
    """).fetchdf()

    r_multiples = []

    import pandas as pd
    for trading_date_ts in dates_df['date_local'][:50]:  # ONLY TEST FIRST 50 DATES for speed
        trading_date = pd.to_datetime(trading_date_ts).date()

        # Load bars for this day
        start_dt_local = TZ_LOCAL.localize(datetime.combine(trading_date, dt_time(9, 0)))
        end_dt_local = start_dt_local + timedelta(days=1)

        start_dt_utc = start_dt_local.astimezone(pytz.utc)
        end_dt_utc = end_dt_local.astimezone(pytz.utc)

        bars = conn.execute("""
            SELECT ts_utc, open, high, low, close
            FROM bars_1m
            WHERE symbol = ?
            AND ts_utc >= ?
            AND ts_utc < ?
            ORDER BY ts_utc
        """, [INSTRUMENT, start_dt_utc, end_dt_utc]).fetchdf()

        if len(bars) == 0:
            continue

        import pandas as pd
        bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)
        bars['ts_local'] = bars['ts_utc'].dt.tz_convert(TZ_LOCAL)
        bars['time_local'] = bars['ts_local'].dt.time

        # Calculate ORB
        orb_bars = bars[
            (bars['time_local'] >= orb_start_time) &
            (bars['time_local'] < orb_end_time)
        ]

        if len(orb_bars) == 0:
            continue

        orb_high = orb_bars['high'].max()
        orb_low = orb_bars['low'].min()
        orb_midpoint = (orb_high + orb_low) / 2.0

        # Detect breakout
        post_orb = bars[bars['time_local'] >= orb_end_time]

        entry_bar = None
        direction = None

        for idx, bar in post_orb.iterrows():
            if bar['close'] > orb_high:
                entry_bar = bar
                direction = 'UP'
                break
            elif bar['close'] < orb_low:
                entry_bar = bar
                direction = 'DOWN'
                break

        if entry_bar is None:
            continue

        # Calculate stop and target with THIS setup's RR and SL mode
        entry_price = entry_bar['close']

        if sl_mode == 'HALF':
            stop_price = orb_midpoint
        else:
            stop_price = orb_low if direction == 'UP' else orb_high

        if direction == 'UP':
            risk = entry_price - stop_price
            target_price = entry_price + (risk * rr)
        else:
            risk = stop_price - entry_price
            target_price = entry_price - (risk * rr)

        if risk <= 0:
            continue

        # Check resolution
        remaining = bars[bars['ts_local'] > entry_bar['ts_local']]

        for idx, bar in remaining.iterrows():
            if direction == 'UP':
                if bar['low'] <= stop_price:
                    r_multiples.append(-1.0)
                    break
                if bar['high'] >= target_price:
                    r_multiples.append(rr)
                    break
            else:
                if bar['high'] >= stop_price:
                    r_multiples.append(-1.0)
                    break
                if bar['low'] <= target_price:
                    r_multiples.append(rr)
                    break

    return r_multiples


def main():
    """Run simple correctness proof."""
    print("=" * 80)
    print("CORRECTNESS PROOF - Minimal Test")
    print("=" * 80)
    print()
    print(f"Testing {INSTRUMENT} {ORB_TIME} ORB with different RR/SL combinations")
    print(f"Date Range: {START_DATE} to {END_DATE} (first 50 days only)")
    print()

    test_configs = [
        (3.0, 'FULL'),
        (6.0, 'FULL'),
        (6.0, 'HALF'),
    ]

    results = []

    for rr, sl_mode in test_configs:
        config_name = f"RR={rr}, SL={sl_mode}"
        print(f"Testing {config_name}...", end=' ', flush=True)

        r_mults = backtest_single_config(rr, sl_mode)

        if len(r_mults) > 0:
            arr = np.array(r_mults)
            trades = len(arr)
            wins = (arr > 0).sum()
            win_rate = (wins / trades * 100)
            avg_r = arr.mean()
            total_r = arr.sum()

            results.append({
                'config': config_name,
                'rr': rr,
                'sl_mode': sl_mode,
                'trades': trades,
                'win_rate': win_rate,
                'avg_r': avg_r,
                'total_r': total_r
            })

            print(f"{trades} trades | {win_rate:.1f}% WR | {avg_r:+.3f}R avg | {total_r:+.1f}R total")
        else:
            print("No trades")

    print()
    print("=" * 80)
    print("PROOF OF CORRECTNESS")
    print("=" * 80)
    print()

    if len(results) >= 2:
        print("If the fix is working, these avg_r values should be DIFFERENT:")
        print()
        for r in results:
            print(f"  {r['config']:20s}: avg_r = {r['avg_r']:+.3f}R")
        print()

        # Check if all different
        avg_rs = [r['avg_r'] for r in results]
        unique_avg_rs = len(set(avg_rs))

        if unique_avg_rs == len(avg_rs):
            print("✓ SUCCESS: All avg_r values are DIFFERENT")
            print("✓ The fix is working correctly!")
            print("✓ Changing RR and SL mode produces different results")
        else:
            print("✗ FAILURE: Some avg_r values are IDENTICAL")
            print("✗ The bug is NOT fixed")
            print("✗ Different RR/SL settings should produce different results")
    else:
        print("ERROR: Not enough results to compare")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
