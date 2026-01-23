"""
MANAGE VALIDATED SETUPS
========================

View, add, update, or remove setups from the validated_setups table.

This is your "library of approved setups" before they go live in the app.

Usage:
    python manage_setups.py list              # View all setups
    python manage_setups.py show MGC          # View MGC setups only
    python manage_setups.py update MGC 1800   # Update 1800 ORB with new proof data
"""

import duckdb
import sys
from pathlib import Path
from datetime import date
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "gold.db"


def list_all_setups():
    """Show all validated setups"""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    con = duckdb.connect(str(DB_PATH), read_only=True)

    query = """
    SELECT
        instrument,
        orb_time,
        rr,
        sl_mode,
        orb_size_filter,
        trades,
        win_rate,
        avg_r,
        tier,
        notes
    FROM validated_setups
    ORDER BY instrument, orb_time, rr
    """

    try:
        df = pd.DataFrame(con.execute(query).fetchall(),
                         columns=['Inst', 'ORB', 'RR', 'SL', 'Filter', 'Trades', 'WR', 'Avg R', 'Tier', 'Notes'])

        print("\n" + "="*120)
        print("VALIDATED SETUPS - YOUR APPROVED LIBRARY")
        print("="*120 + "\n")

        if len(df) == 0:
            print("No setups found in database.\n")
            con.close()
            return

        # Show by instrument
        for inst in df['Inst'].unique():
            inst_df = df[df['Inst'] == inst]
            print(f"\n{inst} SETUPS ({len(inst_df)} total):")
            print("-"*120)
            print(f"{'ORB':<6} {'RR':<6} {'SL':<6} {'Filter':<10} {'Trades':<8} {'WR%':<7} {'Avg R':<9} {'Tier':<6} {'Notes':<50}")
            print("-"*120)

            for _, row in inst_df.iterrows():
                filter_str = f"{row['Filter']:.3f}" if row['Filter'] else "None"
                wr_pct = f"{row['WR']*100:.1f}" if row['WR'] else "?"
                avg_r_str = f"{row['Avg R']:+.3f}" if row['Avg R'] else "?"
                notes_short = row['Notes'][:47] + "..." if len(row['Notes']) > 50 else row['Notes']

                print(f"{row['ORB']:<6} {row['RR']:<6.1f} {row['SL']:<6} {filter_str:<10} {row['Trades']:<8} "
                      f"{wr_pct:<7} {avg_r_str:<9} {row['Tier']:<6} {notes_short:<50}")

        print("\n" + "="*120 + "\n")

    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        con.close()


def show_instrument(instrument):
    """Show setups for specific instrument"""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    con = duckdb.connect(str(DB_PATH), read_only=True)

    query = f"""
    SELECT
        orb_time,
        rr,
        sl_mode,
        close_confirmations,
        buffer_ticks,
        orb_size_filter,
        trades,
        win_rate,
        avg_r,
        annual_trades,
        tier,
        notes,
        validated_date
    FROM validated_setups
    WHERE instrument = '{instrument}'
    ORDER BY orb_time, rr
    """

    try:
        rows = con.execute(query).fetchall()

        if not rows:
            print(f"\nNo setups found for {instrument}\n")
            con.close()
            return

        print(f"\n{'='*120}")
        print(f"{instrument} VALIDATED SETUPS")
        print("="*120 + "\n")

        for row in rows:
            orb, rr, sl_mode, confirm, buffer, orb_filter, trades, wr, avg_r, annual, tier, notes, last_val = row

            print(f"[{tier}] {orb} ORB - RR={rr:.1f} ({sl_mode} SL)")
            print(f"    Performance: {trades} trades, {wr*100:.1f}% WR, {avg_r:+.3f} avg R (~{int(avg_r*annual):+}R/year)")
            if orb_filter:
                print(f"    Filter: ORB size <= {orb_filter:.3f} x ATR")
            print(f"    Entry: {confirm}m close outside, {buffer} tick buffer")
            print(f"    Notes: {notes}")
            print(f"    Last validated: {last_val}")
            print()

        print("="*120 + "\n")

    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        con.close()


def update_from_proof(instrument, orb):
    """Update setup using latest proof data"""

    # Check if proof file exists
    proof_file = Path(__file__).parent.parent / f"PROOF_{orb}_ORB.py"
    if not proof_file.exists():
        print(f"\nERROR: Proof file not found: {proof_file}")
        print(f"Run: python PROOF_{orb}_ORB.py first to generate proof data\n")
        return

    print(f"\nTo update {instrument} {orb} ORB setup:")
    print(f"1. Review PROOF_{orb}_ORB.py output")
    print(f"2. Choose best RR value")
    print(f"3. Run: python update_validated_setup.py {instrument} {orb} <RR> <SL_MODE>")
    print(f"\nExample: python update_validated_setup.py {instrument} {orb} 1.5 FULL\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "list":
        list_all_setups()

    elif command == "show":
        if len(sys.argv) < 3:
            print("ERROR: Specify instrument (MGC, NQ, or MPL)")
            sys.exit(1)
        show_instrument(sys.argv[2])

    elif command == "update":
        if len(sys.argv) < 4:
            print("ERROR: Specify instrument and ORB (e.g., MGC 1800)")
            sys.exit(1)
        update_from_proof(sys.argv[2], sys.argv[3])

    else:
        print(f"ERROR: Unknown command '{command}'")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
