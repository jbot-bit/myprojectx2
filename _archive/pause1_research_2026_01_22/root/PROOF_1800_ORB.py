"""
PROOF: 1800 ORB SETUP FROM CANONICAL DATA ONLY
===============================================

Recompute 18:00 ORB performance from bars_1m only.
No precomputed outcome columns.

Brisbane time: 18:00-18:05
Entry: First 1m close outside ORB after 18:05
SL: FULL (opposite ORB edge)
Test RR: 1.0, 1.5, 2.0
Exit: Scan until next Asia open (09:00 Brisbane)
"""

import duckdb
from datetime import date, timedelta, datetime, time
from dataclasses import dataclass

SYMBOL = "MGC"

@dataclass
class TradeResult:
    outcome: str  # WIN, LOSS, EXPIRED
    r_multiple: float
    break_dir: str


def get_orb_from_bars_1m(con, date_local):
    """Calculate 18:00-18:05 ORB from bars_1m (5 minutes)"""
    start_ts = f"{date_local} 18:00:00"
    end_ts = f"{date_local} 18:05:00"

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

    return {'high': orb_high, 'low': orb_low, 'size': orb_high - orb_low}


def detect_break_and_entry(con, orb, date_local):
    """Detect first 1m close outside ORB after 18:05"""
    entry_start = f"{date_local} 18:05:00"
    scan_end = f"{date_local + timedelta(days=1)} 09:00:00"  # Next Asia open

    query = f"""
    SELECT ts_utc, close
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{entry_start}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """
    rows = con.execute(query).fetchall()

    if not rows:
        return None, None, None

    # First close outside ORB
    for ts, close in rows:
        close_price = float(close)
        if close_price > orb['high']:
            return 'UP', str(ts), close_price
        elif close_price < orb['low']:
            return 'DOWN', str(ts), close_price

    return None, None, None


def simulate_trade(con, orb, break_dir, entry_ts, entry_price, date_local, rr):
    """Simulate trade outcome with explicit rules"""

    # Calculate stop and target
    orb_edge = orb['high'] if break_dir == 'UP' else orb['low']
    stop = orb['low'] if break_dir == 'UP' else orb['high']

    r_size = abs(orb_edge - stop)
    if r_size <= 0:
        return None

    target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)

    # Scan bars after entry until next Asia open
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
        # No bars after entry = trade expires
        return TradeResult('EXPIRED', 0.0, break_dir)

    # Simulate bar by bar
    for ts_utc, h, l in bars:
        h, l = float(h), float(l)

        if break_dir == 'UP':
            # Check if stop and target hit in same bar
            if l <= stop and h >= target:
                # Stop hit first (conservative assumption)
                return TradeResult('LOSS', -1.0, break_dir)
            # Check target hit
            if h >= target:
                return TradeResult('WIN', float(rr), break_dir)
            # Check stop hit
            if l <= stop:
                return TradeResult('LOSS', -1.0, break_dir)
        else:  # DOWN
            if h >= stop and l <= target:
                # Stop hit first
                return TradeResult('LOSS', -1.0, break_dir)
            if l <= target:
                return TradeResult('WIN', float(rr), break_dir)
            if h >= stop:
                return TradeResult('LOSS', -1.0, break_dir)

    # Reached scan_end without hitting TP or SL = trade expires
    return TradeResult('EXPIRED', 0.0, break_dir)


def test_rr(con, dates, rr):
    """Test single RR value across all dates"""
    results = []

    for d in dates:
        # Get ORB
        orb = get_orb_from_bars_1m(con, d)
        if not orb:
            continue

        # Detect break and entry
        break_dir, entry_ts, entry_price = detect_break_and_entry(con, orb, d)
        if not break_dir:
            continue

        # Simulate trade
        result = simulate_trade(con, orb, break_dir, entry_ts, entry_price, d, rr)
        if result:
            results.append(result)

    # Calculate stats
    trades = len(results)
    if trades == 0:
        return None

    wins = sum(1 for r in results if r.outcome == 'WIN')
    losses = sum(1 for r in results if r.outcome == 'LOSS')
    expired = sum(1 for r in results if r.outcome == 'EXPIRED')

    win_rate = wins / trades if trades > 0 else 0.0
    total_r = sum(r.r_multiple for r in results)
    avg_r = total_r / trades

    return {
        'rr': rr,
        'trades': trades,
        'wins': wins,
        'losses': losses,
        'expired': expired,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r
    }


def main():
    print("\n" + "="*80)
    print("PROOF: 1800 ORB FROM CANONICAL DATA (bars_1m only)")
    print("="*80)
    print("\nRecomputing from scratch - no precomputed columns used.\n")

    con = duckdb.connect("data/db/gold.db", read_only=True)

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

    print(f"Testing across {len(dates)} calendar dates\n")

    # Test RR values
    rr_values = [1.0, 1.5, 2.0]

    print("Testing RR values: 1.0, 1.5, 2.0")
    print("This will take ~30 seconds...\n")

    results = []
    for rr in rr_values:
        print(f"  Testing RR={rr}...", end=" ", flush=True)
        result = test_rr(con, dates, rr)
        if result:
            results.append(result)
            print(f"Done. {result['trades']} trades found.")
        else:
            print("No trades.")

    con.close()

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)

    if not results:
        print("ERROR: No trades found. Check database.")
        return

    # Print table
    print(f"\n{'RR':<6} {'Trades':<8} {'Wins':<7} {'Losses':<8} {'Expired':<9} {'WR%':<8} {'Avg R':<10} {'Total R':<10}")
    print("-"*80)

    for r in results:
        print(f"{r['rr']:<6.1f} {r['trades']:<8} {r['wins']:<7} {r['losses']:<8} {r['expired']:<9} "
              f"{r['win_rate']*100:<8.1f} {r['avg_r']:<+10.3f} {r['total_r']:<+10.1f}")

    # Check if results differ
    print("\n" + "="*80)
    avg_rs = [r['avg_r'] for r in results]
    if len(set(avg_rs)) > 1:
        print("PROOF OK - Results differ across RR values (as expected)")
    else:
        print("WARNING - Results identical across RR (check logic)")

    # Show best
    best = max(results, key=lambda x: x['avg_r'])
    print(f"\nBest RR: {best['rr']:.1f} with Avg R = {best['avg_r']:+.3f}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
