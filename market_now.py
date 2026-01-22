#!/usr/bin/env python3
"""
MARKET NOW - Simple Live Market Scanner

What you want: Read the market and show what setups exist or could be coming.
Simple, honest, accurate.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

from datetime import datetime
from trading_app.setup_detector import SetupDetector
from trading_app.cloud_mode import get_database_connection
from trading_app.config import TZ_LOCAL


def main():
    print("=" * 80)
    print("MARKET NOW - MGC Setup Scanner")
    print("=" * 80)
    print()

    # Current context
    now_local = datetime.now(TZ_LOCAL)
    print(f"Time: {now_local.strftime('%Y-%m-%d %H:%M:%S')} Brisbane")
    print(f"Hour: {now_local.hour:02d}:{now_local.minute:02d}")

    # Determine session
    hour = now_local.hour
    if 9 <= hour < 17:
        session = "ASIA (09:00-17:00)"
    elif 18 <= hour < 23:
        session = "LONDON (18:00-23:00)"
    elif hour >= 23 or hour < 2:
        session = "NY FUTURES (23:00-02:00)"
    else:
        session = "PRE-MARKET"

    print(f"Session: {session}")
    print()

    # Get latest price
    conn = get_database_connection()
    bars = conn.execute("""
        SELECT ts_utc, close
        FROM bars_1m
        WHERE symbol = 'MGC'
        ORDER BY ts_utc DESC
        LIMIT 1
    """).fetchdf()

    if len(bars) > 0:
        latest = bars.iloc[0]
        price = latest['close']
        bar_time_utc = latest['ts_utc']
        bar_time_local = bar_time_utc.astimezone(TZ_LOCAL)

        print(f"Latest Price: ${price:.2f}")
        print(f"Latest Bar:   {bar_time_local.strftime('%Y-%m-%d %H:%M')} Brisbane")

        # Check data freshness
        age_hours = (now_local - bar_time_local).total_seconds() / 3600
        if age_hours > 24:
            print(f"[!] WARNING: Data is {age_hours/24:.1f} days old")
            print("    Run backfill to get recent data:")
            print(f"    python backfill_databento_continuous.py 2026-01-22 2026-01-22")
        print()
    else:
        print("[!] No market data - run backfill first")
        print("    python backfill_databento_continuous.py 2026-01-22 2026-01-22")
        return

    # Get all validated setups
    print("-" * 80)
    print("VALIDATED SETUPS (MGC)")
    print("-" * 80)

    detector = SetupDetector()
    setups = detector.get_all_validated_setups(instrument='MGC')

    if not setups:
        print("[!] No validated setups found in database")
        return

    print(f"Total: {len(setups)} validated setups")
    print()

    # Group by ORB time and separate special strategies
    orb_groups = {}
    special_strategies = []

    for setup in setups:
        orb_time = setup['orb_time']

        # Separate CASCADE and SINGLE_LIQ (not traditional ORBs)
        if orb_time in ['CASCADE', 'SINGLE_LIQ']:
            special_strategies.append(setup)
        else:
            if orb_time not in orb_groups:
                orb_groups[orb_time] = []
            orb_groups[orb_time].append(setup)

    # Display ORB setups
    print("ORB SETUPS:")
    print()
    for orb_time in sorted(orb_groups.keys()):
        orb_setups = orb_groups[orb_time]

        print(f"[{orb_time}] {len(orb_setups)} setup(s)")

        for setup in orb_setups:
            tier = setup['tier']
            rr = setup['rr']
            sl_mode = setup['sl_mode']
            win_rate = setup['win_rate']
            avg_r = setup['avg_r']
            annual_trades = setup['annual_trades']

            orb_filter = setup.get('orb_size_filter')
            # Handle None/NaN filters
            if orb_filter is None or (isinstance(orb_filter, float) and orb_filter != orb_filter):
                filter_str = "no filter"
            else:
                filter_str = f"<{orb_filter:.3f}xATR"

            print(f"  RR={rr:.1f} {sl_mode} ({filter_str})")
            print(f"    Tier: {tier} | WR: {win_rate:.1f}% | Avg R: {avg_r:+.3f}R")
            print(f"    Freq: {annual_trades} trades/year")

        print()

    # Display special strategies
    if special_strategies:
        print("SPECIAL STRATEGIES (Liquidity-based):")
        print()
        for setup in special_strategies:
            orb_time = setup['orb_time']
            tier = setup['tier']
            rr = setup['rr']
            sl_mode = setup['sl_mode']
            win_rate = setup['win_rate']
            avg_r = setup['avg_r']
            annual_trades = setup['annual_trades']

            print(f"[{orb_time}]")
            print(f"  RR={rr:.1f} {sl_mode}")
            print(f"    Tier: {tier} | WR: {win_rate:.1f}% | Avg R: {avg_r:+.3f}R")
            print(f"    Freq: {annual_trades} trades/year")
            print()

    # Show what to look for
    print("-" * 80)
    print("WHAT TO WATCH")
    print("-" * 80)
    print()

    current_orb_times = []

    # Check which ORB times are relevant now
    if 9 <= hour < 17:
        if hour == 9 and now_local.minute < 5:
            current_orb_times.append(('0900', 'FORMING NOW', 'Wait for 09:05 close'))
        elif hour == 9 and now_local.minute >= 5:
            current_orb_times.append(('0900', 'ACTIVE', 'Watch for breakout'))
        elif hour == 10 and now_local.minute < 5:
            current_orb_times.append(('1000', 'FORMING NOW', 'Wait for 10:05 close'))
        elif hour == 10 and now_local.minute >= 5:
            current_orb_times.append(('1000', 'ACTIVE', 'Watch for breakout'))
        elif hour == 11 and now_local.minute < 5:
            current_orb_times.append(('1100', 'FORMING NOW', 'Wait for 11:05 close'))
        elif hour == 11 and now_local.minute >= 5:
            current_orb_times.append(('1100', 'ACTIVE', 'Watch for breakout'))

    elif 18 <= hour < 23:
        if hour == 18 and now_local.minute < 5:
            current_orb_times.append(('1800', 'FORMING NOW', 'Wait for 18:05 close'))
        elif hour == 18 and now_local.minute >= 5:
            current_orb_times.append(('1800', 'ACTIVE', 'Watch for breakout'))
        elif hour == 23 and now_local.minute < 5:
            current_orb_times.append(('2300', 'FORMING NOW', 'Wait for 23:05 close'))
        elif hour == 23 and now_local.minute >= 5:
            current_orb_times.append(('2300', 'ACTIVE', 'Watch for breakout'))

    elif hour == 0 and now_local.minute >= 30 and now_local.minute < 35:
        current_orb_times.append(('0030', 'FORMING NOW', 'Wait for 00:35 close'))
    elif hour == 0 and now_local.minute >= 35:
        current_orb_times.append(('0030', 'ACTIVE', 'Watch for breakout'))

    if current_orb_times:
        print("RIGHT NOW:")
        for orb_time, status, action in current_orb_times:
            if orb_time in orb_groups:
                print(f"  [{orb_time}] {status}")
                print(f"          {action}")
                print()
    else:
        print("No ORBs forming right now.")
        print()
        print("UPCOMING:")

        if hour < 9:
            print("  [0900] ORB starts at 09:00")
        elif hour < 10:
            print("  [1000] ORB starts at 10:00")
        elif hour < 11:
            print("  [1100] ORB starts at 11:00")
        elif hour < 18:
            print("  [1800] ORB starts at 18:00")
        elif hour < 23:
            print("  [2300] ORB starts at 23:00")
        else:
            print("  [0030] ORB starts at 00:30")

        print()

    print("-" * 80)
    print()
    print("HOW IT WORKS:")
    print("1. ORB forms during 5-minute window (e.g., 09:00-09:05)")
    print("2. Wait for breakout (close outside ORB range)")
    print("3. Entry on first breakout confirmation")
    print("4. Stop at ORB half or full (depends on setup)")
    print("5. Target at RR multiple (1.5x to 8.0x depending on setup)")
    print()
    print("TRUTH:")
    print("- All setups shown are from validated_setups database")
    print("- Stats are from real backtest results (2020-2026)")
    print("- No lookahead bias - tested with proper methodology")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
