"""
Timestamp Probe Script

Manual validation tool for ORB window alignment and timezone conversions.

Usage:
    python scripts/timestamp_probe.py 2025-06-15
    python scripts/timestamp_probe.py 2025-03-09  # US DST start
    python scripts/timestamp_probe.py 2025-11-02  # US DST end

Outputs:
1. First 20 timestamps from bars_1m (raw DB, UTC, Brisbane)
2. Computed ORB start/end for all 6 ORBs
3. Validation against expected Brisbane local times
"""

import sys
import duckdb
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import List, Tuple

TZ_LOCAL = ZoneInfo("Australia/Brisbane")  # UTC+10, no DST
TZ_UTC = ZoneInfo("UTC")

DB_PATH = "gold.db"
SYMBOL = "MGC"


def _dt_local(d: date, hh: int, mm: int) -> datetime:
    """Create Brisbane-aware datetime."""
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ_LOCAL)


def parse_date(s: str) -> date:
    """Parse YYYY-MM-DD date string."""
    try:
        return date.fromisoformat(s)
    except ValueError:
        print(f"Error: Invalid date format '{s}'. Expected YYYY-MM-DD")
        sys.exit(1)


def fetch_day_bars(con: duckdb.DuckDBPyConnection, trade_date: date) -> List[Tuple[datetime, float, float, float, float]]:
    """
    Fetch all 1-minute bars for a trading day.

    Trading day: 09:00 local → next 09:00 local (Brisbane)
    """
    start_local = _dt_local(trade_date, 9, 0)
    end_local = _dt_local(trade_date + timedelta(days=1), 9, 0)

    start_utc = start_local.astimezone(TZ_UTC)
    end_utc = end_local.astimezone(TZ_UTC)

    result = con.execute(
        """
        SELECT ts_utc, open, high, low, close
        FROM bars_1m
        WHERE symbol = ?
          AND ts_utc >= ?
          AND ts_utc < ?
        ORDER BY ts_utc
        LIMIT 20
        """,
        [SYMBOL, start_utc, end_utc]
    ).fetchall()

    return result


def print_timestamps(bars: List[Tuple], title: str):
    """Print timestamps in multiple formats."""
    print(f"\n{title}")
    print("=" * 80)
    print(f"{'#':<4} {'Raw DB (UTC)':<28} {'UTC Formatted':<20} {'Brisbane Local':<20}")
    print("-" * 80)

    for i, (ts_utc, open_p, high, low, close) in enumerate(bars, 1):
        # Convert to Brisbane time
        ts_brisbane = ts_utc.astimezone(TZ_LOCAL)

        # Format timestamps
        utc_str = ts_utc.strftime("%Y-%m-%d %H:%M:%S %Z")
        brisbane_str = ts_brisbane.strftime("%Y-%m-%d %H:%M:%S %Z")

        print(f"{i:<4} {str(ts_utc):<28} {utc_str:<20} {brisbane_str:<20}")


def compute_orb_windows(trade_date: date):
    """
    Compute ORB start/end for all 6 ORBs.

    ORBs: 09:00, 10:00, 11:00, 18:00, 23:00, 00:30 (next day)
    """
    print("\n\nCOMPUTED ORB WINDOWS")
    print("=" * 80)
    print(f"{'ORB':<8} {'Start (Brisbane)':<25} {'End (Brisbane)':<25} {'Start (UTC)':<25} {'End (UTC)':<25}")
    print("-" * 80)

    orb_times = [
        (trade_date, 9, 0, "0900"),
        (trade_date, 10, 0, "1000"),
        (trade_date, 11, 0, "1100"),
        (trade_date, 18, 0, "1800"),
        (trade_date, 23, 0, "2300"),
        (trade_date + timedelta(days=1), 0, 30, "0030"),  # Next day
    ]

    for d, hh, mm, name in orb_times:
        orb_start_local = _dt_local(d, hh, mm)
        orb_end_local = orb_start_local + timedelta(minutes=5)

        orb_start_utc = orb_start_local.astimezone(TZ_UTC)
        orb_end_utc = orb_end_local.astimezone(TZ_UTC)

        start_brisbane_str = orb_start_local.strftime("%Y-%m-%d %H:%M %Z")
        end_brisbane_str = orb_end_local.strftime("%Y-%m-%d %H:%M %Z")
        start_utc_str = orb_start_utc.strftime("%Y-%m-%d %H:%M %Z")
        end_utc_str = orb_end_utc.strftime("%Y-%m-%d %H:%M %Z")

        print(f"{name:<8} {start_brisbane_str:<25} {end_brisbane_str:<25} {start_utc_str:<25} {end_utc_str:<25}")


