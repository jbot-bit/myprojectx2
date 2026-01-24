"""
ASIA ORB FINDER
===============

FOCUSED SEARCH: Only Asia ORBs (09:00, 10:00, 11:00)
Tests:
- Individual ORBs with optimal parameters
- Conditional relationships (1000 after 0900, 1100 after 0900+1000)
- Directional biases (UP vs DOWN)
- Dynamics between sessions

STRICT MOTHERLOAD FILTERS:
- 100+ trades (frequent)
- 0.25+ avg R (strong edge)
- 40+ R/year (meaningful)
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
class AsiaResult:
    """Result from testing an Asia ORB configuration"""
    orb_time: str
    duration_min: int
    sl_mode: str
    rr: float
    condition: str  # "NONE", "0900_WIN", "0900_LOSS", etc.
    direction: str  # "ANY", "UP", "DOWN"

    trades: int
    wins: int
    win_rate: float
    avg_r: float
    total_r: float
    annual_r: float
    median_hold_hours: float

    # Relationship stats
    after_0900_win: Optional[int] = None
    after_0900_loss: Optional[int] = None
    after_1000_win: Optional[int] = None
    after_1000_loss: Optional[int] = None


def get_orb_from_bars(con, date_local, hour, minute, duration_min):
    """Calculate ORB dynamically"""
    if hour == 0 and minute < 9:
        start_ts = f"{date_local + timedelta(days=1)} {hour:02d}:{minute:02d}:00"
    else:
        start_ts = f"{date_local} {hour:02d}:{minute:02d}:00"

    end_dt = datetime.combine(date_local, time(hour, minute)) + timedelta(minutes=duration_min)
    if hour == 0 and minute < 9:
        end_dt = datetime.combine(date_local + timedelta(days=1), time(hour, minute)) + timedelta(minutes=duration_min)

    end_ts = end_dt.strftime("%Y-%m-%d %H:%M:%S")

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


def simulate_trade(con, date_local, hour, minute, duration_min, sl_mode, rr, direction_filter=None):
    """Simulate a single trade"""
    orb = get_orb_from_bars(con, date_local, hour, minute, duration_min)
    if not orb:
        return None

    entry_start_ts = orb['end_ts']
    scan_end_ts = f"{date_local + timedelta(days=1)} 09:00:00"

    break_dir, entry_ts, entry_price = detect_orb_break(con, orb, entry_start_ts, scan_end_ts)
    if not break_dir:
        return None

    # Direction filter
    if direction_filter and break_dir != direction_filter:
        return None

    # Calculate stop
    orb_mid = (orb['high'] + orb['low']) / 2.0
    orb_size = orb['size']
    orb_edge = orb['high'] if break_dir == 'UP' else orb['low']

    if sl_mode == "FULL":
        stop = orb['low'] if break_dir == 'UP' else orb['high']
    elif sl_mode == "HALF":
        stop = orb_mid
    elif sl_mode == "QUARTER":
        stop = orb_edge - (orb_size * 0.25) if break_dir == 'UP' else orb_edge + (orb_size * 0.25)
    else:
        return None

    r_size = abs(orb_edge - stop)
    if r_size <= 0:
        return None

    target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)

    # Get bars after entry
    bars_query = f"""
    SELECT ts_utc, high, low
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc > '{entry_ts}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end_ts}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """

    bars = con.execute(bars_query).fetchall()
    if not bars:
        return None

    entry_dt = datetime.fromisoformat(entry_ts.replace('+00:00', ''))

    for ts_utc, h, l in bars:
        h = float(h)
        l = float(l)

        if break_dir == 'UP':
            hit_stop = l <= stop
            hit_target = h >= target

            if hit_stop and hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': hold_hours, 'direction': break_dir}
            if hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'WIN', 'r_multiple': float(rr), 'hold_hours': hold_hours, 'direction': break_dir}
            if hit_stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': hold_hours, 'direction': break_dir}
        else:  # DOWN
            hit_stop = h >= stop
            hit_target = l <= target

            if hit_stop and hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': hold_hours, 'direction': break_dir}
            if hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'WIN', 'r_multiple': float(rr), 'hold_hours': hold_hours, 'direction': break_dir}
            if hit_stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': hold_hours, 'direction': break_dir}

    return None


