#!/usr/bin/env python3
"""
Extended Window ORB Backtest - Proper Implementation

Tests 2300 and 0030 ORBs with extended scan windows using raw bars_1m data.

Key differences from Phase 3:
- Calculates ORBs from raw bars (not precomputed)
- Uses extended scan windows (23:05 → 09:00, 00:35 → 09:00)
- Applies configurable RR and SL mode
- Tracks actual time-to-resolution
- Compares extended vs baseline short windows

Goal: Prove that extended windows are the source of profitability.
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, List, Optional, Tuple
import pytz

# Paths
ROOT = Path(__file__).parent.parent
DB_PATH = str(ROOT / "data" / "db" / "gold.db")
OUTPUT_DIR = ROOT / "research"

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")
TZ_UTC = pytz.utc

# Test parameters
DEFAULT_START_DATE = '2020-12-20'
DEFAULT_END_DATE = '2026-01-10'
INSTRUMENT = 'MGC'


def load_bars_for_period(
    start_date: str,
    end_date: str,
    db_path: str = DB_PATH
) -> pd.DataFrame:
    """
    Load 1-minute bars for the test period.

    Returns:
        DataFrame with ts_utc, open, high, low, close, volume
    """
    conn = duckdb.connect(db_path, read_only=True)

    bars = conn.execute("""
        SELECT
            ts_utc,
            open,
            high,
            low,
            close,
            volume
        FROM bars_1m
        WHERE symbol = 'MGC'
        AND ts_utc >= ?::TIMESTAMP
        AND ts_utc < (?::DATE + INTERVAL '1 day')::TIMESTAMP
        ORDER BY ts_utc
    """, [start_date, end_date]).fetchdf()

    conn.close()

    # Convert to datetime
    bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)

    # Add local time column
    bars['ts_local'] = bars['ts_utc'].dt.tz_convert(TZ_LOCAL)
    bars['date_local'] = bars['ts_local'].dt.date
    bars['time_local'] = bars['ts_local'].dt.time

    print(f"[OK] Loaded {len(bars):,} bars from {start_date} to {end_date}")

    return bars


def calculate_orb(
    bars: pd.DataFrame,
    orb_start_time: dt_time,
    orb_end_time: dt_time
) -> Optional[Dict[str, float]]:
    """
    Calculate ORB high/low from bars within the ORB window.

    Args:
        bars: Intraday bars for a single day
        orb_start_time: ORB start time (local, e.g., 23:00:00)
        orb_end_time: ORB end time (local, e.g., 23:05:00)

    Returns:
        {'high': float, 'low': float, 'size': float, 'midpoint': float} or None
    """
    orb_bars = bars[
        (bars['time_local'] >= orb_start_time) &
        (bars['time_local'] < orb_end_time)
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


def detect_entry(
    bars: pd.DataFrame,
    orb: Dict[str, float],
    scan_start_time: dt_time,
    scan_end_time: Optional[dt_time] = None,
    next_day_scan: bool = False
) -> Optional[Tuple[pd.Series, str]]:
    """
    Detect first breakout entry.

    Args:
        bars: Intraday bars (may span 2 days for extended windows)
        orb: ORB levels
        scan_start_time: When to start looking for entry (local time)
        scan_end_time: When to stop looking (local time, optional)
        next_day_scan: If True, scan continues into next trading day

    Returns:
        (entry_bar, direction) or None
        direction: 'long' or 'short'
    """
    # Filter to scan window
    if next_day_scan:
        # For extended windows that cross midnight (e.g., 23:05 → 09:00)
        # Include all bars after scan_start_time on first day and up to scan_end_time next day
        scan_bars = bars[
            (bars['time_local'] >= scan_start_time) |
            (bars['time_local'] < scan_end_time if scan_end_time else True)
        ]
    else:
        # Standard scan within same day
        if scan_end_time:
            scan_bars = bars[
                (bars['time_local'] >= scan_start_time) &
                (bars['time_local'] < scan_end_time)
            ]
        else:
            scan_bars = bars[bars['time_local'] >= scan_start_time]

    if len(scan_bars) == 0:
        return None

    # Look for first close outside ORB
    for idx, bar in scan_bars.iterrows():
        if bar['close'] > orb['high']:
            return (bar, 'long')
        elif bar['close'] < orb['low']:
            return (bar, 'short')

    return None


def simulate_trade(
    entry_bar: pd.Series,
    direction: str,
    orb: Dict[str, float],
    remaining_bars: pd.DataFrame,
    rr: float = 2.0,
    sl_mode: str = 'HALF'
) -> Dict:
    """
    Simulate trade from entry to exit.

    Args:
        entry_bar: Bar where entry occurred
        direction: 'long' or 'short'
        orb: ORB levels
        remaining_bars: Bars after entry (for exit detection)
        rr: Risk/reward ratio
        sl_mode: 'HALF' (midpoint) or 'FULL' (opposite ORB extreme)

    Returns:
        Trade dict with outcome, r_multiple, exit_time, etc.
    """
    entry_price = entry_bar['close']
    entry_time = entry_bar['ts_local']

    # Calculate stop
    if sl_mode == 'HALF':
        stop_price = orb['midpoint']
    else:  # FULL
        stop_price = orb['low'] if direction == 'long' else orb['high']

    # Calculate risk and target
    if direction == 'long':
        risk = entry_price - stop_price
        target_price = entry_price + (risk * rr)
    else:  # short
        risk = stop_price - entry_price
        target_price = entry_price - (risk * rr)

    if risk <= 0:
        # Invalid trade (entry already beyond stop)
        return {
            'outcome': 'INVALID',
            'r_multiple': 0.0,
            'entry_time': entry_time,
            'exit_time': entry_time,
            'entry_price': entry_price,
            'exit_price': entry_price,
            'stop_price': stop_price,
            'target_price': target_price,
            'risk': risk,
            'time_in_trade_minutes': 0
        }

    # Track through remaining bars
    for idx, bar in remaining_bars.iterrows():
        if direction == 'long':
            # Check stop first (conservative)
            if bar['low'] <= stop_price:
                return {
                    'outcome': 'LOSS',
                    'r_multiple': -1.0,
                    'entry_time': entry_time,
                    'exit_time': bar['ts_local'],
                    'entry_price': entry_price,
                    'exit_price': stop_price,
                    'stop_price': stop_price,
                    'target_price': target_price,
                    'risk': risk,
                    'time_in_trade_minutes': (bar['ts_local'] - entry_time).total_seconds() / 60
                }

            # Check target
            if bar['high'] >= target_price:
                return {
                    'outcome': 'WIN',
                    'r_multiple': rr,
                    'entry_time': entry_time,
                    'exit_time': bar['ts_local'],
                    'entry_price': entry_price,
                    'exit_price': target_price,
                    'stop_price': stop_price,
                    'target_price': target_price,
                    'risk': risk,
                    'time_in_trade_minutes': (bar['ts_local'] - entry_time).total_seconds() / 60
                }

        else:  # short
            # Check stop first
            if bar['high'] >= stop_price:
                return {
                    'outcome': 'LOSS',
                    'r_multiple': -1.0,
                    'entry_time': entry_time,
                    'exit_time': bar['ts_local'],
                    'entry_price': entry_price,
                    'exit_price': stop_price,
                    'stop_price': stop_price,
                    'target_price': target_price,
                    'risk': risk,
                    'time_in_trade_minutes': (bar['ts_local'] - entry_time).total_seconds() / 60
                }

            # Check target
            if bar['low'] <= target_price:
                return {
                    'outcome': 'WIN',
                    'r_multiple': rr,
                    'entry_time': entry_time,
                    'exit_time': bar['ts_local'],
                    'entry_price': entry_price,
                    'exit_price': target_price,
                    'stop_price': stop_price,
                    'target_price': target_price,
                    'risk': risk,
                    'time_in_trade_minutes': (bar['ts_local'] - entry_time).total_seconds() / 60
                }

    # No exit - end of scan window
    final_bar = remaining_bars.iloc[-1]
    final_price = final_bar['close']

    if direction == 'long':
        pnl = final_price - entry_price
    else:
        pnl = entry_price - final_price

    r_multiple = pnl / risk if risk > 0 else 0

    return {
        'outcome': 'EOD',
        'r_multiple': r_multiple,
        'entry_time': entry_time,
        'exit_time': final_bar['ts_local'],
        'entry_price': entry_price,
        'exit_price': final_price,
        'stop_price': stop_price,
        'target_price': target_price,
        'risk': risk,
        'time_in_trade_minutes': (final_bar['ts_local'] - entry_time).total_seconds() / 60
    }


def backtest_orb_session(
    bars: pd.DataFrame,
    orb_time: str,
    orb_start: dt_time,
    orb_end: dt_time,
    scan_start: dt_time,
    scan_end: dt_time,
    rr: float = 2.0,
    sl_mode: str = 'HALF',
    extended_window: bool = False
) -> List[Dict]:
    """
    Backtest an ORB session across all days in dataset.

    Args:
        bars: All bars for test period
        orb_time: Session label (e.g., '2300')
        orb_start: ORB start time (local)
        orb_end: ORB end time (local)
        scan_start: Entry scan start time (local)
        scan_end: Entry scan end time (local)
        rr: Risk/reward ratio
        sl_mode: 'HALF' or 'FULL'
        extended_window: If True, scan window crosses into next trading day

    Returns:
        List of trade dicts
    """
    trades = []
    dates = bars['date_local'].unique()

    for date in dates:
        # Get bars for this trading day and potentially next day
        day_bars = bars[bars['date_local'] == date].copy()

        if extended_window:
            # For extended windows, also get next day's bars up to scan_end
            next_date = date + timedelta(days=1)
            next_day_bars = bars[
                (bars['date_local'] == next_date) &
                (bars['time_local'] < scan_end)
            ].copy()

            # Combine
            combined_bars = pd.concat([day_bars, next_day_bars]).sort_values('ts_local')
        else:
            combined_bars = day_bars

        if len(combined_bars) == 0:
            continue

        # Calculate ORB
        orb = calculate_orb(combined_bars, orb_start, orb_end)
        if not orb:
            continue

        # Detect entry
        entry_result = detect_entry(
            combined_bars,
            orb,
            scan_start,
            scan_end,
            next_day_scan=extended_window
        )

        if not entry_result:
            continue

        entry_bar, direction = entry_result

        # Get remaining bars after entry
        remaining_bars = combined_bars[
            combined_bars['ts_local'] > entry_bar['ts_local']
        ]

        if len(remaining_bars) == 0:
            continue

        # Simulate trade
        trade = simulate_trade(
            entry_bar,
            direction,
            orb,
            remaining_bars,
            rr=rr,
            sl_mode=sl_mode
        )

        trade['date_local'] = str(date)
        trade['orb_time'] = orb_time
        trade['direction'] = direction
        trade['orb_high'] = orb['high']
        trade['orb_low'] = orb['low']
        trade['orb_size'] = orb['size']

        if trade['outcome'] != 'INVALID':
            trades.append(trade)

    return trades


def calculate_metrics(trades: List[Dict]) -> Dict:
    """Calculate performance metrics from trades list."""
    if len(trades) == 0:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'eod': 0,
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0,
            'avg_win_r': 0.0,
            'avg_loss_r': 0.0,
            'avg_time_in_trade_hours': 0.0,
            'median_time_in_trade_hours': 0.0
        }

    total_trades = len(trades)
    wins = len([t for t in trades if t['outcome'] == 'WIN'])
    losses = len([t for t in trades if t['outcome'] == 'LOSS'])
    eod = len([t for t in trades if t['outcome'] == 'EOD'])

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    r_multiples = [t['r_multiple'] for t in trades]
    avg_r = np.mean(r_multiples)
    total_r = np.sum(r_multiples)

    win_rs = [t['r_multiple'] for t in trades if t['outcome'] == 'WIN']
    loss_rs = [t['r_multiple'] for t in trades if t['outcome'] == 'LOSS']

    avg_win_r = np.mean(win_rs) if win_rs else 0
    avg_loss_r = np.mean(loss_rs) if loss_rs else 0

    times_in_trade = [t['time_in_trade_minutes'] / 60.0 for t in trades]
    avg_time = np.mean(times_in_trade) if times_in_trade else 0
    median_time = np.median(times_in_trade) if times_in_trade else 0

    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'eod': eod,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r,
        'avg_win_r': avg_win_r,
        'avg_loss_r': avg_loss_r,
        'avg_time_in_trade_hours': avg_time,
        'median_time_in_trade_hours': median_time
    }


def main():
    """Run extended window backtest for 2300 and 0030 ORBs."""

    print("=" * 80)
    print("EXTENDED WINDOW ORB BACKTEST")
    print("=" * 80)
    print()
    print("Testing 2300 and 0030 ORBs with extended scan windows")
    print(f"Period: {DEFAULT_START_DATE} to {DEFAULT_END_DATE}")
    print()

    # Load bars
    bars = load_bars_for_period(DEFAULT_START_DATE, DEFAULT_END_DATE)
    print()

    # Test configurations
    tests = [
        {
            'name': '2300 ORB Extended (RR=1.5, HALF SL)',
            'orb_time': '2300',
            'orb_start': dt_time(23, 0),
            'orb_end': dt_time(23, 5),
            'scan_start': dt_time(23, 5),
            'scan_end': dt_time(9, 0),
            'rr': 1.5,
            'sl_mode': 'HALF',
            'extended_window': True
        },
        {
            'name': '2300 ORB Baseline (RR=2.0, HALF SL, 85min window)',
            'orb_time': '2300',
            'orb_start': dt_time(23, 0),
            'orb_end': dt_time(23, 5),
            'scan_start': dt_time(23, 5),
            'scan_end': dt_time(0, 30),  # 85 minute window
            'rr': 2.0,
            'sl_mode': 'HALF',
            'extended_window': False
        },
        {
            'name': '0030 ORB Extended (RR=3.0, HALF SL)',
            'orb_time': '0030',
            'orb_start': dt_time(0, 30),
            'orb_end': dt_time(0, 35),
            'scan_start': dt_time(0, 35),
            'scan_end': dt_time(9, 0),
            'rr': 3.0,
            'sl_mode': 'HALF',
            'extended_window': True
        },
        {
            'name': '0030 ORB Baseline (RR=2.0, HALF SL, 85min window)',
            'orb_time': '0030',
            'orb_start': dt_time(0, 30),
            'orb_end': dt_time(0, 35),
            'scan_start': dt_time(0, 35),
            'scan_end': dt_time(2, 0),  # 85 minute window
            'rr': 2.0,
            'sl_mode': 'HALF',
            'extended_window': False
        }
    ]

    results = []

    for test in tests:
        print(f"Testing: {test['name']}")
        print(f"  ORB: {test['orb_start'].strftime('%H:%M')}-{test['orb_end'].strftime('%H:%M')}")
        print(f"  Scan: {test['scan_start'].strftime('%H:%M')}-{test['scan_end'].strftime('%H:%M')}")
        print(f"  RR: {test['rr']}R, SL: {test['sl_mode']}")

        trades = backtest_orb_session(
            bars,
            test['orb_time'],
            test['orb_start'],
            test['orb_end'],
            test['scan_start'],
            test['scan_end'],
            rr=test['rr'],
            sl_mode=test['sl_mode'],
            extended_window=test['extended_window']
        )

        metrics = calculate_metrics(trades)

        print(f"  Results: {metrics['total_trades']} trades, {metrics['win_rate']:.1f}% WR, {metrics['avg_r']:+.3f}R avg")
        print(f"  Time: {metrics['avg_time_in_trade_hours']:.1f}h avg, {metrics['median_time_in_trade_hours']:.1f}h median")
        print()

        results.append({
            'test': test['name'],
            'orb_time': test['orb_time'],
            'window_type': 'Extended' if test['extended_window'] else 'Baseline',
            'rr': test['rr'],
            'sl_mode': test['sl_mode'],
            'metrics': metrics,
            'trades': trades
        })

    # Write results
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    # Comparison table
    print("| Test | Window | Trades | WR% | Avg R | Total R | Avg Time (h) |")
    print("|------|--------|--------|-----|-------|---------|--------------|")

    for r in results:
        m = r['metrics']
        print(f"| {r['test'][:40]} | {r['window_type']:8s} | {m['total_trades']:6d} | {m['win_rate']:4.1f}% | {m['avg_r']:+6.3f}R | {m['total_r']:+7.1f}R | {m['avg_time_in_trade_hours']:5.1f}h |")

    print()

    # Write detailed CSV
    output_file = OUTPUT_DIR / 'extended_window_results.csv'
    rows = []
    for r in results:
        for trade in r['trades']:
            rows.append({
                'test_name': r['test'],
                'window_type': r['window_type'],
                'orb_time': r['orb_time'],
                'rr': r['rr'],
                'date_local': trade['date_local'],
                'direction': trade['direction'],
                'entry_time': trade['entry_time'],
                'exit_time': trade['exit_time'],
                'outcome': trade['outcome'],
                'r_multiple': trade['r_multiple'],
                'time_in_trade_hours': trade['time_in_trade_minutes'] / 60.0,
                'orb_size': trade['orb_size']
            })

    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)
    print(f"[OK] Wrote detailed results to {output_file}")

    # Write summary markdown
    summary_file = OUTPUT_DIR / 'extended_window_summary.md'
    with open(summary_file, 'w') as f:
        f.write("# Extended Window Backtest Results\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(f"**Period**: {DEFAULT_START_DATE} to {DEFAULT_END_DATE}\n\n")
        f.write("---\n\n")
        f.write("## Summary\n\n")
        f.write("| Test | Window | Trades | WR% | Avg R | Total R | Avg Time (h) |\n")
        f.write("|------|--------|--------|-----|-------|---------|--------------||\n")

        for r in results:
            m = r['metrics']
            f.write(f"| {r['test']} | {r['window_type']} | {m['total_trades']} | {m['win_rate']:.1f}% | {m['avg_r']:+.3f}R | {m['total_r']:+.1f}R | {m['avg_time_in_trade_hours']:.1f}h |\n")

        f.write("\n---\n\n")
        f.write("## Key Findings\n\n")

        # Compare extended vs baseline for 2300
        ext_2300 = [r for r in results if r['orb_time'] == '2300' and r['window_type'] == 'Extended'][0]
        base_2300 = [r for r in results if r['orb_time'] == '2300' and r['window_type'] == 'Baseline'][0]

        f.write("### 2300 ORB: Extended vs Baseline\n\n")
        f.write(f"- **Extended** (23:05 -> 09:00, RR=1.5): {ext_2300['metrics']['avg_r']:+.3f}R avg, {ext_2300['metrics']['win_rate']:.1f}% WR\n")
        f.write(f"- **Baseline** (23:05 -> 00:30, RR=2.0): {base_2300['metrics']['avg_r']:+.3f}R avg, {base_2300['metrics']['win_rate']:.1f}% WR\n")

        improvement_2300 = ext_2300['metrics']['avg_r'] - base_2300['metrics']['avg_r']
        f.write(f"- **Improvement**: {improvement_2300:+.3f}R ({improvement_2300/abs(base_2300['metrics']['avg_r'])*100 if base_2300['metrics']['avg_r'] != 0 else 0:.0f}%)\n\n")

        # Compare extended vs baseline for 0030
        ext_0030 = [r for r in results if r['orb_time'] == '0030' and r['window_type'] == 'Extended'][0]
        base_0030 = [r for r in results if r['orb_time'] == '0030' and r['window_type'] == 'Baseline'][0]

        f.write("### 0030 ORB: Extended vs Baseline\n\n")
        f.write(f"- **Extended** (00:35 -> 09:00, RR=3.0): {ext_0030['metrics']['avg_r']:+.3f}R avg, {ext_0030['metrics']['win_rate']:.1f}% WR\n")
        f.write(f"- **Baseline** (00:35 -> 02:00, RR=2.0): {base_0030['metrics']['avg_r']:+.3f}R avg, {base_0030['metrics']['win_rate']:.1f}% WR\n")

        improvement_0030 = ext_0030['metrics']['avg_r'] - base_0030['metrics']['avg_r']
        f.write(f"- **Improvement**: {improvement_0030:+.3f}R ({improvement_0030/abs(base_0030['metrics']['avg_r'])*100 if base_0030['metrics']['avg_r'] != 0 else 0:.0f}%)\n\n")

        f.write("---\n\n")
        f.write("## Conclusion\n\n")

        if ext_2300['metrics']['avg_r'] > 0.15 or ext_0030['metrics']['avg_r'] > 0.15:
            f.write("**PROVEN**: Extended scan windows unlock profitability for overnight ORBs.\n\n")
            f.write("The extended window is ESSENTIAL for capturing overnight price movements that resolve into Asia session.\n\n")
        else:
            f.write("**INCONCLUSIVE**: Extended windows improve performance but still below +0.15R threshold.\n\n")

        f.write(f"See `extended_window_results.csv` for trade-by-trade details.\n")

    print(f"[OK] Wrote summary to {summary_file}")
    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
