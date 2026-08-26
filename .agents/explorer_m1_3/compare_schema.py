import sys
import os
sys.path.insert(0, os.path.abspath("."))
import sqlite3
import json
from sqlalchemy import create_engine
from backend.app.database import Base
from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.escalation import Escalation
from backend.app.models.audit import AuditLog
from backend.app.scripts.seed_db import seed_database

# Create an in-memory DB or a test db
test_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=test_engine)

from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=test_engine)
db = Session()

# Seed it
seed_database(db=db, force=True, data_dir="data")

# Inspect memory DB schema
raw_conn = test_engine.raw_connection()
cursor = raw_conn.cursor()

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

print("=== IN-MEMORY (FROM SQLALCHEMY METADATA) ===")
print(json.dumps(table_info, indent=2, default=str))

print("\n=== INDICES ===")
cursor.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE type='index';")
indices = cursor.fetchall()
for idx in indices:
    print(idx)
