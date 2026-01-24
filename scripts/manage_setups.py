"""
Setup Management Tool

Commands:
  python manage_setups.py list                    - Show all setups (published + draft)
  python manage_setups.py list --published        - Show only published setups
  python manage_setups.py list --draft            - Show only draft setups
  python manage_setups.py publish <setup_id>      - Publish a draft setup
  python manage_setups.py unpublish <setup_id>    - Unpublish a setup
  python manage_setups.py add-tier1               - Add validated Tier 1 setups as drafts
"""

import duckdb
import sys

DB_PATH = "data/db/gold.db"

def list_setups(filter_type=None):
    """List setups with optional filtering."""
    con = duckdb.connect(DB_PATH, read_only=True)

    where_clause = ""
    if filter_type == "published":
        where_clause = "WHERE published = TRUE"
    elif filter_type == "draft":
        where_clause = "WHERE published = FALSE OR published IS NULL"

    result = con.execute(f"""
        SELECT
            setup_id,
            instrument,
            orb_time,
            rr,
            direction_filter,
            trades,
            win_rate,
            avg_r,
            tier,
            slippage_tier,
            oos_validation_status,
            published
        FROM validated_setups
        {where_clause}
        ORDER BY
            CASE WHEN published THEN 0 ELSE 1 END,
            instrument,
            orb_time,
            rr
    """).fetchall()

    con.close()

    if not result:
        print(f"No setups found ({filter_type or 'all'})")
        return

    print(f"\n{'='*140}")
    print(f"SETUP INVENTORY ({filter_type.upper() if filter_type else 'ALL'})")
    print(f"{'='*140}\n")

    print(f"{'ID':<15} {'Inst':<5} {'ORB':<5} {'RR':<4} {'Dir':<5} {'Trades':<7} {'WR%':<6} {'AvgR':<7} {'Tier':<10} {'Slip':<12} {'OOS':<10} {'Status':<10}")
    print('-'*140)

    for row in result:
        setup_id, inst, orb, rr, direction, trades, wr, avg_r, tier, slip_tier, oos_status, published = row

        direction_str = direction if direction else "BOTH"
        tier_str = tier if tier else "N/A"
        slip_str = slip_tier if slip_tier else "N/A"
        oos_str = oos_status if oos_status else "N/A"
        status_str = "PUBLISHED" if published else "DRAFT"

        print(f"{setup_id:<15} {inst:<5} {orb:<5} {rr:<4.1f} {direction_str:<5} {trades:<7} {wr:<6.1f} {avg_r:<+7.3f} {tier_str:<10} {slip_str:<12} {oos_str:<10} {status_str:<10}")

    print()
    print(f"Total: {len(result)} setups")
    published_count = sum(1 for r in result if r[11])
    draft_count = len(result) - published_count
    print(f"  Published: {published_count}")
    print(f"  Draft: {draft_count}")
    print()

def publish_setup(setup_id):
    """Publish a draft setup."""
    con = duckdb.connect(DB_PATH)

    # Check if setup exists
    exists = con.execute("SELECT setup_id, published FROM validated_setups WHERE setup_id = ?", [setup_id]).fetchone()

    if not exists:
        print(f"[ERROR] Setup '{setup_id}' not found")
        con.close()
        return

    if exists[1]:
        print(f"[WARN] Setup '{setup_id}' is already published")
        con.close()
        return

    # Publish the setup
    con.execute("UPDATE validated_setups SET published = TRUE WHERE setup_id = ?", [setup_id])

    print(f"[OK] Published setup: {setup_id}")

    con.close()

def unpublish_setup(setup_id):
    """Unpublish a setup."""
    con = duckdb.connect(DB_PATH)

    # Check if setup exists
    exists = con.execute("SELECT setup_id, published FROM validated_setups WHERE setup_id = ?", [setup_id]).fetchone()

    if not exists:
        print(f"[ERROR] Setup '{setup_id}' not found")
        con.close()
        return

    if not exists[1]:
        print(f"[WARN] Setup '{setup_id}' is already unpublished")
        con.close()
        return

    # Unpublish the setup
    con.execute("UPDATE validated_setups SET published = FALSE WHERE setup_id = ?", [setup_id])

    print(f"[OK] Unpublished setup: {setup_id}")

    con.close()

