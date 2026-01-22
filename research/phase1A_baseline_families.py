#!/usr/bin/env python3
"""
PHASE 1A - BASELINE FAMILY DISCOVERY (NO FILTERS)

Tests ALL ORB family combinations to find robust baseline edges.

Family definition:
- instrument (MGC only for Phase 1A)
- ORB time (0900, 1000, 1100, 1800, 2300, 0030)
- direction (UP, DOWN)
- RR (2.0, 2.5, 3.0, 4.0, 6.0, 8.0)
- stop mode (FULL, HALF)

Total families: 6 × 2 × 6 × 2 = 144 families

NO FILTERS - pure baseline edge measurement.

Outputs:
- research/phase1A_baseline_families.csv
- research/phase1A_baseline_families.md
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

# Phase 1A Configuration
INSTRUMENT = 'MGC'
ORB_TIMES = ['0900', '1000', '1100', '1800', '2300', '0030']
DIRECTIONS = ['UP', 'DOWN']
RR_VALUES = [2.0, 2.5, 3.0, 4.0, 6.0, 8.0]
SL_MODES = ['FULL', 'HALF']


@dataclass
class FamilyResult:
    """Results for a single family."""
    family_id: str
    instrument: str
    orb_time: str
    direction: str
    rr: float
    sl_mode: str

    # Overall metrics
    trades: int
    wins: int
    losses: int
    win_rate: float
    avg_r: float
    total_r: float
    max_drawdown: float
    profit_factor: float

    # Time split metrics
    split1_trades: int
    split1_avg_r: float
    split2_trades: int
    split2_avg_r: float
    split3_trades: int
    split3_avg_r: float

    # Stability flags
    positive_splits: int  # How many splits have positive avg_r
    stability_flag: str   # STABLE, UNSTABLE, INSUFFICIENT


def get_data_range(conn: duckdb.DuckDBPyConnection) -> Tuple[date, date]:
    """Get available data range from database."""
    result = conn.execute("""
        SELECT MIN(DATE(ts_utc AT TIME ZONE 'Australia/Brisbane')) as min_date,
               MAX(DATE(ts_utc AT TIME ZONE 'Australia/Brisbane')) as max_date
        FROM bars_1m
        WHERE symbol = ?
    """, [INSTRUMENT]).fetchone()

    return result[0], result[1]


def load_bars_for_date_range(conn: duckdb.DuckDBPyConnection, start_date: date, end_date: date) -> pd.DataFrame:
    """Load all bars for date range."""
    # Convert to UTC for query
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


def backtest_family(
    bars_df: pd.DataFrame,
    orb_time: str,
    direction: str,
    rr: float,
    sl_mode: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    Backtest a single family across all days.

    Returns list of trades with date, outcome, r_multiple.
    """
    if bars_df.empty:
        return []

    orb_hour = int(orb_time[:2])
    orb_minute = int(orb_time[2:])

    trades = []

    # Group by date
    for trading_date in pd.date_range(start_date, end_date, freq='D'):
        trading_date = trading_date.date()

        # Get bars for this trading day (09:00 → next 09:00)
        day_start = TZ_LOCAL.localize(datetime.combine(trading_date, dt_time(9, 0)))
        day_end = day_start + timedelta(days=1)

        day_bars = bars_df[
            (bars_df['ts_local'] >= day_start) &
            (bars_df['ts_local'] < day_end)
        ]

        if day_bars.empty:
            continue

        # Calculate ORB (5-minute window)
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

        # Find entry (first close outside ORB in specified direction)
        # Scan from ORB end onwards
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

        # Calculate trade parameters
        entry_price = entry_bar['close']

        if sl_mode == 'HALF':
            stop_price = orb_mid
        else:  # FULL
            stop_price = orb_low if direction == 'UP' else orb_high

        if direction == 'UP':
            risk = entry_price - stop_price
            target_price = entry_price + (risk * rr)
        else:  # DOWN
            risk = stop_price - entry_price
            target_price = entry_price - (risk * rr)

        if risk <= 0:
            continue

        # Simulate outcome (remaining bars after entry)
        remaining_bars = day_bars[day_bars['ts_local'] > entry_bar['ts_local']]

        outcome = 'TIME_EXIT'
        r_multiple = 0.0

        for idx, bar in remaining_bars.iterrows():
            if direction == 'UP':
                # Check stop first (conservative)
                if bar['low'] <= stop_price:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    break
                if bar['high'] >= target_price:
                    outcome = 'WIN'
                    r_multiple = rr
                    break
            else:  # DOWN
                if bar['high'] >= stop_price:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    break
                if bar['low'] <= target_price:
                    outcome = 'WIN'
                    r_multiple = rr
                    break

        # Record trade
        trades.append({
            'date': trading_date,
            'outcome': outcome,
            'r_multiple': r_multiple
        })

    return trades


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
    """
    Split trades into 3 equal time periods and calculate metrics for each.

    Returns (split1_metrics, split2_metrics, split3_metrics)
    """
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


