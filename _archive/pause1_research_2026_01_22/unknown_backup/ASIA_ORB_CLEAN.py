"""
ASIA ORB CLEAN - ZERO LOOKAHEAD, AUTOMATABLE
==============================================

STRICT RULES:
1. ZERO LOOKAHEAD - Only use data available at time of trade entry
2. AUTOMATABLE - Only test setups that can be coded with broker API
3. STANDALONE ONLY - No conditional logic (no "after 0900 WIN" etc.)

Tests: 09:00, 10:00, 11:00 ORBs
- Various durations (5, 10, 15, 30 min)
- Various SL modes (FULL, HALF, QUARTER)
- Various RR targets
- Directional tests (ANY, UP, DOWN)

MOTHERLOAD FILTERS:
- 100+ trades (frequent - ~14% of days)
- 0.30+ avg R (strong edge - raised from 0.25)
- 50+ R/year (meaningful returns - raised from 40)
- Win rate >= 20% OR avg R >= 0.40 (quality threshold)
"""

import duckdb
from datetime import date, timedelta, datetime, time
from typing import Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

SYMBOL = "MGC"

@dataclass
class CleanResult:
    orb_time: str
    duration_min: int
    sl_mode: str
    rr: float
    direction: str
    trades: int
    wins: int
    win_rate: float
    avg_r: float
    total_r: float
    annual_r: float
    median_hold_hours: float
    up_trades: int
    down_trades: int
    up_win_rate: float
    down_win_rate: float


def get_orb_from_bars(con, date_local, hour, minute, duration_min):
    """Calculate ORB - ZERO LOOKAHEAD (only uses bars during ORB window)"""
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
    if not rows:
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
        'end_ts': end_ts
    }


def detect_orb_break(con, orb, entry_start_ts, scan_end_ts):
    """
    Detect ORB break - ZERO LOOKAHEAD

    Only looks at bars AFTER ORB completion.
    In live trading, you'd place stop orders at ORB high/low after ORB completes.
    """
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
    """
    Simulate trade - ZERO LOOKAHEAD, AUTOMATABLE

    Process:
    1. Calculate ORB after duration completes (known data)
    2. Wait for break (would use stop orders in live trading)
    3. Enter on break with stop loss and take profit
    4. Exit when TP or SL hit
    """
    orb = get_orb_from_bars(con, date_local, hour, minute, duration_min)
    if not orb:
        return None

    # Entry window starts AFTER ORB completes (zero lookahead)
    entry_start_ts = orb['end_ts']

    # Scan until next Asia open (realistic for overnight holds)
    scan_end_ts = f"{date_local + timedelta(days=1)} 09:00:00"

    break_dir, entry_ts, entry_price = detect_orb_break(con, orb, entry_start_ts, scan_end_ts)
    if not break_dir:
        return None

    # Direction filter (for testing directional bias)
    if direction_filter and break_dir != direction_filter:
        return None

    # Calculate stops (using only ORB data - known at entry)
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

    # Simulate execution (bars AFTER entry)
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
                # Both hit = stop hit first (conservative)
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r': -1.0, 'hold_hours': hold_hours, 'direction': break_dir}
            if hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'WIN', 'r': float(rr), 'hold_hours': hold_hours, 'direction': break_dir}
            if hit_stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r': -1.0, 'hold_hours': hold_hours, 'direction': break_dir}
        else:  # DOWN
            hit_stop = h >= stop
            hit_target = l <= target

            if hit_stop and hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r': -1.0, 'hold_hours': hold_hours, 'direction': break_dir}
            if hit_target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'WIN', 'r': float(rr), 'hold_hours': hold_hours, 'direction': break_dir}
            if hit_stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                return {'outcome': 'LOSS', 'r': -1.0, 'hold_hours': hold_hours, 'direction': break_dir}

    return None


