#!/usr/bin/env python3
"""
Comprehensive 11am ORB Backtest - Complete Asia Session Picture

Tests all combinations for 11am ORB to understand 9/10/11am relationships.
"""

import duckdb
import pandas as pd
import numpy as np
import pytz
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Paths
ROOT = Path(__file__).parent
DB_PATH = str(ROOT / "data" / "db" / "gold.db")
OUTPUT_DIR = ROOT / "research"

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")
TZ_UTC = pytz.utc

# Test parameters
INSTRUMENT = 'MGC'
ORB_TIME = '1100'
ORB_MINUTES = 5
START_DATE = '2020-12-20'
END_DATE = '2026-01-10'

# Parameter combinations
RR_TARGETS = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
SL_MODES = ['HALF', 'FULL']
SCAN_WINDOWS = [
    ('standard', dt_time(11, 5), dt_time(17, 0)),
    ('extended', dt_time(11, 5), dt_time(9, 0))  # Next day
]


@dataclass
class Trade:
    variant_name: str
    date_local: str
    direction: str
    entry_ts_local: datetime
    entry_price: float
    stop_price: float
    target_price: float
    risk: float
    exit_ts_local: Optional[datetime] = None
    exit_price: Optional[float] = None
    outcome: str = 'NO_TRADE'
    r_multiple: float = 0.0
    time_to_resolution_minutes: float = 0.0


def load_bars_for_date(conn: duckdb.DuckDBPyConnection, trading_date: date, extended: bool = False) -> pd.DataFrame:
    start_dt_local = TZ_LOCAL.localize(datetime.combine(trading_date, dt_time(9, 0)))

    if extended:
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
        return pd.DataFrame()

    bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)
    bars['ts_local'] = bars['ts_utc'].dt.tz_convert(TZ_LOCAL)
    bars['time_local'] = bars['ts_local'].dt.time

    return bars


def calculate_orb(bars: pd.DataFrame) -> Optional[Dict[str, float]]:
    orb_start = dt_time(11, 0)
    orb_end = dt_time(11, 5)

    orb_bars = bars[(bars['time_local'] >= orb_start) & (bars['time_local'] < orb_end)]

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


def detect_breakout(bars: pd.DataFrame, orb: Dict[str, float], scan_start: dt_time, scan_end: dt_time, trading_date: date) -> Optional[Tuple[pd.Series, str]]:
    scan_start_dt = TZ_LOCAL.localize(datetime.combine(trading_date, scan_start))

    if scan_end < scan_start:
        scan_end_dt = TZ_LOCAL.localize(datetime.combine(trading_date + timedelta(days=1), scan_end))
    else:
        scan_end_dt = TZ_LOCAL.localize(datetime.combine(trading_date, scan_end))

    scan_bars = bars[(bars['ts_local'] >= scan_start_dt) & (bars['ts_local'] < scan_end_dt)]

    if len(scan_bars) == 0:
        return None

    for idx, bar in scan_bars.iterrows():
        if bar['close'] > orb['high']:
            return (bar, 'long')
        elif bar['close'] < orb['low']:
            return (bar, 'short')

    return None


