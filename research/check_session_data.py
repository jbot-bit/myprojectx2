#!/usr/bin/env python3
"""Quick check of session data to understand liquidity patterns"""
import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data/db/gold.db"
con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 70)
print("SESSION DATA ANALYSIS")
print("=" * 70)

# Sample session type codes
print("\nSample of session type codes:")
result = con.execute("""
    SELECT
        date_local,
        asia_type_code,
        london_type_code,
        pre_ny_type_code,
        asia_high,
        asia_low,
        london_high,
        london_low
    FROM daily_features_v2
    WHERE instrument = 'MGC'
    ORDER BY date_local DESC
    LIMIT 10
""").fetchall()

for r in result:
    print(f"  {r[0]}: asia_type={r[1]}, london_type={r[2]}, pre_ny_type={r[3]}")

# Distribution of type codes
print("\nDistribution of session type codes:")
result = con.execute("""
    SELECT
        asia_type_code,
        COUNT(*) as cnt
    FROM daily_features_v2
    WHERE instrument = 'MGC'
    GROUP BY asia_type_code
    ORDER BY cnt DESC
""").fetchall()

print("  Asia type codes:")
for r in result:
    print(f"    {r[0]}: {r[1]} days")

result = con.execute("""
    SELECT
        london_type_code,
        COUNT(*) as cnt
    FROM daily_features_v2
    WHERE instrument = 'MGC'
    GROUP BY london_type_code
    ORDER BY cnt DESC
""").fetchall()

print("\n  London type codes:")
for r in result:
    print(f"    {r[0]}: {r[1]} days")

# Check for liquidity-related setup names
print("\nLiquidity-related validated setups:")
result = con.execute("""
    SELECT
        setup_id,
        orb_time,
        tier,
        win_rate,
        avg_r,
        trades,
        notes
    FROM validated_setups
    WHERE instrument = 'MGC'
      AND (setup_id LIKE '%CASCADE%' OR setup_id LIKE '%LIQUIDITY%' OR setup_id LIKE '%SWEEP%')
    ORDER BY avg_r DESC
""").fetchall()

for r in result:
    print(f"  {r[0]}: tier={r[2]}, WR={r[3]:.0f}%, AvgR={r[4]:+.2f}R, trades={r[5]}")
    if r[6]:
        print(f"    Notes: {r[6][:80]}")

con.close()

print("\n" + "=" * 70)