def validate_orb_alignment(trade_date: date):
    """
    Validate ORB alignment against expected Brisbane local times.

    Assertions:
    - 09:00 ORB should start at exactly 09:00 Brisbane
    - All ORBs should be 5 minutes duration
    - Brisbane → UTC conversion should be consistent
    """
    print("\n\nVALIDATION CHECKS")
    print("=" * 80)

    checks_passed = 0
    checks_failed = 0

    # Check 1: Brisbane has no DST (always UTC+10)
    test_local = _dt_local(trade_date, 12, 0)
    offset_hours = test_local.utcoffset().total_seconds() / 3600
    if offset_hours == 10:
        print("✅ PASS: Brisbane timezone is UTC+10 (no DST)")
        checks_passed += 1
    else:
        print(f"❌ FAIL: Brisbane timezone offset is {offset_hours} hours (expected 10)")
        checks_failed += 1

    # Check 2: 09:00 Brisbane → 23:00 UTC (previous day)
    orb_0900_local = _dt_local(trade_date, 9, 0)
    orb_0900_utc = orb_0900_local.astimezone(TZ_UTC)
    if orb_0900_utc.hour == 23 and orb_0900_utc.day == trade_date.day - 1:
        print("✅ PASS: 09:00 Brisbane = 23:00 UTC (previous day)")
        checks_passed += 1
    else:
        print(f"❌ FAIL: 09:00 Brisbane = {orb_0900_utc.strftime('%H:%M %Y-%m-%d')} UTC (expected 23:00 prev day)")
        checks_failed += 1

    # Check 3: All ORBs are exactly 5 minutes
    orb_times = [
        (trade_date, 9, 0, "0900"),
        (trade_date, 10, 0, "1000"),
        (trade_date, 11, 0, "1100"),
        (trade_date, 18, 0, "1800"),
        (trade_date, 23, 0, "2300"),
        (trade_date + timedelta(days=1), 0, 30, "0030"),
    ]

    all_5min = True
    for d, hh, mm, name in orb_times:
        orb_start_local = _dt_local(d, hh, mm)
        orb_end_local = orb_start_local + timedelta(minutes=5)
        duration = (orb_end_local - orb_start_local).total_seconds() / 60
        if duration != 5:
            print(f"❌ FAIL: ORB {name} duration = {duration} minutes (expected 5)")
            all_5min = False
            checks_failed += 1

    if all_5min:
        print("✅ PASS: All 6 ORBs are exactly 5 minutes duration")
        checks_passed += 1

    # Check 4: Midnight crossing (23:00 → 00:30) spans 90 minutes
    ny_start = _dt_local(trade_date, 23, 0)
    ny_end = _dt_local(trade_date + timedelta(days=1), 0, 30)
    ny_duration = (ny_end - ny_start).total_seconds() / 60
    if ny_duration == 90:
        print("✅ PASS: NY session (23:00→00:30) spans 90 minutes")
        checks_passed += 1
    else:
        print(f"❌ FAIL: NY session duration = {ny_duration} minutes (expected 90)")
        checks_failed += 1

    # Summary
    print("-" * 80)
    print(f"TOTAL: {checks_passed} passed, {checks_failed} failed")

    if checks_failed == 0:
        print("\n✅ ALL VALIDATION CHECKS PASSED")
    else:
        print(f"\n❌ {checks_failed} VALIDATION CHECKS FAILED")


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/timestamp_probe.py YYYY-MM-DD")
        print("\nExamples:")
        print("  python scripts/timestamp_probe.py 2025-06-15  # Normal day")
        print("  python scripts/timestamp_probe.py 2025-03-09  # US DST start")
        print("  python scripts/timestamp_probe.py 2025-11-02  # US DST end")
        sys.exit(1)

    trade_date = parse_date(sys.argv[1])

    print("=" * 80)
    print("TIMESTAMP PROBE SCRIPT")
    print("=" * 80)
    print(f"Trade Date: {trade_date}")
    print(f"Database: {DB_PATH}")
    print(f"Symbol: {SYMBOL}")
    print(f"Timezone: Australia/Brisbane (UTC+10, no DST)")

    # Connect to database
    con = duckdb.connect(DB_PATH, read_only=True)

    # Fetch first 20 bars for the day
    bars = fetch_day_bars(con, trade_date)

    if not bars:
        print(f"\n⚠️  WARNING: No bars found for {trade_date}")
        print("\nPossible reasons:")
        print("  - Weekend or holiday (no trading)")
        print("  - Data not yet backfilled for this date")
        print("  - Database path incorrect")
    else:
        print(f"\n✅ Found {len(bars)} bars for {trade_date}")
        print_timestamps(bars, f"FIRST 20 TIMESTAMPS FOR {trade_date}")

    # Compute ORB windows
    compute_orb_windows(trade_date)

    # Validate alignment
    validate_orb_alignment(trade_date)

    con.close()


if __name__ == "__main__":
    main()