def test_family(
    bars_df: pd.DataFrame,
    orb_time: str,
    direction: str,
    rr: float,
    sl_mode: str,
    start_date: date,
    end_date: date
) -> FamilyResult:
    """Test a single family and return comprehensive results."""
    family_id = f"{INSTRUMENT}_{orb_time}_{direction}_{rr}R_{sl_mode}"

    # Backtest
    trades = backtest_family(bars_df, orb_time, direction, rr, sl_mode, start_date, end_date)

    # Overall metrics
    overall = calculate_metrics(trades)

    # Time splits
    split1, split2, split3 = calculate_time_splits(trades, start_date, end_date)

    # Stability analysis
    positive_splits = sum([
        1 if split1['avg_r'] > 0 else 0,
        1 if split2['avg_r'] > 0 else 0,
        1 if split3['avg_r'] > 0 else 0
    ])

    if overall['trades'] < 30:
        stability_flag = 'INSUFFICIENT'
    elif positive_splits >= 2:
        stability_flag = 'STABLE'
    else:
        stability_flag = 'UNSTABLE'

    return FamilyResult(
        family_id=family_id,
        instrument=INSTRUMENT,
        orb_time=orb_time,
        direction=direction,
        rr=rr,
        sl_mode=sl_mode,
        trades=overall['trades'],
        wins=overall['wins'],
        losses=overall['losses'],
        win_rate=overall['win_rate'],
        avg_r=overall['avg_r'],
        total_r=overall['total_r'],
        max_drawdown=overall['max_drawdown'],
        profit_factor=overall['profit_factor'],
        split1_trades=split1['trades'],
        split1_avg_r=split1['avg_r'],
        split2_trades=split2['trades'],
        split2_avg_r=split2['avg_r'],
        split3_trades=split3['trades'],
        split3_avg_r=split3['avg_r'],
        positive_splits=positive_splits,
        stability_flag=stability_flag
    )


