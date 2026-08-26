"""
Empirical Challenger Test Suite for Milestone 1 (Backend Foundation & SQLite DB Migration).
Rigorous adversarial, boundary, fuzzing, and stress tests for:
1. Malformed and edge-case currency parsing & money representations.
2. SQL injection resilience across path params, query params, and JSON request bodies.
3. Duplicate primary keys, case variations, whitespace anomalies, and collision prevention.
4. Null bytes, control characters, multi-byte Unicode, and zero-width spaces.
5. Extreme pagination limits (negative, giant, boundary, invalid types).
6. Invalid data types, schema validation errors, and malformed payload recovery.
7. Multi-threaded SQLite concurrency and transaction rollback resilience.
"""
import math
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from backend.app.database import Base
from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.escalation import Escalation
from backend.app.scripts.seed_db import clean_money_string, clean_str, normalize_id, clean_agency_name


# ===========================================================================
# 1. Malformed Currencies & Money Parsing Stress Tests
# ===========================================================================

class TestCurrencyAndMoneyStress:
    """Stress test currency sanitization and API monetary field boundaries."""

    @pytest.mark.parametrize("raw_input,expected", [
        ("₹ 1,50,000.50", 150000.50),
        ("₹150000", 150000.0),
        ("INR 45,250", 45250.0),
        ("$12,345.67", 12345.67),
        ("€9,999.00", 0.0),       # Unsupported currency gracefully defaults to 0.0 without exception
        ("£500.50", 0.0),         # Unsupported currency gracefully defaults to 0.0 without exception
        ("¥1000", 0.0),           # Unsupported currency gracefully defaults to 0.0 without exception
        ("  25000.00  ", 25000.0),
        ("-₹5,000", -5000.0),     # Negative refund/deduction
        ("-1500.75", -1500.75),
        ("0001250.50", 1250.50),  # Leading zeros
        ("1e4", 10000.0),         # Scientific notation
        ("2.5e3", 2500.0),
        (15000, 15000.0),         # Direct int
        (1234.56, 1234.56),       # Direct float
        (0, 0.0),
        (0.0, 0.0),
        (None, 0.0),
        ("", 0.0),
        ("   ", 0.0),
        ("nan", 0.0),
        ("NaN", 0.0),
        ("null", 0.0),
        ("None", 0.0),
        ("-", 0.0),
        ("N/A", 0.0),
        ("FREE", 0.0),
        ("invalid_amount", 0.0),
        ("₹₹₹", 0.0),
        ("1.2.3.4", 0.0),
        (float("nan"), 0.0),
        (float("inf"), 0.0),
        (float("-inf"), 0.0),
    ])
    def test_clean_money_string_adversarial_inputs(self, raw_input, expected):
        """Verify clean_money_string returns expected float without throwing exceptions."""
        result = clean_money_string(raw_input)
        assert isinstance(result, float)
        assert math.isclose(result, expected, abs_tol=1e-4)

    def test_api_support_ticket_currency_payload_coercion(self, client: TestClient):
        """Verify API handles various monetary formats in JSON payload."""
        # 1. Standard float
        res1 = client.post("/api/v1/support-tickets", json={
            "Ticket ID": "RF-CH-001",
            "Agent": "Peak Journeys",
            "Refund Amount (INR)": 12500.50,
            "Status": "Pending"
        })
        assert res1.status_code == 201
        assert res1.json()["Refund Amount (INR)"] == 12500.50

        # 2. String float coercion by Pydantic
        res2 = client.post("/api/v1/support-tickets", json={
            "Ticket ID": "RF-CH-002",
            "Agent": "Peak Journeys",
            "Refund Amount (INR)": "15000.0",
            "Status": "Pending"
        })
        assert res2.status_code == 201
        assert res2.json()["Refund Amount (INR)"] == 15000.0

        # 3. Negative float (valid refund adjustment)
        res3 = client.post("/api/v1/support-tickets", json={
            "Ticket ID": "RF-CH-003",
            "Agent": "Peak Journeys",
            "Refund Amount (INR)": -500.0,
            "Status": "Pending"
        })
        assert res3.status_code == 201
        assert res3.json()["Refund Amount (INR)"] == -500.0

        # 4. Invalid non-numeric string rejected with 422
        res4 = client.post("/api/v1/support-tickets", json={
            "Ticket ID": "RF-CH-004",
            "Agent": "Peak Journeys",
            "Refund Amount (INR)": "ten thousand rupees",
            "Status": "Pending"
        })
        assert res4.status_code == 422


