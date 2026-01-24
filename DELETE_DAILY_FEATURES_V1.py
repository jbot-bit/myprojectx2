#!/usr/bin/env python3
"""
DELETE daily_features (v1) table - clean up confusion

Authority: CLAUDE.md (daily_features_v2 is canonical)
Reason: Confusion between v1 and v2 must be resolved completely

This script:
1. Backs up daily_features (v1) data to CSV (just in case)
2. Drops the daily_features table
3. Verifies deletion
"""

import duckdb
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data/db/gold.db"
BACKUP_DIR = Path(__file__).parent / "data/backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_FILE = BACKUP_DIR / f"daily_features_v1_backup_{timestamp}.csv"

con = duckdb.connect(str(DB_PATH), read_only=False)

print("=" * 80)
print("DELETING DAILY_FEATURES (V1) TABLE")
print("=" * 80)

# Check if table exists
tables = con.execute("SHOW TABLES").fetchall()
table_names = [t[0] for t in tables]

if 'daily_features' not in table_names:
    print("\n[OK] daily_features (v1) does not exist. Nothing to delete.")
    con.close()
    exit(0)

# Step 1: Backup to CSV
print(f"\nStep 1: Backing up daily_features (v1) to CSV...")
print(f"  Backup file: {BACKUP_FILE}")

try:
    row_count = con.execute("SELECT COUNT(*) FROM daily_features").fetchone()[0]
    print(f"  Rows to backup: {row_count}")

    # Export to CSV
    con.execute(f"""
        COPY daily_features TO '{BACKUP_FILE}'
        (HEADER, DELIMITER ',')
    """)
    print(f"  [OK] Backup complete")
except Exception as e:
    print(f"  [ERROR] Backup failed: {e}")
    print("  Aborting deletion for safety")
    con.close()
    exit(1)

# Step 2: Drop table
print(f"\nStep 2: Dropping daily_features table...")

try:
    con.execute("DROP TABLE daily_features")
    print(f"  [OK] Table dropped")
except Exception as e:
    print(f"  [ERROR] Drop failed: {e}")
    con.close()
    exit(1)

# Step 3: Verify deletion
print(f"\nStep 3: Verifying deletion...")

tables_after = con.execute("SHOW TABLES").fetchall()
table_names_after = [t[0] for t in tables_after]

if 'daily_features' in table_names_after:
    print(f"  [ERROR] Table still exists!")
    con.close()
    exit(1)
else:
    print(f"  [OK] daily_features (v1) successfully deleted")

# Show remaining daily_features tables
print(f"\nRemaining daily_features tables:")
for t in table_names_after:
    if 'daily_features' in t:
        row_count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  - {t}: {row_count} rows")

con.close()

print("\n" + "=" * 80)
print("DELETION COMPLETE")
print("=" * 80)
print(f"\nBackup saved to: {BACKUP_FILE}")
print(f"\ndaily_features_v2 remains as ONLY canonical table")
print(f"\nNo confusion between v1 and v2 anymore!")
print("=" * 80)
