"""
Log fill slippage.

Usage:
  # Log entry fill
  python log_fill.py entry <trade_id> <direction> <intended> <actual> [--instrument MGC] [--setup_id XXX]

  # Log exit fill
  python log_fill.py exit <trade_id> <intended> <actual>

  # Complete example
  python log_fill.py entry TRADE_001 LONG 2650.5 2650.6 --instrument MGC --setup_id MGC_1800_BOTH_TIER1
  python log_fill.py exit TRADE_001 2653.0 2652.8

Examples:
  Entry LONG @ 2650.5, filled @ 2650.6 (0.1 points higher = 1 tick worse)
  Exit @ 2653.0, filled @ 2652.8 (0.2 points lower = 2 ticks worse)
"""

import duckdb
import sys
from datetime import datetime, timezone

DB_PATH = "data/db/gold.db"
TICK_SIZE = 0.1  # MGC tick size

def log_entry(trade_id: str, direction: str, intended: float, actual: float, instrument: str = "MGC", setup_id: str = None):
    """Log entry fill."""

    # Calculate slippage
    # LONG: worse fill = higher price (positive slippage)
    # SHORT: worse fill = lower price (positive slippage)
    price_diff = actual - intended

    if direction.upper() == "LONG":
        slippage_ticks = price_diff / TICK_SIZE
    elif direction.upper() == "SHORT":
        slippage_ticks = -price_diff / TICK_SIZE  # Negative diff is bad for SHORT
    else:
        print(f"[ERROR] Invalid direction: {direction} (must be LONG or SHORT)")
        return

    con = duckdb.connect(DB_PATH)

    # Check if trade already exists
    existing = con.execute("SELECT trade_id FROM slippage_log WHERE trade_id = ?", [trade_id]).fetchone()

    if existing:
        print(f"[ERROR] Trade ID '{trade_id}' already exists")
        con.close()
        return

    # Insert entry
    con.execute("""
        INSERT INTO slippage_log (
            trade_id, timestamp, instrument, setup_id,
            entry_direction, intended_entry_price, actual_entry_price, entry_slippage_ticks
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        trade_id,
        datetime.now(timezone.utc),
        instrument,
        setup_id,
        direction.upper(),
        intended,
        actual,
        slippage_ticks
    ])

    con.close()

    print(f"[OK] Entry logged: {trade_id}")
    print(f"  Direction: {direction.upper()}")
    print(f"  Intended: {intended:.2f}")
    print(f"  Actual: {actual:.2f}")
    print(f"  Slippage: {slippage_ticks:+.1f} ticks ({slippage_ticks * TICK_SIZE:+.2f} points)")

def log_exit(trade_id: str, intended: float, actual: float):
    """Log exit fill."""

    con = duckdb.connect(DB_PATH)

    # Get entry info
    entry = con.execute("""
        SELECT entry_direction, entry_slippage_ticks
        FROM slippage_log
        WHERE trade_id = ?
    """, [trade_id]).fetchone()

    if not entry:
        print(f"[ERROR] Trade ID '{trade_id}' not found. Log entry first.")
        con.close()
        return

    direction, entry_slip = entry

    # Calculate exit slippage
    # LONG: worse fill = lower price (negative slippage)
    # SHORT: worse fill = higher price (negative slippage)
    price_diff = actual - intended

    if direction == "LONG":
        exit_slippage_ticks = -price_diff / TICK_SIZE  # Negative diff is bad for LONG exit
    else:  # SHORT
        exit_slippage_ticks = price_diff / TICK_SIZE  # Positive diff is bad for SHORT exit

    # Round-trip slippage
    roundtrip_slippage_ticks = entry_slip + exit_slippage_ticks

    # Update exit
    con.execute("""
        UPDATE slippage_log
        SET intended_exit_price = ?,
            actual_exit_price = ?,
            exit_slippage_ticks = ?,
            roundtrip_slippage_ticks = ?
        WHERE trade_id = ?
    """, [intended, actual, exit_slippage_ticks, roundtrip_slippage_ticks, trade_id])

    con.close()

    print(f"[OK] Exit logged: {trade_id}")
    print(f"  Direction: {direction}")
    print(f"  Intended: {intended:.2f}")
    print(f"  Actual: {actual:.2f}")
    print(f"  Exit slippage: {exit_slippage_ticks:+.1f} ticks ({exit_slippage_ticks * TICK_SIZE:+.2f} points)")
    print(f"  Round-trip slippage: {roundtrip_slippage_ticks:+.1f} ticks ({roundtrip_slippage_ticks * TICK_SIZE:+.2f} points)")

def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return

    fill_type = sys.argv[1].lower()

    if fill_type == "entry":
        trade_id = sys.argv[2]
        direction = sys.argv[3]
        intended = float(sys.argv[4])
        actual = float(sys.argv[5])

        instrument = "MGC"
        setup_id = None

        # Parse optional args
        for i in range(6, len(sys.argv)):
            if sys.argv[i] == "--instrument" and i + 1 < len(sys.argv):
                instrument = sys.argv[i + 1]
            elif sys.argv[i] == "--setup_id" and i + 1 < len(sys.argv):
                setup_id = sys.argv[i + 1]

        log_entry(trade_id, direction, intended, actual, instrument, setup_id)

    elif fill_type == "exit":
        trade_id = sys.argv[2]
        intended = float(sys.argv[3])
        actual = float(sys.argv[4])

        log_exit(trade_id, intended, actual)

    else:
        print(f"[ERROR] Unknown fill type: {fill_type}")
        print(__doc__)

if __name__ == "__main__":
    main()