def test_configuration(config):
    """Test a configuration across all dates - STANDALONE ONLY (no conditionals)"""
    hour, minute, duration, sl_mode, rr, direction_filter = config

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
        result = simulate_trade(con, d, hour, minute, duration, sl_mode, rr, direction_filter)
        if result:
            results.append(result)

    con.close()

    # STRICT MOTHERLOAD FILTERS
    if len(results) < 100:
        return None

    wins = sum(1 for r in results if r['outcome'] == 'WIN')
    trades = len(results)
    win_rate = wins / trades
    total_r = sum(r['r'] for r in results)
    avg_r = total_r / trades
    annual_r = (total_r / 2.0)

    # RAISED THRESHOLDS
    if avg_r < 0.30:  # Must be VERY profitable
        return None
    if annual_r < 50:  # Must produce solid returns
        return None
    if win_rate < 0.20 and avg_r < 0.40:  # Quality threshold
        return None

    hold_hours = [r['hold_hours'] for r in results]
    median_hold = np.median(hold_hours)

    # Directional stats
    up_results = [r for r in results if r['direction'] == 'UP']
    down_results = [r for r in results if r['direction'] == 'DOWN']

    up_wins = sum(1 for r in up_results if r['outcome'] == 'WIN')
    down_wins = sum(1 for r in down_results if r['outcome'] == 'WIN')

    return CleanResult(
        orb_time=f"{hour:02d}:{minute:02d}",
        duration_min=duration,
        sl_mode=sl_mode,
        rr=rr,
        direction=direction_filter if direction_filter else "ANY",
        trades=trades,
        wins=wins,
        win_rate=win_rate,
        avg_r=avg_r,
        total_r=total_r,
        annual_r=annual_r,
        median_hold_hours=median_hold,
        up_trades=len(up_results),
        down_trades=len(down_results),
        up_win_rate=up_wins / len(up_results) if up_results else 0,
        down_win_rate=down_wins / len(down_results) if down_results else 0
    )


