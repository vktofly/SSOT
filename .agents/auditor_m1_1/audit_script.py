"""
Independent Forensic Verification Script for Milestone 1.
Tests SQLite file, raw schema, table counts, SQLAlchemy ORM queries, real CRUD lifecycle, and FastAPI routes.
"""
import os
import sys
import sqlite3
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal, get_db
from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.escalation import Escalation
from backend.app.models.audit import AuditLog
from backend.app.main import app
from backend.app.scripts.seed_db import seed_database


def test_sqlite_file_and_schema():
    print("=== 1. Physical SQLite File & Schema Inspection ===")
    db_file = os.path.join(PROJECT_ROOT, "data", "ssot.db")
    print(f"Checking SQLite DB file at: {db_file}")
    assert os.path.exists(db_file), f"Database file does not exist: {db_file}"
    db_size = os.path.getsize(db_file)
    print(f"Database file size: {db_size} bytes ({db_size / 1024:.2f} KB)")
    assert db_size > 10000, f"Database file suspiciously small ({db_size} bytes)"

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Found tables: {tables}")
    
    expected_tables = ["support_tracker", "finance_tracker", "escalations", "audit_logs"]
    for t in expected_tables:
        assert t in tables, f"Expected table '{t}' not found in SQLite tables: {tables}"
        cursor.execute(f"SELECT COUNT(*) FROM \"{t}\";")
        count = cursor.fetchone()[0]
        cursor.execute(f"PRAGMA table_info(\"{t}\");")
        cols = cursor.fetchall()
        col_names = [c[1] for c in cols]
        print(f"  Table: {t} -> {count} rows, Columns ({len(cols)}): {col_names}")
        if t == "support_tracker":
            assert count >= 700, f"Support tracker count {count} < 700"
            assert "Ticket ID" in col_names
            assert "Agent" in col_names
            assert "Refund Amount (INR)" in col_names
        elif t == "finance_tracker":
            assert count >= 650, f"Finance tracker count {count} < 650"
            assert "Ref No" in col_names
            assert "Agent Name" in col_names
            assert "Amount Paid (INR)" in col_names
        elif t == "escalations":
            assert count >= 100, f"Escalations count {count} < 100"
            assert "Escalation ID" in col_names
            assert "Message" in col_names
    conn.close()
    print("[PASS] SQLite file and schema verification PASSED.")


def test_orm_operations_on_real_db():
    print("\n=== 2. SQLAlchemy ORM Operations on Real Database ===")
    db = SessionLocal()
    try:
        sup_count = db.query(SupportTicket).count()
        fin_count = db.query(FinanceRecord).count()
        esc_count = db.query(Escalation).count()
        print(f"ORM Row Counts -> Support: {sup_count}, Finance: {fin_count}, Escalation: {esc_count}")
        assert sup_count >= 700
        assert fin_count >= 650
        assert esc_count >= 100

        # Test live query with filters
        sample_ticket = db.query(SupportTicket).first()
        print(f"Sample SupportTicket query -> ID: {sample_ticket.ticket_id}, Agent: {sample_ticket.agent}, Refund: {sample_ticket.refund_amount}")
        assert sample_ticket.ticket_id is not None
        assert sample_ticket.agent is not None

        # Test live query by primary key
        pk_ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == sample_ticket.ticket_id).first()
        assert pk_ticket is not None
        assert pk_ticket.ticket_id == sample_ticket.ticket_id

        # Test ORM create, query, update, delete cycle in isolated transaction
        test_id = "RF-AUDIT-TEST-01"
        existing = db.query(SupportTicket).filter(SupportTicket.ticket_id == test_id).first()
        if existing:
            db.delete(existing)
            db.commit()

        new_ticket = SupportTicket(
            ticket_id=test_id,
            agent="Audit Agency",
            route="BOM-DEL",
            refund_amount=5555.0,
            status="Pending",
            channel="Email",
            notes="Audit test record",
        )
        db.add(new_ticket)
        db.commit()

        fetched = db.query(SupportTicket).filter(SupportTicket.ticket_id == test_id).first()
        assert fetched is not None
        assert fetched.refund_amount == 5555.0
        assert fetched.agent == "Audit Agency"

        # Update
        fetched.status = "Audit Approved"
        fetched.refund_amount = 7777.0
        db.commit()

        re_fetched = db.query(SupportTicket).filter(SupportTicket.ticket_id == test_id).first()
        assert re_fetched.status == "Audit Approved"
        assert re_fetched.refund_amount == 7777.0

        # Delete
        db.delete(re_fetched)
        db.commit()

        deleted = db.query(SupportTicket).filter(SupportTicket.ticket_id == test_id).first()
        assert deleted is None
        print("[PASS] ORM CRUD transaction cycle PASSED.")
    finally:
        db.close()


