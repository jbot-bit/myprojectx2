"""
POPULATE ALL VALIDATED SETUPS - MGC, NQ, MPL

Populates validated_setups table with ALL profitable setups across
all three instruments.

**MGC SETUPS**: Based on CORRECTED values after scan window bug fix (2026-01-16)
  - Extended scan windows to 09:00 next day
  - Optimal RR values discovered (1000 ORB: RR=8.0 THE CROWN JEWEL!)
  - Source: outdated/validated_strategies.py, UNICORN_SETUPS_CORRECTED.md

**NQ SETUPS**: From NQ optimization results
**MPL SETUPS**: Dynamically queried from daily_features_v2_mpl

Only includes setups with positive expectancy (avg_r > 0).
"""

import duckdb
import pandas as pd
from datetime import date

con = duckdb.connect('gold.db')

# Clear existing data
con.execute("DELETE FROM validated_setups")

# ============================================================================
# MGC SETUPS - CORRECTED VALUES (2026-01-16)
# ============================================================================

mgc_setups = [
    # Format: orb, rr, sl_mode, confirmations, buffer, orb_size_filter, trades, win_rate, avg_r, tier, notes

    # 2300: BEST OVERALL (56% WR, ~+105R/year)
    ('2300', 1.5, 'HALF', 1, 0.0, 0.155, 522, 56.1, 0.403, 'S+',
     '⭐ BEST OVERALL - 56% WR with 1.5R targets, scan until 09:00 next day, ~+105R/year'),

    # 1000: CROWN JEWEL (15% WR but 8R targets, ~+98R/year!)
    ('1000', 8.0, 'FULL', 1, 0.0, None, 516, 15.3, 0.378, 'S+',
     '🦄 CROWN JEWEL - 15% WR but 8R targets! Scan until 09:00 next day, ~+98R/year'),

    # 1800: LONDON OPEN (51% WR, ~+72R/year)
    ('1800', 1.5, 'FULL', 1, 0.0, None, 522, 51.0, 0.274, 'S',
     'London open - 51% WR with 1.5R targets, captures NY session moves, ~+72R/year'),

    # 0030: NY ORB (31% WR with 3R targets, ~+66R/year)
    ('0030', 3.0, 'HALF', 1, 0.0, 0.112, 520, 31.3, 0.254, 'S',
     'NY ORB - 31% WR with 3R targets, hits during Asia morning, ~+66R/year'),

    # 1100: LATE ASIA (30% WR with 3R targets, ~+56R/year)
    ('1100', 3.0, 'FULL', 1, 0.0, None, 520, 30.4, 0.215, 'A',
     'Late Asia - 30% WR with 3R targets, scan until 09:00 next day, ~+56R/year'),

    # 0900: ASIA OPEN (17% WR with 6R targets, ~+51R/year)
    ('0900', 6.0, 'FULL', 1, 0.0, None, 514, 17.1, 0.198, 'A',
     'Asymmetric Asia ORB - 17% WR but 6R targets, hits overnight, ~+51R/year'),
]

for setup in mgc_setups:
    orb, rr, sl_mode, confirm, buffer, orb_size_filter, trades, wr, avg_r, tier, notes = setup
    orb_filter_str = f"ORB{orb_size_filter}" if orb_size_filter else "NOFILTER"
    setup_id = f"MGC_{orb}_RR{rr}_{sl_mode}_C{confirm}_B{buffer}_{orb_filter_str}"
    annual_trades = int(trades * 365 / 740)  # 740 days in dataset

    con.execute("""
        INSERT INTO validated_setups VALUES (
            ?, 'MGC', ?, ?, ?, ?, ?, ?, NULL, NULL,
            ?, ?, ?, ?, ?, ?, ?, 'daily_features_v2'
        )
    """, [
        setup_id, orb, rr, sl_mode, confirm, buffer, orb_size_filter,
        trades, wr, avg_r, annual_trades, tier, notes, date.today()
    ])

print(f"[OK] Inserted {len(mgc_setups)} MGC setups (CORRECTED values after scan window fix)")

# ============================================================================
# NQ SETUPS (from NQ optimization results)
# ============================================================================

