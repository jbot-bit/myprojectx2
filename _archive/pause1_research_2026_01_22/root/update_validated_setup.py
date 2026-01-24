"""
UPDATE VALIDATED SETUP
======================

Update or add a single setup to validated_setups table.

Usage:
    python update_validated_setup.py MGC 1800 1.5 FULL

This is the CORRECT way to update the "library of approved setups"
before they go live in the app.
"""

import duckdb
import sys
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "gold.db"


def update_setup(instrument, orb, rr, sl_mode, confirm=1, buffer=0.0,
                 orb_size_filter=None, trades=None, win_rate=None, avg_r=None,
                 tier='A', notes=''):
    """
    Update or insert a setup into validated_setups.

    Args:
        instrument: 'MGC', 'NQ', or 'MPL'
        orb: '0900', '1000', '1100', '1800', '2300', '0030'
        rr: float (e.g., 1.5)
        sl_mode: 'FULL', 'HALF', 'QUARTER'
        confirm: int (1 = 1m close, default)
        buffer: float (0.0 = no buffer, default)
        orb_size_filter: None or float (e.g., 0.155 for ATR filter)
        trades: int (total trades in backtest)
        win_rate: float (0.0-1.0)
        avg_r: float (e.g., 0.269)
        tier: 'S+', 'S', 'A', 'B', 'C'
        notes: str (description)
    """

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return False

    con = duckdb.connect(str(DB_PATH))

    # Generate setup_id
    orb_filter_str = f"ORB{orb_size_filter}" if orb_size_filter else "NOFILTER"
    setup_id = f"{instrument}_{orb}_RR{rr}_{sl_mode}_C{confirm}_B{buffer}_{orb_filter_str}"

    # Calculate annual trades (assuming 740 days in dataset = 2 years)
    annual_trades = int(trades * 365 / 740) if trades else None

    # Check if setup exists
    existing = con.execute("""
        SELECT setup_id FROM validated_setups
        WHERE instrument = ? AND orb = ? AND rr = ? AND sl_mode = ?
    """, [instrument, orb, rr, sl_mode]).fetchone()

    if existing:
        print(f"[UPDATE] Found existing setup: {existing[0]}")

        # Update
        con.execute("""
            UPDATE validated_setups SET
                confirm_bars = ?,
                buffer_ticks = ?,
                orb_size_filter = ?,
                total_trades = ?,
                win_rate = ?,
                avg_r_per_trade = ?,
                estimated_annual_trades = ?,
                tier = ?,
                notes = ?,
                last_validated = ?
            WHERE instrument = ? AND orb = ? AND rr = ? AND sl_mode = ?
        """, [
            confirm, buffer, orb_size_filter,
            trades, win_rate, avg_r, annual_trades,
            tier, notes, date.today(),
            instrument, orb, rr, sl_mode
        ])

        print(f"[OK] Updated setup: {setup_id}")
    else:
        print(f"[INSERT] Creating new setup: {setup_id}")

        # Insert
        con.execute("""
            INSERT INTO validated_setups VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL,
                ?, ?, ?, ?, ?, ?, ?, 'daily_features_v2'
            )
        """, [
            setup_id, instrument, orb, rr, sl_mode, confirm, buffer, orb_size_filter,
            trades, win_rate, avg_r, annual_trades, tier, notes, date.today()
        ])

        print(f"[OK] Inserted setup: {setup_id}")

    con.close()

    print(f"\n{'='*80}")
    print("NEXT STEPS:")
    print("="*80)
    print("1. Run: python test_app_sync.py")
    print("2. Verify all tests pass")
    print("3. If tests fail: config.py needs manual update (see CLAUDE.md)")
    print("4. If tests pass: Setup is ready for live trading!")
    print("="*80 + "\n")

    return True


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        print("\nExample:")
        print("  python update_validated_setup.py MGC 1800 1.5 FULL")
        print("\nThis updates the 1800 ORB setup with RR=1.5, FULL SL\n")
        sys.exit(1)

    instrument = sys.argv[1]
    orb = sys.argv[2]
    rr = float(sys.argv[3])
    sl_mode = sys.argv[4]

    print(f"\n{'='*80}")
    print(f"UPDATING VALIDATED SETUP")
    print("="*80)
    print(f"Instrument: {instrument}")
    print(f"ORB: {orb}")
    print(f"RR: {rr}")
    print(f"SL Mode: {sl_mode}")
    print("="*80 + "\n")

    # For now, just update the key fields
    # User can run full backtest to get detailed stats
    update_setup(
        instrument=instrument,
        orb=orb,
        rr=rr,
        sl_mode=sl_mode,
        notes=f"Updated {date.today()} - Run PROOF_{orb}_ORB.py for full stats"
    )


if __name__ == "__main__":
    main()
