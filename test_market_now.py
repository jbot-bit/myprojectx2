#!/usr/bin/env python3
"""
MARKET NOW - Simple Market State & Setup Scanner

Shows:
1. Current market context (time, session, price)
2. ORBs detected (formed, broken, active)
3. Setups READY NOW (entry signals)
4. Setups POTENTIAL (what could trigger)

Truth-focused: Only shows what's backed by database and real data.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

from datetime import datetime
from trading_app.setup_detector import SetupDetector
from trading_app.strategy_engine import StrategyEngine, ActionType
from trading_app.cloud_mode import get_database_connection
from trading_app.config import TZ_LOCAL
import pandas as pd


def get_latest_bars(instrument='MGC', lookback_hours=2):
    """Get recent bars from database."""
    conn = get_database_connection()

    query = """
    SELECT ts_utc, open, high, low, close, volume
    FROM bars_1m
    WHERE symbol = ?
    ORDER BY ts_utc DESC
    LIMIT ?
    """

    bars = conn.execute(query, [instrument, lookback_hours * 60]).fetchdf()

    if len(bars) == 0:
        return None

    # Reverse to chronological order
    bars = bars.iloc[::-1].reset_index(drop=True)
    bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)

    return bars


def main():
    print("=" * 80)
    print("MARKET NOW - Current State & Setups")
    print("=" * 80)
    print()

    # 1. Current time context
    now_local = datetime.now(TZ_LOCAL)
    print(f"[TIME] {now_local.strftime('%Y-%m-%d %H:%M:%S')} (Brisbane)")
    print(f"[HOUR] {now_local.hour:02d}:{now_local.minute:02d}")
    print()

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

    print(f"[SESSION] {session}")
    print()

    # 2. Get latest market data
    print("Loading latest market data...")
    bars = get_latest_bars('MGC', lookback_hours=2)

    if bars is None or len(bars) == 0:
        print(" No market data available")
        print()
        print("ACTIONS:")
        print("- Run backfill to get recent data:")
        print("  python backfill_databento_continuous.py 2026-01-22 2026-01-22")
        return

    latest_bar = bars.iloc[-1]
    current_price = latest_bar['close']
    latest_time_local = latest_bar['ts_utc'].astimezone(TZ_LOCAL)

    print(f" Current Price: ${current_price:.2f}")
    print(f" Latest Bar: {latest_time_local.strftime('%H:%M:%S')}")
    print(f" High: ${latest_bar['high']:.2f}")
    print(f" Low: ${latest_bar['low']:.2f}")
    print()

    # 3. Detect ORBs and setups
    print("-" * 80)
    print("ORB DETECTION")
    print("-" * 80)

    detector = SetupDetector()

    # Convert bars to format detector expects
    bars_dict = {
        'ts_utc': bars['ts_utc'].tolist(),
        'open': bars['open'].tolist(),
        'high': bars['high'].tolist(),
        'low': bars['low'].tolist(),
        'close': bars['close'].tolist(),
    }

    orb_results = detector.detect_all_orbs(bars_dict, now_local)

    if not orb_results:
        print("  No ORBs detected yet (data may be insufficient)")
        print()
    else:
        for orb_time, orb_data in sorted(orb_results.items()):
            state = orb_data.get('state', 'UNKNOWN')

            if state == 'PENDING':
                print(f" {orb_time} ORB: {orb_data.get('note', 'Not reached yet')}")

            elif state == 'FORMING':
                print(f" {orb_time} ORB: FORMING (completes soon)")

            elif state == 'ACTIVE':
                orb_high = orb_data.get('high', 0)
                orb_low = orb_data.get('low', 0)
                orb_size = orb_data.get('size', 0)
                print(f" {orb_time} ORB: ACTIVE")
                print(f"   Range: ${orb_low:.2f} - ${orb_high:.2f} (size: ${orb_size:.2f})")
                print(f"   Status: Waiting for breakout")

            elif state in ['BROKEN_UP', 'BROKEN_DOWN']:
                direction = "UP" if state == 'BROKEN_UP' else "DOWN"
                orb_high = orb_data.get('high', 0)
                orb_low = orb_data.get('low', 0)
                break_price = orb_data.get('break_price', 0)
                break_time = orb_data.get('break_time')

                if break_time:
                    break_time_local = break_time.astimezone(TZ_LOCAL)
                    break_time_str = break_time_local.strftime('%H:%M')
                else:
                    break_time_str = "unknown"

                print(f" {orb_time} ORB: BROKEN {direction}")
                print(f"   Range: ${orb_low:.2f} - ${orb_high:.2f}")
                print(f"   Break: ${break_price:.2f} at {break_time_str}")
                print(f"   Status: LOCKED (immutable)")

            else:
                print(f" {orb_time} ORB: {state}")

            print()

    # 4. Check for active setups
    print("-" * 80)
    print("SETUP ANALYSIS")
    print("-" * 80)

    engine = StrategyEngine()

    # Evaluate current state for each validated ORB time
    validated_orbs = ['0900', '1000', '1100', '1800', '2300', '0030']

    active_setups = []
    potential_setups = []

    for orb_time in validated_orbs:
        if orb_time not in orb_results:
            continue

        orb_data = orb_results[orb_time]
        state = orb_data.get('state')

        # Only check broken ORBs for entries
        if state not in ['BROKEN_UP', 'BROKEN_DOWN']:
            if state == 'ACTIVE':
                potential_setups.append({
                    'orb_time': orb_time,
                    'status': 'Waiting for breakout',
                    'range': f"${orb_data.get('low', 0):.2f} - ${orb_data.get('high', 0):.2f}"
                })
            continue

        # Use strategy engine to evaluate entry
        decision = engine.evaluate(
            instrument='MGC',
            orb_time=orb_time,
            orb_data=orb_data,
            bars=bars_dict,
            current_time_local=now_local
        )

        if decision.action == ActionType.ENTER:
            active_setups.append({
                'orb_time': orb_time,
                'direction': decision.direction,
                'entry': decision.entry_price,
                'stop': decision.stop_price,
                'target': decision.target_price,
                'rr': decision.rr,
                'tier': decision.setup_tier,
                'reason': decision.reasons
            })

    # Display active setups
    if active_setups:
        print(" ACTIVE SETUPS (ENTRY SIGNALS)")
        print()
        for setup in active_setups:
            print(f"  {setup['orb_time']} ORB  {setup['direction']} ({setup['tier']} tier)")
            print(f"    Entry:  ${setup['entry']:.2f}")
            print(f"    Stop:   ${setup['stop']:.2f}")
            print(f"    Target: ${setup['target']:.2f}")
            print(f"    RR:     {setup['rr']:.1f}R")
            print(f"    Reason: {', '.join(setup['reason'])}")
            print()
    else:
        print("  NO ACTIVE SETUPS")
        print("   No entry signals at current time")
        print()

    # Display potential setups
    if potential_setups:
        print(" POTENTIAL SETUPS (COULD TRIGGER)")
        print()
        for setup in potential_setups:
            print(f"  {setup['orb_time']} ORB: {setup['status']}")
            print(f"    Range: {setup['range']}")
            print(f"     Entry on breakout above/below range")
            print()

    if not active_setups and not potential_setups:
        print(" No setups available")
        print()

    print("-" * 80)
    print()
    print("TRUTHFUL NOTES:")
    print("- Only shows setups backed by validated_setups database")
    print("- Entry signals from strategy_engine (zero-lookahead)")
    print("- ORB states are immutable once broken (temporal consistency)")
    print("- Data freshness: last bar timestamp shown above")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f" Error: {e}")
        import traceback
        traceback.print_exc()
