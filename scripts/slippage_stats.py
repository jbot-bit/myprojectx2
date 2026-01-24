"""
Analyze slippage statistics from logged fills.

Usage:
  python slippage_stats.py                  # All fills
  python slippage_stats.py --instrument MGC # Filter by instrument
  python slippage_stats.py --setup_id XXX   # Filter by setup
  python slippage_stats.py --days 30        # Last 30 days only
"""

import duckdb
import sys
from datetime import datetime, timedelta, timezone

DB_PATH = "data/db/gold.db"
TICK_SIZE = 0.1

def analyze_slippage(instrument=None, setup_id=None, days=None):
    """Analyze slippage statistics."""

    con = duckdb.connect(DB_PATH, read_only=True)

    # Build WHERE clause
    where_clauses = []

    if instrument:
        where_clauses.append(f"instrument = '{instrument}'")

    if setup_id:
        where_clauses.append(f"setup_id = '{setup_id}'")

    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        where_clauses.append(f"timestamp >= '{cutoff.isoformat()}'")

    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Count total fills
    total_fills = con.execute(f"""
        SELECT COUNT(*) FROM slippage_log WHERE {where_clause}
    """).fetchone()[0]

    if total_fills == 0:
        print("[WARN] No fills found matching criteria")
        con.close()
        return

    # Count complete trades (entry + exit)
    complete_trades = con.execute(f"""
        SELECT COUNT(*)
        FROM slippage_log
        WHERE {where_clause}
          AND exit_slippage_ticks IS NOT NULL
    """).fetchone()[0]

    print("=" * 100)
    print("SLIPPAGE ANALYSIS")
    print("=" * 100)
    print()
    print(f"Total fills logged: {total_fills}")
    print(f"Complete trades (entry + exit): {complete_trades}")
    print(f"Entry only (no exit yet): {total_fills - complete_trades}")
    print()

    if instrument:
        print(f"Filter: Instrument = {instrument}")
    if setup_id:
        print(f"Filter: Setup ID = {setup_id}")
    if days:
        print(f"Filter: Last {days} days")

    print()
    print("=" * 100)

    # Entry slippage stats
    entry_stats = con.execute(f"""
        SELECT
            COUNT(*) as count,
            AVG(entry_slippage_ticks) as mean,
            MEDIAN(entry_slippage_ticks) as median,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY entry_slippage_ticks) as p25,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY entry_slippage_ticks) as p75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY entry_slippage_ticks) as p90,
            MIN(entry_slippage_ticks) as min,
            MAX(entry_slippage_ticks) as max
        FROM slippage_log
        WHERE {where_clause}
    """).fetchone()

    print()
    print("ENTRY SLIPPAGE (ticks)")
    print("-" * 100)
    print(f"  Count:  {entry_stats[0]}")
    print(f"  Mean:   {entry_stats[1]:+.2f}")
    print(f"  Median: {entry_stats[2]:+.2f}")
    print(f"  25th %: {entry_stats[3]:+.2f}")
    print(f"  75th %: {entry_stats[4]:+.2f}")
    print(f"  90th %: {entry_stats[5]:+.2f}")
    print(f"  Min:    {entry_stats[6]:+.2f}")
    print(f"  Max:    {entry_stats[7]:+.2f}")

    # Exit slippage stats (if any exits logged)
    if complete_trades > 0:
        exit_stats = con.execute(f"""
            SELECT
                COUNT(*) as count,
                AVG(exit_slippage_ticks) as mean,
                MEDIAN(exit_slippage_ticks) as median,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY exit_slippage_ticks) as p25,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY exit_slippage_ticks) as p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY exit_slippage_ticks) as p90,
                MIN(exit_slippage_ticks) as min,
                MAX(exit_slippage_ticks) as max
            FROM slippage_log
            WHERE {where_clause}
              AND exit_slippage_ticks IS NOT NULL
        """).fetchone()

        print()
        print("EXIT SLIPPAGE (ticks)")
        print("-" * 100)
        print(f"  Count:  {exit_stats[0]}")
        print(f"  Mean:   {exit_stats[1]:+.2f}")
        print(f"  Median: {exit_stats[2]:+.2f}")
        print(f"  25th %: {exit_stats[3]:+.2f}")
        print(f"  75th %: {exit_stats[4]:+.2f}")
        print(f"  90th %: {exit_stats[5]:+.2f}")
        print(f"  Min:    {exit_stats[6]:+.2f}")
        print(f"  Max:    {exit_stats[7]:+.2f}")

        # Round-trip slippage stats
        rt_stats = con.execute(f"""
            SELECT
                COUNT(*) as count,
                AVG(roundtrip_slippage_ticks) as mean,
                MEDIAN(roundtrip_slippage_ticks) as median,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY roundtrip_slippage_ticks) as p25,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY roundtrip_slippage_ticks) as p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY roundtrip_slippage_ticks) as p90,
                MIN(roundtrip_slippage_ticks) as min,
                MAX(roundtrip_slippage_ticks) as max
            FROM slippage_log
            WHERE {where_clause}
              AND roundtrip_slippage_ticks IS NOT NULL
        """).fetchone()

        print()
        print("ROUND-TRIP SLIPPAGE (ticks)")
        print("-" * 100)
        print(f"  Count:  {rt_stats[0]}")
        print(f"  Mean:   {rt_stats[1]:+.2f}")
        print(f"  Median: {rt_stats[2]:+.2f}")
        print(f"  25th %: {rt_stats[3]:+.2f}")
        print(f"  75th %: {rt_stats[4]:+.2f}")
        print(f"  90th %: {rt_stats[5]:+.2f}")
        print(f"  Min:    {rt_stats[6]:+.2f}")
        print(f"  Max:    {rt_stats[7]:+.2f}")

    print()
    print("=" * 100)
    print()
    print("INTERPRETATION:")
    print()

    median_entry = entry_stats[2]
    p90_entry = entry_stats[5]

    if complete_trades > 0:
        median_rt = rt_stats[2]
        p90_rt = rt_stats[5]

        print(f"  Median round-trip: {median_rt:+.2f} ticks (${median_rt * TICK_SIZE:+.2f})")
        print(f"  90th percentile:   {p90_rt:+.2f} ticks (${p90_rt * TICK_SIZE:+.2f})")
        print()

        # Recommendation for transaction costs
        if median_rt < 0.5:
            print("  Status: EXCELLENT - Very low slippage")
            print(f"  Recommended cost assumption: 0.5 ticks (conservative)")
        elif median_rt < 1.0:
            print("  Status: GOOD - Low slippage")
            print(f"  Recommended cost assumption: 1.0 ticks")
        elif median_rt < 1.5:
            print("  Status: ACCEPTABLE - Moderate slippage")
            print(f"  Recommended cost assumption: 1.5 ticks")
        elif median_rt < 2.0:
            print("  Status: MARGINAL - High slippage")
            print(f"  Recommended cost assumption: 2.0 ticks (worst-case)")
        else:
            print("  Status: POOR - Very high slippage")
            print(f"  Action: Review execution quality, consider limit orders")

        print()
        print(f"  For backtesting, use: SLIPPAGE_TICKS = {p90_rt:.1f} (90th percentile, conservative)")

    else:
        print("  (Need complete trades for round-trip statistics)")

    print()

    # Direction breakdown
    print("=" * 100)
    print("BREAKDOWN BY DIRECTION")
    print("=" * 100)
    print()

    direction_stats = con.execute(f"""
        SELECT
            entry_direction,
            COUNT(*) as trades,
            AVG(entry_slippage_ticks) as avg_entry,
            MEDIAN(entry_slippage_ticks) as median_entry,
            AVG(roundtrip_slippage_ticks) as avg_rt,
            MEDIAN(roundtrip_slippage_ticks) as median_rt
        FROM slippage_log
        WHERE {where_clause}
        GROUP BY entry_direction
    """).fetchall()

    if direction_stats:
        print(f"{'Direction':<10} {'Trades':<8} {'Entry Avg':<12} {'Entry Med':<12} {'RT Avg':<12} {'RT Med':<12}")
        print("-" * 100)

        for direction, trades, avg_entry, med_entry, avg_rt, med_rt in direction_stats:
            avg_rt_str = f"{avg_rt:+.2f}" if avg_rt is not None else "N/A"
            med_rt_str = f"{med_rt:+.2f}" if med_rt is not None else "N/A"

            print(f"{direction:<10} {trades:<8} {avg_entry:+11.2f} {med_entry:+11.2f} {avg_rt_str:<12} {med_rt_str:<12}")

    print()

    # Recent fills
    print("=" * 100)
    print("RECENT FILLS (last 10)")
    print("=" * 100)
    print()

    recent = con.execute(f"""
        SELECT
            trade_id,
            timestamp,
            entry_direction,
            entry_slippage_ticks,
            exit_slippage_ticks,
            roundtrip_slippage_ticks,
            setup_id
        FROM slippage_log
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT 10
    """).fetchall()

    if recent:
        print(f"{'Trade ID':<15} {'Time':<20} {'Dir':<6} {'Entry':<8} {'Exit':<8} {'RT':<8} {'Setup':<20}")
        print("-" * 100)

        for trade_id, timestamp, direction, entry_slip, exit_slip, rt_slip, setup in recent:
            time_str = timestamp.strftime("%Y-%m-%d %H:%M")
            exit_str = f"{exit_slip:+.1f}" if exit_slip is not None else "N/A"
            rt_str = f"{rt_slip:+.1f}" if rt_slip is not None else "N/A"
            setup_str = setup if setup else "N/A"

            print(f"{trade_id:<15} {time_str:<20} {direction:<6} {entry_slip:+7.1f} {exit_str:<8} {rt_str:<8} {setup_str:<20}")

    print()

    con.close()

def main():
    instrument = None
    setup_id = None
    days = None

    # Parse args
    for i in range(1, len(sys.argv)):
        if sys.argv[i] == "--instrument" and i + 1 < len(sys.argv):
            instrument = sys.argv[i + 1]
        elif sys.argv[i] == "--setup_id" and i + 1 < len(sys.argv):
            setup_id = sys.argv[i + 1]
        elif sys.argv[i] == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    analyze_slippage(instrument, setup_id, days)

if __name__ == "__main__":
    main()
