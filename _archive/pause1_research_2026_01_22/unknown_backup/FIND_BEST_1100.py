"""
Quick search for best 11:00am ORB configurations
"""

import duckdb
from datetime import date, timedelta, datetime, time
from dataclasses import dataclass
import pandas as pd
import numpy as np

SYMBOL = "MGC"

@dataclass
class Result:
    duration_min: int
    sl_mode: str
    rr: float
    trades: int
    wins: int
    win_rate: float
    avg_r: float
    total_r: float
    annual_r: float
    median_hold_hours: float


def get_orb_from_bars(con, date_local, hour, minute, duration_min):
    """Calculate ORB dynamically"""
    start_ts = f"{date_local} {hour:02d}:{minute:02d}:00"
    end_dt = datetime.combine(date_local, time(hour, minute)) + timedelta(minutes=duration_min)
    end_ts = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    query = f"""
    SELECT high, low
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{start_ts}'::TIMESTAMPTZ
        AND ts_utc < '{end_ts}'::TIMESTAMPTZ
    """
    rows = con.execute(query).fetchall()
    if not rows:
        return None

    orb_high = max(float(r[0]) for r in rows)
    orb_low = min(float(r[1]) for r in rows)

    if orb_high <= orb_low:
        return None

    return {'high': orb_high, 'low': orb_low, 'size': orb_high - orb_low, 'end_ts': end_ts}


def detect_orb_break(con, orb, entry_start_ts, scan_end_ts):
    """Detect ORB break"""
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


def simulate_trade(con, date_local, hour, minute, duration_min, sl_mode, rr):
    """Simulate single trade"""
    orb = get_orb_from_bars(con, date_local, hour, minute, duration_min)
    if not orb:
        return None

    entry_start_ts = orb['end_ts']
    scan_end_ts = f"{date_local + timedelta(days=1)} 09:00:00"

    break_dir, entry_ts, entry_price = detect_orb_break(con, orb, entry_start_ts, scan_end_ts)
    if not break_dir:
        return None

    orb_mid = (orb['high'] + orb['low']) / 2.0
    orb_edge = orb['high'] if break_dir == 'UP' else orb['low']

    if sl_mode == "FULL":
        stop = orb['low'] if break_dir == 'UP' else orb['high']
    elif sl_mode == "HALF":
        stop = orb_mid
    elif sl_mode == "QUARTER":
        stop = orb_edge - (orb['size'] * 0.25) if break_dir == 'UP' else orb_edge + (orb['size'] * 0.25)
    else:
        return None

    r_size = abs(orb_edge - stop)
    if r_size <= 0:
        return None

    target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)

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
        h, l = float(h), float(l)

        if break_dir == 'UP':
            if l <= stop and h >= target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600}
            if h >= target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'WIN', 'r_multiple': float(rr), 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600}
            if l <= stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600}
        else:
            if h >= stop and l <= target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600}
            if l <= target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'WIN', 'r_multiple': float(rr), 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600}
            if h >= stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600}

    return None


def test_configuration(con, dates, duration, sl_mode, rr):
    """Test one configuration across all dates"""
    results = []
    for d in dates:
        result = simulate_trade(con, d, 11, 0, duration, sl_mode, rr)
        if result:
            results.append(result)

    if len(results) < 50:  # Need at least 50 trades
        return None

    wins = sum(1 for r in results if r['outcome'] == 'WIN')
    trades = len(results)
    win_rate = wins / trades
    total_r = sum(r['r_multiple'] for r in results)
    avg_r = total_r / trades
    annual_r = total_r / 2.0

    if avg_r < 0.1:  # Must be profitable
        return None

    return Result(
        duration_min=duration,
        sl_mode=sl_mode,
        rr=rr,
        trades=trades,
        wins=wins,
        win_rate=win_rate,
        avg_r=avg_r,
        total_r=total_r,
        annual_r=annual_r,
        median_hold_hours=np.median([r['hold_hours'] for r in results])
    )


def main():
    print("\n" + "="*80)
    print("FINDING BEST 11:00 ORB CONFIGURATIONS")
    print("="*80 + "\n")

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
    print(f"Testing across {len(dates)} trading days...\n")

    results = []
    configs_tested = 0

    for duration in [5, 10, 15, 30, 60]:
        for sl_mode in ["FULL", "HALF", "QUARTER"]:
            for rr in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]:
                configs_tested += 1
                result = test_configuration(con, dates, duration, sl_mode, rr)
                if result:
                    results.append(result)
                if configs_tested % 10 == 0:
                    print(f"Progress: {configs_tested}/150 configs tested, found {len(results)} profitable", flush=True)

    con.close()

    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}\n")
    print(f"Tested: {configs_tested} configurations")
    print(f"Found: {len(results)} profitable setups\n")

    if not results:
        print("No profitable setups found for 11:00 ORB!")
        return

    results.sort(key=lambda x: x.avg_r, reverse=True)

    # Save CSV
    df = pd.DataFrame([{
        'orb_time': '11:00',
        'duration_min': r.duration_min,
        'sl_mode': r.sl_mode,
        'rr': r.rr,
        'trades': r.trades,
        'wins': r.wins,
        'win_rate': r.win_rate,
        'avg_r': r.avg_r,
        'total_r': r.total_r,
        'annual_r': r.annual_r,
        'median_hold_hours': r.median_hold_hours
    } for r in results])
    df.to_csv("BEST_1100_SETUPS.csv", index=False)
    print(f"Results saved: BEST_1100_SETUPS.csv\n")

    # Print top 20
    print("="*80)
    print("TOP 20 CONFIGURATIONS FOR 11:00 ORB")
    print("="*80)
    print(f"{'Rank':<5} {'Dur':<6} {'SL':<8} {'RR':<5} {'Trades':<8} {'WR%':<7} {'Avg R':<8} {'Ann R':<8} {'Hold(h)':<8}")
    print("-"*80)

    for i, r in enumerate(results[:20], 1):
        print(f"{i:<5} {r.duration_min:<6} {r.sl_mode:<8} {r.rr:<5.1f} {r.trades:<8} {r.win_rate*100:<7.1f} {r.avg_r:<+8.3f} {r.annual_r:<+8.0f} {r.median_hold_hours:<8.1f}")

    print("\n" + "="*80)
    best = results[0]
    print(f"BEST 11:00 SETUP:")
    print(f"  Duration: {best.duration_min} minutes")
    print(f"  SL Mode: {best.sl_mode}")
    print(f"  RR Target: {best.rr}R")
    print(f"  Trades: {best.trades} ({best.wins} wins, {best.win_rate*100:.1f}% WR)")
    print(f"  Avg R per trade: {best.avg_r:+.3f}R")
    print(f"  Annual return: ~{best.annual_r:+.0f}R/year")
    print(f"  Median hold time: {best.median_hold_hours:.1f} hours")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
