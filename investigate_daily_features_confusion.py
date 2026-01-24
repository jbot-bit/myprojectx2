#!/usr/bin/env python3
"""
Investigate daily_features vs daily_features_v2 confusion

Need to understand:
1. What data is in daily_features (v1)?
2. Is it different from daily_features_v2?
3. Is any code still using daily_features?
4. Can we safely delete it?
"""

import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent / "data/db/gold.db"
con = duckdb.connect(str(DB_PATH), read_only=False)

print("=" * 80)
print("INVESTIGATING DAILY_FEATURES CONFUSION")
print("=" * 80)

# Check both tables
tables = con.execute("SHOW TABLES").fetchall()
table_names = [t[0] for t in tables]

print("\nTables in database:")
for t in table_names:
    if 'daily_features' in t:
        print(f"  - {t}")

# Compare schemas
print("\n" + "=" * 80)
print("SCHEMA COMPARISON")
print("=" * 80)

if 'daily_features' in table_names:
    print("\ndaily_features (v1) schema:")
    v1_schema = con.execute("DESCRIBE daily_features").fetchall()
    v1_cols = [col[0] for col in v1_schema]
    for col in v1_schema[:10]:
        print(f"  {col[0]}: {col[1]}")
    print(f"  ... (total {len(v1_schema)} columns)")

    v1_count = con.execute("SELECT COUNT(*) FROM daily_features").fetchone()[0]
    print(f"\nRow count: {v1_count}")

    # Check date range
    v1_dates = con.execute("SELECT MIN(date_local), MAX(date_local) FROM daily_features").fetchone()
    print(f"Date range: {v1_dates[0]} to {v1_dates[1]}")

    # Check instruments
    v1_instruments = con.execute("SELECT DISTINCT instrument FROM daily_features").fetchall()
    print(f"Instruments: {[i[0] for i in v1_instruments]}")

if 'daily_features_v2' in table_names:
    print("\ndaily_features_v2 schema:")
    v2_schema = con.execute("DESCRIBE daily_features_v2").fetchall()
    v2_cols = [col[0] for col in v2_schema]
    for col in v2_schema[:10]:
        print(f"  {col[0]}: {col[1]}")
    print(f"  ... (total {len(v2_schema)} columns)")

    v2_count = con.execute("SELECT COUNT(*) FROM daily_features_v2 WHERE instrument='MGC'").fetchone()[0]
    print(f"\nMGC row count: {v2_count}")

    # Check date range
    v2_dates = con.execute("SELECT MIN(date_local), MAX(date_local) FROM daily_features_v2 WHERE instrument='MGC'").fetchone()
    print(f"Date range: {v2_dates[0]} to {v2_dates[1]}")

    # Check instruments
    v2_instruments = con.execute("SELECT DISTINCT instrument FROM daily_features_v2").fetchall()
    print(f"Instruments: {[i[0] for i in v2_instruments]}")

# Compare columns
print("\n" + "=" * 80)
print("COLUMN DIFFERENCES")
print("=" * 80)

if 'daily_features' in table_names and 'daily_features_v2' in table_names:
    v1_only = set(v1_cols) - set(v2_cols)
    v2_only = set(v2_cols) - set(v1_cols)
    common = set(v1_cols) & set(v2_cols)

    print(f"\nColumns in v1 ONLY ({len(v1_only)}):")
    for col in sorted(v1_only)[:20]:
        print(f"  - {col}")
    if len(v1_only) > 20:
        print(f"  ... and {len(v1_only) - 20} more")

    print(f"\nColumns in v2 ONLY ({len(v2_only)}):")
    for col in sorted(v2_only)[:20]:
        print(f"  - {col}")
    if len(v2_only) > 20:
        print(f"  ... and {len(v2_only) - 20} more")

    print(f"\nCommon columns: {len(common)}")

# Check if any data differs
print("\n" + "=" * 80)
print("DATA COMPARISON (sample dates)")
print("=" * 80)

if 'daily_features' in table_names and 'daily_features_v2' in table_names:
    # Check a few sample dates
    sample_dates = con.execute("""
        SELECT DISTINCT date_local
        FROM daily_features
        ORDER BY date_local DESC
        LIMIT 3
    """).fetchall()

    for date_tuple in sample_dates:
        date = date_tuple[0]
        print(f"\nDate: {date}")

        # Get orb_0900_high from both tables (if exists)
        try:
            v1_val = con.execute(f"SELECT orb_0900_high FROM daily_features WHERE date_local = '{date}'").fetchone()
            v2_val = con.execute(f"SELECT orb_0900_high FROM daily_features_v2 WHERE date_local = '{date}' AND instrument='MGC'").fetchone()

            if v1_val and v2_val:
                print(f"  orb_0900_high: v1={v1_val[0]}, v2={v2_val[0]}")
                if v1_val[0] != v2_val[0]:
                    print(f"    [DIFFERENT!]")
        except Exception as e:
            print(f"  Could not compare orb_0900_high: {e}")

# Check for any code references
print("\n" + "=" * 80)
print("CODE REFERENCES (need manual check)")
print("=" * 80)

print("\nNeed to check these files for 'daily_features' references:")
print("  - All .py files in repository")
print("  - Look for: FROM daily_features, SELECT ... daily_features")
print("  - Use: git grep 'daily_features' or search manually")

con.close()

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

print("""
Based on investigation above:

IF daily_features (v1) is:
- Same date range as v2
- Same or subset of columns
- No meaningful differences in data
- Not referenced by any code

THEN: SAFE TO DELETE

IF daily_features (v1) has:
- Different data than v2
- Code still references it
- Unique columns not in v2

THEN: NEED TO MIGRATE/FIX FIRST

Next step: Review output above and decide.
""")
