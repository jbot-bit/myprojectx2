#!/usr/bin/env python3
"""
ORB Filter Analysis - Find Conditions That Improve Win Rates

Analyzes what makes ORB setups work by comparing winners vs losers.

Filters tested:
1. ORB size (% of price) - avoid tiny/huge ORBs
2. Session bias - did Asia high/low already break?
3. Gap analysis - overnight gap direction
4. Pre-ORB momentum - what happened before ORB?
5. Directional alignment - trade with or against session?
6. Time of week - Monday vs Friday performance
7. Recent volatility - ATR analysis

Output:
- Which filters improve win rate
- Optimal filter values
- Expected performance with filters
"""

import duckdb
import pandas as pd
import numpy as np
import pytz
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta, date
from typing import Dict, List, Optional, Tuple

# Paths
ROOT = Path(__file__).parent
DB_PATH = str(ROOT / "data" / "db" / "gold.db")
OUTPUT_DIR = ROOT / "research"

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")
TZ_UTC = pytz.utc

INSTRUMENT = 'MGC'


def load_orb_trades(orb_time: str, rr: float, sl_mode: str, window: str) -> pd.DataFrame:
    """
    Simulate and load all trades for a specific setup.
    Returns DataFrame with trade results and date info.
    """
    conn = duckdb.connect(DB_PATH, read_only=True)

    # Get date range
    start_date = date(2020, 12, 20)
    end_date = date(2026, 1, 10)

    trades = []
    current_date = start_date

    orb_hour = int(orb_time[:2])
    orb_minute = int(orb_time[2:])

    while current_date <= end_date:
        # Load bars for trading day
        start_dt_local = TZ_LOCAL.localize(datetime.combine(current_date, dt_time(9, 0)))

        if window == 'extended':
            end_dt_local = start_dt_local + timedelta(days=1)
        else:
            end_dt_local = start_dt_local + timedelta(hours=8)

        start_dt_utc = start_dt_local.astimezone(TZ_UTC)
        end_dt_utc = end_dt_local.astimezone(TZ_UTC)

        bars = conn.execute("""
            SELECT ts_utc, open, high, low, close, volume
            FROM bars_1m
            WHERE symbol = ?
            AND ts_utc >= ?
            AND ts_utc < ?
            ORDER BY ts_utc
        """, [INSTRUMENT, start_dt_utc, end_dt_utc]).fetchdf()

        if len(bars) == 0:
            current_date += timedelta(days=1)
            continue

        bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)
        bars['ts_local'] = bars['ts_utc'].dt.tz_convert(TZ_LOCAL)
        bars['time_local'] = bars['ts_local'].dt.time

        # Calculate ORB
        orb_start = dt_time(orb_hour, orb_minute)
        orb_end = dt_time(orb_hour, orb_minute + 5)

        orb_bars = bars[(bars['time_local'] >= orb_start) & (bars['time_local'] < orb_end)]

        if len(orb_bars) == 0:
            current_date += timedelta(days=1)
            continue

        orb_high = orb_bars['high'].max()
        orb_low = orb_bars['low'].min()
        orb_size = orb_high - orb_low
        orb_mid = (orb_high + orb_low) / 2.0

        # Get pre-ORB price (09:00 open for context)
        pre_orb_bars = bars[bars['time_local'] < orb_start]
        if len(pre_orb_bars) > 0:
            pre_orb_high = pre_orb_bars['high'].max()
            pre_orb_low = pre_orb_bars['low'].min()
            pre_orb_close = pre_orb_bars.iloc[-1]['close']
        else:
            pre_orb_high = orb_high
            pre_orb_low = orb_low
            pre_orb_close = orb_bars.iloc[0]['open']

        # Detect breakout
        scan_start_time = dt_time(orb_hour, orb_minute + 5)
        if window == 'extended':
            scan_end_time = dt_time(9, 0)
        else:
            scan_end_time = dt_time(17, 0)

        scan_start_dt = TZ_LOCAL.localize(datetime.combine(current_date, scan_start_time))

        if scan_end_time < scan_start_time:
            scan_end_dt = TZ_LOCAL.localize(datetime.combine(current_date + timedelta(days=1), scan_end_time))
        else:
            scan_end_dt = TZ_LOCAL.localize(datetime.combine(current_date, scan_end_time))

        scan_bars = bars[(bars['ts_local'] >= scan_start_dt) & (bars['ts_local'] < scan_end_dt)]

        if len(scan_bars) == 0:
            current_date += timedelta(days=1)
            continue

        # Find first breakout
        entry_bar = None
        direction = None

        for idx, bar in scan_bars.iterrows():
            if bar['close'] > orb_high:
                entry_bar = bar
                direction = 'long'
                break
            elif bar['close'] < orb_low:
                entry_bar = bar
                direction = 'short'
                break

        if entry_bar is None:
            current_date += timedelta(days=1)
            continue

        # Calculate trade
        entry_price = entry_bar['close']
        entry_ts = entry_bar['ts_local']

        if sl_mode == 'HALF':
            stop_price = orb_mid
        else:
            stop_price = orb_low if direction == 'long' else orb_high

        if direction == 'long':
            risk = entry_price - stop_price
            target_price = entry_price + (risk * rr)
        else:
            risk = stop_price - entry_price
            target_price = entry_price - (risk * rr)

        if risk <= 0:
            current_date += timedelta(days=1)
            continue

        # Simulate outcome
        remaining_bars = bars[bars['ts_local'] > entry_ts]
        outcome = 'TIME_EXIT'
        r_multiple = 0.0
        exit_ts = None

        for idx, bar in remaining_bars.iterrows():
            if direction == 'long':
                if bar['low'] <= stop_price:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    exit_ts = bar['ts_local']
                    break
                if bar['high'] >= target_price:
                    outcome = 'WIN'
                    r_multiple = rr
                    exit_ts = bar['ts_local']
                    break
            else:
                if bar['high'] >= stop_price:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    exit_ts = bar['ts_local']
                    break
                if bar['low'] <= target_price:
                    outcome = 'WIN'
                    r_multiple = rr
                    exit_ts = bar['ts_local']
                    break

        if exit_ts is None and len(remaining_bars) > 0:
            final_bar = remaining_bars.iloc[-1]
            exit_ts = final_bar['ts_local']
            final_price = final_bar['close']

            if direction == 'long':
                pnl = final_price - entry_price
            else:
                pnl = entry_price - final_price

            r_multiple = pnl / risk

        # Store trade with metadata
        trades.append({
            'date': current_date,
            'day_of_week': current_date.strftime('%A'),
            'outcome': outcome,
            'r_multiple': r_multiple,
            'direction': direction,
            'orb_size': orb_size,
            'orb_size_pct': (orb_size / orb_mid * 100) if orb_mid > 0 else 0,
            'entry_price': entry_price,
            'orb_high': orb_high,
            'orb_low': orb_low,
            'orb_mid': orb_mid,
            'pre_orb_high': pre_orb_high,
            'pre_orb_low': pre_orb_low,
            'pre_orb_close': pre_orb_close,
            'session_high_taken': pre_orb_high > orb_high if direction == 'long' else False,
            'session_low_taken': pre_orb_low < orb_low if direction == 'short' else False,
            'with_pre_orb_trend': (direction == 'long' and pre_orb_close > pre_orb_low + (pre_orb_high - pre_orb_low) * 0.6) or
                                  (direction == 'short' and pre_orb_close < pre_orb_high - (pre_orb_high - pre_orb_low) * 0.6),
            'entry_vs_orb_mid': entry_price - orb_mid,
            'risk': risk,
            'entry_hour': entry_ts.hour
        })

        current_date += timedelta(days=1)

    conn.close()

    return pd.DataFrame(trades)