# ===========================================================================
# 2. SQL Injection Resilience Stress Tests
# ===========================================================================

class TestSqlInjectionResilience:
    """Stress test SQL injection payloads across all endpoints, parameters, and bodies."""

    SQLI_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE support_tracker; --",
        "1' UNION ALL SELECT 'a','b','c',1,2,'d','e','f','g','h' --",
        "' OR 1=1 --",
        "\" OR \"\"=\"",
        "admin'--",
        "admin' /*",
        "' OR '1'='1' ({",
        "' OR '1'='1' /*",
        "'; ATTACH DATABASE ':memory:' AS evil; --",
        "' UNION SELECT sqlite_version() --",
    ]

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_sqli_in_path_parameters(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict, payload: str):
        """Verify SQL injection payloads in path variables return 404 without SQL error."""
        # Support ticket path
        res_support = client.get(f"/api/v1/support-tickets/{payload}")
        assert res_support.status_code == 404
        assert "not found" in res_support.json()["detail"].lower()

        # Finance record path
        res_finance = client.get(f"/api/v1/finance-records/{payload}", headers=manager_auth_headers)
        assert res_finance.status_code == 404
        assert "not found" in res_finance.json()["detail"].lower()

        # Escalation path
        res_esc = client.get(f"/api/v1/escalations/{payload}")
        assert res_esc.status_code == 404
        assert "not found" in res_esc.json()["detail"].lower()

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_sqli_in_query_parameters(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict, payload: str):
        """Verify SQL injection payloads in query filters (search, status, agent) execute safely."""
        # Query search on support tickets
        res = client.get("/api/v1/support-tickets", params={"search": payload})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # Query filter on status
        res_status = client.get("/api/v1/support-tickets", params={"status": payload})
        assert res_status.status_code == 200
        assert isinstance(res_status.json(), list)

        # Query search on finance records
        res_fin = client.get("/api/v1/finance-records", params={"search": payload}, headers=manager_auth_headers)
        assert res_fin.status_code == 200
        assert isinstance(res_fin.json(), list)

        # Query search on escalations
        res_esc = client.get("/api/v1/escalations", params={"search": payload})
        assert res_esc.status_code == 200
        assert isinstance(res_esc.json(), list)

        # Ensure database tables are completely intact after attack payloads
        assert seeded_db.query(SupportTicket).count() > 0
        assert seeded_db.query(FinanceRecord).count() > 0
        assert seeded_db.query(Escalation).count() > 0


    def test_sqli_in_request_body_stored_as_literal_data(self, client: TestClient, seeded_db: Session):
        """Verify SQL injection string in body is stored as literal string and does not execute."""
        attack_body = {
            "Ticket ID": "RF-SQLI-001",
            "Agent": "Peak Journeys'); DROP TABLE support_tracker; --",
            "Route": "DEL-BOM",
            "Refund Amount (INR)": 5000.0,
            "Status": "Pending",
            "Notes": "Testing injection: ' OR 1=1; DELETE FROM support_tracker; --"
        }
        res = client.post("/api/v1/support-tickets", json=attack_body)
        assert res.status_code == 201
        created = res.json()
        assert created["Agent"] == "Peak Journeys'); DROP TABLE support_tracker; --"
        assert "DELETE FROM support_tracker" in created["Notes"]

        # Verify record retrieval returns literal string
        get_res = client.get("/api/v1/support-tickets/RF-SQLI-001")
        assert get_res.status_code == 200
        assert get_res.json()["Agent"] == attack_body["Agent"]

        # Verify table still exists and count is intact
        assert seeded_db.query(SupportTicket).count() > 0


# ===========================================================================
# 3. Duplicate Primary Keys, Case Normalization, & Collision Stress Tests
# ===========================================================================

