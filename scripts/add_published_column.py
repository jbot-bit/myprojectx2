"""
Add 'published' status column to validated_setups table.

This allows us to:
1. Save validated setups without making them live in the app
2. Review and approve setups before publishing
3. Gradually roll out new strategies
"""

import duckdb

DB_PATH = "data/db/gold.db"

con = duckdb.connect(DB_PATH)

print("Adding 'published' column to validated_setups...")

try:
    # Add published column (default False for new setups)
    con.execute("""
        ALTER TABLE validated_setups
        ADD COLUMN IF NOT EXISTS published BOOLEAN DEFAULT FALSE
    """)

    # Add validation status column
    con.execute("""
        ALTER TABLE validated_setups
        ADD COLUMN IF NOT EXISTS oos_validation_status VARCHAR DEFAULT NULL
    """)

    # Add slippage tier column
    con.execute("""
        ALTER TABLE validated_setups
        ADD COLUMN IF NOT EXISTS slippage_tier VARCHAR DEFAULT NULL
    """)

    # Add direction filter column
    con.execute("""
        ALTER TABLE validated_setups
        ADD COLUMN IF NOT EXISTS direction_filter VARCHAR DEFAULT NULL
    """)

    print("[OK] Columns added successfully")
    print()

    # Show current table schema
    schema = con.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'validated_setups'
        ORDER BY ordinal_position
    """).fetchall()

    print("Updated validated_setups schema:")
    for col, dtype, nullable in schema:
        print(f"  {col:30s} {dtype:15s} {'NULL' if nullable else 'NOT NULL'}")

    print()
    print("[OK] Schema update complete")

except Exception as e:
    print(f"[ERROR] {e}")
    con.rollback()

con.close()
