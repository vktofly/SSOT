"""
Empirical Challenge & Adversarial Stress Suite for Milestone 1.
Challenger 2 verification suite covering:
1. Data normalization & edge cases in seed_db.py.
2. SQLite transaction rollback and session recovery.
3. Multi-threaded concurrent writes & race conditions.
4. Edge-case filtering, SQL injection resilience, and pagination bounds across CRUD endpoints.
5. Payload fuzzing, unicode preservation, and boundary constraints.
"""
import os
import tempfile
import concurrent.futures
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError

from backend.app.main import app
from backend.app.database import get_db, SessionLocal, Base
from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.escalation import Escalation
from backend.app.scripts.seed_db import (
    clean_money_string,
    clean_str,
    normalize_id,
    clean_agency_name,
    seed_database,
)


# ===========================================================================
# 1. DATA NORMALIZATION EMPIRICAL STRESS TESTS
# ===========================================================================

@pytest.mark.parametrize("raw_input,expected", [
    ("  RF  1234  ", "RF-1234"),
    ("rf 999", "RF-999"),
    ("RF\t888", "RF-888"),
    ("ESC 101", "ESC-101"),
    ("esc  202", "ESC-202"),
    ("esc-303", "ESC-303"),
    ("rf-404", "RF-404"),
    ("CUSTOM 505", "CUSTOM 505"), # Non RF/ESC untouched
    ("", None),
    ("   ", None),
    ("nan", None),
    ("NAN", None),
    ("None", None),
    ("null", None),
    (None, None),
])
def test_normalize_id_adversarial_inputs(raw_input, expected):
    """Stress test normalize_id with unusual whitespace, casing, and null sentinels."""
    assert normalize_id(raw_input) == expected


@pytest.mark.parametrize("raw_input,expected", [
    ("  ₹  45,678.90 ", 45678.90),
    ("INR  1,00,000.00", 100000.00),
    ("$ 999.99", 999.99),
    ("-500.50", -500.50),
    ("-₹1,200", -1200.0),
    ("0.00", 0.0),
    ("0", 0.0),
    (12345, 12345.0),
    (67.89, 67.89),
    (float("nan"), 0.0),
    (float("inf"), 0.0),
    (float("-inf"), 0.0),
    ("invalid_money", 0.0),
    ("₹", 0.0),
    ("INR", 0.0),
    ("FREE", 0.0),
    ("N/A", 0.0),
    ("--", 0.0),
    ("", 0.0),
    (None, 0.0),
])
def test_clean_money_string_adversarial_inputs(raw_input, expected):
    """Stress test clean_money_string across currency symbols, negative values, and non-numeric inputs."""
    assert clean_money_string(raw_input) == expected


@pytest.mark.parametrize("raw_input,expected", [
    ("  sunrise trips  ", "Sunrise Trips"),
    ("PEAK JOURNEYS", "Peak Journeys"),
    ("  goFLy   HoLiDaYs  ", "GoFly Holidays"),
    ("ziptrip", "ZipTrip"),
    ("  custom new travel agency  ", "Custom New Travel Agency"),
    ("already Capitalized Agency", "Already Capitalized Agency"),
    ("", None),
    ("   ", None),
    ("nan", None),
    (None, None),
])
def test_clean_agency_name_adversarial_inputs(raw_input, expected):
    """Stress test agency name normalization, canonical mappings, and title-casing fallbacks."""
    assert clean_agency_name(raw_input) == expected


def test_seed_database_idempotency(db_session: Session):
    """Verify that running seed_database repeatedly with force=True produces identical row counts."""
    counts1 = seed_database(db=db_session, force=True, data_dir="data")
    assert counts1["support"] == 733
    assert counts1["finance"] == 680
    assert counts1["escalations"] == 155

    # Run second time without force
    counts2 = seed_database(db=db_session, force=False, data_dir="data")
    assert counts2 == counts1

    # Run third time with force=True (truncate & rehydrate)
    counts3 = seed_database(db=db_session, force=True, data_dir="data")
    assert counts3 == counts1

    # Verify no phantom rows or duplicate primary keys
    assert db_session.query(SupportTicket).count() == 733
    assert db_session.query(FinanceRecord).count() == 680
    assert db_session.query(Escalation).count() == 155


