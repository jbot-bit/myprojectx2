"""
PROOF: 1000 ORB RR=6.0 FROM CANONICAL DATA
===========================================

Validate the highest RR setup NOT in library:
- ORB: 10:00-10:05 (Brisbane time)
- Entry: First 1m close outside ORB
- SL: FULL (opposite ORB edge)
- Target: 6.0R
- Exit: Scan until next Asia open (09:00)

Compare with RR=5.0 and RR=8.0 (8.0 is already in library).
"""

import duckdb
from datetime import date, timedelta, datetime, time
from dataclasses import dataclass

SYMBOL = "MGC"

@dataclass
class TradeResult:
    outcome: str
    r_multiple: float
    break_dir: str


def get_orb_from_bars_1m(con, date_local):
    """Calculate 10:00-10:05 ORB from bars_1m"""
    start_ts = f"{date_local} 10:00:00"
    end_ts = f"{date_local} 10:05:00"

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


def detect_break_and_entry(con, orb, date_local):
    """Detect first 1m close outside ORB after 10:05"""
    entry_start = f"{date_local} 10:05:00"
    scan_end = f"{date_local + timedelta(days=1)} 09:00:00"

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

    for ts, close in rows:
        close_price = float(close)
        if close_price > orb['high']:
            return 'UP', str(ts), close_price
        elif close_price < orb['low']:
            return 'DOWN', str(ts), close_price

    return None, None, None


def simulate_trade(con, orb, break_dir, entry_ts, date_local, rr):
    """Simulate trade outcome with FULL SL"""

    orb_edge = orb['high'] if break_dir == 'UP' else orb['low']
    stop = orb['low'] if break_dir == 'UP' else orb['high']  # FULL SL

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
        return TradeResult('EXPIRED', 0.0, break_dir)

    for ts_utc, h, l in bars:
        h, l = float(h), float(l)

        if break_dir == 'UP':
            if l <= stop and h >= target:
                return TradeResult('LOSS', -1.0, break_dir)
            if h >= target:
                return TradeResult('WIN', float(rr), break_dir)
            if l <= stop:
                return TradeResult('LOSS', -1.0, break_dir)
        else:
            if h >= stop and l <= target:
                return TradeResult('LOSS', -1.0, break_dir)
            if l <= target:
                return TradeResult('WIN', float(rr), break_dir)
            if h >= stop:
                return TradeResult('LOSS', -1.0, break_dir)

    return TradeResult('EXPIRED', 0.0, break_dir)


def test_rr(con, dates, rr):
    """Test single RR value"""
    results = []

    for d in dates:
        orb = get_orb_from_bars_1m(con, d)
        if not orb:
            continue

        break_dir, entry_ts, entry_price = detect_break_and_entry(con, orb, d)
        if not break_dir:
            continue

        result = simulate_trade(con, orb, break_dir, entry_ts, d, rr)
        if result:
            results.append(result)

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
    print("PROOF: 1000 ORB RR=6.0 FROM CANONICAL DATA (bars_1m only)")
    print("="*80)
    print("\nValidating highest RR setup NOT in library.")
    print("Comparing RR=5.0, 6.0, 8.0 (8.0 already in library)\n")

    con = duckdb.connect("data/db/gold.db", read_only=True)

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

    rr_values = [5.0, 6.0, 8.0]

    print("Testing RR values: 5.0, 6.0, 8.0")
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

    print(f"\n{'RR':<6} {'Trades':<8} {'Wins':<7} {'Losses':<8} {'Expired':<9} {'WR%':<8} {'Avg R':<10} {'Total R':<10} {'Ann R':<10}")
    print("-"*100)

    for r in results:
        annual_r = r['total_r'] / 2.0
        print(f"{r['rr']:<6.1f} {r['trades']:<8} {r['wins']:<7} {r['losses']:<8} {r['expired']:<9} "
              f"{r['win_rate']*100:<8.1f} {r['avg_r']:<+10.3f} {r['total_r']:<+10.1f} {annual_r:<+10.0f}")

    print("\n" + "="*80)
    avg_rs = [r['avg_r'] for r in results]
    if len(set(avg_rs)) > 1:
        print("PROOF OK - Results differ across RR values (as expected)")
    else:
        print("WARNING - Results identical (check logic)")

    best = max(results, key=lambda x: x['avg_r'])
    print(f"\nBest RR: {best['rr']:.1f} with Avg R = {best['avg_r']:+.3f}")
    print(f"Annual: ~{best['total_r']/2:+.0f}R/year")

    print("\n" + "="*80)
    print("RECOMMENDATION:")
    print("="*80)

    rr6 = next(r for r in results if r['rr'] == 6.0)
    rr8_in_lib = next(r for r in results if r['rr'] == 8.0)

    print(f"\nRR=6.0: {rr6['trades']} trades, {rr6['win_rate']*100:.1f}% WR, {rr6['avg_r']:+.3f} avg R")
    print(f"RR=8.0: {rr8_in_lib['trades']} trades, {rr8_in_lib['win_rate']*100:.1f}% WR, {rr8_in_lib['avg_r']:+.3f} avg R (in library)")

    if rr6['avg_r'] > rr8_in_lib['avg_r']:
        print(f"\n*** RR=6.0 IS BETTER than RR=8.0! ***")
        print(f"Consider replacing RR=8.0 in library with RR=6.0")
    else:
        print(f"\nRR=8.0 (already in library) is better. Keep it.")

    print("="*80 + "\n")


if __name__ == "__main__":
    main()
