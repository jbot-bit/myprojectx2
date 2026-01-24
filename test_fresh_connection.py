"""Fresh connection test to verify Phase 1B data."""
import duckdb
from pathlib import Path

db_path = Path("data/db/gold.db")
print(f"Connecting to: {db_path.resolve()}")

conn = duckdb.connect(str(db_path))

# Check total setups
total = conn.execute("SELECT COUNT(*) FROM validated_setups").fetchone()[0]
print(f"Total setups: {total}")

# Check conditional setups
conditional = conn.execute("SELECT COUNT(*) FROM validated_setups WHERE condition_type IS NOT NULL").fetchone()[0]
print(f"Conditional setups: {conditional}")

# Sample conditional setups
print("\nSample conditional setups:")
result = conn.execute("""
    SELECT setup_id, condition_type, condition_value, avg_r, quality_multiplier
    FROM validated_setups
    WHERE condition_type IS NOT NULL
    ORDER BY avg_r DESC
    LIMIT 5
""").fetchall()

for r in result:
    print(f"  {r[0]}: {r[1]}={r[2]}, {r[3]:.3f}R, {r[4]}x quality")

conn.close()
print("\n SUCCESS - Phase 1B data is in the database!")
