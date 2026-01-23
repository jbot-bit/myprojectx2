"""
FIND HIGH RR SETUPS NOT IN VALIDATED LIBRARY
==============================================

Scan all ORBs for high-RR setups (RR >= 3.0) that are:
1. Frequent (>= 400 trades over 2 years = ~54% of days)
2. Profitable (avg_r > 0.15)
3. NOT already in validated_setups

Then show the best candidate for validation.
"""

import duckdb
from datetime import date, timedelta, datetime, time
from dataclasses import dataclass

DB_PATH = "data/db/gold.db"
SYMBOL = "MGC"

@dataclass
class TestResult:
    orb: str
    rr: float
    sl_mode: str
    trades: int
    wins: int
    win_rate: float
    avg_r: float
    total_r: float
    in_library: bool


def get_orb_from_bars(con, date_local, hour, minute, duration=5):
    """Get ORB from bars_1m"""
    start_ts = f"{date_local} {hour:02d}:{minute:02d}:00"
    end_dt = datetime.combine(date_local, time(hour, minute)) + timedelta(minutes=duration)
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

    return {'high': orb_high, 'low': orb_low}


def detect_break(con, orb, date_local, hour, minute):
    """Detect first close outside ORB"""
    entry_start = datetime.combine(date_local, time(hour, minute)) + timedelta(minutes=5)
    entry_start_str = entry_start.strftime("%Y-%m-%d %H:%M:%S")
    scan_end = f"{date_local + timedelta(days=1)} 09:00:00"

    query = f"""
    SELECT ts_utc, close
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{entry_start_str}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """
    rows = con.execute(query).fetchall()

    if not rows:
        return None, None

    for ts, close in rows:
        if float(close) > orb['high']:
            return 'UP', str(ts)
        elif float(close) < orb['low']:
            return 'DOWN', str(ts)
    return None, None


def simulate_trade(con, orb, break_dir, entry_ts, date_local, rr, sl_mode):
    """Simulate trade outcome"""
    orb_edge = orb['high'] if break_dir == 'UP' else orb['low']
    orb_mid = (orb['high'] + orb['low']) / 2.0

    if sl_mode == "FULL":
        stop = orb['low'] if break_dir == 'UP' else orb['high']
    elif sl_mode == "HALF":
        stop = orb_mid
    else:
        return None

    r_size = abs(orb_edge - stop)
    if r_size <= 0:
        return None

    target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)

    scan_end = f"{date_local + timedelta(days=1)} 09:00:00"

    query = f"""
    SELECT ts_utc, high, low
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc > '{entry_ts}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """
    bars = con.execute(query).fetchall()

    if not bars:
        return None

    for ts_utc, h, l in bars:
        h, l = float(h), float(l)

        if break_dir == 'UP':
            if l <= stop and h >= target:
                return -1.0
            if h >= target:
                return float(rr)
            if l <= stop:
                return -1.0
        else:
            if h >= stop and l <= target:
                return -1.0
            if l <= target:
                return float(rr)
            if h >= stop:
                return -1.0

    return None


def test_config(con, dates, orb_name, hour, minute, rr, sl_mode):
    """Test one configuration"""
    results = []

    for d in dates:
        orb = get_orb_from_bars(con, d, hour, minute)
        if not orb:
            continue

        break_dir, entry_ts = detect_break(con, orb, d, hour, minute)
        if not break_dir:
            continue

        r_mult = simulate_trade(con, orb, break_dir, entry_ts, d, rr, sl_mode)
        if r_mult is not None:
            results.append(r_mult)

    if len(results) < 400:  # Need frequency >= 400 trades
        return None

    wins = sum(1 for r in results if r > 0)
    trades = len(results)
    win_rate = wins / trades
    total_r = sum(results)
    avg_r = total_r / trades

    if avg_r <= 0.15:  # Must be meaningfully profitable
        return None

    return TestResult(
        orb=orb_name,
        rr=rr,
        sl_mode=sl_mode,
        trades=trades,
        wins=wins,
        win_rate=win_rate,
        avg_r=avg_r,
        total_r=total_r,
        in_library=False
    )


