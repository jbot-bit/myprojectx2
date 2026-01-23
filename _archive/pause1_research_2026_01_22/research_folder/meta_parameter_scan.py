#!/usr/bin/env python3
"""
Meta-Parameter Scanner - Find OPTIMAL ORB window size and entry timing

Tests combinations of:
- ORB window: 5, 10, 15, 30 minutes
- Entry confirmation: 1-minute close, 5-minute close
- ORB times: 0900, 1000, 2300 (representative sample)
- RR targets: 1R, 3R, 6R
- SL modes: HALF, FULL

This determines if our assumptions (5min ORB + 1min entry) are actually optimal.
"""

import sys
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta
import pandas as pd
import numpy as np
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_app.cloud_mode import get_database_connection

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")

# Test parameters
INSTRUMENT = 'MGC'
START_DATE = '2024-01-02'
END_DATE = '2026-01-10'

# Meta-parameters to test
ORB_WINDOWS = [5, 10, 15, 30]  # minutes
ENTRY_CONFIRMATIONS = [1, 5]   # minutes (bar size for entry)
ORB_TIMES = ['0900', '1000', '2300']
RR_TARGETS = [1.0, 3.0, 6.0]
SL_MODES = ['HALF', 'FULL']


def calculate_orb_from_bars(bars_df, orb_start_time, orb_window_minutes):
    """
    Calculate ORB from bars within window.

    Args:
        bars_df: DataFrame with bars (ts_local, open, high, low, close)
        orb_start_time: time object (e.g., time(9, 0))
        orb_window_minutes: ORB window size in minutes

    Returns:
        dict with orb_high, orb_low, orb_size, orb_midpoint
    """
    orb_end_time = (datetime.combine(datetime.today(), orb_start_time) + timedelta(minutes=orb_window_minutes)).time()

    orb_bars = bars_df[
        (bars_df['time_local'] >= orb_start_time) &
        (bars_df['time_local'] < orb_end_time)
    ]

    if len(orb_bars) == 0:
        return None

    orb_high = orb_bars['high'].max()
    orb_low = orb_bars['low'].min()
    orb_size = orb_high - orb_low
    orb_midpoint = (orb_high + orb_low) / 2.0

    return {
        'high': orb_high,
        'low': orb_low,
        'size': orb_size,
        'midpoint': orb_midpoint
    }


def detect_breakout_with_confirmation(bars_df, orb, orb_end_time, confirm_bars, bar_size_minutes):
    """
    Detect first breakout using N-bar confirmation on specified bar size.

    Args:
        bars_df: DataFrame with bars after ORB
        orb: ORB dict
        orb_end_time: time object for when ORB completes
        confirm_bars: Number of bars for confirmation (usually 1)
        bar_size_minutes: Bar size for entry confirmation (1 or 5)

    Returns:
        (entry_bar, direction) or None
    """
    # Filter bars after ORB
    post_orb_bars = bars_df[bars_df['time_local'] >= orb_end_time].copy()

    if len(post_orb_bars) == 0:
        return None

    # If bar_size_minutes > 1, need to resample bars
    if bar_size_minutes == 5:
        # Resample to 5-minute bars
        post_orb_bars = resample_to_5m(post_orb_bars)

    # Check for first close outside ORB
    for idx, bar in post_orb_bars.iterrows():
        if bar['close'] > orb['high']:
            return (bar, 'UP')
        elif bar['close'] < orb['low']:
            return (bar, 'DOWN')

    return None


