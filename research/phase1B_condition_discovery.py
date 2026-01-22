#!/usr/bin/env python3
"""
PHASE 1B - CONDITION-FIRST DISCOVERY (CONTROLLED)

Tests ONE condition at a time on each ORB family to find edges that ONLY exist
under specific circumstances.

CRITICAL: Evaluate conditions independently per ORB time.
DO NOT assume conditions that work for 10AM apply to other ORBs.

Actively look for cases where a condition FLIPS a weak baseline into profitable edge.

Foundation Condition Set (8 conditions):
1. ORB size bucket (small/medium/large)
2. Pre-ORB trend direction (bullish/bearish/neutral)
3. Asia session bias (above/below asia range)
4. London session sweep (swept asia high/low/neither)
5. RSI extreme (oversold/neutral/overbought)
6. Day of week group (Mon-Tue/Wed-Thu/Fri)
7. Pre-move volatility (calm/volatile)
8. Entry timing (immediate/delayed)

Outputs:
- research/phase1B_condition_edges.csv
- research/phase1B_condition_edges.md
"""

import duckdb
import pandas as pd
import numpy as np
import pytz
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import sys

# Paths
ROOT = Path(__file__).parent.parent
DB_PATH = str(ROOT / "data" / "db" / "gold.db")
OUTPUT_DIR = ROOT / "research"

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")
TZ_UTC = pytz.utc

# Phase 1B Configuration
INSTRUMENT = 'MGC'
ORB_TIMES = ['0900', '1000', '1100', '1800', '2300', '0030']

# Focus on RR values that showed promise in Phase 1A
RR_VALUES = [2.0, 2.5, 3.0, 4.0, 6.0, 8.0]
SL_MODES = ['FULL', 'HALF']
DIRECTIONS = ['UP', 'DOWN']


@dataclass
class ConditionResult:
    """Results for a family + condition combo."""
    family_id: str
    condition_name: str
    condition_value: str

    # Baseline (no filter)
    baseline_trades: int
    baseline_win_rate: float
    baseline_avg_r: float
    baseline_total_r: float
    baseline_stability: str

    # Filtered (with condition)
    filtered_trades: int
    filtered_wins: int
    filtered_losses: int
    filtered_win_rate: float
    filtered_avg_r: float
    filtered_total_r: float
    filtered_max_dd: float
    filtered_profit_factor: float
    filtered_stability: str

    # Deltas
    delta_avg_r: float
    delta_win_rate: float
    trade_retention_pct: float

    # Time splits
    split1_avg_r: float
    split2_avg_r: float
    split3_avg_r: float
    positive_splits: int