def simulate_trade(entry_bar: pd.Series, direction: str, orb: Dict[str, float], remaining_bars: pd.DataFrame, rr: float, sl_mode: str, variant_name: str) -> Trade:
    entry_price = entry_bar['close']
    entry_ts = entry_bar['ts_local']

    if sl_mode == 'HALF':
        stop_price = orb['midpoint']
    else:
        stop_price = orb['low'] if direction == 'long' else orb['high']

    if direction == 'long':
        risk = entry_price - stop_price
        target_price = entry_price + (risk * rr)
    else:
        risk = stop_price - entry_price
        target_price = entry_price - (risk * rr)

    if risk <= 0:
        return Trade(
            variant_name=variant_name,
            date_local=str(entry_ts.date()),
            direction=direction,
            entry_ts_local=entry_ts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            risk=risk,
            outcome='NO_TRADE'
        )

    for idx, bar in remaining_bars.iterrows():
        if direction == 'long':
            if bar['low'] <= stop_price:
                return Trade(
                    variant_name=variant_name,
                    date_local=str(entry_ts.date()),
                    direction=direction,
                    entry_ts_local=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk=risk,
                    exit_ts_local=bar['ts_local'],
                    exit_price=stop_price,
                    outcome='LOSS',
                    r_multiple=-1.0,
                    time_to_resolution_minutes=(bar['ts_local'] - entry_ts).total_seconds() / 60
                )

            if bar['high'] >= target_price:
                return Trade(
                    variant_name=variant_name,
                    date_local=str(entry_ts.date()),
                    direction=direction,
                    entry_ts_local=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk=risk,
                    exit_ts_local=bar['ts_local'],
                    exit_price=target_price,
                    outcome='WIN',
                    r_multiple=rr,
                    time_to_resolution_minutes=(bar['ts_local'] - entry_ts).total_seconds() / 60
                )
        else:
            if bar['high'] >= stop_price:
                return Trade(
                    variant_name=variant_name,
                    date_local=str(entry_ts.date()),
                    direction=direction,
                    entry_ts_local=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk=risk,
                    exit_ts_local=bar['ts_local'],
                    exit_price=stop_price,
                    outcome='LOSS',
                    r_multiple=-1.0,
                    time_to_resolution_minutes=(bar['ts_local'] - entry_ts).total_seconds() / 60
                )

            if bar['low'] <= target_price:
                return Trade(
                    variant_name=variant_name,
                    date_local=str(entry_ts.date()),
                    direction=direction,
                    entry_ts_local=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk=risk,
                    exit_ts_local=bar['ts_local'],
                    exit_price=target_price,
                    outcome='WIN',
                    r_multiple=rr,
                    time_to_resolution_minutes=(bar['ts_local'] - entry_ts).total_seconds() / 60
                )

    if len(remaining_bars) > 0:
        final_bar = remaining_bars.iloc[-1]
        final_price = final_bar['close']

        if direction == 'long':
            pnl = final_price - entry_price
        else:
            pnl = entry_price - final_price

        r_mult = pnl / risk if risk != 0 else 0

        return Trade(
            variant_name=variant_name,
            date_local=str(entry_ts.date()),
            direction=direction,
            entry_ts_local=entry_ts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            risk=risk,
            exit_ts_local=final_bar['ts_local'],
            exit_price=final_price,
            outcome='TIME_EXIT',
            r_multiple=r_mult,
            time_to_resolution_minutes=(final_bar['ts_local'] - entry_ts).total_seconds() / 60
        )

    return Trade(
        variant_name=variant_name,
        date_local=str(entry_ts.date()),
        direction=direction,
        entry_ts_local=entry_ts,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        risk=risk,
        outcome='NO_TRADE'
    )


def backtest_variant(rr: float, sl_mode: str, scan_window_name: str, scan_start: dt_time, scan_end: dt_time, db_path: str = DB_PATH) -> List[Trade]:
    variant_name = f"RR{rr}_{sl_mode}_{scan_window_name}"
    conn = duckdb.connect(db_path, read_only=True)

    start_dt = datetime.strptime(START_DATE, '%Y-%m-%d').date()
    end_dt = datetime.strptime(END_DATE, '%Y-%m-%d').date()

    trades = []
    current_date = start_dt
    extended = (scan_window_name == 'extended')

    while current_date <= end_dt:
        bars = load_bars_for_date(conn, current_date, extended)

        if len(bars) == 0:
            current_date += timedelta(days=1)
            continue

        orb = calculate_orb(bars)
        if not orb:
            current_date += timedelta(days=1)
            continue

        entry_result = detect_breakout(bars, orb, scan_start, scan_end, current_date)

        if entry_result:
            entry_bar, direction = entry_result
            remaining_bars = bars[bars['ts_local'] > entry_bar['ts_local']]

            trade = simulate_trade(entry_bar, direction, orb, remaining_bars, rr, sl_mode, variant_name)

            if trade.outcome != 'NO_TRADE':
                trades.append(trade)

        current_date += timedelta(days=1)

    conn.close()
    return trades


