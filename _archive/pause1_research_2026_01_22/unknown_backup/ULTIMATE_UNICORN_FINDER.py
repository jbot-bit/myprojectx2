"""
ULTIMATE UNICORN FINDER
=======================

COMPREHENSIVE GRID SEARCH FOR ALL POSSIBLE UNICORN SETUPS

Tests:
- Every hour (24 ORB times)
- Multiple ORB durations (5, 10, 15, 30, 60 minutes)
- Multiple SL modes (FULL, HALF, QUARTER, THREE_QUARTER)
- RR values from 1.0 to 10.0
- Different entry methods
- Extended scan windows (until 09:00 next day)

Goal: Find EVERY profitable setup, no matter how rare or unusual.
"""

import duckdb
from datetime import date, timedelta, datetime, time
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

SYMBOL = "MGC"
TICK_SIZE = 0.1

@dataclass
class UnicornResult:
    """Result from testing a single configuration"""
    orb_hour: int
    orb_minute: int
    orb_duration_min: int
    sl_mode: str  # FULL, HALF, QUARTER, THREE_QUARTER
    rr: float
    trades: int
    wins: int
    win_rate: float
    avg_r: float
    total_r: float
    annual_r: float
    median_hold_hours: float
    max_r: float  # Best single trade


def get_orb_from_bars(con, date_local, hour, minute, duration_min):
    """Calculate ORB dynamically for any time and duration"""

    # Get ORB start time
    if hour == 0 and minute < 9:  # Crosses midnight into next day
        start_ts = f"{date_local + timedelta(days=1)} {hour:02d}:{minute:02d}:00"
    else:
        start_ts = f"{date_local} {hour:02d}:{minute:02d}:00"

    # Get ORB end time
    end_dt = datetime.combine(date_local, time(hour, minute)) + timedelta(minutes=duration_min)
    if hour == 0 and minute < 9:
        end_dt = datetime.combine(date_local + timedelta(days=1), time(hour, minute)) + timedelta(minutes=duration_min)

    end_ts = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Query bars during ORB window
    query = f"""
    SELECT high, low
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{start_ts}'::TIMESTAMPTZ
        AND ts_utc < '{end_ts}'::TIMESTAMPTZ
    ORDER BY ts_utc
    """

    rows = con.execute(query).fetchall()
    if not rows or len(rows) == 0:
        return None

    highs = [float(r[0]) for r in rows]
    lows = [float(r[1]) for r in rows]

    orb_high = max(highs)
    orb_low = min(lows)
    orb_size = orb_high - orb_low

    if orb_size <= 0:
        return None

    return {
        'high': orb_high,
        'low': orb_low,
        'size': orb_size,
        'start_ts': start_ts,
        'end_ts': end_ts
    }


def detect_orb_break(con, orb, entry_start_ts, scan_end_ts):
    """Detect if ORB broke and which direction"""

    query = f"""
    SELECT ts_utc, close
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{entry_start_ts}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end_ts}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    LIMIT 100
    """

    rows = con.execute(query).fetchall()
    if not rows:
        return None, None, None

    for ts, close in rows:
        if float(close) > orb['high']:
            return 'UP', str(ts), float(close)
        elif float(close) < orb['low']:
            return 'DOWN', str(ts), float(close)

    return None, None, None