def add_tier1_setups():
    """Add validated Tier 1 setups as drafts."""
    con = duckdb.connect(DB_PATH)

    # Tier 1 validated setups from OOS analysis
    tier1_setups = [
        {
            'setup_id': 'MGC_1800_BOTH_TIER1',
            'instrument': 'MGC',
            'orb_time': '1800',
            'rr': 1.0,
            'sl_mode': 'full',
            'close_confirmations': 1,
            'buffer_ticks': 0.0,
            'direction_filter': None,
            'trades': 525,
            'win_rate': 61.9,
            'avg_r': 0.046,
            'annual_trades': 525,
            'tier': 'TIER1',
            'slippage_tier': 'TIER1_ROBUST',
            'oos_validation_status': 'VALIDATED',
            'notes': 'London open, both directions, OOS validated (IS: +0.022R, OOS: +0.115R)',
            'validated_date': '2026-01-24',
            'data_source': 'walk_forward_validation.py',
        },
        {
            'setup_id': 'MGC_1100_UP_TIER1',
            'instrument': 'MGC',
            'orb_time': '1100',
            'rr': 1.0,
            'sl_mode': 'full',
            'close_confirmations': 1,
            'buffer_ticks': 0.0,
            'direction_filter': 'UP',
            'trades': 269,
            'win_rate': 62.1,
            'avg_r': 0.086,
            'annual_trades': 269,
            'tier': 'TIER1',
            'slippage_tier': 'TIER1_ROBUST',
            'oos_validation_status': 'VALIDATED',
            'notes': 'Late Asia session, UP breaks only, OOS validated (IS: +0.080R, OOS: +0.102R)',
            'validated_date': '2026-01-24',
            'data_source': 'walk_forward_validation.py',
        },
        {
            'setup_id': 'MGC_2300_BOTH_TIER1',
            'instrument': 'MGC',
            'orb_time': '2300',
            'rr': 1.0,
            'sl_mode': 'full',
            'close_confirmations': 1,
            'buffer_ticks': 0.0,
            'direction_filter': None,
            'trades': 525,
            'win_rate': 58.1,
            'avg_r': 0.041,
            'annual_trades': 525,
            'tier': 'TIER1',
            'slippage_tier': 'TIER1_ROBUST',
            'oos_validation_status': 'VALIDATED',
            'notes': 'NY open, both directions, OOS validated (IS: -0.010R, OOS: +0.182R)',
            'validated_date': '2026-01-24',
            'data_source': 'walk_forward_validation.py',
        },
        {
            'setup_id': 'MGC_0030_DOWN_TIER1',
            'instrument': 'MGC',
            'orb_time': '0030',
            'rr': 1.0,
            'sl_mode': 'full',
            'close_confirmations': 1,
            'buffer_ticks': 0.0,
            'direction_filter': 'DOWN',
            'trades': 239,
            'win_rate': 59.4,
            'avg_r': 0.085,
            'annual_trades': 239,
            'tier': 'TIER1',
            'slippage_tier': 'TIER1_ROBUST',
            'oos_validation_status': 'VALIDATED',
            'notes': 'Overnight NY, DOWN breaks only, OOS validated (IS: +0.051R, OOS: +0.182R)',
            'validated_date': '2026-01-24',
            'data_source': 'walk_forward_validation.py',
        },
    ]

    added_count = 0

    for setup in tier1_setups:
        # Check if already exists
        existing = con.execute("SELECT setup_id FROM validated_setups WHERE setup_id = ?", [setup['setup_id']]).fetchone()

        if existing:
            print(f"[SKIP] Setup already exists: {setup['setup_id']}")
            continue

        # Insert as draft (published=FALSE)
        con.execute("""
            INSERT INTO validated_setups (
                setup_id, instrument, orb_time, rr, sl_mode, close_confirmations,
                buffer_ticks, direction_filter, trades, win_rate, avg_r, annual_trades,
                tier, slippage_tier, oos_validation_status, notes, validated_date,
                data_source, published
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
        """, [
            setup['setup_id'], setup['instrument'], setup['orb_time'], setup['rr'],
            setup['sl_mode'], setup['close_confirmations'], setup['buffer_ticks'],
            setup['direction_filter'], setup['trades'], setup['win_rate'], setup['avg_r'],
            setup['annual_trades'], setup['tier'], setup['slippage_tier'],
            setup['oos_validation_status'], setup['notes'], setup['validated_date'],
            setup['data_source']
        ])

        print(f"[OK] Added draft setup: {setup['setup_id']}")
        added_count += 1

    con.close()

    print()
    print(f"[OK] Added {added_count} new draft setups")
    print()
    print("Next steps:")
    print("  1. Review draft setups: python manage_setups.py list --draft")
    print("  2. Publish when ready: python manage_setups.py publish <setup_id>")
    print()

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]

    if command == "list":
        filter_type = None
        if len(sys.argv) > 2 and sys.argv[2] == "--published":
            filter_type = "published"
        elif len(sys.argv) > 2 and sys.argv[2] == "--draft":
            filter_type = "draft"
        list_setups(filter_type)

    elif command == "publish":
        if len(sys.argv) < 3:
            print("[ERROR] Usage: python manage_setups.py publish <setup_id>")
            return
        publish_setup(sys.argv[2])

    elif command == "unpublish":
        if len(sys.argv) < 3:
            print("[ERROR] Usage: python manage_setups.py unpublish <setup_id>")
            return
        unpublish_setup(sys.argv[2])

    elif command == "add-tier1":
        add_tier1_setups()

    else:
        print(f"[ERROR] Unknown command: {command}")
        print(__doc__)

if __name__ == "__main__":
    main()