def test_asia_orb(config):
    """Test a single Asia ORB configuration"""
    hour, minute, duration, sl_mode, rr, condition, direction_filter = config

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

    # First pass: Get 0900 and 1000 results for all dates (for conditional logic)
    orb_0900_results = {}
    orb_1000_results = {}

    if condition != "NONE":
        # Need to simulate 0900 for conditioning
        for d in dates:
            r = simulate_trade(con, d, 9, 0, 5, "FULL", 1.0)  # Simple 0900 baseline
            if r:
                orb_0900_results[d] = r

        # Need 1000 results for 1100 conditioning
        if hour == 11:
            for d in dates:
                r = simulate_trade(con, d, 10, 0, 5, "FULL", 1.0)  # Simple 1000 baseline
                if r:
                    orb_1000_results[d] = r

    # Second pass: Simulate actual trades with conditions
    results = []
    for d in dates:
        # Check condition
        if condition == "0900_WIN" and (d not in orb_0900_results or orb_0900_results[d]['outcome'] != 'WIN'):
            continue
        if condition == "0900_LOSS" and (d not in orb_0900_results or orb_0900_results[d]['outcome'] != 'LOSS'):
            continue
        if condition == "0900_WIN_1000_WIN" and (
            d not in orb_0900_results or orb_0900_results[d]['outcome'] != 'WIN' or
            d not in orb_1000_results or orb_1000_results[d]['outcome'] != 'WIN'
        ):
            continue

        result = simulate_trade(con, d, hour, minute, duration, sl_mode, rr, direction_filter)
        if result:
            results.append(result)

    con.close()

    # MOTHERLOAD FILTERS
    if len(results) < 100:  # Must occur frequently
        return None

    wins = sum(1 for r in results if r['outcome'] == 'WIN')
    trades = len(results)
    win_rate = wins / trades
    total_r = sum(r['r_multiple'] for r in results)
    avg_r = total_r / trades
    annual_r = (total_r / 2.0)

    if avg_r < 0.25:  # Must be strongly profitable
        return None
    if annual_r < 40:  # Must produce meaningful returns
        return None
    if win_rate < 0.25 and avg_r < 0.35:  # Low WR needs high payoff
        return None

    hold_hours = [r['hold_hours'] for r in results]
    median_hold = np.median(hold_hours)

    # Count directional stats
    up_trades = sum(1 for r in results if r['direction'] == 'UP')
    down_trades = sum(1 for r in results if r['direction'] == 'DOWN')

    return AsiaResult(
        orb_time=f"{hour:02d}:{minute:02d}",
        duration_min=duration,
        sl_mode=sl_mode,
        rr=rr,
        condition=condition,
        direction=direction_filter if direction_filter else "ANY",
        trades=trades,
        wins=wins,
        win_rate=win_rate,
        avg_r=avg_r,
        total_r=total_r,
        annual_r=annual_r,
        median_hold_hours=median_hold
    )