# ===========================================================================
# 2. SQLITE TRANSACTION ROLLBACK & INTEGRITY TESTS
# ===========================================================================

def test_transaction_rollback_on_integrity_violation(db_session: Session):
    """Verify that a failed insert cleanly rolls back without corrupting the session or DB state."""
    initial_count = db_session.query(SupportTicket).count()

    ticket_valid = SupportTicket(
        ticket_id="RF-ROLLBACK-01",
        agent="Test Agent",
        status="Pending"
    )
    db_session.add(ticket_valid)
    db_session.commit()
    assert db_session.query(SupportTicket).count() == initial_count + 1

    # Attempt to insert duplicate primary key in new isolated session to test DB integrity
    session2 = Session(bind=db_session.bind)
    try:
        ticket_dup = SupportTicket(
            ticket_id="RF-ROLLBACK-01",
            agent="Conflicting Agent",
            status="Closed"
        )
        session2.add(ticket_dup)
        with pytest.raises(IntegrityError):
            session2.commit()
    finally:
        session2.rollback()
        session2.close()

    assert db_session.query(SupportTicket).count() == initial_count + 1
    reloaded = db_session.query(SupportTicket).filter_by(ticket_id="RF-ROLLBACK-01").first()
    assert reloaded.agent == "Test Agent"


def test_multi_table_atomic_transaction_rollback(db_session: Session):
    """Verify atomicity across multiple tables in a single transaction."""
    # Pre-populate conflicting record
    pre_existing = FinanceRecord(ref_no="RF-ATOMIC-CONFLICT", agent_name="Pre Existing")
    db_session.add(pre_existing)
    db_session.commit()

    try:
        # Step 1: Valid support ticket
        t = SupportTicket(ticket_id="RF-ATOMIC-1", agent="Atomic Agency")
        db_session.add(t)

        # Step 2: Valid finance record
        f = FinanceRecord(ref_no="RF-ATOMIC-2", agent_name="Atomic Agency")
        db_session.add(f)

        # Step 3: Duplicate finance record that triggers DB error
        f_dup = FinanceRecord(ref_no="RF-ATOMIC-CONFLICT", agent_name="Conflicting Agency")
        db_session.add(f_dup)

        db_session.commit()
    except IntegrityError:
        db_session.rollback()

    # Verify atomic additions were rolled back
    assert db_session.query(SupportTicket).filter_by(ticket_id="RF-ATOMIC-1").first() is None
    assert db_session.query(FinanceRecord).filter_by(ref_no="RF-ATOMIC-2").first() is None


# ===========================================================================
# 3. CONCURRENT WRITES & MULTI-THREADED STRESS TESTS (File-backed SQLite)
# ===========================================================================