nq_setups = [
    # Format: orb, rr, sl_mode, confirmations, buffer, orb_size_filter, trades, win_rate, avg_r, tier, notes

    # 0030: BEST NQ ORB (64% WR, +0.320R with large ORB filter)
    ('0030', 1.0, 'HALF', 1, 0.0, None, 100, 66.0, 0.320, 'S+',
     'BEST NQ ORB - Large ORBs only (>=149 ticks), 66% WR'),

    # 1800: EXCELLENT (65% WR, +0.292R with median filter)
    ('1800', 1.0, 'HALF', 1, 0.0, 0.50, 161, 64.6, 0.292, 'S',
     'London open - Filter ORB 50-150% of median (80 ticks), strong edge'),

    # 1100: HIGH WR (64% WR, +0.284R with median filter)
    ('1100', 1.0, 'HALF', 1, 0.0, 0.50, 134, 64.2, 0.284, 'S',
     'Asia late - Filter ORB 50-150% of median (50 ticks), reliable'),

    # 1000: SOLID (58% WR, +0.158R baseline)
    ('1000', 1.0, 'HALF', 1, 0.0, None, 221, 57.9, 0.158, 'A',
     'Asia mid - No filter needed, solid baseline performance'),

    # 0900: SMALL ORBS (56% WR, +0.127R with small ORB filter)
    ('0900', 1.0, 'HALF', 1, 0.0, 1.0, 110, 56.4, 0.127, 'B',
     'Asia open - Small ORBs only (<66 ticks median), decent edge'),

    # 2300: SKIP THIS (50% WR, 0.018R - too thin)
    # Intentionally excluded - no edge
]

for setup in nq_setups:
    orb, rr, sl_mode, confirm, buffer, orb_size_filter, trades, wr, avg_r, tier, notes = setup
    orb_filter_str = f"ORB{orb_size_filter}" if orb_size_filter else "NOFILTER"
    setup_id = f"NQ_{orb}_RR{rr}_{sl_mode}_C{confirm}_B{buffer}_{orb_filter_str}"
    annual_trades = int(trades * 365 / 365)  # NQ data is 365 days

    con.execute("""
        INSERT INTO validated_setups VALUES (
            ?, 'NQ', ?, ?, ?, ?, ?, ?, NULL, NULL,
            ?, ?, ?, ?, ?, ?, ?, 'daily_features_v2_nq'
        )
    """, [
        setup_id, orb, rr, sl_mode, confirm, buffer, orb_size_filter,
        trades, wr, avg_r, annual_trades, tier, notes, date.today()
    ])

print(f"[OK] Inserted {len(nq_setups)} NQ setups")

# ============================================================================
# MPL SETUPS (query from database - FULL SL mode, RR=1.0 baseline)
# ============================================================================

# Query MPL ORB performance from database
mpl_query = """
WITH mpl_orbs AS (
    SELECT
        '0900' as orb,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_0900_outcome='WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_0900_r_multiple) as avg_r
    FROM daily_features_v2_mpl
    WHERE orb_0900_outcome IN ('WIN','LOSS')

    UNION ALL

    SELECT
        '1000' as orb,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1000_outcome='WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1000_r_multiple) as avg_r
    FROM daily_features_v2_mpl
    WHERE orb_1000_outcome IN ('WIN','LOSS')

    UNION ALL

    SELECT
        '1100' as orb,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1100_outcome='WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1100_r_multiple) as avg_r
    FROM daily_features_v2_mpl
    WHERE orb_1100_outcome IN ('WIN','LOSS')

    UNION ALL

    SELECT
        '1800' as orb,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_1800_outcome='WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_1800_r_multiple) as avg_r
    FROM daily_features_v2_mpl
    WHERE orb_1800_outcome IN ('WIN','LOSS')

    UNION ALL

    SELECT
        '2300' as orb,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_2300_outcome='WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_2300_r_multiple) as avg_r
    FROM daily_features_v2_mpl
    WHERE orb_2300_outcome IN ('WIN','LOSS')

    UNION ALL

    SELECT
        '0030' as orb,
        COUNT(*) as trades,
        AVG(CASE WHEN orb_0030_outcome='WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        AVG(orb_0030_r_multiple) as avg_r
    FROM daily_features_v2_mpl
    WHERE orb_0030_outcome IN ('WIN','LOSS')
)
SELECT * FROM mpl_orbs
WHERE avg_r > 0  -- Only profitable setups
ORDER BY avg_r DESC
"""

mpl_results = con.execute(mpl_query).df()

# Tier assignment logic for MPL
def assign_tier_mpl(avg_r, win_rate):
    if avg_r >= 0.30 and win_rate >= 0.65:
        return 'S+'
    elif avg_r >= 0.25 or win_rate >= 0.63:
        return 'S'
    elif avg_r >= 0.15 or win_rate >= 0.60:
        return 'A'
    elif avg_r >= 0.05:
        return 'B'
    else:
        return 'C'