def resample_to_5m(bars_1m):
    """Resample 1-minute bars to 5-minute bars."""
    # Group by 5-minute buckets
    bars_1m = bars_1m.copy()
    bars_1m['bucket'] = bars_1m['ts_local'].apply(
        lambda x: x.replace(minute=(x.minute // 5) * 5, second=0, microsecond=0)
    )

    bars_5m = bars_1m.groupby('bucket').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).reset_index()

    bars_5m['ts_local'] = bars_5m['bucket']
    bars_5m['time_local'] = bars_5m['ts_local'].dt.time

    return bars_5m


def simulate_trade(entry_bar, direction, orb, remaining_bars, rr, sl_mode):
    """Simulate trade from entry to resolution."""
    entry_price = entry_bar['close']

    if sl_mode == 'HALF':
        stop_price = orb['midpoint']
    else:
        stop_price = orb['low'] if direction == 'UP' else orb['high']

    if direction == 'UP':
        risk = entry_price - stop_price
        target_price = entry_price + (risk * rr)
    else:
        risk = stop_price - entry_price
        target_price = entry_price - (risk * rr)

    if risk <= 0:
        return {'outcome': 'NO_TRADE', 'r_multiple': 0.0}

    # Check resolution
    for idx, bar in remaining_bars.iterrows():
        if direction == 'UP':
            if bar['low'] <= stop_price:
                return {'outcome': 'LOSS', 'r_multiple': -1.0}
            if bar['high'] >= target_price:
                return {'outcome': 'WIN', 'r_multiple': rr}
        else:
            if bar['high'] >= stop_price:
                return {'outcome': 'LOSS', 'r_multiple': -1.0}
            if bar['low'] <= target_price:
                return {'outcome': 'WIN', 'r_multiple': rr}

    # Time exit
    if len(remaining_bars) > 0:
        final_bar = remaining_bars.iloc[-1]
        final_price = final_bar['close']
        pnl = (final_price - entry_price) if direction == 'UP' else (entry_price - final_price)
        r_mult = pnl / risk if risk != 0 else 0
        return {'outcome': 'TIME_EXIT', 'r_multiple': r_mult}

    return {'outcome': 'NO_TRADE', 'r_multiple': 0.0}


def backtest_meta_config(orb_time, orb_window_min, entry_confirm_min, rr, sl_mode):
    """
    Backtest a single meta-parameter configuration.

    Returns:
        dict with trades, avg_r, win_rate
    """
    conn = get_database_connection()

    # Parse ORB time
    orb_hour = int(orb_time[:2])
    orb_minute = int(orb_time[2:])
    orb_start_time = dt_time(orb_hour, orb_minute)
    orb_end_time = (datetime.combine(datetime.today(), orb_start_time) + timedelta(minutes=orb_window_min)).time()

    trades = []

    # Get all trading dates
    dates_df = conn.execute(f"""
        SELECT DISTINCT date_local
        FROM daily_features_v2
        WHERE instrument = '{INSTRUMENT}'
        AND date_local >= '{START_DATE}'
        AND date_local <= '{END_DATE}'
        ORDER BY date_local
    """).fetchdf()

    for trading_date_str in dates_df['date_local']:
        trading_date = pd.to_datetime(trading_date_str).date()

        # Load 1-minute bars for this trading day (09:00 → next 09:00)
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

        # Calculate ORB with specified window
        orb = calculate_orb_from_bars(bars, orb_start_time, orb_window_min)
        if not orb:
            continue

        # Detect breakout with specified entry confirmation
        entry_result = detect_breakout_with_confirmation(
            bars, orb, orb_end_time, confirm_bars=1, bar_size_minutes=entry_confirm_min
        )

        if not entry_result:
            continue

        entry_bar, direction = entry_result

        # Get remaining bars
        remaining_bars = bars[bars['ts_local'] > entry_bar.get('ts_local', entry_bar.name)]

        # Simulate trade
        trade_result = simulate_trade(entry_bar, direction, orb, remaining_bars, rr, sl_mode)

        if trade_result['outcome'] != 'NO_TRADE':
            trades.append(trade_result['r_multiple'])

    # Calculate metrics
    if len(trades) == 0:
        return {
            'trades': 0,
            'avg_r': 0.0,
            'win_rate': 0.0,
            'total_r': 0.0
        }

    trades_arr = np.array(trades)
    wins = (trades_arr > 0).sum()

    return {
        'trades': len(trades),
        'avg_r': trades_arr.mean(),
        'win_rate': (wins / len(trades) * 100),
        'total_r': trades_arr.sum()
    }


def main():
    """Run meta-parameter scan."""
    print("=" * 80)
    print("META-PARAMETER SCAN")
    print("Finding optimal ORB window size and entry timing")
    print("=" * 80)
    print()

    # Calculate total combinations
    total = len(ORB_TIMES) * len(ORB_WINDOWS) * len(ENTRY_CONFIRMATIONS) * len(RR_TARGETS) * len(SL_MODES)
    print(f"Testing {total} combinations...")
    print(f"  - ORB times: {ORB_TIMES}")
    print(f"  - ORB windows: {ORB_WINDOWS} minutes")
    print(f"  - Entry confirmations: {ENTRY_CONFIRMATIONS} minute bars")
    print(f"  - RR targets: {RR_TARGETS}")
    print(f"  - SL modes: {SL_MODES}")
    print()

    results = []
    count = 0

    for orb_time in ORB_TIMES:
        for orb_window in ORB_WINDOWS:
            for entry_confirm in ENTRY_CONFIRMATIONS:
                for rr in RR_TARGETS:
                    for sl_mode in SL_MODES:
                        count += 1
                        config_name = f"{orb_time}_W{orb_window}m_E{entry_confirm}m_RR{rr}_{sl_mode}"

                        print(f"[{count}/{total}] {config_name}...", end=' ', flush=True)

                        metrics = backtest_meta_config(orb_time, orb_window, entry_confirm, rr, sl_mode)

                        results.append({
                            'config': config_name,
                            'orb_time': orb_time,
                            'orb_window_min': orb_window,
                            'entry_confirm_min': entry_confirm,
                            'rr': rr,
                            'sl_mode': sl_mode,
                            **metrics
                        })

                        print(f"{metrics['trades']} trades | {metrics['win_rate']:.1f}% WR | {metrics['avg_r']:+.3f}R")

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    # Convert to DataFrame
    results_df = pd.DataFrame(results)

    # Sort by avg_r
    results_df = results_df.sort_values('avg_r', ascending=False)

    # Display top 20
    print("TOP 20 CONFIGURATIONS:")
    print()
    cols = ['config', 'trades', 'win_rate', 'avg_r', 'total_r']
    print(results_df[cols].head(20).to_string(index=False))
    print()

    # Analyze by parameter
    print("=" * 80)
    print("PARAMETER ANALYSIS")
    print("=" * 80)
    print()

    print("1. ORB WINDOW SIZE (averaged across all other params):")
    window_analysis = results_df.groupby('orb_window_min')['avg_r'].mean().sort_values(ascending=False)
    for window, avg_r in window_analysis.items():
        print(f"   {window:2d} minutes: {avg_r:+.3f}R avg")
    print()

    print("2. ENTRY CONFIRMATION (averaged across all other params):")
    entry_analysis = results_df.groupby('entry_confirm_min')['avg_r'].mean().sort_values(ascending=False)
    for entry, avg_r in entry_analysis.items():
        print(f"   {entry:2d}-minute bars: {avg_r:+.3f}R avg")
    print()

    print("3. ORB TIME (averaged across all other params):")
    time_analysis = results_df.groupby('orb_time')['avg_r'].mean().sort_values(ascending=False)
    for orb_time, avg_r in time_analysis.items():
        print(f"   {orb_time}: {avg_r:+.3f}R avg")
    print()

    # Save results
    output_csv = Path(__file__).parent / 'meta_parameter_scan_results.csv'
    results_df.to_csv(output_csv, index=False)
    print(f"[OK] Saved full results to {output_csv}")
    print()

    print("=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)
    print()

    best_config = results_df.iloc[0]
    print(f"BEST CONFIGURATION: {best_config['config']}")
    print(f"  - ORB Window: {best_config['orb_window_min']} minutes")
    print(f"  - Entry Confirmation: {best_config['entry_confirm_min']}-minute bars")
    print(f"  - Trades: {best_config['trades']}")
    print(f"  - Win Rate: {best_config['win_rate']:.1f}%")
    print(f"  - Avg R: {best_config['avg_r']:+.3f}R")
    print(f"  - Total R: {best_config['total_r']:+.1f}R")
    print()

    print("=" * 80)


if __name__ == "__main__":
    main()
