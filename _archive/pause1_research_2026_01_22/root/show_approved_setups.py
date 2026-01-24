"""
SHOW APPROVED SETUPS
====================

Simple view of validated_setups table - your "library" before publishing to app.
"""

import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "gold.db"

def show_setups():
    """Show all validated setups in clean format"""

    con = duckdb.connect(str(DB_PATH), read_only=True)

    rows = con.execute("""
        SELECT instrument, orb_time, rr, sl_mode, orb_size_filter,
               trades, win_rate, avg_r, tier, notes
        FROM validated_setups
        ORDER BY instrument, orb_time, rr
    """).fetchall()

    con.close()

    print("\n" + "="*120)
    print("VALIDATED SETUPS - YOUR APPROVED LIBRARY (Before Publishing to App)")
    print("="*120)

    current_inst = None

    for row in rows:
        inst, orb, rr, sl, filt, trades, wr, avg_r, tier, notes = row

        if inst != current_inst:
            current_inst = inst
            print(f"\n[{inst}] Setups:")
            print("-"*120)

        # Format filter
        filt_str = f"Filter={filt:.3f}" if filt else "No filter"

        # Clean notes (remove emojis - keep only ASCII)
        notes_clean = ''.join(c for c in notes if ord(c) < 128)[:60]

        print(f"  {orb:12} RR={rr:<4.1f} {sl:8} {filt_str:15} | "
              f"{trades:3} trades, {wr:5.1f}% WR, {avg_r:+.3f} R  [{tier:2}]  {notes_clean}")

    print("\n" + "="*120)
    print("WORKFLOW:")
    print("="*120)
    print("1. Research     -> Run PROOF_1800_ORB.py (validate with canonical data)")
    print("2. Approve      -> Update this table (validated_setups)")
    print("3. Auto-Config  -> config_generator.py loads from DB automatically")
    print("4. Verify       -> python test_app_sync.py (ensures sync)")
    print("5. Publish      -> Apps use config.py (live trading)")
    print("="*120 + "\n")

    print("To update 1800 ORB with new proof data:")
    print("  1. Review PROOF_1800_ORB.py output")
    print("  2. Run: python tools/update_validated_setup.py MGC 1800 1.5 FULL")
    print("  3. Run: python test_app_sync.py")
    print("  4. If tests pass -> Ready for live!\n")


if __name__ == "__main__":
    show_setups()
