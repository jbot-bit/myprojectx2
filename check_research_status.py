#!/usr/bin/env python3
"""
Quick check of research status: data coverage, validated setups, backtest results
"""

import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent / "data/db/gold.db"

con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 70)
print("RESEARCH STATUS CHECK")
print("=" * 70)

# Data coverage
print("\nDATA COVERAGE:")
result = con.execute("""
    SELECT
        instrument,
        MIN(date_local) as start_date,
        MAX(date_local) as end_date,
        COUNT(*) as total_days
    FROM daily_features_v2
    GROUP BY instrument
    ORDER BY instrument
""").fetchall()

for row in result:
    print(f"  {row[0]}: {row[1]} to {row[2]} ({row[3]} days)")

# Validated setups by ORB time
print("\nVALIDATED SETUPS BY ORB:")
result = con.execute("""
    SELECT
        instrument,
        orb_time,
        tier,
        COUNT(*) as cnt,
        ROUND(AVG(win_rate), 2) as avg_wr,
        ROUND(AVG(avg_r), 3) as avg_r_multiple
    FROM validated_setups
    GROUP BY instrument, orb_time, tier
    ORDER BY instrument, orb_time,
        CASE tier
            WHEN 'S+' THEN 1
            WHEN 'S' THEN 2
            WHEN 'A' THEN 3
            WHEN 'B' THEN 4
            ELSE 5
        END
""").fetchall()

current_inst = None
current_orb = None
for row in result:
    inst, orb_time, tier, cnt, avg_wr, avg_r = row

    if inst != current_inst:
        print(f"\n  {inst}:")
        current_inst = inst
        current_orb = None

    if orb_time != current_orb:
        print(f"    {orb_time}:")
        current_orb = orb_time

    print(f"      {tier} tier: {cnt} setups (WR={avg_wr:.0f}%, AvgR={avg_r:+.2f}R)")

# Best performing setups (top 10)
print("\nTOP 10 BEST SETUPS (by AvgR):")
result = con.execute("""
    SELECT
        setup_id,
        instrument,
        orb_time,
        rr,
        sl_mode,
        tier,
        win_rate,
        avg_r,
        trades,
        notes
    FROM validated_setups
    WHERE tier IN ('S+', 'S', 'A')
    ORDER BY avg_r DESC
    LIMIT 10
""").fetchall()

print(f"  {'ID':<8} {'Inst':<5} {'ORB':<6} {'RR':<5} {'SL':<6} {'Tier':<5} {'WR%':<6} {'AvgR':<8} {'Trades':<8} {'Notes':<30}")
print("  " + "-" * 110)
for row in result:
    setup_id, inst, orb, rr, sl, tier, wr, avgr, trades, notes = row
    notes = (notes or "")[:30]
    print(f"  {setup_id:<8} {inst:<5} {orb:<6} {rr:<5.1f} {sl:<6} {tier:<5} {wr:<6.0f} {avgr:<8.2f} {trades:<8} {notes}")

# ORB performance summary (all trades aggregated)
print("\nORB PERFORMANCE SUMMARY (MGC only):")
result = con.execute("""
    SELECT
        orb_time,
        COUNT(*) as setups,
        ROUND(AVG(win_rate), 1) as avg_wr,
        ROUND(AVG(avg_r), 3) as avg_r,
        SUM(trades) as total_trades
    FROM validated_setups
    WHERE instrument = 'MGC'
    GROUP BY orb_time
    ORDER BY avg_r DESC
""").fetchall()

print(f"  {'ORB':<6} {'Setups':<8} {'Avg WR%':<10} {'Avg R':<10} {'Total Trades'}")
print("  " + "-" * 60)
for row in result:
    orb, setups, avg_wr, avg_r, trades = row
    print(f"  {orb:<6} {setups:<8} {avg_wr:<10.1f} {avg_r:<10.3f} {trades}")

con.close()

print("\n" + "=" * 70)
print("Research status check complete!")
print("=" * 70)