def check_in_library(con, orb, rr, sl_mode):
    """Check if setup already exists in validated_setups"""
    query = """
    SELECT COUNT(*) FROM validated_setups
    WHERE instrument = 'MGC'
        AND orb_time = ?
        AND rr = ?
        AND sl_mode = ?
    """
    count = con.execute(query, [orb, rr, sl_mode]).fetchone()[0]
    return count > 0


def main():
    print("\n" + "="*80)
    print("SCANNING FOR HIGH-RR SETUPS NOT IN LIBRARY")
    print("="*80)
    print("\nCriteria:")
    print("  - RR >= 3.0 (high reward)")
    print("  - Trades >= 400 (frequent)")
    print("  - Avg R > 0.15 (profitable)")
    print("  - NOT in validated_setups\n")

    con = duckdb.connect(DB_PATH, read_only=True)

    # Get all dates
    dates_query = """
    SELECT DISTINCT date(ts_utc) as date_local
    FROM bars_1m
    WHERE symbol = 'MGC'
        AND ts_utc >= '2024-01-02'::TIMESTAMPTZ
        AND ts_utc <= '2026-01-10'::TIMESTAMPTZ
    ORDER BY date_local
    """
    dates = [row[0] for row in con.execute(dates_query).fetchall()]
    print(f"Testing across {len(dates)} dates...\n")

    # Test configurations
    orb_configs = [
        ("0900", 9, 0),
        ("1000", 10, 0),
        ("1100", 11, 0),
        ("1800", 18, 0),
        ("2300", 23, 0),
        ("0030", 0, 30),
    ]

    rr_values = [3.0, 4.0, 5.0, 6.0, 8.0, 10.0]  # High RR only
    sl_modes = ["FULL", "HALF"]

    candidates = []

    print("Scanning configurations...")
    for orb_name, hour, minute in orb_configs:
        for rr in rr_values:
            for sl_mode in sl_modes:
                # Check if already in library
                if check_in_library(con, orb_name, rr, sl_mode):
                    continue  # Skip - already validated

                result = test_config(con, dates, orb_name, hour, minute, rr, sl_mode)
                if result:
                    candidates.append(result)
                    print(f"  Found: {orb_name} RR={rr:.1f} {sl_mode} -> {result.trades} trades, {result.avg_r:+.3f} avg R")

    con.close()

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80 + "\n")

    if not candidates:
        print("No new high-RR setups found meeting criteria.")
        print("All good setups already in library!\n")
        return

    # Sort by avg_r
    candidates.sort(key=lambda x: x.avg_r, reverse=True)

    print(f"Found {len(candidates)} new high-RR setups:\n")
    print(f"{'Rank':<5} {'ORB':<6} {'RR':<5} {'SL':<6} {'Trades':<8} {'WR%':<7} {'Avg R':<9} {'Total R':<9}")
    print("-"*80)

    for i, c in enumerate(candidates[:15], 1):
        print(f"{i:<5} {c.orb:<6} {c.rr:<5.1f} {c.sl_mode:<6} {c.trades:<8} {c.win_rate*100:<7.1f} {c.avg_r:<+9.3f} {c.total_r:<+9.1f}")

    print("\n" + "="*80)
    print("BEST NEW HIGH-RR SETUP:")
    print("="*80)
    best = candidates[0]
    print(f"\n  ORB: {best.orb}")
    print(f"  RR: {best.rr}")
    print(f"  SL Mode: {best.sl_mode}")
    print(f"  Trades: {best.trades} ({best.trades/740*100:.1f}% of days)")
    print(f"  Win Rate: {best.win_rate*100:.1f}%")
    print(f"  Avg R: {best.avg_r:+.3f}")
    print(f"  Total: {best.total_r:+.0f}R over 2 years")
    print(f"  Annual: ~{best.total_r/2:+.0f}R/year")
    print("\n" + "="*80)
    print("NEXT STEP:")
    print("="*80)
    print(f"\nCreate proof script:")
    print(f"  python PROOF_{best.orb}_ORB.py")
    print(f"\nOr create new proof for RR={best.rr}, {best.sl_mode} specifically")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
