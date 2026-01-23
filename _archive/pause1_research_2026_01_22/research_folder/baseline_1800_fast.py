#!/usr/bin/env python3
"""
Baseline Study - 18:00 ORB (FAST VERSION)

Uses daily_features_v2 for ORB data and breakout detection (fast),
only recomputes outcomes for different RR/SL combinations.

This is the correct approach:
- Use pre-computed ORB high/low/direction from daily_features_v2
- Recompute stop/target/outcome based on specific RR/SL parameters
"""

import sys
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta
import pandas as pd
import numpy as np
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_app.cloud_mode import get_database_connection

# Configuration
INSTRUMENT = 'MGC'
ORB_TIME = '1800'
START_DATE = '2024-01-02'
END_DATE = '2026-01-10'
TZ_LOCAL = pytz.timezone("Australia/Brisbane")

# Parameters to test
RR_VALUES = [1.5, 2.0, 3.0, 4.0, 6.0]
SL_MODES = ['FULL', 'HALF']


def backtest_1800_fast(rr, sl_mode):
    """
    Fast backtest using daily_features_v2 for ORB data.

    Only recomputes outcomes based on RR/SL parameters.
    """
    conn = get_database_connection()

    # Get all 18:00 ORB breakouts from daily_features_v2
    df = conn.execute(f"""
        SELECT
            date_local,
            orb_1800_high,
            orb_1800_low,
            orb_1800_break_dir,
            orb_1800_entry_price,
            orb_1800_entry_time_local
        FROM daily_features_v2
        WHERE instrument = '{INSTRUMENT}'
        AND date_local >= '{START_DATE}'
        AND date_local <= '{END_DATE}'
        AND orb_1800_break_dir IS NOT NULL
        AND orb_1800_break_dir != 'NONE'
    """).fetchdf()

    if len(df) == 0:
        return []

    r_multiples = []

    for idx, row in df.iterrows():
        orb_high = row['orb_1800_high']
        orb_low = row['orb_1800_low']
        orb_mid = (orb_high + orb_low) / 2.0
        direction = row['orb_1800_break_dir']
        entry_price = row['orb_1800_entry_price']
        entry_time_str = row['orb_1800_entry_time_local']
        trading_date = pd.to_datetime(row['date_local']).date()

        # Calculate stop based on SL mode
        if sl_mode == 'HALF':
            stop_price = orb_mid
        else:  # FULL
            stop_price = orb_low if direction == 'UP' else orb_high

        # Calculate risk and target
        if direction == 'UP':
            risk = entry_price - stop_price
            target_price = entry_price + (risk * rr)
        else:
            risk = stop_price - entry_price
            target_price = entry_price - (risk * rr)

        if risk <= 0:
            continue

        # Now we need bars_1m ONLY after entry to check resolution
        # Parse entry time
        entry_time = datetime.strptime(entry_time_str, '%H:%M:%S').time()
        entry_dt_local = TZ_LOCAL.localize(datetime.combine(trading_date, entry_time))

        # Get trading day end (next 09:00)
        if entry_time < dt_time(9, 0):
            # Entry before 09:00, so it's from previous day's session
            # Trading day ends at this date's 09:00
            end_dt_local = TZ_LOCAL.localize(datetime.combine(trading_date, dt_time(9, 0)))
        else:
            # Entry after 09:00, trading day ends next 09:00
            next_date = trading_date + timedelta(days=1)
            end_dt_local = TZ_LOCAL.localize(datetime.combine(next_date, dt_time(9, 0)))

        entry_dt_utc = entry_dt_local.astimezone(pytz.utc)
        end_dt_utc = end_dt_local.astimezone(pytz.utc)

        # Get bars AFTER entry
        bars = conn.execute("""
            SELECT ts_utc, high, low, close
            FROM bars_1m
            WHERE symbol = ?
            AND ts_utc > ?
            AND ts_utc < ?
            ORDER BY ts_utc
        """, [INSTRUMENT, entry_dt_utc, end_dt_utc]).fetchdf()

        if len(bars) == 0:
            continue

        # Check resolution
        outcome = None
        r_multiple = 0.0

        for _, bar in bars.iterrows():
            if direction == 'UP':
                if bar['low'] <= stop_price:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    break
                if bar['high'] >= target_price:
                    outcome = 'WIN'
                    r_multiple = rr
                    break
            else:
                if bar['high'] >= stop_price:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    break
                if bar['low'] <= target_price:
                    outcome = 'WIN'
                    r_multiple = rr
                    break

        if outcome is None and len(bars) > 0:
            # Time exit
            final_price = bars.iloc[-1]['close']
            pnl = (final_price - entry_price) if direction == 'UP' else (entry_price - final_price)
            r_multiple = pnl / risk if risk != 0 else 0
            outcome = 'TIME_EXIT'

        if outcome:
            r_multiples.append(r_multiple)

    return r_multiples