class TestDuplicateKeyAndCollisionStress:
    """Stress test primary key uniqueness, normalization, and conflict handling."""

    def test_duplicate_support_ticket_id_case_insensitive(self, client: TestClient, sample_support_ticket: SupportTicket):
        """Verify duplicate ticket creation fails with 409 Conflict even with lowercase/whitespace."""
        # Exact duplicate
        res1 = client.post("/api/v1/support-tickets", json={
            "Ticket ID": "RF-9999",
            "Agent": "Peak Journeys",
            "Status": "Pending"
        })
        assert res1.status_code == 409
        assert "already exists" in res1.json()["detail"].lower()

        # Lowercase variation "rf-9999"
        res2 = client.post("/api/v1/support-tickets", json={
            "Ticket ID": "rf-9999",
            "Agent": "Peak Journeys",
            "Status": "Pending"
        })
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"].lower()

        # Whitespace padded "  RF-9999  "
        res3 = client.post("/api/v1/support-tickets", json={
            "Ticket ID": "  RF-9999  ",
            "Agent": "Peak Journeys",
            "Status": "Pending"
        })
        assert res3.status_code == 409

    def test_duplicate_finance_ref_no(self, client: TestClient, sample_finance_record: FinanceRecord, manager_auth_headers: dict):
        """Verify duplicate ref_no in finance records returns 409 Conflict."""
        res = client.post("/api/v1/finance-records", json={
            "Ref No": "rf-9999",
            "Agent Name": "Peak Journeys",
            "Payout Status": "Pending Payout"
        }, headers=manager_auth_headers)
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"].lower()

    def test_duplicate_escalation_id(self, client: TestClient, sample_escalation: Escalation):
        """Verify duplicate escalation_id in escalations returns 409 Conflict."""
        res = client.post("/api/v1/escalations", json={
            "Escalation ID": "esc-999",
            "Agent": "Peak Journeys",
            "Message": "Duplicate complaint test",
            "Status": "Open"
        })
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"].lower()

    def test_orm_level_duplicate_raises_integrity_error(self, db_session: Session, sample_support_ticket: SupportTicket):
        """Verify direct ORM duplicate insertion raises IntegrityError."""
        dup = SupportTicket(
            ticket_id="RF-9999",
            agent="Duplicate Agent",
            status="Pending"
        )
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ===========================================================================
# 4. Null Bytes, Control Characters, & Unicode Stress Tests
# ===========================================================================