def simulate_unicorn_trade(con, date_local, hour, minute, duration_min, sl_mode, rr):
    """Simulate a single trade configuration"""

    # Get ORB
    orb = get_orb_from_bars(con, date_local, hour, minute, duration_min)
    if not orb:
        return None

    # Entry window starts after ORB completes
    entry_start_ts = orb['end_ts']

    # Scan until 09:00 next day
    scan_end_ts = f"{date_local + timedelta(days=1)} 09:00:00"

    # Detect break
    break_dir, entry_ts, entry_price = detect_orb_break(con, orb, entry_start_ts, scan_end_ts)
    if not break_dir:
        return None

    # Calculate stop based on mode
    orb_mid = (orb['high'] + orb['low']) / 2.0
    orb_size = orb['size']
    orb_edge = orb['high'] if break_dir == 'UP' else orb['low']

    if sl_mode == "FULL":
        stop = orb['low'] if break_dir == 'UP' else orb['high']
    elif sl_mode == "HALF":
        stop = orb_mid
    elif sl_mode == "QUARTER":
        # Stop at 25% into range from edge
        stop = orb_edge - (orb_size * 0.25) if break_dir == 'UP' else orb_edge + (orb_size * 0.25)
    elif sl_mode == "THREE_QUARTER":
        # Stop at 75% into range from edge
        stop = orb_edge - (orb_size * 0.75) if break_dir == 'UP' else orb_edge + (orb_size * 0.75)
    else:
        return None

    # Calculate R
    r_size = abs(orb_edge - stop)
    if r_size <= 0:
        return None

    # Calculate target
    target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)

    # Get bars after entry
    bars_query = f"""
    SELECT ts_utc, high, low, close
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc > '{entry_ts}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end_ts}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """

    bars = con.execute(bars_query).fetchall()
    if not bars:
        return None

    # Simulate trade
    entry_dt = datetime.fromisoformat(entry_ts.replace('+00:00', ''))

    for ts_utc, h, l, c in bars:
        h = float(h)
        l = float(l)

        if break_dir == 'UP':
            hit_stop = l <= stop
            hit_target = h >= target

            if hit_stop and hit_target:
                # Both hit same bar = LOSS
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': hold_hours}
            if hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'WIN', 'r_multiple': float(rr), 'hold_hours': hold_hours}
            if hit_stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': hold_hours}
        else:  # DOWN
            hit_stop = h >= stop
            hit_target = l <= target

            if hit_stop and hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': hold_hours}
            if hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'WIN', 'r_multiple': float(rr), 'hold_hours': hold_hours}
            if hit_stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': hold_hours}

    # No TP/SL hit
    return None


def test_configuration(config):
    """Test a single configuration across all dates"""
    hour, minute, duration, sl_mode, rr = config

    con = duckdb.connect("gold.db", read_only=True)

    dates_query = """
    SELECT DISTINCT date_local
    FROM daily_features_v2
    WHERE instrument = 'MGC'
        AND date_local >= '2024-01-02'
        AND date_local <= '2026-01-10'
    ORDER BY date_local
    """
    dates = [row[0] for row in con.execute(dates_query).fetchall()]

    results = []
    for d in dates:
        result = simulate_unicorn_trade(con, d, hour, minute, duration, sl_mode, rr)
        if result:
            results.append(result)

    con.close()

    # STRICT FILTERS: Only catch the real motherloads!
    if len(results) < 100:  # Must occur frequently (100+ trades over 2 years = ~7% of days minimum)
        return None

    wins = sum(1 for r in results if r['outcome'] == 'WIN')
    trades = len(results)
    win_rate = wins / trades
    total_r = sum(r['r_multiple'] for r in results)
    avg_r = total_r / trades
    annual_r = (total_r / 2.0)  # 2 years of data

    hold_hours = [r['hold_hours'] for r in results]
    median_hold = np.median(hold_hours)

    max_r = max([r['r_multiple'] for r in results])

    # MOTHERLOAD FILTERS:
    # 1. Must be strongly profitable (avg_r >= 0.25)
    if avg_r < 0.25:
        return None

    # 2. Must produce meaningful annual returns (>= 40R/year)
    if annual_r < 40:
        return None

    # 3. Must have either decent win rate OR high payoff
    if win_rate < 0.25 and avg_r < 0.35:  # Low WR needs high payoff
        return None

    return UnicornResult(
        orb_hour=hour,
        orb_minute=minute,
        orb_duration_min=duration,
        sl_mode=sl_mode,
        rr=rr,
        trades=trades,
        wins=wins,
        win_rate=win_rate,
        avg_r=avg_r,
        total_r=total_r,
        annual_r=annual_r,
        median_hold_hours=median_hold,
        max_r=max_r
    )


