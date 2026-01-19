"""
Compute ATR(20) for NQ and update daily_features_v2_nq
"""

import duckdb
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from typing import Optional

TZ_LOCAL = ZoneInfo("Australia/Brisbane")

def calculate_atr_for_date(con: duckdb.DuckDBPyConnection, trade_date: date) -> Optional[float]:
    """
    Calculate ATR(20) for a given date using previous 20 days of data.
    """
    # Get previous 20 days
    lookback_start = trade_date - timedelta(days=30)  # Extra buffer for weekends

    # Query daily ranges
    result = con.execute("""
        SELECT
            date_local,
            asia_range,
            london_range,
            ny_range
        FROM daily_features_v2_nq
        WHERE date_local >= ? AND date_local < ?
        ORDER BY date_local
    """, [lookback_start, trade_date]).fetchall()

    if len(result) < 20:
        return None

    # Take last 20 days
    last_20 = result[-20:]

    # Calculate ATR: average of (asia + london + ny) ranges
    total_ranges = []
    for row in last_20:
        day_range = 0
        if row[1]: day_range += row[1]  # asia_range
        if row[2]: day_range += row[2]  # london_range
        if row[3]: day_range += row[3]  # ny_range
        total_ranges.append(day_range)

    atr = sum(total_ranges) / len(total_ranges) if total_ranges else None
    return atr


def main():
    con = duckdb.connect("../gold.db")

    # Get all dates that need ATR
    dates = con.execute("""
        SELECT DISTINCT date_local
        FROM daily_features_v2_nq
        ORDER BY date_local
    """).fetchall()

    print(f"Computing ATR for {len(dates)} dates...")

    updated = 0
    for (trade_date,) in dates:
        atr = calculate_atr_for_date(con, trade_date)

        if atr is not None:
            con.execute("""
                UPDATE daily_features_v2_nq
                SET atr_20 = ?
                WHERE date_local = ?
            """, [atr, trade_date])
            updated += 1

            if updated % 50 == 0:
                print(f"  Processed {updated} dates...")

    con.commit()
    print(f"✓ Updated ATR for {updated} dates")

    # Verify
    result = con.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(atr_20) as has_atr,
            AVG(atr_20) as avg_atr,
            MIN(atr_20) as min_atr,
            MAX(atr_20) as max_atr
        FROM daily_features_v2_nq
    """).fetchone()

    print(f"")
    print(f"Verification:")
    print(f"  Total rows: {result[0]}")
    print(f"  Has ATR: {result[1]}")
    print(f"  Avg ATR: {result[2]:.2f}")
    print(f"  Min ATR: {result[3]:.2f}")
    print(f"  Max ATR: {result[4]:.2f}")

    con.close()


if __name__ == "__main__":
    main()