def main():
    print("\n" + "="*80)
    print("ASIA ORB FINDER - FOCUSED SEARCH")
    print("="*80)
    print("\nSearching for motherload setups in Asia session...")
    print("Testing: 09:00, 10:00, 11:00 ORBs + relationships\n")

    # Generate configurations
    configs = []

    asia_hours = [(9, 0), (10, 0), (11, 0)]
    durations = [5, 10, 15, 30]
    sl_modes = ["FULL", "HALF", "QUARTER"]
    rrs = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]

    # 1. Standalone tests (no conditions)
    for hour, minute in asia_hours:
        for duration in durations:
            for sl_mode in sl_modes:
                for rr in rrs:
                    configs.append((hour, minute, duration, sl_mode, rr, "NONE", None))

    # 2. Conditional tests
    # 1000 after 0900 WIN/LOSS
    for duration in durations:
        for sl_mode in sl_modes:
            for rr in rrs:
                configs.append((10, 0, duration, sl_mode, rr, "0900_WIN", None))
                configs.append((10, 0, duration, sl_mode, rr, "0900_LOSS", None))

    # 1100 after 0900+1000 combinations
    for duration in durations:
        for sl_mode in sl_modes:
            for rr in rrs:
                configs.append((11, 0, duration, sl_mode, rr, "0900_WIN", None))
                configs.append((11, 0, duration, sl_mode, rr, "0900_LOSS", None))
                configs.append((11, 0, duration, sl_mode, rr, "0900_WIN_1000_WIN", None))

    # 3. Directional tests (UP only, DOWN only)
    for hour, minute in asia_hours:
        for duration in [5, 10]:  # Just test shorter durations for directional
            for sl_mode in ["FULL", "HALF"]:
                for rr in [1.5, 2.0, 3.0, 4.0]:
                    configs.append((hour, minute, duration, sl_mode, rr, "NONE", "UP"))
                    configs.append((hour, minute, duration, sl_mode, rr, "NONE", "DOWN"))

    cpu_count = mp.cpu_count()
    workers = min(cpu_count, 8)

    print(f"Total configurations: {len(configs):,}")
    print(f"Using {workers} CPU cores\n")
    print("Starting search...\n")

    results = []
    last_percent = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for i, result in enumerate(executor.map(test_asia_orb, configs), 1):
            if result:
                results.append(result)

            current_percent = (i * 100) // len(configs)
            if i % 50 == 0 or current_percent > last_percent:
                last_percent = current_percent
                print(f"Progress: {i:,}/{len(configs):,} ({current_percent}%) - Found {len(results)} motherloads", flush=True)

    print(f"\n{'='*80}")
    print(f"SEARCH COMPLETE!")
    print(f"{'='*80}\n")
    print(f"Tested: {len(configs):,} configurations")
    print(f"Found: {len(results)} motherload setups\n")

    if not results:
        print("No setups passed motherload criteria!")
        return

    # Sort by avg_r
    results.sort(key=lambda x: x.avg_r, reverse=True)

    # Save to CSV
    df = pd.DataFrame([{
        'orb_time': r.orb_time,
        'duration_min': r.duration_min,
        'sl_mode': r.sl_mode,
        'rr': r.rr,
        'condition': r.condition,
        'direction': r.direction,
        'trades': r.trades,
        'wins': r.wins,
        'win_rate': r.win_rate,
        'avg_r': r.avg_r,
        'total_r': r.total_r,
        'annual_r': r.annual_r,
        'median_hold_hours': r.median_hold_hours
    } for r in results])

    df.to_csv("ASIA_MOTHERLOADS.csv", index=False)
    print(f"Saved to: ASIA_MOTHERLOADS.csv\n")

    # Print top 30
    print("="*80)
    print("TOP 30 ASIA MOTHERLOADS (by Avg R)")
    print("="*80)
    print(f"{'Rank':<5} {'ORB':<8} {'Dur':<5} {'SL':<8} {'RR':<5} {'Cond':<20} {'Dir':<5} {'Trades':<8} {'WR%':<7} {'Avg R':<8} {'Ann R':<8}")
    print("-"*80)

    for i, r in enumerate(results[:30], 1):
        print(f"{i:<5} {r.orb_time:<8} {r.duration_min:<5} {r.sl_mode:<8} {r.rr:<5.1f} {r.condition:<20} {r.direction:<5} {r.trades:<8} {r.win_rate*100:<7.1f} {r.avg_r:<+8.3f} {r.annual_r:<+8.0f}")

    # Analysis
    print(f"\n{'='*80}")
    print("DYNAMICS ANALYSIS")
    print(f"{'='*80}\n")

    # Standalone vs Conditional
    standalone = [r for r in results if r.condition == "NONE" and r.direction == "ANY"]
    conditional = [r for r in results if r.condition != "NONE"]

    print(f"STANDALONE setups: {len(standalone)}")
    if standalone:
        print(f"  Avg R: {np.mean([r.avg_r for r in standalone]):+.3f}")
        print(f"  Best: {standalone[0].orb_time} {standalone[0].duration_min}min, RR={standalone[0].rr}, {standalone[0].avg_r:+.3f}R\n")

    print(f"CONDITIONAL setups: {len(conditional)}")
    if conditional:
        print(f"  Avg R: {np.mean([r.avg_r for r in conditional]):+.3f}")
        by_cond = {}
        for r in conditional:
            if r.condition not in by_cond:
                by_cond[r.condition] = []
            by_cond[r.condition].append(r)

        for cond in sorted(by_cond.keys()):
            setups = by_cond[cond]
            avg_r = np.mean([s.avg_r for s in setups])
            best = max(setups, key=lambda x: x.avg_r)
            print(f"  {cond}: {len(setups)} setups, avg R={avg_r:+.3f}, best={best.orb_time} RR={best.rr} ({best.avg_r:+.3f}R)")

    # Directional
    directional = [r for r in results if r.direction != "ANY"]
    if directional:
        print(f"\nDIRECTIONAL setups: {len(directional)}")
        up_setups = [r for r in directional if r.direction == "UP"]
        down_setups = [r for r in directional if r.direction == "DOWN"]

        if up_setups:
            print(f"  UP only: {len(up_setups)} setups, avg R={np.mean([r.avg_r for r in up_setups]):+.3f}")
        if down_setups:
            print(f"  DOWN only: {len(down_setups)} setups, avg R={np.mean([r.avg_r for r in down_setups]):+.3f}")

    print(f"\n{'='*80}")
    print("DONE!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