def calculate_metrics(trades: List[Trade]) -> Dict:
    if len(trades) == 0:
        return {
            'trades': 0, 'wins': 0, 'losses': 0, 'time_exits': 0,
            'win_rate': 0.0, 'avg_r': 0.0, 'total_r': 0.0,
            'max_dd_r': 0.0, 'avg_time_hours': 0.0, 'annual_trades': 0.0
        }

    total = len(trades)
    wins = len([t for t in trades if t.outcome == 'WIN'])
    losses = len([t for t in trades if t.outcome == 'LOSS'])
    time_exits = len([t for t in trades if t.outcome == 'TIME_EXIT'])

    win_rate = (wins / total * 100) if total > 0 else 0

    r_multiples = [t.r_multiple for t in trades]
    avg_r = np.mean(r_multiples)
    total_r = np.sum(r_multiples)

    equity_curve = np.cumsum(np.concatenate([[0], r_multiples]))
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = equity_curve - running_max
    max_dd = abs(np.min(drawdowns))

    times = [t.time_to_resolution_minutes / 60.0 for t in trades]
    avg_time = np.mean(times)

    years = (datetime.strptime(END_DATE, '%Y-%m-%d') - datetime.strptime(START_DATE, '%Y-%m-%d')).days / 365.25
    annual_trades = total / years if years > 0 else 0

    return {
        'trades': total, 'wins': wins, 'losses': losses, 'time_exits': time_exits,
        'win_rate': win_rate, 'avg_r': avg_r, 'total_r': total_r,
        'max_dd_r': max_dd, 'avg_time_hours': avg_time, 'annual_trades': annual_trades
    }


def main():
    print("=" * 80)
    print("COMPREHENSIVE 11AM ORB BACKTEST")
    print("=" * 80)
    print()
    print(f"Instrument: {INSTRUMENT}")
    print(f"ORB Time: {ORB_TIME} (5 minutes)")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print()
    print(f"Testing {len(RR_TARGETS) * len(SL_MODES) * len(SCAN_WINDOWS)} variants")
    print()

    results = []
    variant_count = 0
    total_variants = len(RR_TARGETS) * len(SL_MODES) * len(SCAN_WINDOWS)

    for rr in RR_TARGETS:
        for sl_mode in SL_MODES:
            for window_name, scan_start, scan_end in SCAN_WINDOWS:
                variant_count += 1
                variant_name = f"RR{rr}_{sl_mode}_{window_name}"

                print(f"[{variant_count}/{total_variants}] Testing {variant_name}...", end=' ')

                trades = backtest_variant(rr, sl_mode, window_name, scan_start, scan_end)
                metrics = calculate_metrics(trades)

                results.append({
                    'variant': variant_name,
                    'rr': rr,
                    'sl_mode': sl_mode,
                    'scan_window': window_name,
                    **metrics
                })

                print(f"{metrics['trades']} trades | {metrics['win_rate']:.1f}% WR | {metrics['avg_r']:+.3f}R avg | {metrics['total_r']:+.1f}R total")

    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()

    results_df = pd.DataFrame(results).sort_values('avg_r', ascending=False)

    print("Top 10 Variants by Avg R:")
    print()
    print(results_df.head(10).to_string(index=False))
    print()

    output_csv = OUTPUT_DIR / 'backtest_1100_results.csv'
    results_df.to_csv(output_csv, index=False)
    print(f"[OK] Saved results to {output_csv}")
    print()

    winner = results_df.iloc[0]
    print("=" * 80)
    print("BEST 11AM STRATEGY")
    print("=" * 80)
    print()
    print(f"Variant: {winner['variant']}")
    print(f"RR Target: {winner['rr']}R")
    print(f"SL Mode: {winner['sl_mode']}")
    print(f"Scan Window: {winner['scan_window']}")
    print()
    print(f"Trades: {winner['trades']}")
    print(f"Win Rate: {winner['win_rate']:.1f}%")
    print(f"Avg R: {winner['avg_r']:+.3f}R")
    print(f"Total R: {winner['total_r']:+.1f}R")
    print(f"Max Drawdown: {winner['max_dd_r']:.1f}R")
    print(f"Annual Trades: {winner['annual_trades']:.0f}")
    print()


if __name__ == "__main__":
    main()
