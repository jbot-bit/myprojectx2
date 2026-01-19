import duckdb
con = duckdb.connect("data/db/gold.db")
row = con.execute("SELECT candidate_id, code_version, data_version, test_config_json, status FROM edge_candidates WHERE candidate_id=1").fetchone()
print(row)
con.close()