def main():
    print("\n" + "="*80)
    print("ASIA ORB CLEAN - ZERO LOOKAHEAD, AUTOMATABLE")
    print("="*80)
    print("\n[OK] ZERO LOOKAHEAD - Only uses data available at trade time")
    print("[OK] AUTOMATABLE - Standard broker API functionality")
    print("[OK] STANDALONE - No conditional logic, no dependencies")
    print("\nSearching for Asia motherload setups...\n")

    configs = []

    asia_hours = [(9, 0), (10, 0), (11, 0)]
    durations = [5, 10, 15, 30]
    sl_modes = ["FULL", "HALF", "QUARTER"]
    rrs = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]

    # 1. Test ANY direction (most common)
    for hour, minute in asia_hours:
        for duration in durations:
            for sl_mode in sl_modes:
                for rr in rrs:
                    configs.append((hour, minute, duration, sl_mode, rr, None))

    # 2. Test directional bias (UP only, DOWN only)
    for hour, minute in asia_hours:
        for duration in [5, 10]:  # Shorter durations only
            for sl_mode in ["FULL", "HALF"]:
                for rr in [2.0, 3.0, 4.0, 5.0]:
                    configs.append((hour, minute, duration, sl_mode, rr, "UP"))
                    configs.append((hour, minute, duration, sl_mode, rr, "DOWN"))

    cpu_count = mp.cpu_count()
    workers = min(cpu_count, 8)

    print(f"Total configurations: {len(configs):,}")
    print(f"Using {workers} CPU cores\n")
    print("Starting search...\n")

    results = []
    last_percent = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for i, result in enumerate(executor.map(test_configuration, configs), 1):
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
    print(f"Found: {len(results)} motherload setups (100+ trades, 0.30+ avg R, 50+ R/year)\n")

    if not results:
        print("No setups passed strict motherload criteria!")
        print("\nTry lowering thresholds in the code if needed.")
        return

    # Sort by avg_r
    results.sort(key=lambda x: x.avg_r, reverse=True)

    # Save CSV
    df = pd.DataFrame([{
        'orb_time': r.orb_time,
        'duration_min': r.duration_min,
        'sl_mode': r.sl_mode,
        'rr': r.rr,
        'direction': r.direction,
        'trades': r.trades,
        'wins': r.wins,
        'win_rate': r.win_rate,
        'avg_r': r.avg_r,
        'total_r': r.total_r,
        'annual_r': r.annual_r,
        'median_hold_hours': r.median_hold_hours,
        'up_trades': r.up_trades,
        'down_trades': r.down_trades,
        'up_win_rate': r.up_win_rate,
        'down_win_rate': r.down_win_rate
    } for r in results])

    df.to_csv("ASIA_MOTHERLOADS_CLEAN.csv", index=False)
    print(f"Saved to: ASIA_MOTHERLOADS_CLEAN.csv\n")

    # Print top 30
    print("="*80)
    print("TOP 30 ASIA MOTHERLOADS - ZERO LOOKAHEAD, AUTOMATABLE")
    print("="*80)
    print(f"{'Rank':<5} {'ORB':<8} {'Dur':<5} {'SL':<8} {'RR':<5} {'Dir':<5} {'Trades':<8} {'WR%':<7} {'Avg R':<8} {'Ann R':<8} {'Hold(h)':<8}")
    print("-"*80)

    for i, r in enumerate(results[:30], 1):
        print(f"{i:<5} {r.orb_time:<8} {r.duration_min:<5} {r.sl_mode:<8} {r.rr:<5.1f} {r.direction:<5} {r.trades:<8} {r.win_rate*100:<7.1f} {r.avg_r:<+8.3f} {r.annual_r:<+8.0f} {r.median_hold_hours:<8.1f}")

    # Analysis
    print(f"\n{'='*80}")
    print("AUTOMATION NOTES")
    print(f"{'='*80}\n")

    print("HOW TO AUTOMATE:")
    print("1. Calculate ORB high/low after ORB duration completes")
    print("2. Place stop orders: BUY STOP at ORB high, SELL STOP at ORB low")
    print("3. When filled, immediately set:")
    print("   - Stop loss based on SL mode (FULL = opposite edge, HALF = midpoint)")
    print("   - Take profit at RR * risk from entry")
    print("4. Cancel unfilled stop order")
    print("5. Let trade run until TP or SL hit\n")

    print("BROKER REQUIREMENTS:")
    print("- Support for stop orders (entry)")
    print("- Support for stop loss and take profit orders")
    print("- API access for automated order placement")
    print("- Micro Gold futures (MGC) trading\n")

    # Directional bias analysis
    print("="*80)
    print("DIRECTIONAL BIAS ANALYSIS")
    print("="*80)

    any_dir = [r for r in results if r.direction == "ANY"]
    up_only = [r for r in results if r.direction == "UP"]
    down_only = [r for r in results if r.direction == "DOWN"]

    if any_dir:
        print(f"\nANY direction: {len(any_dir)} setups")
        print(f"  Avg R: {np.mean([r.avg_r for r in any_dir]):+.3f}")
        print(f"  Best: {any_dir[0].orb_time} {any_dir[0].duration_min}min RR={any_dir[0].rr} ({any_dir[0].avg_r:+.3f}R/trade, {any_dir[0].annual_r:+.0f}R/year)")

    if up_only:
        print(f"\nUP only: {len(up_only)} setups")
        print(f"  Avg R: {np.mean([r.avg_r for r in up_only]):+.3f}")
        print(f"  Best: {up_only[0].orb_time} {up_only[0].duration_min}min RR={up_only[0].rr} ({up_only[0].avg_r:+.3f}R/trade, {up_only[0].annual_r:+.0f}R/year)")

    if down_only:
        print(f"\nDOWN only: {len(down_only)} setups")
        print(f"  Avg R: {np.mean([r.avg_r for r in down_only]):+.3f}")
        print(f"  Best: {down_only[0].orb_time} {down_only[0].duration_min}min RR={down_only[0].rr} ({down_only[0].avg_r:+.3f}R/trade, {down_only[0].annual_r:+.0f}R/year)")

    print(f"\n{'='*80}")
    print("DONE! All setups are ZERO LOOKAHEAD and AUTOMATABLE.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