def analyze_filter(df: pd.DataFrame, filter_name: str, filter_func, baseline_metrics: Dict) -> Dict:
    """
    Test a filter and compare to baseline.

    Args:
        df: All trades DataFrame
        filter_name: Name of filter
        filter_func: Function that returns True/False for each row
        baseline_metrics: Baseline performance

    Returns:
        Filter analysis results
    """
    filtered = df[filter_func(df)]

    if len(filtered) == 0:
        return None

    wins = len(filtered[filtered['outcome'] == 'WIN'])
    total = len(filtered)
    win_rate = (wins / total * 100) if total > 0 else 0
    avg_r = filtered['r_multiple'].mean()
    total_r = filtered['r_multiple'].sum()

    # Calculate improvement
    wr_improvement = win_rate - baseline_metrics['win_rate']
    avg_r_improvement = avg_r - baseline_metrics['avg_r']

    return {
        'filter': filter_name,
        'trades': total,
        'trades_pct': (total / len(df) * 100),
        'wins': wins,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r,
        'wr_improvement': wr_improvement,
        'avg_r_improvement': avg_r_improvement,
        'improvement_score': (wr_improvement / 10) + (avg_r_improvement * 100)  # Combined metric
    }


def main():
    """Run filter analysis on best setups."""

    print("=" * 80)
    print("ORB FILTER ANALYSIS - IMPROVING WIN RATES")
    print("=" * 80)
    print()

    # Analyze best realistic setups
    setups = [
        ('0900', 8.0, 'HALF', 'extended', '9am 8R HALF ext'),
        ('1000', 6.0, 'FULL', 'extended', '10am 6R FULL ext'),
        ('1000', 4.0, 'FULL', 'standard', '10am 4R FULL std')
    ]

    all_results = []

    for orb_time, rr, sl_mode, window, name in setups:
        print(f"\n{'=' * 80}")
        print(f"ANALYZING: {name}")
        print(f"{'=' * 80}\n")

        # Load trades
        print("Loading trades...", end=' ')
        df = load_orb_trades(orb_time, rr, sl_mode, window)
        print(f"{len(df)} trades loaded")

        # Baseline metrics
        baseline = {
            'trades': len(df),
            'wins': len(df[df['outcome'] == 'WIN']),
            'win_rate': (len(df[df['outcome'] == 'WIN']) / len(df) * 100),
            'avg_r': df['r_multiple'].mean(),
            'total_r': df['r_multiple'].sum()
        }

        print(f"\nBaseline: {baseline['trades']} trades | {baseline['win_rate']:.1f}% WR | {baseline['avg_r']:+.3f}R avg\n")

        # Test filters
        filters = []

        # 1. ORB size filters (avoid tiny and huge ORBs)
        for min_pct, max_pct in [(0.10, 0.30), (0.12, 0.25), (0.15, 0.35)]:
            result = analyze_filter(
                df,
                f"ORB size {min_pct:.2f}-{max_pct:.2f}%",
                lambda x: (x['orb_size_pct'] >= min_pct) & (x['orb_size_pct'] <= max_pct),
                baseline
            )
            if result:
                filters.append(result)

        # 2. Session bias filters
        result = analyze_filter(
            df,
            "With pre-ORB trend",
            lambda x: x['with_pre_orb_trend'] == True,
            baseline
        )
        if result:
            filters.append(result)

        result = analyze_filter(
            df,
            "Against pre-ORB trend",
            lambda x: x['with_pre_orb_trend'] == False,
            baseline
        )
        if result:
            filters.append(result)

        # 3. Entry timing filters
        if orb_time == '0900':
            result = analyze_filter(
                df,
                "Entry before 10am",
                lambda x: x['entry_hour'] < 10,
                baseline
            )
            if result:
                filters.append(result)

            result = analyze_filter(
                df,
                "Entry after 10am",
                lambda x: x['entry_hour'] >= 10,
                baseline
            )
            if result:
                filters.append(result)

        elif orb_time == '1000':
            result = analyze_filter(
                df,
                "Entry before 11am",
                lambda x: x['entry_hour'] < 11,
                baseline
            )
            if result:
                filters.append(result)

            result = analyze_filter(
                df,
                "Entry after 11am",
                lambda x: x['entry_hour'] >= 11,
                baseline
            )
            if result:
                filters.append(result)

        # 4. Day of week filters
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            result = analyze_filter(
                df,
                f"{day} only",
                lambda x, d=day: x['day_of_week'] == d,
                baseline
            )
            if result and result['trades'] >= 30:  # Min sample size
                filters.append(result)

        # 5. Large ORB filter (momentum)
        result = analyze_filter(
            df,
            "Large ORB (>0.20%)",
            lambda x: x['orb_size_pct'] > 0.20,
            baseline
        )
        if result:
            filters.append(result)

        # 6. Small ORB filter (compression)
        result = analyze_filter(
            df,
            "Small ORB (<0.15%)",
            lambda x: x['orb_size_pct'] < 0.15,
            baseline
        )
        if result:
            filters.append(result)

        # Sort by improvement score
        filters_df = pd.DataFrame(filters).sort_values('improvement_score', ascending=False)

        print("\nTop 10 Filters by Improvement Score:")
        print(filters_df.head(10).to_string(index=False))
        print()

        # Store for export
        filters_df['setup'] = name
        all_results.append(filters_df)

    # Export results
    combined = pd.concat(all_results, ignore_index=True)
    output_csv = OUTPUT_DIR / 'orb_filter_analysis.csv'
    combined.to_csv(output_csv, index=False)

    print("\n" + "=" * 80)
    print(f"Results saved to {output_csv}")
    print("=" * 80)


if __name__ == "__main__":
    main()
