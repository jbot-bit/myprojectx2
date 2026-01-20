#!/usr/bin/env python3
"""
Diagnose the isolation exit bug - find trades that exit outside window.
"""

import duckdb
import pandas as pd
from pathlib import Path
from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from asia_backtest_core import compute_orb_levels, simulate_orb_breakout

TZ_LOCAL = ZoneInfo("Australia/Brisbane")
TZ_UTC = ZoneInfo("UTC")

# Database
root = Path(__file__).parent.parent.parent
db_path = root / "data" / "db" / "gold.db"
conn = duckdb.connect(str(db_path), read_only=True)

# Get some trading days
query = """
    SELECT DISTINCT date_local
    FROM daily_features_v2
    WHERE instrument = 'MGC'
    AND date_local >= '2025-09-13'
    ORDER BY date_local
    LIMIT 30
"""
trading_days = [row[0] for row in conn.execute(query).fetchall()]

print("Diagnosing 0900 ORB isolation exits...")
print("="*80)

orb_configs = {
    "0900": {"hour": 9, "min": 0, "scan_end_hour": 11, "scan_end_min": 0},
}

bad_exits = []

for trading_date in trading_days:
    config = orb_configs["0900"]

    # Compute ORB
    orb = compute_orb_levels(conn, trading_date, config["hour"], config["min"])
    if orb is None:
        continue

    # Simulate trade
    try:
        trade = simulate_orb_breakout(
            conn,
            trading_date,
            orb,
            config["hour"],
            config["min"],
            config["scan_end_hour"],
            config["scan_end_min"],
            1.5,
            "HALF",
            "ISOLATION"
        )
    except AssertionError as e:
        print(f"\nAssertion failed for {trading_date}: {e}")

        # Calculate scan_end manually to debug
        scan_end_local = datetime.combine(trading_date, dt_time(11, 0)).replace(tzinfo=TZ_LOCAL)
        scan_end_utc = scan_end_local.astimezone(TZ_UTC)

        print(f"  scan_end_local: {scan_end_local}")
        print(f"  scan_end_utc: {scan_end_utc}")

        # Get the bars near the end
        query_debug = """
            SELECT ts_utc
            FROM bars_1m
            WHERE symbol = 'MGC'
            AND ts_utc >= ? - INTERVAL '10 minutes'
            AND ts_utc <= ? + INTERVAL '10 minutes'
            ORDER BY ts_utc
        """
        debug_bars = conn.execute(query_debug, [scan_end_utc, scan_end_utc]).fetchdf()
        print(f"  Bars near scan_end:")
        for idx, row in debug_bars.iterrows():
            bar_ts = pd.to_datetime(row['ts_utc'], utc=True)
            print(f"    {bar_ts} (utc) = {bar_ts.astimezone(TZ_LOCAL)} (local)")

        bad_exits.append({
            'date': trading_date,
            'scan_end_utc': scan_end_utc,
            'error': str(e)
        })

        continue

    if trade and trade.exit_reason == 'FORCE_EXIT' and trade.exit_ts:
        # Check if exit is outside window
        scan_end_local = datetime.combine(trading_date, dt_time(11, 0)).replace(tzinfo=TZ_LOCAL)
        scan_end_utc = scan_end_local.astimezone(TZ_UTC)

        if trade.exit_ts > scan_end_utc:
            print(f"\nFOUND BAD EXIT: {trading_date}")
            print(f"  Exit ts: {trade.exit_ts} (utc) = {trade.exit_ts.astimezone(TZ_LOCAL)} (local)")
            print(f"  Scan end: {scan_end_utc} (utc) = {scan_end_local} (local)")
            print(f"  Difference: {(trade.exit_ts - scan_end_utc).total_seconds()} seconds")

            bad_exits.append({
                'date': trading_date,
                'exit_ts': trade.exit_ts,
                'scan_end_utc': scan_end_utc,
                'diff_seconds': (trade.exit_ts - scan_end_utc).total_seconds()
            })

print("\n" + "="*80)
print(f"Total bad exits found: {len(bad_exits)}")

if bad_exits:
    print("\nSummary:")
    for be in bad_exits[:5]:
        print(f"  {be}")

conn.close()
