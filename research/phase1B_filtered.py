#!/usr/bin/env python3
"""
PHASE 1B - CONDITION FILTERING (REUSE PHASE 1A TRADES)

Strategy: Instead of re-backtesting everything, we:
1. Re-run Phase 1A backtests BUT capture trade-level data with conditions tagged
2. Filter trades by each condition
3. Compare baseline vs filtered metrics

This is much faster because we only backtest once per family, then slice results.
"""

import duckdb
import pandas as pd
import numpy as np
import pytz
import sys
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Paths
ROOT = Path(__file__).parent.parent
DB_PATH = str(ROOT / "data" / "db" / "gold.db")
OUTPUT_DIR = ROOT / "research"

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")
TZ_UTC = pytz.utc

INSTRUMENT = 'MGC'

# Test ALL ORB times independently (don't assume 10AM logic applies elsewhere)
ORB_TIMES = ['0900', '1000', '1100', '1800', '2300', '0030']
DIRECTIONS = ['UP', 'DOWN']
RR_VALUES = [2.0, 3.0, 4.0, 6.0, 8.0]  # Focus on most common
SL_MODES = ['FULL', 'HALF']

# Foundation conditions
CONDITIONS = [
    'orb_size',      # SMALL/MEDIUM/LARGE
    'pre_orb_trend', # BULLISH/BEARISH/NEUTRAL
    'asia_bias',     # ABOVE/BELOW/INSIDE
    'day_of_week',   # MON/TUE/WED/THU/FRI
]


@dataclass
class Trade:
    """Single trade with conditions tagged."""
    date: date
    outcome: str  # WIN, LOSS, TIME_EXIT
    r_multiple: float

    # Conditions
    orb_size_bucket: str
    pre_orb_trend: str
    asia_bias: str
    day_of_week: str