def test_concurrent_multithreaded_ticket_inserts():
    """
    Stress test multi-threaded concurrent POST requests to /api/v1/support-tickets.
    Uses file-backed SQLite database to accurately verify concurrent multi-connection writes in production conditions.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        file_engine = create_engine(
            f"sqlite:///{tmp_db_path}",
            connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(bind=file_engine)
        FileSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=file_engine)

        def file_get_db():
            db = FileSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = file_get_db
        test_client = TestClient(app)

        num_threads = 20
        created_ids = []
        errors = []

        def create_ticket_worker(worker_id: int):
            t_id = f"RF-CONCUR-{worker_id:04d}"
            payload = {
                "Ticket ID": t_id,
                "Agent": f"Concurrent Agency {worker_id}",
                "Route": "DEL-BOM",
                "Refund Amount (INR)": 1000.0 * worker_id,
                "Status": "Pending",
            }
            try:
                resp = test_client.post("/api/v1/support-tickets", json=payload)
                if resp.status_code == status.HTTP_201_CREATED:
                    return (True, t_id)
                else:
                    return (False, f"Status {resp.status_code}: {resp.text}")
            except Exception as ex:
                return (False, str(ex))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(create_ticket_worker, i) for i in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                ok, res = f.result()
                if ok:
                    created_ids.append(res)
                else:
                    errors.append(res)

        app.dependency_overrides.clear()

        assert len(errors) == 0, f"Concurrent insert errors encountered: {errors}"
        assert len(created_ids) == num_threads

        # Verify all records exist in DB
        verify_session = FileSessionLocal()
        count = verify_session.query(SupportTicket).count()
        verify_session.close()
        assert count == num_threads

    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass


def test_concurrent_read_write_race_condition():
    """
    Simultaneously execute rapid reads (GET /api/v1/support-tickets) while writes are happening on file-backed SQLite.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        file_engine = create_engine(
            f"sqlite:///{tmp_db_path}",
            connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(bind=file_engine)
        FileSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=file_engine)

        def file_get_db():
            db = FileSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = file_get_db
        test_client = TestClient(app)

        read_results = []
        write_results = []

        def read_task(i: int):
            resp = test_client.get("/api/v1/support-tickets", params={"limit": 50})
            return resp.status_code, len(resp.json())

        def write_task(i: int):
            resp = test_client.post("/api/v1/support-tickets", json={
                "Ticket ID": f"RF-RW-RACE-{i:03d}",
                "Agent": "Race Agency",
                "Refund Amount (INR)": 500.0,
                "Status": "Processing",
            })
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            read_futures = [executor.submit(read_task, i) for i in range(20)]
            write_futures = [executor.submit(write_task, i) for i in range(10)]

            for rf in concurrent.futures.as_completed(read_futures):
                read_results.append(rf.result())
            for wf in concurrent.futures.as_completed(write_futures):
                write_results.append(wf.result())

        app.dependency_overrides.clear()

        assert all(code == status.HTTP_200_OK for code, count in read_results)
        assert all(code == status.HTTP_201_CREATED for code in write_results)

    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass


# ===========================================================================
# 4. EDGE-CASE FILTERING, SQL INJECTION RESILIENCE, & PAGINATION TESTS
# ===========================================================================

@pytest.mark.parametrize("injection_payload", [
    "' OR '1'='1",
    "'; DROP TABLE support_tracker; --",
    "admin'--",
    "' UNION SELECT null, null, null, null, null, null, null, null, null, null --",
    "1; SELECT pg_sleep(5); --",
])
def test_sql_injection_resilience_in_filtering(client: TestClient, sample_support_ticket, injection_payload):
    """Verify that SQL injection patterns in query params are safely parameterized and do not execute."""
    # Test on status filter
    resp = client.get("/api/v1/support-tickets", params={"status": injection_payload})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []

    # Test on agent filter
    resp = client.get("/api/v1/support-tickets", params={"agent": injection_payload})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []

    # Test on search filter
    resp = client.get("/api/v1/support-tickets", params={"search": injection_payload})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []

    # Verify table is still intact and sample record exists
    resp_check = client.get(f"/api/v1/support-tickets/{sample_support_ticket.ticket_id}")
    assert resp_check.status_code == status.HTTP_200_OK


def test_pagination_extreme_boundaries(client: TestClient):
    """Verify pagination validation and boundary behavior across all endpoints."""
    # Negative skip -> 422 Unprocessable Entity
    resp = client.get("/api/v1/support-tickets", params={"skip": -1})
    assert resp.status_code == 422

    # Zero limit -> 422 Unprocessable Entity (limit ge=1)
    resp = client.get("/api/v1/support-tickets", params={"limit": 0})
    assert resp.status_code == 422

    # Overly large limit (> 1000) -> 422 Unprocessable Entity
    resp = client.get("/api/v1/support-tickets", params={"limit": 1001})
    assert resp.status_code == 422

    # Valid upper limit 1000
    resp = client.get("/api/v1/support-tickets", params={"limit": 1000})
    assert resp.status_code == status.HTTP_200_OK

    # Non-integer skip -> 422
    resp = client.get("/api/v1/support-tickets", params={"skip": "abc"})
    assert resp.status_code == 422


