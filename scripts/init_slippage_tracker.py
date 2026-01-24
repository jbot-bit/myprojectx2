"""
Initialize slippage tracking table.

Simple table to record intended vs actual fills.
"""

import duckdb

DB_PATH = "data/db/gold.db"

con = duckdb.connect(DB_PATH)

print("Creating slippage_log table...")

con.execute("""
    CREATE TABLE IF NOT EXISTS slippage_log (
        trade_id VARCHAR PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL,
        instrument VARCHAR NOT NULL,
        setup_id VARCHAR,

        -- Entry
        entry_direction VARCHAR NOT NULL,  -- 'LONG' or 'SHORT'
        intended_entry_price DOUBLE NOT NULL,
        actual_entry_price DOUBLE NOT NULL,
        entry_slippage_ticks DOUBLE NOT NULL,

        -- Exit
        intended_exit_price DOUBLE,
        actual_exit_price DOUBLE,
        exit_slippage_ticks DOUBLE,

        -- Round-trip
        roundtrip_slippage_ticks DOUBLE,

        -- Metadata
        notes VARCHAR,
        logged_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    )
""")

print("[OK] slippage_log table created")
print()

# Show schema
schema = con.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'slippage_log'
    ORDER BY ordinal_position
""").fetchall()

print("Schema:")
for col, dtype in schema:
    print(f"  {col:30s} {dtype}")

con.close()

print()
print("[OK] Slippage tracker initialized")
print()
print("Next steps:")
print("  1. Log fills: python scripts/log_fill.py")
print("  2. View stats: python scripts/slippage_stats.py")