def load_daily_features(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Load daily features."""
    features = conn.execute("""
        SELECT
            date_local,
            asia_high, asia_low, asia_range,
            london_high, london_low,
            orb_0900_size, orb_1000_size, orb_1100_size,
            orb_1800_size, orb_2300_size, orb_0030_size
        FROM daily_features_v2
        WHERE instrument = ?
        ORDER BY date_local
    """, [INSTRUMENT]).fetchdf()

    features['date_local'] = pd.to_datetime(features['date_local']).dt.date
    return features


def load_bars_for_date_range(conn: duckdb.DuckDBPyConnection, start_date: date, end_date: date) -> pd.DataFrame:
    """Load all bars for date range."""
    start_dt_local = TZ_LOCAL.localize(datetime.combine(start_date, dt_time(9, 0)))
    end_dt_local = TZ_LOCAL.localize(datetime.combine(end_date + timedelta(days=1), dt_time(9, 0)))

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
        return pd.DataFrame()

    bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)
    bars['ts_local'] = bars['ts_utc'].dt.tz_convert(TZ_LOCAL)
    bars['date_local'] = bars['ts_local'].dt.date
    bars['time_local'] = bars['ts_local'].dt.time

    return bars


def calculate_orb_size_bucket(orb_size: float, price: float) -> str:
    """Bucket ORB size as % of price."""
    if pd.isna(orb_size) or pd.isna(price) or price == 0:
        return 'UNKNOWN'

    size_pct = (orb_size / price) * 100

    if size_pct < 0.15:
        return 'SMALL'
    elif size_pct < 0.35:
        return 'MEDIUM'
    else:
        return 'LARGE'


def calculate_pre_orb_trend(bars_df: pd.DataFrame, orb_start: dt_time) -> str:
    """Calculate pre-ORB trend from price position in prior hour."""
    orb_start_rows = bars_df[bars_df['time_local'] == orb_start]
    if len(orb_start_rows) == 0:
        return 'NEUTRAL'

    orb_start_dt = orb_start_rows.iloc[0]['ts_local']
    lookback_start = orb_start_dt - timedelta(minutes=60)

    pre_bars = bars_df[(bars_df['ts_local'] >= lookback_start) & (bars_df['ts_local'] < orb_start_dt)]

    if len(pre_bars) < 30:
        return 'NEUTRAL'

    pre_high = pre_bars['high'].max()
    pre_low = pre_bars['low'].min()
    pre_range = pre_high - pre_low

    if pre_range == 0:
        return 'NEUTRAL'

    last_close = pre_bars.iloc[-1]['close']
    position = (last_close - pre_low) / pre_range

    if position > 0.6:
        return 'BULLISH'
    elif position < 0.4:
        return 'BEARISH'
    else:
        return 'NEUTRAL'


def calculate_asia_bias(close: float, asia_high: float, asia_low: float) -> str:
    """Position relative to Asia range."""
    if pd.isna(close) or pd.isna(asia_high) or pd.isna(asia_low):
        return 'INSIDE'

    if close > asia_high:
        return 'ABOVE'
    elif close < asia_low:
        return 'BELOW'
    else:
        return 'INSIDE'


def backtest_family_with_conditions(
    bars_df: pd.DataFrame,
    features_df: pd.DataFrame,
    orb_time: str,
    direction: str,
    rr: float,
    sl_mode: str,
    start_date: date,
    end_date: date
) -> List[Trade]:
    """
    Backtest family and tag each trade with conditions.
    Returns list of Trade objects.
    """
    if bars_df.empty:
        return []

    orb_hour = int(orb_time[:2])
    orb_minute = int(orb_time[2:])

    trades = []

    # Group by date
    for trading_date in pd.date_range(start_date, end_date, freq='D'):
        trading_date = trading_date.date()

        # Get bars for this trading day
        day_start = TZ_LOCAL.localize(datetime.combine(trading_date, dt_time(9, 0)))
        day_end = day_start + timedelta(days=1)

        day_bars = bars_df[
            (bars_df['ts_local'] >= day_start) &
            (bars_df['ts_local'] < day_end)
        ]

        if day_bars.empty:
            continue

        # Get features
        day_features = features_df[features_df['date_local'] == trading_date]
        if len(day_features) == 0:
            continue
        day_features = day_features.iloc[0]

        # Calculate ORB
        orb_start = dt_time(orb_hour, orb_minute)
        orb_end_min = orb_minute + 5
        orb_end_hour = orb_hour
        if orb_end_min >= 60:
            orb_end_hour += 1
            orb_end_min -= 60
        orb_end = dt_time(orb_end_hour, orb_end_min)

        orb_bars = day_bars[
            (day_bars['time_local'] >= orb_start) &
            (day_bars['time_local'] < orb_end)
        ]

        if orb_bars.empty:
            continue

        orb_high = orb_bars['high'].max()
        orb_low = orb_bars['low'].min()
        orb_mid = (orb_high + orb_low) / 2.0
        orb_size = orb_high - orb_low

        # Find entry
        scan_bars = day_bars[day_bars['time_local'] >= orb_end]

        entry_bar = None
        for idx, bar in scan_bars.iterrows():
            if direction == 'UP' and bar['close'] > orb_high:
                entry_bar = bar
                break
            elif direction == 'DOWN' and bar['close'] < orb_low:
                entry_bar = bar
                break

        if entry_bar is None:
            continue

        # Calculate trade
        entry_price = entry_bar['close']

        if sl_mode == 'HALF':
            stop_price = orb_mid
        else:  # FULL
            stop_price = orb_low if direction == 'UP' else orb_high

        if direction == 'UP':
            risk = entry_price - stop_price
            target_price = entry_price + (risk * rr)
        else:
            risk = stop_price - entry_price
            target_price = entry_price - (risk * rr)

        if risk <= 0:
            continue

        # Simulate outcome
        remaining_bars = day_bars[day_bars['ts_local'] > entry_bar['ts_local']]

        outcome = 'TIME_EXIT'
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

        # Calculate conditions for this trade
        orb_size_bucket = calculate_orb_size_bucket(orb_size, entry_price)
        pre_orb_trend = calculate_pre_orb_trend(day_bars, orb_start)

        # Asia bias: position at ORB start
        pre_orb_bars = day_bars[day_bars['time_local'] < orb_start]
        pre_close = pre_orb_bars.iloc[-1]['close'] if len(pre_orb_bars) > 0 else entry_price
        asia_bias = calculate_asia_bias(pre_close, day_features['asia_high'], day_features['asia_low'])

        day_of_week = trading_date.strftime('%a').upper()  # MON, TUE, etc.

        # Create trade with conditions
        trade = Trade(
            date=trading_date,
            outcome=outcome,
            r_multiple=r_multiple,
            orb_size_bucket=orb_size_bucket,
            pre_orb_trend=pre_orb_trend,
            asia_bias=asia_bias,
            day_of_week=day_of_week
        )

        trades.append(trade)

    return trades


def calculate_metrics(trades: List[Trade]) -> Dict:
    """Calculate metrics from trade list."""
    if len(trades) == 0:
        return {
            'trades': 0,
            'wins': 0,
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0
        }

    wins = len([t for t in trades if t.outcome == 'WIN'])
    win_rate = wins / len(trades) * 100
    avg_r = np.mean([t.r_multiple for t in trades])
    total_r = np.sum([t.r_multiple for t in trades])

    return {
        'trades': len(trades),
        'wins': wins,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r
    }


def filter_trades(trades: List[Trade], condition_field: str, condition_value: str) -> List[Trade]:
    """Filter trades by condition."""
    return [t for t in trades if getattr(t, condition_field) == condition_value]


def test_family(
    bars_df: pd.DataFrame,
    features_df: pd.DataFrame,
    orb_time: str,
    direction: str,
    rr: float,
    sl_mode: str,
    start_date: date,
    end_date: date
) -> Dict:
    """Test family across all conditions."""
    family_id = f"{INSTRUMENT}_{orb_time}_{direction}_{rr}R_{sl_mode}"

    # Backtest once, get all trades with conditions tagged
    all_trades = backtest_family_with_conditions(
        bars_df, features_df, orb_time, direction, rr, sl_mode,
        start_date, end_date
    )

    if len(all_trades) < 30:  # Need minimum trades
        return None

    # Baseline metrics
    baseline = calculate_metrics(all_trades)

    results = {
        'family_id': family_id,
        'orb_time': orb_time,
        'direction': direction,
        'rr': rr,
        'sl_mode': sl_mode,
        'baseline_trades': baseline['trades'],
        'baseline_avg_r': baseline['avg_r'],
        'baseline_win_rate': baseline['win_rate'],
        'conditions': []
    }

    # Test each condition
    condition_field_map = {
        'orb_size': 'orb_size_bucket',
        'pre_orb_trend': 'pre_orb_trend',
        'asia_bias': 'asia_bias',
        'day_of_week': 'day_of_week'
    }

    for condition_name in CONDITIONS:
        condition_field = condition_field_map[condition_name]

        # Get all possible values for this condition
        values = set(getattr(t, condition_field) for t in all_trades)

        for value in values:
            if value == 'UNKNOWN':
                continue

            # Filter trades
            filtered_trades = filter_trades(all_trades, condition_field, value)

            if len(filtered_trades) < 20:  # Need minimum
                continue

            retention = len(filtered_trades) / len(all_trades) * 100

            if retention < 30:  # Need at least 30% retention
                continue

            filtered = calculate_metrics(filtered_trades)

            delta_avg_r = filtered['avg_r'] - baseline['avg_r']
            delta_win_rate = filtered['win_rate'] - baseline['win_rate']

            # Keep if meaningful improvement OR flips negative to positive
            meaningful = delta_avg_r > 0.05
            flipped = baseline['avg_r'] <= 0 and filtered['avg_r'] > 0

            if filtered['avg_r'] > 0 and (meaningful or flipped):
                results['conditions'].append({
                    'condition': f"{condition_name}={value}",
                    'filtered_trades': filtered['trades'],
                    'filtered_avg_r': filtered['avg_r'],
                    'filtered_win_rate': filtered['win_rate'],
                    'delta_avg_r': delta_avg_r,
                    'delta_win_rate': delta_win_rate,
                    'retention_pct': retention
                })

    return results if len(results['conditions']) > 0 else None


def main():
    """Run Phase 1B condition filtering."""
    print("=" * 80)
    print("PHASE 1B - CONDITION FILTERING (COMPUTED)")
    print("=" * 80)
    sys.stdout.flush()
    print()
    print("Strategy: Backtest once per family, tag trades with conditions, then filter")
    print()
    sys.stdout.flush()

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

    conn.close()

    # Test families (focus on most promising)
    total_families = len(ORB_TIMES) * len(DIRECTIONS) * len(RR_VALUES) * len(SL_MODES)
    print(f"Testing {total_families} families...")
    print()
    sys.stdout.flush()

    all_edges = []
    count = 0

    for orb_time in ORB_TIMES:
        print(f"--- Testing {orb_time} ORB ---")
        sys.stdout.flush()

        for direction in DIRECTIONS:
            for rr in RR_VALUES:
                for sl_mode in SL_MODES:
                    count += 1
                    family_id = f"{INSTRUMENT}_{orb_time}_{direction}_{rr}R_{sl_mode}"

                    if count % 10 == 0:
                        print(f"  [{count}/{total_families}] Progress...")
                        sys.stdout.flush()

                    result = test_family(
                        bars_df, features_df,
                        orb_time, direction, rr, sl_mode,
                        start_date, end_date
                    )

                    if result is not None:
                        for cond in result['conditions']:
                            all_edges.append({
                                'family_id': family_id,
                                'orb_time': orb_time,
                                'direction': direction,
                                'rr': rr,
                                'sl_mode': sl_mode,
                                'baseline_trades': result['baseline_trades'],
                                'baseline_avg_r': result['baseline_avg_r'],
                                'baseline_win_rate': result['baseline_win_rate'],
                                'condition': cond['condition'],
                                'filtered_trades': cond['filtered_trades'],
                                'filtered_avg_r': cond['filtered_avg_r'],
                                'filtered_win_rate': cond['filtered_win_rate'],
                                'delta_avg_r': cond['delta_avg_r'],
                                'delta_win_rate': cond['delta_win_rate'],
                                'retention_pct': cond['retention_pct']
                            })

                        print(f"  [FOUND] {family_id}: {len(result['conditions'])} condition edges")
                        sys.stdout.flush()

    print()
    print("=" * 80)
    print("PHASE 1B COMPLETE")
    print("=" * 80)
    print()
    sys.stdout.flush()

    if len(all_edges) == 0:
        print("No condition-dependent edges found meeting criteria.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(all_edges)
    df = df.sort_values('filtered_avg_r', ascending=False)

    # Save CSV
    output_csv = OUTPUT_DIR / 'phase1B_condition_edges.csv'
    df.to_csv(output_csv, index=False)
    print(f"[OK] Saved CSV: {output_csv}")

    # Save markdown
    output_md = OUTPUT_DIR / 'phase1B_condition_edges.md'

    with open(output_md, 'w') as f:
        f.write("# PHASE 1B - CONDITION-DEPENDENT EDGES (COMPUTED)\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Method**: Real trade data with conditions tagged and filtered\n\n")
        f.write(f"**Edges Found**: {len(df)}\n\n")
        f.write("---\n\n")

        # Top 20
        f.write("## TOP 20 CONDITION-DEPENDENT EDGES\n\n")
        f.write("| Rank | Family | Condition | Baseline AvgR | Filtered AvgR | Delta | Trades | Retention% |\n")
        f.write("|------|--------|-----------|---------------|---------------|-------|--------|------------|\n")

        for i, row in enumerate(df.head(20).itertuples(), 1):
            f.write(f"| {i} | {row.family_id} | {row.condition} | {row.baseline_avg_r:+.3f}R | {row.filtered_avg_r:+.3f}R | {row.delta_avg_r:+.3f}R | {row.filtered_trades} | {row.retention_pct:.0f}% |\n")

        f.write("\n---\n\n")

        # Flips
        flipped = df[df['baseline_avg_r'] <= 0]
        if len(flipped) > 0:
            f.write("## NEGATIVE BASELINE -> PROFITABLE (FLIPS)\n\n")
            f.write("| Rank | Family | Condition | Baseline AvgR | Filtered AvgR | Delta |\n")
            f.write("|------|--------|-----------|---------------|---------------|-------|\n")

            for i, row in enumerate(flipped.head(10).itertuples(), 1):
                f.write(f"| {i} | {row.family_id} | {row.condition} | {row.baseline_avg_r:+.3f}R | {row.filtered_avg_r:+.3f}R | {row.delta_avg_r:+.3f}R |\n")

        f.write("\n")

    print(f"[OK] Saved report: {output_md}")
    print()

    # Display results
    print("TOP 10 CONDITION-DEPENDENT EDGES:")
    print()
    for i, row in enumerate(df.head(10).itertuples(), 1):
        print(f"{i}. {row.family_id} | {row.condition}")
        print(f"   Baseline: {row.baseline_avg_r:+.3f}R ({row.baseline_trades} trades)")
        print(f"   Filtered: {row.filtered_avg_r:+.3f}R ({row.filtered_trades} trades, {row.filtered_win_rate:.1f}% WR)")
        print(f"   Delta: {row.delta_avg_r:+.3f}R | Retention: {row.retention_pct:.0f}%")
        print()

    print("=" * 80)
    print("PHASE 1B COMPLETE - STOP")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