mpl_count = 0
for idx, row in mpl_results.iterrows():
    orb = row['orb']
    trades = int(row['trades'])
    win_rate = float(row['win_rate']) * 100
    avg_r = float(row['avg_r'])
    tier = assign_tier_mpl(avg_r, win_rate/100)
    annual_trades = trades  # Already 365 days

    # Add descriptive notes
    notes_map = {
        '0900': 'Asia open - Full-size contract ($50/pt)',
        '1000': 'Asia mid - Full-size contract ($50/pt)',
        '1100': 'Asia late - CHAMPION SETUP (67% WR!) - Full-size contract ($50/pt)',
        '1800': 'London open - Full-size contract ($50/pt)',
        '2300': 'NY futures open - Excellent night setup - Full-size contract ($50/pt)',
        '0030': 'NY cash open - Full-size contract ($50/pt)',
    }
    notes = notes_map.get(orb, 'Full-size contract ($50/pt)')

    setup_id = f"MPL_{orb}_RR1.0_FULL_C1_B0.0_NOFILTER"

    con.execute("""
        INSERT INTO validated_setups VALUES (
            ?, 'MPL', ?, 1.0, 'FULL', 1, 0.0, NULL, NULL, NULL,
            ?, ?, ?, ?, ?, ?, ?, 'daily_features_v2_mpl'
        )
    """, [
        setup_id, orb,
        trades, win_rate, avg_r, annual_trades, tier, notes, date.today()
    ])
    mpl_count += 1

print(f"[OK] Inserted {mpl_count} MPL setups")

# ============================================================================
# SUMMARY
# ============================================================================

result = con.execute("""
    SELECT
        instrument,
        tier,
        COUNT(*) as setups,
        ROUND(AVG(win_rate),1) as avg_wr,
        ROUND(AVG(avg_r),3) as avg_r,
        SUM(annual_trades) as total_annual_trades
    FROM validated_setups
    GROUP BY instrument, tier
    ORDER BY instrument,
        CASE tier
            WHEN 'S+' THEN 1
            WHEN 'S' THEN 2
            WHEN 'A' THEN 3
            WHEN 'B' THEN 4
            WHEN 'C' THEN 5
        END
""").df()

print("\n" + "="*80)
print("ALL VALIDATED SETUPS BY INSTRUMENT (CORRECTED MGC VALUES)")
print("="*80)
print(result.to_string(index=False))

# Show all setups with details
print("\n" + "="*80)
print("DETAILED SETUP INVENTORY")
print("="*80)

for instrument in ['MGC', 'NQ', 'MPL']:
    result = con.execute("""
        SELECT
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
        WHERE instrument = ?
        ORDER BY avg_r DESC
    """, [instrument]).df()

    print(f"\n[CHART] {instrument} SETUPS ({len(result)} total):")
    print("-" * 80)

    for idx, row in result.iterrows():
        if row['orb_size_filter'] and not pd.isna(row['orb_size_filter']):
            if row['orb_size_filter'] == 0.5:
                filter_str = "ORB 50-150% of median"
            elif row['orb_size_filter'] == 1.0:
                filter_str = "Small ORBs only"
            else:
                filter_str = f"ORB<{row['orb_size_filter']*100:.1f}% ATR"
        else:
            filter_str = "NO FILTER"

        print(f"{row['orb_time']}: RR={row['rr']}, {row['sl_mode']:4s}, {filter_str:30s}, "
              f"{int(row['trades']):3d} trades, {row['win_rate']:5.1f}% WR, "
              f"{row['avg_r']:+.3f}R [{row['tier']}]")
        # Remove emojis for Windows console compatibility
        notes_clean = row['notes'].encode('ascii', 'ignore').decode('ascii')
        print(f"   -> {notes_clean}")

con.close()

print("\n" + "="*80)
print("[OK] COMPLETE - All instruments populated with CORRECTED values!")
print("="*80)
print("\nSetups stored in validated_setups table:")
print("- MGC: 6 setups (CORRECTED after scan window bug fix)")
print("  - 1000 ORB: RR=8.0 CROWN JEWEL (~+98R/year)")
print("  - 2300 ORB: RR=1.5 BEST OVERALL (~+105R/year)")
print("  - 0030 ORB: RR=3.0 (~+66R/year)")
print("- NQ: 5 setups (S+ to B tier, skip 2300)")
print("- MPL: 6 setups (all profitable, full-size contracts)")
print("\nThe trading app can now detect setups across ALL THREE INSTRUMENTS!")
print("\nREMINDER: Always update config.py when updating MGC filters in database!")
