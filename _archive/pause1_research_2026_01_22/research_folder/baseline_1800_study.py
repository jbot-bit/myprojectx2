#!/usr/bin/env python3
"""
Baseline Study - 18:00 ORB Only

Focused, trustworthy baseline study testing different RR and SL combinations
for the 18:00 ORB (London session).

Scope:
- Session: 18:00 ORB only
- ORB window: 5 minutes
- Entry: 1-minute close breakout
- Data source: bars_1m + daily_features_v2 only

Parameters:
- RR values: 1.5, 2.0, 3.0, 4.0, 6.0
- SL modes: FULL and HALF

No combinatorial scans, no indicators, no filters yet.
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
ORB_WINDOW_MINUTES = 5
START_DATE = '2024-01-02'
END_DATE = '2026-01-10'
TZ_LOCAL = pytz.timezone("Australia/Brisbane")

# Parameters to test
RR_VALUES = [1.5, 2.0, 3.0, 4.0, 6.0]
SL_MODES = ['FULL', 'HALF']


def backtest_1800_orb(rr, sl_mode):
    """
    Backtest 18:00 ORB with specific RR and SL mode.

    Recomputes outcomes from bars_1m for correctness.

    Args:
        rr: Risk/reward ratio (1.5, 2.0, 3.0, 4.0, 6.0)
        sl_mode: 'FULL' or 'HALF'

    Returns:
        List of r_multiples (one per trade)
    """
    conn = get_database_connection()

    # Parse ORB time
    orb_start_time = dt_time(18, 0)
    orb_end_time = dt_time(18, 5)

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

    for trading_date_ts in dates_df['date_local']:
        trading_date = pd.to_datetime(trading_date_ts).date()

        # Load 1-minute bars for this trading day (09:00 -> next 09:00)
        start_dt_local = TZ_LOCAL.localize(datetime.combine(trading_date, dt_time(9, 0)))
        end_dt_local = start_dt_local + timedelta(days=1)

        start_dt_utc = start_dt_local.astimezone(pytz.utc)
        end_dt_utc = end_dt_local.astimezone(pytz.utc)

        bars = conn.execute("""
            SELECT ts_utc, open, high, low, close, volume
            FROM bars_1m
            WHERE symbol = ?
            AND ts_utc >= ?
            AND ts_utc < ?
            ORDER BY ts_utc
        """, [INSTRUMENT, start_dt_utc, end_dt_utc]).fetchdf()

        if len(bars) == 0:
            continue

        bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)
        bars['ts_local'] = bars['ts_utc'].dt.tz_convert(TZ_LOCAL)
        bars['time_local'] = bars['ts_local'].dt.time

        # Calculate 18:00 ORB (5-minute window)
        orb_bars = bars[
            (bars['time_local'] >= orb_start_time) &
            (bars['time_local'] < orb_end_time)
        ]

        if len(orb_bars) == 0:
            continue

        orb_high = orb_bars['high'].max()
        orb_low = orb_bars['low'].min()
        orb_midpoint = (orb_high + orb_low) / 2.0

        # Detect breakout (first 1-minute close outside ORB)
        post_orb_bars = bars[bars['time_local'] >= orb_end_time]

        entry_bar = None
        direction = None

        for idx, bar in post_orb_bars.iterrows():
            if bar['close'] > orb_high:
                entry_bar = bar
                direction = 'UP'
                break
            elif bar['close'] < orb_low:
                entry_bar = bar
                direction = 'DOWN'
                break

        if entry_bar is None:
            continue  # No breakout

        # Calculate stop and target based on THIS setup's RR and SL mode
        entry_price = entry_bar['close']

        if sl_mode == 'HALF':
            stop_price = orb_midpoint
        else:  # FULL
            stop_price = orb_low if direction == 'UP' else orb_high

        if direction == 'UP':
            risk = entry_price - stop_price
            target_price = entry_price + (risk * rr)
        else:
            risk = stop_price - entry_price
            target_price = entry_price - (risk * rr)

        if risk <= 0:
            continue  # Invalid risk

        # Check resolution
        remaining_bars = bars[bars['ts_local'] > entry_bar['ts_local']]

        outcome = None
        r_multiple = 0.0

        for idx, bar in remaining_bars.iterrows():
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

        if outcome is None and len(remaining_bars) > 0:
            # Time exit at end of trading day
            final_bar = remaining_bars.iloc[-1]
            final_price = final_bar['close']
            pnl = (final_price - entry_price) if direction == 'UP' else (entry_price - final_price)
            r_multiple = pnl / risk if risk != 0 else 0
            outcome = 'TIME_EXIT'

        if outcome and outcome != 'NO_TRADE':
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
    """Run baseline study for 18:00 ORB."""
    print("=" * 80)
    print("BASELINE STUDY - 18:00 ORB")
    print("=" * 80)
    print()
    print(f"Instrument: {INSTRUMENT}")
    print(f"ORB Time: {ORB_TIME} (5-minute window)")
    print(f"Entry: 1-minute close breakout")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print(f"Data Source: bars_1m + daily_features_v2")
    print()
    print(f"Testing {len(RR_VALUES)} RR values × {len(SL_MODES)} SL modes = {len(RR_VALUES) * len(SL_MODES)} combinations")
    print()

    results = []

    for rr in RR_VALUES:
        for sl_mode in SL_MODES:
            config_name = f"RR={rr}, SL={sl_mode}"
            print(f"Testing {config_name}...", end=' ', flush=True)

            try:
                r_mults = backtest_1800_orb(rr, sl_mode)
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