class TestNullBytesAndUnicodeStress:
    """Stress test system resilience against null bytes, control codes, and Unicode."""

    @pytest.mark.parametrize("special_str", [
        "RF-TEST\x00NULL",                 # Embedded null byte
        "Peak\r\nJourneys\t\x01\x02",       # CRLF and ASCII control chars
        "Zero\u200bWidth\u200cSpace",       # Zero-width spaces
        "Unicode \u092d\u093e\u0930\u0924 (Bharat)", # Devanagari Hindi
        "Emoji ✈️ 🏨 💰 ⚠️ 🚀",             # Multi-byte emojis
        "RTL \u202eReversed Text\u202c",    # Right-to-left override
        "Quote \" ' ` -- ; /* */",          # Code delimiters
    ])
    def test_special_strings_in_support_ticket_fields(self, client: TestClient, special_str: str):
        """Verify special characters, null bytes, emojis, and Unicode strings are accepted and safely returned."""
        unique_id = f"RF-UNICODE-{abs(hash(special_str)) % 100000}"
        payload = {
            "Ticket ID": unique_id,
            "Agent": f"Agent {special_str}",
            "Route": "DEL-BOM",
            "Refund Amount (INR)": 5000.0,
            "Status": "Pending",
            "Notes": f"Notes with special content: {special_str}"
        }
        res = client.post("/api/v1/support-tickets", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["Ticket ID"] == unique_id
        assert special_str in data["Notes"]

        # Search query by special string
        search_res = client.get("/api/v1/support-tickets", params={"search": special_str})
        assert search_res.status_code == 200

    def test_clean_str_with_control_chars_and_whitespace(self):
        """Verify clean_str helper sanitizes whitespace variations and returns None for empty."""
        assert clean_str("   ") is None
        assert clean_str("\n\t\r ") is None
        assert clean_str("nan") is None
        assert clean_str("null") is None
        assert clean_str("  Valid String  ") == "Valid String"
        assert clean_str("Hello\x00World") == "Hello\x00World"

    def test_normalize_id_regex_handling(self):
        """Verify normalize_id accurately cleans space variations in IDs."""
        assert normalize_id("rf 1001") == "RF-1001"
        assert normalize_id("esc  801") == "ESC-801"
        assert normalize_id("  RF   2050  ") == "RF-2050"
        assert normalize_id("RF-3000") == "RF-3000"
        assert normalize_id("TICKET_123") == "TICKET_123"
        assert normalize_id(None) is None
        assert normalize_id("") is None


# ===========================================================================
# 5. Extreme Pagination Limits & Boundary Stress Tests
# ===========================================================================

class TestPaginationBoundariesAndExtremes:
    """Stress test query parameters for skip and limit boundaries."""

    def test_pagination_boundary_valid_limits(self, client: TestClient, seeded_db: Session):
        """Verify valid boundary limits (limit=1, limit=1000, skip=0)."""
        # Minimum valid limit
        res_min = client.get("/api/v1/support-tickets", params={"skip": 0, "limit": 1})
        assert res_min.status_code == 200
        assert len(res_min.json()) == 1

        # Maximum valid limit (1000)
        res_max = client.get("/api/v1/support-tickets", params={"skip": 0, "limit": 1000})
        assert res_max.status_code == 200
        assert len(res_max.json()) <= 1000

    @pytest.mark.parametrize("invalid_params,endpoint", [
        ({"limit": 0}, "/api/v1/support-tickets"),      # limit < 1
        ({"limit": -1}, "/api/v1/support-tickets"),     # limit negative
        ({"limit": 1001}, "/api/v1/support-tickets"),   # limit > 1000
        ({"skip": -1}, "/api/v1/support-tickets"),      # skip < 0
        ({"limit": "abc"}, "/api/v1/support-tickets"),  # non-integer limit
        ({"skip": "xyz"}, "/api/v1/support-tickets"),   # non-integer skip
        ({"limit": 1.5}, "/api/v1/support-tickets"),    # float limit
        ({"limit": 0}, "/api/v1/finance-records"),
        ({"limit": 1001}, "/api/v1/finance-records"),
        ({"skip": -5}, "/api/v1/finance-records"),
        ({"limit": 0}, "/api/v1/escalations"),
        ({"limit": 1001}, "/api/v1/escalations"),
        ({"skip": -10}, "/api/v1/escalations"),
    ])
    def test_pagination_invalid_parameters_return_422(self, client: TestClient, invalid_params: dict, endpoint: str, manager_auth_headers: dict):
        """Verify invalid pagination limits/skips return HTTP 422 Unprocessable Entity."""
        res = client.get(endpoint, params=invalid_params, headers=manager_auth_headers)
        assert res.status_code == 422

    def test_pagination_extreme_offset_returns_empty_list(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify massive skip returns empty list without error."""
        res = client.get("/api/v1/support-tickets", params={"skip": 1000000, "limit": 50})
        assert res.status_code == 200
        assert res.json() == []

        res_fin = client.get("/api/v1/finance-records", params={"skip": 1000000, "limit": 50}, headers=manager_auth_headers)
        assert res_fin.status_code == 200
        assert res_fin.json() == []

        res_esc = client.get("/api/v1/escalations", params={"skip": 1000000, "limit": 50})
        assert res_esc.status_code == 200
        assert res_esc.json() == []


# ===========================================================================
# 6. Invalid Data Types & Schema Robustness Stress Tests
# ===========================================================================

class TestSchemaRobustnessAndInvalidDataTypes:
    """Stress test schema validation, missing fields, type mismatches, and massive payloads."""

    def test_missing_required_fields_return_422(self, client: TestClient, manager_auth_headers: dict):
        """Verify omitting required fields (e.g. agent, ticket_id, message) returns 422."""
        # Missing agent in support ticket
        res1 = client.post("/api/v1/support-tickets", json={"Ticket ID": "RF-INV-01"})
        assert res1.status_code == 422

        # Missing ticket_id in support ticket
        res2 = client.post("/api/v1/support-tickets", json={"Agent": "Peak Journeys"})
        assert res2.status_code == 422

        # Missing ref_no in finance record
        res3 = client.post("/api/v1/finance-records", json={"Agent Name": "Peak Journeys"}, headers=manager_auth_headers)
        assert res3.status_code == 422

        # Missing message in escalation
        res4 = client.post("/api/v1/escalations", json={"Escalation ID": "ESC-INV-01", "Agent": "Peak Journeys"})
        assert res4.status_code == 422

    def test_empty_json_body_on_post_returns_422(self, client: TestClient, manager_auth_headers: dict):
        """Verify sending empty object on POST returns 422."""
        assert client.post("/api/v1/support-tickets", json={}).status_code == 422
        assert client.post("/api/v1/finance-records", json={}, headers=manager_auth_headers).status_code == 422
        assert client.post("/api/v1/escalations", json={}).status_code == 422

    def test_array_payload_instead_of_object_returns_422(self, client: TestClient):
        """Verify sending JSON array when JSON object is expected returns 422."""
        res = client.post("/api/v1/support-tickets", json=[{"Ticket ID": "RF-ARR-01", "Agent": "Peak"}])
        assert res.status_code == 422

    def test_massive_string_payload_stress(self, client: TestClient):
        """Verify system handles a 100,000 character notes/message payload without crashing."""
        giant_text = "Detailed escalation notes " + ("A" * 100000)
        res = client.post("/api/v1/support-tickets", json={
            "Ticket ID": "RF-GIANT-01",
            "Agent": "Peak Journeys",
            "Route": "DEL-BOM",
            "Refund Amount (INR)": 1000.0,
            "Status": "Pending",
            "Notes": giant_text
        })
        assert res.status_code == 201
        created = res.json()
        assert len(created["Notes"]) >= 100000

        # Retrieve again
        get_res = client.get("/api/v1/support-tickets/RF-GIANT-01")
        assert get_res.status_code == 200
        assert len(get_res.json()["Notes"]) >= 100000

    def test_patch_with_invalid_types_returns_422(self, client: TestClient, sample_support_ticket: SupportTicket):
        """Verify PATCH with invalid data types (e.g. array for status, string for refund_amount) returns 422."""
        res = client.patch(f"/api/v1/support-tickets/{sample_support_ticket.ticket_id}", json={
            "Refund Amount (INR)": "invalid_number_format"
        })
        assert res.status_code == 422

        res_obj = client.patch(f"/api/v1/support-tickets/{sample_support_ticket.ticket_id}", json={
            "Status": {"nested": "object"}
        })
        assert res_obj.status_code == 422


# ===========================================================================
# 7. SQLite Concurrency & Transaction Rollback Resilience
# ===========================================================================

class TestDatabaseConcurrencyAndRollback:
    """Stress test concurrent thread operations and transaction rollback isolation."""

    def test_multi_threaded_concurrent_inserts(self, tmp_path):
        """Verify 20 concurrent threads inserting unique tickets into SQLite database succeed."""
        db_file = str(tmp_path / "concurrent_test.db")
        concur_engine = create_engine(
            f"sqlite:///{db_file}",
            connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(bind=concur_engine)
        ConcurSession = sessionmaker(autocommit=False, autoflush=False, bind=concur_engine)

        errors = []
        successes = []

        def worker_insert(thread_idx: int):
            session = ConcurSession()
            try:
                ticket_id = f"RF-CONCUR-{thread_idx:04d}"
                ticket = SupportTicket(
                    ticket_id=ticket_id,
                    agent=f"Thread Agent {thread_idx}",
                    route="DEL-BOM",
                    refund_amount=float(thread_idx * 100),
                    status="Pending"
                )
                session.add(ticket)
                session.commit()
                successes.append(ticket_id)
            except Exception as e:
                errors.append((thread_idx, str(e)))
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker_insert, i) for i in range(20)]
            for f in futures:
                f.result()

        verify_session = ConcurSession()
        count = verify_session.query(SupportTicket).count()
        verify_session.close()

        assert len(errors) == 0, f"Encountered concurrency errors: {errors}"
        assert len(successes) == 20
        assert count == 20

    def test_transaction_rollback_preserves_database_state(self, db_session: Session):
        """Verify failed transaction rollback does not corrupt session or leave partial records."""
        initial_count = db_session.query(SupportTicket).count()

        # Step 1: Valid ticket added
        t1 = SupportTicket(ticket_id="RF-ROLLBACK-01", agent="Agent 1", status="Pending")
        db_session.add(t1)
        db_session.commit()
        assert db_session.query(SupportTicket).count() == initial_count + 1

        # Step 2: Attempt duplicate insert causing IntegrityError
        # Using a new transaction to test rollback
        t2 = SupportTicket(ticket_id="RF-ROLLBACK-01", agent="Duplicate Agent", status="Pending")
        db_session.add(t2)
        try:
            db_session.commit()
        except IntegrityError:
            db_session.rollback()

        # Step 3: Verify session is healthy and can perform further operations
        assert db_session.query(SupportTicket).count() == initial_count + 1
        t3 = SupportTicket(ticket_id="RF-ROLLBACK-02", agent="Agent 2", status="Pending")
        db_session.add(t3)
        db_session.commit()
        assert db_session.query(SupportTicket).count() == initial_count + 2