def main():
    """Run Phase 1A baseline family discovery."""
    print("=" * 80)
    print("PHASE 1A - BASELINE FAMILY DISCOVERY")
    print("=" * 80)
    print()
    print("Testing ALL ORB families (NO FILTERS)")
    print()
    print(f"Instrument: {INSTRUMENT}")
    print(f"ORB Times: {ORB_TIMES}")
    print(f"Directions: {DIRECTIONS}")
    print(f"RR Values: {RR_VALUES}")
    print(f"SL Modes: {SL_MODES}")
    print()

    total_families = len(ORB_TIMES) * len(DIRECTIONS) * len(RR_VALUES) * len(SL_MODES)
    print(f"Total families to test: {total_families}")
    print()

    # Connect to database
    conn = duckdb.connect(DB_PATH, read_only=True)

    # Get data range
    start_date, end_date = get_data_range(conn)
    print(f"Data range: {start_date} to {end_date}")

    total_days = (end_date - start_date).days
    years = total_days / 365.25
    print(f"Duration: {total_days} days ({years:.2f} years)")
    print()

    # Load all bars once (more efficient)
    print("Loading bars from database...")
    bars_df = load_bars_for_date_range(conn, start_date, end_date)
    print(f"Loaded {len(bars_df):,} bars")
    print()

    # Test all families
    results = []
    count = 0

    for orb_time in ORB_TIMES:
        for direction in DIRECTIONS:
            for rr in RR_VALUES:
                for sl_mode in SL_MODES:
                    count += 1
                    family_id = f"{INSTRUMENT}_{orb_time}_{direction}_{rr}R_{sl_mode}"

                    print(f"[{count}/{total_families}] Testing {family_id}...", end=' ')

                    result = test_family(bars_df, orb_time, direction, rr, sl_mode, start_date, end_date)
                    results.append(result)

                    print(f"{result.trades} trades | {result.win_rate:.1f}% WR | {result.avg_r:+.3f}R avg | {result.stability_flag}")

    conn.close()

    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()

    # Convert to DataFrame
    df = pd.DataFrame([vars(r) for r in results])

    # Sort by avg_r (descending)
    df = df.sort_values('avg_r', ascending=False)

    # Save CSV
    output_csv = OUTPUT_DIR / 'phase1A_baseline_families.csv'
    df.to_csv(output_csv, index=False)
    print(f"[OK] Saved CSV: {output_csv}")

    # Generate markdown report
    output_md = OUTPUT_DIR / 'phase1A_baseline_families.md'

    with open(output_md, 'w') as f:
        f.write("# PHASE 1A - BASELINE FAMILY DISCOVERY\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Instrument**: {INSTRUMENT}\n\n")
        f.write(f"**Data Range**: {start_date} to {end_date} ({years:.2f} years)\n\n")
        f.write(f"**Families Tested**: {total_families}\n\n")
        f.write("---\n\n")

        # Summary stats
        f.write("## Summary Statistics\n\n")
        f.write(f"- Total families: {total_families}\n")
        f.write(f"- Profitable families (avg_r > 0): {len(df[df['avg_r'] > 0])}\n")
        f.write(f"- Stable families: {len(df[df['stability_flag'] == 'STABLE'])}\n")
        f.write(f"- Families with >=100 trades: {len(df[df['trades'] >= 100])}\n")
        f.write(f"- Best avg_r: {df['avg_r'].max():.3f}R\n")
        f.write(f"- Worst avg_r: {df['avg_r'].min():.3f}R\n\n")

        # Top 20
        f.write("---\n\n")
        f.write("## TOP 20 BASELINE FAMILIES\n\n")
        f.write("Ranked by avg_r (expectancy per trade)\n\n")
        f.write("| Rank | Family | Trades | WR% | Avg R | Total R | Max DD | PF | Stability | Splits (+) |\n")
        f.write("|------|--------|--------|-----|-------|---------|--------|----|-----------|-----------|\n")

        for i, row in enumerate(df.head(20).itertuples(), 1):
            f.write(f"| {i} | {row.family_id} | {row.trades} | {row.win_rate:.1f}% | {row.avg_r:+.3f}R | {row.total_r:+.1f}R | {row.max_drawdown:.1f}R | {row.profit_factor:.2f} | {row.stability_flag} | {row.positive_splits}/3 |\n")

        f.write("\n---\n\n")

        # By ORB time
        f.write("## ANALYSIS BY ORB TIME\n\n")
        for orb_time in ORB_TIMES:
            orb_families = df[df['orb_time'] == orb_time]
            best = orb_families.iloc[0] if len(orb_families) > 0 else None

            f.write(f"### {orb_time} ORB\n\n")
            if best is not None:
                f.write(f"- Best family: {best['family_id']}\n")
                f.write(f"- Avg R: {best['avg_r']:+.3f}R\n")
                f.write(f"- Win rate: {best['win_rate']:.1f}%\n")
                f.write(f"- Trades: {best['trades']}\n")
                f.write(f"- Stability: {best['stability_flag']}\n\n")

        f.write("---\n\n")

        # Full results table
        f.write("## ALL FAMILIES (Top 50)\n\n")
        f.write("| Rank | Family | ORB | Dir | RR | SL | Trades | WR% | Avg R | Total R | Max DD | Stability |\n")
        f.write("|------|--------|-----|-----|----|----|--------|-----|-------|---------|--------|-----------|\n")

        for i, row in enumerate(df.head(50).itertuples(), 1):
            f.write(f"| {i} | {row.family_id} | {row.orb_time} | {row.direction} | {row.rr}R | {row.sl_mode} | {row.trades} | {row.win_rate:.1f}% | {row.avg_r:+.3f}R | {row.total_r:+.1f}R | {row.max_drawdown:.1f}R | {row.stability_flag} |\n")

        f.write("\n")

    print(f"[OK] Saved report: {output_md}")
    print()

    # Display top 10
    print("=" * 80)
    print("TOP 10 BASELINE FAMILIES")
    print("=" * 80)
    print()

    for i, row in enumerate(df.head(10).itertuples(), 1):
        print(f"{i}. {row.family_id}")
        print(f"   Trades: {row.trades} | WR: {row.win_rate:.1f}% | Avg R: {row.avg_r:+.3f}R | Total R: {row.total_r:+.1f}R")
        print(f"   Max DD: {row.max_drawdown:.1f}R | PF: {row.profit_factor:.2f} | Stability: {row.stability_flag}")
        print(f"   Splits: {row.split1_avg_r:+.3f}R / {row.split2_avg_r:+.3f}R / {row.split3_avg_r:+.3f}R ({row.positive_splits}/3 positive)")
        print()

    print("=" * 80)
    print("PHASE 1A COMPLETE")
    print("=" * 80)
    print()
    print(f"Outputs saved:")
    print(f"  - {output_csv}")
    print(f"  - {output_md}")
    print()
    print("STOP - Awaiting confirmation to proceed to Phase 1B")
    print()


if __name__ == "__main__":
    main()