def load_daily_features(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Load daily features for condition calculation."""
    features = conn.execute("""
        SELECT
            date_local,
            asia_high, asia_low, asia_range,
            london_high, london_low,
            ny_high, ny_low,
            pre_asia_range,
            orb_0900_high, orb_0900_low, orb_0900_size,
            orb_1000_high, orb_1000_low, orb_1000_size,
            orb_1100_high, orb_1100_low, orb_1100_size,
            orb_1800_high, orb_1800_low, orb_1800_size,
            orb_2300_high, orb_2300_low, orb_2300_size,
            orb_0030_high, orb_0030_low, orb_0030_size,
            rsi_at_0030
        FROM daily_features_v2
        WHERE instrument = ?
        ORDER BY date_local
    """, [INSTRUMENT]).fetchdf()

    features['date_local'] = pd.to_datetime(features['date_local']).dt.date
    return features


def calculate_pre_orb_trend(bars_df: pd.DataFrame, orb_start_time: dt_time, lookback_minutes: int = 60) -> str:
    """
    Calculate pre-ORB trend direction.

    Look at price position relative to range in the hour before ORB.
    Returns: BULLISH, BEARISH, NEUTRAL
    """
    orb_start_dt = bars_df[bars_df['time_local'] == orb_start_time].iloc[0]['ts_local'] if len(bars_df[bars_df['time_local'] == orb_start_time]) > 0 else None

    if orb_start_dt is None:
        return 'NEUTRAL'

    lookback_start = orb_start_dt - timedelta(minutes=lookback_minutes)
    pre_orb_bars = bars_df[(bars_df['ts_local'] >= lookback_start) & (bars_df['ts_local'] < orb_start_dt)]

    if len(pre_orb_bars) < 30:  # Need at least 30 bars for valid trend
        return 'NEUTRAL'

    pre_high = pre_orb_bars['high'].max()
    pre_low = pre_orb_bars['low'].min()
    pre_range = pre_high - pre_low

    if pre_range == 0:
        return 'NEUTRAL'

    last_close = pre_orb_bars.iloc[-1]['close']
    position = (last_close - pre_low) / pre_range

    if position > 0.6:
        return 'BULLISH'
    elif position < 0.4:
        return 'BEARISH'
    else:
        return 'NEUTRAL'


def calculate_orb_size_bucket(orb_size: float, price: float) -> str:
    """
    Categorize ORB size as percentage of price.

    Returns: SMALL, MEDIUM, LARGE
    """
    if pd.isna(orb_size) or pd.isna(price):
        return 'UNKNOWN'

    size_pct = (orb_size / price) * 100

    if size_pct < 0.15:
        return 'SMALL'
    elif size_pct < 0.35:
        return 'MEDIUM'
    else:
        return 'LARGE'


def calculate_session_bias(close_price: float, asia_high: float, asia_low: float) -> str:
    """
    Calculate bias based on position relative to Asia session range.

    Returns: ABOVE (bullish), BELOW (bearish), INSIDE (neutral)
    """
    if pd.isna(close_price) or pd.isna(asia_high) or pd.isna(asia_low):
        return 'INSIDE'

    if close_price > asia_high:
        return 'ABOVE'
    elif close_price < asia_low:
        return 'BELOW'
    else:
        return 'INSIDE'


def calculate_london_sweep(london_high: float, london_low: float,
                           asia_high: float, asia_low: float) -> str:
    """
    Detect if London session swept Asia highs/lows.

    Returns: SWEPT_HIGH (bullish), SWEPT_LOW (bearish), NO_SWEEP
    """
    if any(pd.isna([london_high, london_low, asia_high, asia_low])):
        return 'NO_SWEEP'

    swept_high = london_high > asia_high
    swept_low = london_low < asia_low

    if swept_high and not swept_low:
        return 'SWEPT_HIGH'
    elif swept_low and not swept_high:
        return 'SWEPT_LOW'
    elif swept_high and swept_low:
        return 'BOTH'
    else:
        return 'NO_SWEEP'


def get_day_of_week_group(trading_date: date) -> str:
    """
    Group days by behavior patterns.

    Returns: MON_TUE, WED_THU, FRI
    """
    weekday = trading_date.weekday()  # 0=Monday, 4=Friday

    if weekday in [0, 1]:
        return 'MON_TUE'
    elif weekday in [2, 3]:
        return 'WED_THU'
    else:  # 4=Friday
        return 'FRI'


def calculate_rsi_category(rsi: float) -> str:
    """
    Categorize RSI into zones.

    Returns: OVERSOLD, NEUTRAL, OVERBOUGHT
    """
    if pd.isna(rsi):
        return 'NEUTRAL'

    if rsi < 30:
        return 'OVERSOLD'
    elif rsi > 70:
        return 'OVERBOUGHT'
    else:
        return 'NEUTRAL'


def calculate_pre_move_volatility(asia_range: float, typical_range: float = 10.0) -> str:
    """
    Categorize pre-ORB volatility based on Asia session range.

    Returns: CALM, VOLATILE
    """
    if pd.isna(asia_range):
        return 'CALM'

    return 'VOLATILE' if asia_range > typical_range else 'CALM'


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


def backtest_with_condition(
    bars_df: pd.DataFrame,
    features_df: pd.DataFrame,
    orb_time: str,
    direction: str,
    rr: float,
    sl_mode: str,
    condition_name: str,
    condition_value: str,
    start_date: date,
    end_date: date
) -> Tuple[List[Dict], List[Dict]]:
    """
    Backtest family with and without condition.

    Returns: (baseline_trades, filtered_trades)
    """
    if bars_df.empty:
        return [], []

    orb_hour = int(orb_time[:2])
    orb_minute = int(orb_time[2:])
    orb_col_prefix = f'orb_{orb_time}'

    baseline_trades = []
    filtered_trades = []

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

        # Get features for this date
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

        # Calculate condition for this day
        passes_condition = False

        if condition_name == 'orb_size':
            orb_bucket = calculate_orb_size_bucket(orb_size, orb_mid)
            passes_condition = (orb_bucket == condition_value)

        elif condition_name == 'pre_orb_trend':
            trend = calculate_pre_orb_trend(day_bars, orb_start)
            passes_condition = (trend == condition_value)

        elif condition_name == 'asia_bias':
            # Get close just before ORB
            pre_orb_bars = day_bars[day_bars['time_local'] < orb_start]
            if len(pre_orb_bars) > 0:
                pre_close = pre_orb_bars.iloc[-1]['close']
                bias = calculate_session_bias(pre_close, day_features['asia_high'], day_features['asia_low'])
                passes_condition = (bias == condition_value)

        elif condition_name == 'london_sweep':
            sweep = calculate_london_sweep(
                day_features['london_high'], day_features['london_low'],
                day_features['asia_high'], day_features['asia_low']
            )
            passes_condition = (sweep == condition_value)

        elif condition_name == 'rsi_category':
            if orb_time == '0030':
                rsi_cat = calculate_rsi_category(day_features['rsi_at_0030'])
                passes_condition = (rsi_cat == condition_value)
            else:
                passes_condition = False  # RSI only relevant for 0030

        elif condition_name == 'day_group':
            day_group = get_day_of_week_group(trading_date)
            passes_condition = (day_group == condition_value)

        elif condition_name == 'pre_volatility':
            vol_cat = calculate_pre_move_volatility(day_features['asia_range'])
            passes_condition = (vol_cat == condition_value)

        else:
            passes_condition = False

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

        trade = {
            'date': trading_date,
            'outcome': outcome,
            'r_multiple': r_multiple
        }

        # Add to baseline (all trades)
        baseline_trades.append(trade)

        # Add to filtered only if passes condition
        if passes_condition:
            filtered_trades.append(trade)

    return baseline_trades, filtered_trades


def calculate_metrics(trades: List[Dict]) -> Dict:
    """Calculate metrics from trade list."""
    if len(trades) == 0:
        return {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0
        }

    total = len(trades)
    wins = len([t for t in trades if t['outcome'] == 'WIN'])
    losses = len([t for t in trades if t['outcome'] == 'LOSS'])

    win_rate = (wins / total * 100) if total > 0 else 0.0

    r_multiples = [t['r_multiple'] for t in trades]
    avg_r = np.mean(r_multiples)
    total_r = np.sum(r_multiples)

    # Max drawdown
    equity_curve = np.cumsum(np.concatenate([[0], r_multiples]))
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = equity_curve - running_max
    max_dd = abs(np.min(drawdowns))

    # Profit factor
    winning_r = sum([r for r in r_multiples if r > 0])
    losing_r = abs(sum([r for r in r_multiples if r < 0]))
    profit_factor = winning_r / losing_r if losing_r > 0 else 0.0

    return {
        'trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r,
        'max_drawdown': max_dd,
        'profit_factor': profit_factor
    }


def calculate_time_splits(trades: List[Dict], start_date: date, end_date: date) -> Tuple[Dict, Dict, Dict]:
    """Split trades into 3 equal time periods."""
    total_days = (end_date - start_date).days
    split_days = total_days // 3

    split1_end = start_date + timedelta(days=split_days)
    split2_end = split1_end + timedelta(days=split_days)

    split1_trades = [t for t in trades if t['date'] <= split1_end]
    split2_trades = [t for t in trades if split1_end < t['date'] <= split2_end]
    split3_trades = [t for t in trades if t['date'] > split2_end]

    return (
        calculate_metrics(split1_trades),
        calculate_metrics(split2_trades),
        calculate_metrics(split3_trades)
    )


def test_condition(
    bars_df: pd.DataFrame,
    features_df: pd.DataFrame,
    orb_time: str,
    direction: str,
    rr: float,
    sl_mode: str,
    condition_name: str,
    condition_value: str,
    start_date: date,
    end_date: date
) -> Optional[ConditionResult]:
    """Test a family + condition combination."""

    family_id = f"{INSTRUMENT}_{orb_time}_{direction}_{rr}R_{sl_mode}"

    # Backtest with and without condition
    baseline_trades, filtered_trades = backtest_with_condition(
        bars_df, features_df, orb_time, direction, rr, sl_mode,
        condition_name, condition_value, start_date, end_date
    )

    # Calculate metrics
    baseline = calculate_metrics(baseline_trades)
    filtered = calculate_metrics(filtered_trades)

    # Need minimum trades for valid test
    if filtered['trades'] < 20:
        return None

    # Calculate trade retention
    trade_retention_pct = (filtered['trades'] / baseline['trades'] * 100) if baseline['trades'] > 0 else 0

    # Must retain at least 40% of trades
    if trade_retention_pct < 40:
        return None

    # Time split stability for filtered
    split1, split2, split3 = calculate_time_splits(filtered_trades, start_date, end_date)

    positive_splits = sum([
        1 if split1['avg_r'] > 0 else 0,
        1 if split2['avg_r'] > 0 else 0,
        1 if split3['avg_r'] > 0 else 0
    ])

    if filtered['trades'] < 30:
        filtered_stability = 'INSUFFICIENT'
    elif positive_splits >= 2:
        filtered_stability = 'STABLE'
    else:
        filtered_stability = 'UNSTABLE'

    # Baseline stability
    baseline_splits = calculate_time_splits(baseline_trades, start_date, end_date)
    baseline_positive = sum([
        1 if baseline_splits[0]['avg_r'] > 0 else 0,
        1 if baseline_splits[1]['avg_r'] > 0 else 0,
        1 if baseline_splits[2]['avg_r'] > 0 else 0
    ])

    if baseline['trades'] < 30:
        baseline_stability = 'INSUFFICIENT'
    elif baseline_positive >= 2:
        baseline_stability = 'STABLE'
    else:
        baseline_stability = 'UNSTABLE'

    # Calculate deltas
    delta_avg_r = filtered['avg_r'] - baseline['avg_r']
    delta_win_rate = filtered['win_rate'] - baseline['win_rate']

    # Keep if:
    # 1. Filtered is profitable AND stable
    # 2. Meaningful improvement (delta > 0.05R) OR flipped from negative to positive

    is_profitable = filtered['avg_r'] > 0
    is_stable = filtered_stability == 'STABLE'
    meaningful_improvement = delta_avg_r > 0.05
    flipped_positive = baseline['avg_r'] <= 0 and filtered['avg_r'] > 0

    if not (is_profitable and is_stable):
        return None

    if not (meaningful_improvement or flipped_positive):
        return None

    return ConditionResult(
        family_id=family_id,
        condition_name=condition_name,
        condition_value=condition_value,
        baseline_trades=baseline['trades'],
        baseline_win_rate=baseline['win_rate'],
        baseline_avg_r=baseline['avg_r'],
        baseline_total_r=baseline['total_r'],
        baseline_stability=baseline_stability,
        filtered_trades=filtered['trades'],
        filtered_wins=filtered['wins'],
        filtered_losses=filtered['losses'],
        filtered_win_rate=filtered['win_rate'],
        filtered_avg_r=filtered['avg_r'],
        filtered_total_r=filtered['total_r'],
        filtered_max_dd=filtered['max_drawdown'],
        filtered_profit_factor=filtered['profit_factor'],
        filtered_stability=filtered_stability,
        delta_avg_r=delta_avg_r,
        delta_win_rate=delta_win_rate,
        trade_retention_pct=trade_retention_pct,
        split1_avg_r=split1['avg_r'],
        split2_avg_r=split2['avg_r'],
        split3_avg_r=split3['avg_r'],
        positive_splits=positive_splits
    )


def main():
    """Run Phase 1B condition discovery."""
    print("=" * 80)
    print("PHASE 1B - CONDITION-FIRST DISCOVERY")
    print("=" * 80)
    sys.stdout.flush()
    print()
    print("Testing ONE condition at a time per ORB family")
    print("Looking for edges that ONLY exist under specific conditions")
    print()
    sys.stdout.flush()

    # Foundation conditions to test
    CONDITIONS = [
        ('orb_size', ['SMALL', 'MEDIUM', 'LARGE']),
        ('pre_orb_trend', ['BULLISH', 'BEARISH', 'NEUTRAL']),
        ('asia_bias', ['ABOVE', 'BELOW', 'INSIDE']),
        ('london_sweep', ['SWEPT_HIGH', 'SWEPT_LOW', 'NO_SWEEP']),
        ('rsi_category', ['OVERSOLD', 'OVERBOUGHT', 'NEUTRAL']),
        ('day_group', ['MON_TUE', 'WED_THU', 'FRI']),
        ('pre_volatility', ['CALM', 'VOLATILE']),
    ]

    print("Foundation Condition Set:")
    for cond_name, cond_values in CONDITIONS:
        print(f"  - {cond_name}: {', '.join(cond_values)}")
    print()

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

    total_days = (end_date - start_date).days
    years = total_days / 365.25
    print(f"Duration: {total_days} days ({years:.2f} years)")
    print()

    # Load bars and features
    print("Loading data from database...")
    bars_df = load_bars_for_date_range(conn, start_date, end_date)
    features_df = load_daily_features(conn)
    print(f"Loaded {len(bars_df):,} bars and {len(features_df):,} feature rows")
    print()

    # Test all combinations
    results = []
    total_tests = len(ORB_TIMES) * len(DIRECTIONS) * len(RR_VALUES) * len(SL_MODES) * sum(len(cv) for _, cv in CONDITIONS)
    count = 0

    print(f"Total potential tests: {total_tests}")
    print("Testing (will only keep profitable + stable + meaningful improvements)...")
    print()

    for orb_time in ORB_TIMES:
        print(f"--- Testing {orb_time} ORB ---")

        for direction in DIRECTIONS:
            for rr in RR_VALUES:
                for sl_mode in SL_MODES:
                    family_id = f"{INSTRUMENT}_{orb_time}_{direction}_{rr}R_{sl_mode}"

                    for condition_name, condition_values in CONDITIONS:
                        # Skip RSI for non-0030 ORBs
                        if condition_name == 'rsi_category' and orb_time != '0030':
                            continue

                        for condition_value in condition_values:
                            count += 1

                            if count % 100 == 0:
                                print(f"  [{count}/{total_tests}] Processed...")

                            result = test_condition(
                                bars_df, features_df,
                                orb_time, direction, rr, sl_mode,
                                condition_name, condition_value,
                                start_date, end_date
                            )

                            if result is not None:
                                results.append(result)
                                print(f"  [FOUND] {family_id} + {condition_name}={condition_value}")
                                print(f"          Baseline: {result.baseline_avg_r:+.3f}R | Filtered: {result.filtered_avg_r:+.3f}R | Delta: {result.delta_avg_r:+.3f}R")

    conn.close()

    print()
    print("=" * 80)
    print("CONDITION DISCOVERY COMPLETE")
    print("=" * 80)
    print()

    if len(results) == 0:
        print("No condition-dependent edges found that meet criteria.")
        print("(Profitable + Stable + Meaningful improvement + 40%+ trade retention)")
        return

    # Convert to DataFrame
    df = pd.DataFrame([vars(r) for r in results])

    # Sort by filtered_avg_r (best filtered performance)
    df = df.sort_values('filtered_avg_r', ascending=False)

    # Save CSV
    output_csv = OUTPUT_DIR / 'phase1B_condition_edges.csv'
    df.to_csv(output_csv, index=False)
    print(f"[OK] Saved CSV: {output_csv}")

    # Generate markdown report
    output_md = OUTPUT_DIR / 'phase1B_condition_edges.md'

    with open(output_md, 'w') as f:
        f.write("# PHASE 1B - CONDITION-DEPENDENT EDGES\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Instrument**: {INSTRUMENT}\n\n")
        f.write(f"**Data Range**: {start_date} to {end_date} ({years:.2f} years)\n\n")
        f.write(f"**Edges Found**: {len(df)}\n\n")
        f.write("---\n\n")

        # Summary
        f.write("## Summary Statistics\n\n")
        f.write(f"- Total condition-dependent edges: {len(df)}\n")
        f.write(f"- Edges that flipped negative baseline: {len(df[df['baseline_avg_r'] <= 0])}\n")
        f.write(f"- Best filtered avg_r: {df['filtered_avg_r'].max():.3f}R\n")
        f.write(f"- Best improvement (delta): {df['delta_avg_r'].max():.3f}R\n\n")

        # Top 20
        f.write("---\n\n")
        f.write("## TOP 20 CONDITION-DEPENDENT EDGES\n\n")
        f.write("Ranked by filtered avg_r (performance WITH condition)\n\n")
        f.write("| Rank | Family | Condition | Baseline AvgR | Filtered AvgR | Delta | WR% | Trades | Retention% | Stability |\n")
        f.write("|------|--------|-----------|---------------|---------------|-------|-----|--------|------------|-----------|\n")

        for i, row in enumerate(df.head(20).itertuples(), 1):
            f.write(f"| {i} | {row.family_id} | {row.condition_name}={row.condition_value} | {row.baseline_avg_r:+.3f}R | {row.filtered_avg_r:+.3f}R | {row.delta_avg_r:+.3f}R | {row.filtered_win_rate:.1f}% | {row.filtered_trades} | {row.trade_retention_pct:.0f}% | {row.filtered_stability} |\n")

        f.write("\n---\n\n")

        # Biggest flips (weak baseline to profitable)
        flipped = df[df['baseline_avg_r'] <= 0].sort_values('filtered_avg_r', ascending=False)
        if len(flipped) > 0:
            f.write("## BIGGEST FLIPS (Negative Baseline -> Profitable)\n\n")
            f.write("These edges ONLY exist under specific conditions:\n\n")
            f.write("| Rank | Family | Condition | Baseline AvgR | Filtered AvgR | Delta | Trades | Stability |\n")
            f.write("|------|--------|-----------|---------------|---------------|-------|--------|-----------|\ n")

            for i, row in enumerate(flipped.head(10).itertuples(), 1):
                f.write(f"| {i} | {row.family_id} | {row.condition_name}={row.condition_value} | {row.baseline_avg_r:+.3f}R | {row.filtered_avg_r:+.3f}R | {row.delta_avg_r:+.3f}R | {row.filtered_trades} | {row.filtered_stability} |\n")

            f.write("\n---\n\n")

        # By ORB time
        f.write("## ANALYSIS BY ORB TIME\n\n")
        for orb_time in ORB_TIMES:
            orb_edges = df[df['family_id'].str.contains(f'_{orb_time}_')]
            if len(orb_edges) > 0:
                f.write(f"### {orb_time} ORB ({len(orb_edges)} edges)\n\n")

                best = orb_edges.iloc[0]
                f.write(f"- Best edge: {best['family_id']} + {best['condition_name']}={best['condition_value']}\n")
                f.write(f"- Filtered avg_r: {best['filtered_avg_r']:+.3f}R (baseline: {best['baseline_avg_r']:+.3f}R)\n")
                f.write(f"- Win rate: {best['filtered_win_rate']:.1f}%\n")
                f.write(f"- Trades: {best['filtered_trades']} ({best['trade_retention_pct']:.0f}% retention)\n\n")

    print(f"[OK] Saved report: {output_md}")
    print()

    # Display top 10
    print("=" * 80)
    print("TOP 10 CONDITION-DEPENDENT EDGES")
    print("=" * 80)
    print()

    for i, row in enumerate(df.head(10).itertuples(), 1):
        print(f"{i}. {row.family_id} + {row.condition_name}={row.condition_value}")
        print(f"   Baseline: {row.baseline_avg_r:+.3f}R ({row.baseline_trades} trades, {row.baseline_stability})")
        print(f"   Filtered: {row.filtered_avg_r:+.3f}R ({row.filtered_trades} trades, {row.filtered_win_rate:.1f}% WR, {row.filtered_stability})")
        print(f"   Delta: {row.delta_avg_r:+.3f}R | Retention: {row.trade_retention_pct:.0f}%")
        print(f"   Splits: {row.split1_avg_r:+.3f}R / {row.split2_avg_r:+.3f}R / {row.split3_avg_r:+.3f}R ({row.positive_splits}/3 positive)")
        print()

    print("=" * 80)
    print("PHASE 1B COMPLETE")
    print("=" * 80)
    print()
    print(f"Outputs saved:")
    print(f"  - {output_csv}")
    print(f"  - {output_md}")
    print()
    print("STOP - Awaiting confirmation to proceed to Phase 2")
    print()


if __name__ == "__main__":
    main()