def main():
    print("\n" + "="*80)
    print("ULTIMATE UNICORN FINDER")
    print("="*80)
    print("\nSearching for EVERY profitable setup...")

    # Validate database exists and has data
    try:
        con = duckdb.connect("gold.db", read_only=True)

        # Check if daily_features table exists
        tables = con.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]

        if 'daily_features_v2' not in table_names:
            print("\nERROR: 'daily_features_v2' table not found in gold.db!")
            print("Available tables:", table_names)
            print("\nPlease run the V2 backfill scripts first.")
            return

        # Check data availability
        date_count = con.execute("""
            SELECT COUNT(DISTINCT date_local)
            FROM daily_features_v2
            WHERE instrument = 'MGC'
        """).fetchone()[0]

        bar_count = con.execute("""
            SELECT COUNT(*)
            FROM bars_1m
            WHERE symbol = 'MGC'
        """).fetchone()[0]

        con.close()

        print(f"\nDatabase validation:")
        print(f"  - Trading days available: {date_count}")
        print(f"  - 1-minute bars available: {bar_count:,}")

        if date_count < 100:
            print(f"\nWARNING: Only {date_count} days of data found. Need at least 100 days for reliable results.")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                return

    except Exception as e:
        print(f"\nERROR validating database: {e}")
        return

    print("\nThis will take 15-30 minutes...\n")

    # Generate all configurations to test
    configs = []

    # Test every hour + 00:30
    hours_to_test = list(range(24)) + [(0, 30)]  # 0-23 + 00:30

    for hour_spec in hours_to_test:
        if isinstance(hour_spec, tuple):
            hour, minute = hour_spec
        else:
            hour, minute = hour_spec, 0

        for duration in [5, 10, 15, 30, 60]:  # ORB durations
            for sl_mode in ["FULL", "HALF", "QUARTER"]:
                for rr in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]:
                    configs.append((hour, minute, duration, sl_mode, rr))

    # Determine CPU cores to use
    cpu_count = mp.cpu_count()
    workers = min(cpu_count, 8)  # Cap at 8 to avoid overwhelming system

    print(f"Total configurations to test: {len(configs):,}")
    print(f"System has {cpu_count} CPU cores, using {workers} workers\n")
    print("Starting parallel search...\n")

    # Run parallel testing with progress tracking
    results = []
    last_percent = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for i, result in enumerate(executor.map(test_configuration, configs), 1):
            if result:
                results.append(result)

            # Show progress every 50 configs OR every 5% progress
            current_percent = (i * 100) // len(configs)
            if i % 50 == 0 or current_percent > last_percent:
                last_percent = current_percent
                print(f"Progress: {i:,}/{len(configs):,} ({current_percent}%) - Found {len(results)} profitable setups", flush=True)

            # Save checkpoint every 250 configs (allows stopping early)
            if i % 250 == 0 and results:
                results_sorted = sorted(results, key=lambda x: x.avg_r, reverse=True)
                df_checkpoint = pd.DataFrame([{
                    'orb_time': f"{r.orb_hour:02d}:{r.orb_minute:02d}",
                    'duration_min': r.orb_duration_min,
                    'sl_mode': r.sl_mode,
                    'rr': r.rr,
                    'trades': r.trades,
                    'wins': r.wins,
                    'win_rate': r.win_rate,
                    'avg_r': r.avg_r,
                    'total_r': r.total_r,
                    'annual_r': r.annual_r,
                    'median_hold_hours': r.median_hold_hours,
                    'max_r': r.max_r
                } for r in results_sorted])
                df_checkpoint.to_csv(f"ULTIMATE_UNICORNS_checkpoint_{i}.csv", index=False)
                print(f"  → Checkpoint saved: ULTIMATE_UNICORNS_checkpoint_{i}.csv", flush=True)

    print(f"\n{'='*80}")
    print(f"SEARCH COMPLETE!")
    print(f"{'='*80}\n")
    print(f"Tested: {len(configs):,} configurations")
    print(f"Found: {len(results)} profitable setups\n")

    if not results:
        print("No profitable setups found!")
        return

    # Sort by avg_r
    results.sort(key=lambda x: x.avg_r, reverse=True)

    # Save to CSV
    df = pd.DataFrame([{
        'orb_time': f"{r.orb_hour:02d}:{r.orb_minute:02d}",
        'duration_min': r.orb_duration_min,
        'sl_mode': r.sl_mode,
        'rr': r.rr,
        'trades': r.trades,
        'wins': r.wins,
        'win_rate': r.win_rate,
        'avg_r': r.avg_r,
        'total_r': r.total_r,
        'annual_r': r.annual_r,
        'median_hold_hours': r.median_hold_hours,
        'max_r': r.max_r
    } for r in results])

    df.to_csv("ULTIMATE_UNICORNS.csv", index=False)
    print(f"Results saved to: ULTIMATE_UNICORNS.csv\n")

    # Print top 50
    print("="*80)
    print("TOP 50 UNICORNS (by Avg R)")
    print("="*80)
    print(f"{'Rank':<5} {'Time':<8} {'Dur':<5} {'SL':<8} {'RR':<5} {'Trades':<8} {'WR%':<7} {'Avg R':<8} {'Ann R':<8} {'Hold(h)':<8}")
    print("-"*80)

    for i, r in enumerate(results[:50], 1):
        print(f"{i:<5} {r.orb_hour:02d}:{r.orb_minute:02d}    {r.orb_duration_min:<5} {r.sl_mode:<8} {r.rr:<5.1f} {r.trades:<8} {r.win_rate*100:<7.1f} {r.avg_r:<+8.3f} {r.annual_r:<+8.0f} {r.median_hold_hours:<8.1f}")

    print("\n" + "="*80)
    print("ANALYSIS BY CATEGORY")
    print("="*80)

    # Best by time of day
    print("\nBEST BY TIME OF DAY:")
    by_hour = {}
    for r in results:
        key = r.orb_hour
        if key not in by_hour or r.avg_r > by_hour[key].avg_r:
            by_hour[key] = r

    for hour in sorted(by_hour.keys()):
        r = by_hour[hour]
        print(f"  {hour:02d}:00 ORB: {r.orb_duration_min}min, {r.sl_mode}, RR={r.rr}, {r.avg_r:+.3f}R avg, ~{r.annual_r:+.0f}R/year")

    # Best by duration
    print("\nBEST BY ORB DURATION:")
    by_duration = {}
    for r in results:
        key = r.orb_duration_min
        if key not in by_duration or r.avg_r > by_duration[key].avg_r:
            by_duration[key] = r

    for dur in sorted(by_duration.keys()):
        r = by_duration[dur]
        print(f"  {dur}min ORB: {r.orb_hour:02d}:{r.orb_minute:02d}, {r.sl_mode}, RR={r.rr}, {r.avg_r:+.3f}R avg, ~{r.annual_r:+.0f}R/year")

    # Best by SL mode
    print("\nBEST BY SL MODE:")
    by_sl = {}
    for r in results:
        key = r.sl_mode
        if key not in by_sl or r.avg_r > by_sl[key].avg_r:
            by_sl[key] = r

    for sl in sorted(by_sl.keys()):
        r = by_sl[sl]
        print(f"  {sl}: {r.orb_hour:02d}:{r.orb_minute:02d}, {r.orb_duration_min}min, RR={r.rr}, {r.avg_r:+.3f}R avg, ~{r.annual_r:+.0f}R/year")

    # Highest single trade
    best_single = max(results, key=lambda x: x.max_r)
    print(f"\nLARGEST SINGLE WINNER:")
    print(f"  {best_single.orb_hour:02d}:{best_single.orb_minute:02d} ORB, {best_single.orb_duration_min}min, {best_single.sl_mode}, RR={best_single.rr}")
    print(f"  Best trade: {best_single.max_r:+.1f}R")

    print("\n" + "="*80)
    print("DONE!")
    print("="*80)


if __name__ == "__main__":
    main()