def calculate_metrics(r_multiples):
    """Calculate performance metrics from R multiples."""
    if len(r_multiples) == 0:
        return {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0,
            'max_dd_r': 0.0
        }

    arr = np.array(r_multiples)
    total = len(arr)
    wins = (arr > 0).sum()
    losses = (arr < 0).sum()

    win_rate = (wins / total * 100) if total > 0 else 0.0
    avg_r = arr.mean()
    total_r = arr.sum()

    # Max drawdown
    equity_curve = np.cumsum(np.concatenate([[0], arr]))
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = equity_curve - running_max
    max_dd = abs(drawdowns.min()) if len(drawdowns) > 0 else 0.0

    return {
        'trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r,
        'max_dd_r': max_dd
    }


def main():
    """Run baseline study for 18:00 ORB (FAST)."""
    print("=" * 80)
    print("BASELINE STUDY - 18:00 ORB (FAST VERSION)")
    print("=" * 80)
    print()
    print(f"Instrument: {INSTRUMENT}")
    print(f"ORB Time: {ORB_TIME} (5-minute window)")
    print(f"Entry: 1-minute close breakout")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print(f"Data Source: daily_features_v2 (ORB data) + bars_1m (outcomes only)")
    print()
    print(f"Testing {len(RR_VALUES)} RR values × {len(SL_MODES)} SL modes = {len(RR_VALUES) * len(SL_MODES)} combinations")
    print()

    results = []

    for rr in RR_VALUES:
        for sl_mode in SL_MODES:
            config_name = f"RR={rr}, SL={sl_mode}"
            print(f"Testing {config_name}...", end=' ', flush=True)

            try:
                r_mults = backtest_1800_fast(rr, sl_mode)
                metrics = calculate_metrics(r_mults)

                results.append({
                    'rr': rr,
                    'sl_mode': sl_mode,
                    **metrics
                })

                print(f"{metrics['trades']} trades | {metrics['win_rate']:.1f}% WR | {metrics['avg_r']:+.3f}R avg | {metrics['total_r']:+.1f}R total")

            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()

    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()

    if len(results) == 0:
        print("ERROR: No results!")
        return

    # Create DataFrame and sort by avg_r
    df = pd.DataFrame(results)
    df_sorted = df.sort_values('avg_r', ascending=False)

    # Display full results table
    print("18:00 ORB Baseline Results (sorted by Avg R):")
    print()
    print(df_sorted.to_string(index=False))
    print()

    # Identify best configuration
    best = df_sorted.iloc[0]
    print(f"BEST CONFIGURATION: RR={best['rr']}, SL={best['sl_mode']}")
    print(f"  Trades: {best['trades']}")
    print(f"  Win Rate: {best['win_rate']:.1f}%")
    print(f"  Avg R: {best['avg_r']:+.3f}R")
    print(f"  Total R: {best['total_r']:+.1f}R")
    print(f"  Max DD: {best['max_dd_r']:.1f}R")
    print()

    # Save to CSV
    output_path = Path(__file__).parent / 'baseline_1800_results.csv'
    df_sorted.to_csv(output_path, index=False)
    print(f"[OK] Saved results to {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
