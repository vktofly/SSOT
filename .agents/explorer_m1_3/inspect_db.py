import sqlite3
import json

conn = sqlite3.connect('data/ssot.db')
cursor = conn.cursor()

# PRAGMA integrity_check
cursor.execute("PRAGMA integrity_check;")
integrity = cursor.fetchall()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]

table_info = {}
for tbl in tables:
    cursor.execute(f"PRAGMA table_info('{tbl}');")
    cols = cursor.fetchall()
    cursor.execute(f"SELECT count(*) FROM '{tbl}';")
    cnt = cursor.fetchone()[0]
    cursor.execute(f"SELECT * FROM '{tbl}' LIMIT 2;")
    samples = cursor.fetchall()
    table_info[tbl] = {
        'count': cnt,
        'columns': [{'cid': c[0], 'name': c[1], 'type': c[2], 'notnull': c[3], 'dflt_value': c[4], 'pk': c[5]} for c in cols],
        'sample_rows': samples
    }

print("=== INTEGRITY CHECK ===")
print(integrity)
print("\n=== TABLE DETAILS ===")
print(json.dumps(table_info, indent=2, default=str))

# Foreign keys and indices
print("\n=== INDICES ===")
cursor.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE type='index';")
indices = cursor.fetchall()
for idx in indices:
    print(idx)

conn.close()