def test_fastapi_rest_endpoints():
    print("\n=== 3. FastAPI REST Endpoints Verification (Opaque Client) ===")
    client = TestClient(app)

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    # List support tickets
    res = client.get("/api/v1/support-tickets?limit=5")
    assert res.status_code == 200
    tickets = res.json()
    assert len(tickets) == 5
    print(f"Fetched 5 support tickets via REST: {[t['Ticket ID'] for t in tickets]}")

    # Create via REST
    audit_ticket_id = "RF-REST-AUDIT-99"
    # Ensure cleaned up first
    client.delete(f"/api/v1/support-tickets/{audit_ticket_id}")

    create_payload = {
        "Ticket ID": audit_ticket_id,
        "Agent": "Peak Journeys",
        "Route": "DEL-BOM",
        "Refund Amount (INR)": 8888.50,
        "Status": "Pending",
        "Handled By": "Auditor",
        "Channel": "WhatsApp",
        "Notes": "REST CRUD audit test",
    }
    create_res = client.post("/api/v1/support-tickets", json=create_payload)
    assert create_res.status_code == 201, f"Create returned {create_res.status_code}: {create_res.text}"
    created_data = create_res.json()
    assert created_data["Ticket ID"] == audit_ticket_id
    assert created_data["Refund Amount (INR)"] == 8888.50

    # Get by ID via REST
    get_res = client.get(f"/api/v1/support-tickets/{audit_ticket_id}")
    assert get_res.status_code == 200
    assert get_res.json()["Refund Amount (INR)"] == 8888.50

    # Patch via REST
    patch_res = client.patch(
        f"/api/v1/support-tickets/{audit_ticket_id}",
        json={"Status": "Resolved", "Refund Amount (INR)": 9999.0}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["Status"] == "Resolved"
    assert patch_res.json()["Refund Amount (INR)"] == 9999.0

    # Filter via REST
    filter_res = client.get("/api/v1/support-tickets", params={"search": "REST CRUD audit test"})
    assert filter_res.status_code == 200
    matching = filter_res.json()
    assert len(matching) >= 1
    assert any(m["Ticket ID"] == audit_ticket_id for m in matching)

    # Delete via REST
    del_res = client.delete(f"/api/v1/support-tickets/{audit_ticket_id}")
    assert del_res.status_code == 200

    # Confirm 404
    get_after_del = client.get(f"/api/v1/support-tickets/{audit_ticket_id}")
    assert get_after_del.status_code == 404

    # Repeat for Finance Records
    audit_ref_no = "RF-FIN-AUDIT-99"
    client.delete(f"/api/v1/finance-records/{audit_ref_no}")
    fin_create = client.post("/api/v1/finance-records", json={
        "Ref No": audit_ref_no,
        "Agent Name": "Peak Journeys",
        "Sector": "DEL-BOM",
        "Amount Paid (INR)": 15000.0,
        "Deduction (INR)": 1000.0,
        "Payout Status": "Pending Payout",
        "Approved By": "Finance Admin",
        "Remarks": "Audit test",
    })
    assert fin_create.status_code == 201
    assert fin_create.json()["Ref No"] == audit_ref_no

    fin_get = client.get(f"/api/v1/finance-records/{audit_ref_no}")
    assert fin_get.status_code == 200

    fin_del = client.delete(f"/api/v1/finance-records/{audit_ref_no}")
    assert fin_del.status_code == 200

    # Repeat for Escalations
    audit_esc_id = "ESC-AUDIT-99"
    client.delete(f"/api/v1/escalations/{audit_esc_id}")
    esc_create = client.post("/api/v1/escalations", json={
        "Escalation ID": audit_esc_id,
        "Ticket ID": "RF-1001",
        "Agent": "Peak Journeys",
        "Channel": "Email",
        "Message": "Audit test complaint",
        "Status": "Open",
        "Days Open": 1.0,
    })
    assert esc_create.status_code == 201
    assert esc_create.json()["Escalation ID"] == audit_esc_id

    esc_get = client.get(f"/api/v1/escalations/{audit_esc_id}")
    assert esc_get.status_code == 200

    esc_del = client.delete(f"/api/v1/escalations/{audit_esc_id}")
    assert esc_del.status_code == 200

    print("[PASS] FastAPI REST Endpoints CRUD cycle PASSED.")


def test_adversarial_code_inspection():
    print("\n=== 4. Codebase Forensic Check (No Hardcoded Mock Logic) ===")
    router_files = [
        os.path.join(PROJECT_ROOT, "backend", "app", "routers", "support.py"),
        os.path.join(PROJECT_ROOT, "backend", "app", "routers", "finance.py"),
        os.path.join(PROJECT_ROOT, "backend", "app", "routers", "escalations.py"),
    ]
    for rf in router_files:
        with open(rf, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Verify db.query is used and not returning static fake list
        assert "db.query(" in content, f"{rf} does not call db.query"
        assert "db.commit()" in content, f"{rf} does not call db.commit"
        assert "db.add(" in content, f"{rf} does not call db.add"
        assert "db.delete(" in content, f"{rf} does not call db.delete"
        
        # Check for banned fake return patterns
        assert "return [{'Ticket ID': 'RF-1001'" not in content
        assert "return [{'Ref No': 'RF-1001'" not in content
        print(f"  Checked {os.path.basename(rf)}: genuine SQLAlchemy query and session usage confirmed.")

    print("[PASS] Codebase forensic checks PASSED.")


def main():
    print("Starting Milestone 1 Forensic Audit Verification...\n")
    test_sqlite_file_and_schema()
    test_orm_operations_on_real_db()
    test_fastapi_rest_endpoints()
    test_adversarial_code_inspection()
    print("\n==========================================")
    print("ALL MILESTONE 1 FORENSIC CHECKS PASSED!")
    print("Verdict: CLEAN")
    print("==========================================")


if __name__ == "__main__":
    main()
