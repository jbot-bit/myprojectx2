import duckdb
conn = duckdb.connect('data/db/gold.db', read_only=True)
print('=== validated_setups schema ===')
schema = conn.execute('PRAGMA table_info(validated_setups)').fetchall()
for s in schema:
    print(s)
print()
print('=== MGC 1000 setups ===')
results = conn.execute("SELECT * FROM validated_setups WHERE instrument='MGC' AND orb_time='1000' ORDER BY rr, sl_mode").fetchall()
for row in results:
    print(row)
conn.close()