def test_case_insensitive_and_whitespace_search_across_entities(client: TestClient, manager_auth_headers: dict):
    """Verify case-insensitive search and trimming behavior across support, finance, and escalations."""
    client.post("/api/v1/support-tickets", json={
        "Ticket ID": "RF-SEARCH-TEST",
        "Agent": "Special Alpha Travels",
        "Route": "DEL-IXL-LEH",
        "Refund Amount (INR)": 8900.0,
        "Notes": "Special medical emergency refund request",
    })
    client.post("/api/v1/finance-records", json={
        "Ref No": "RF-SEARCH-TEST",
        "Agent Name": "Special Alpha Travels",
        "Sector": "DEL-IXL-LEH",
        "Amount Paid (INR)": 8900.0,
        "Remarks": "Medical documentation approved",
    }, headers=manager_auth_headers)
    client.post("/api/v1/escalations", json={
        "Escalation ID": "ESC-SEARCH-TEST",
        "Ticket ID": "RF-SEARCH-TEST",
        "Agent": "Special Alpha Travels",
        "Message": "Urgent review for medical case",
    })

    # Search with lower case
    resp1 = client.get("/api/v1/support-tickets", params={"search": "medical"})
    assert resp1.status_code == status.HTTP_200_OK
    assert len(resp1.json()) >= 1
    assert resp1.json()[0]["Ticket ID"] == "RF-SEARCH-TEST"

    # Search with upper case
    resp2 = client.get("/api/v1/finance-records", params={"search": "DOCUMENTATION"}, headers=manager_auth_headers)
    assert resp2.status_code == status.HTTP_200_OK
    assert len(resp2.json()) >= 1
    assert resp2.json()[0]["Ref No"] == "RF-SEARCH-TEST"


    # Search escalations with mixed case
    resp3 = client.get("/api/v1/escalations", params={"search": "uRgEnT"})
    assert resp3.status_code == status.HTTP_200_OK
    assert len(resp3.json()) >= 1
    assert resp3.json()[0]["Escalation ID"] == "ESC-SEARCH-TEST"


# ===========================================================================
# 5. PAYLOAD FUZZING & BOUNDARY CONSTRAINTS
# ===========================================================================

def test_extreme_numerical_values_in_crud(client: TestClient):
    """Verify handling of extreme numerical values in refund amounts and deductions."""
    payload = {
        "Ticket ID": "RF-EXTREME-NUM",
        "Agent": "Big Money Agency",
        "Refund Amount (INR)": 999999999.99,
        "Status": "Pending",
    }
    resp = client.post("/api/v1/support-tickets", json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["Refund Amount (INR)"] == 999999999.99

    # Zero refund amount
    patch_resp = client.patch("/api/v1/support-tickets/RF-EXTREME-NUM", json={"Refund Amount (INR)": 0.0})
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.json()["Refund Amount (INR)"] == 0.0


def test_unicode_and_special_character_payloads(client: TestClient):
    """Verify that unicode characters, emojis, and special symbols persist and retrieve without corruption."""
    unicode_notes = "Ref: ✈️ Passenger flight cancelled due to ⛈️ bad weather. हिंदी विवरण: टिकट रद्द।"
    payload = {
        "Ticket ID": "RF-UNICODE-01",
        "Agent": "Namastē Journeys 🇮🇳",
        "Route": "DEL-CCU",
        "Refund Amount (INR)": 4500.0,
        "Notes": unicode_notes,
    }
    resp = client.post("/api/v1/support-tickets", json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["Notes"] == unicode_notes
    assert resp.json()["Agent"] == "Namastē Journeys 🇮🇳"

    get_resp = client.get("/api/v1/support-tickets/RF-UNICODE-01")
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["Notes"] == unicode_notes


def test_idempotent_delete_and_subsequent_crud(client: TestClient):
    """Verify deleting an item twice returns 404 on the second call, and re-creation succeeds."""
    t_id = "RF-LIFECYCLE-01"
    client.post("/api/v1/support-tickets", json={"Ticket ID": t_id, "Agent": "Lifecycle Agent"})

    # First delete -> 200 OK
    resp1 = client.delete(f"/api/v1/support-tickets/{t_id}")
    assert resp1.status_code == status.HTTP_200_OK

    # Second delete -> 404 Not Found
    resp2 = client.delete(f"/api/v1/support-tickets/{t_id}")
    assert resp2.status_code == status.HTTP_404_NOT_FOUND

    # Re-create same ticket ID -> 201 Created
    resp3 = client.post("/api/v1/support-tickets", json={"Ticket ID": t_id, "Agent": "Reborn Agent"})
    assert resp3.status_code == status.HTTP_201_CREATED
    assert resp3.json()["Agent"] == "Reborn Agent"
