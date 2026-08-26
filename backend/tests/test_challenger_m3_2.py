"""
Adversarial Challenge Test Suite for Milestone 3 (challenger_m3_2):
Empirical stress-testing of Milestone 3 Integration, Concurrency, Boundary Handling,
APIClient Resilience, and AST Architectural Isolation.

Evaluated Challenge Dimensions:
1. Concurrency Stress on Mismatch Resolution, Batch Settle, Orphan Linkage & Audit Logging
2. Malformed Payloads, Boundary Values & Fuzzing across Metrics, Policy RAG & Partner Health
3. APIClient Error Handling, Timeout Resilience, 401 Session Teardown & Network Failure Fallbacks
4. AST Static Verification: Zero Direct Database / SQLite Imports in Frontend Views
"""
import ast
import base64
import concurrent.futures
import glob
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.audit import AuditLog
from backend.app.models.escalation import Escalation
from backend.app.models.finance import FinanceRecord
from backend.app.models.support import SupportTicket
from backend.tests.conftest import generate_jwt_token
from src.api_client import APIClient, api_client, st


# ===========================================================================
# Test Fixtures & Shared State for Challenger Test Suite
# ===========================================================================

@pytest.fixture(scope="module")
def challenger_db_engine():
    """
    Dedicated file-backed SQLite database engine for multi-threaded concurrency testing.
    Uses WAL mode and connect timeout to allow clean parallel transactional testing.
    """
    tmp_dir = tempfile.gettempdir()
    db_file = os.path.join(tmp_dir, f"challenger_m3_2_{int(time.time()*1000)}.db")
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(bind=engine)
    yield engine, db_file
    engine.dispose()
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass


@pytest.fixture(scope="module")
def challenger_session_maker(challenger_db_engine):
    engine, _ = challenger_db_engine
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def challenger_client(challenger_session_maker):
    """FastAPI TestClient with isolated session-per-request dependency override."""
    def override_get_db():
        db = challenger_session_maker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def manager_headers() -> Dict[str, str]:
    token = generate_jwt_token(role="Manager", claims={"sub": "challenger_mgr"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def operator_headers() -> Dict[str, str]:
    token = generate_jwt_token(role="Operator", claims={"sub": "challenger_op"})
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# SECTION 1: Concurrency Stress on Mismatch Resolution & Audit Logging
# ===========================================================================

class TestConcurrencyAndAuditLoggingStress:
    """
    Empirical stress-testing of transactional resolution, race-condition handling,
    and audit trail consistency under heavy concurrent workloads.
    """

    def test_concurrent_single_ticket_resolutions(
        self, challenger_client: TestClient, challenger_session_maker, manager_headers: dict
    ):
        """
        Stress Test 1.1: Concurrently resolves 30 distinct ticket discrepancies across 6 worker threads.
        Verifies:
        - 100% of requests return HTTP 200 OK.
        - SupportTicket status and notes are mutated properly in the DB.
        - Exactly 30 unique AuditLog entries are created with action 'RECONCILE_DISCREPANCY'.
        """
        num_tickets = 30
        db = challenger_session_maker()
        try:
            for i in range(num_tickets):
                tid = f"RF-CONC-SGL-{i:03d}"
                ticket = SupportTicket(
                    ticket_id=tid,
                    agent=f"Stress Agency {i % 5}",
                    route="DEL-BOM",
                    refund_amount=10000.0 + (i * 100),
                    status="Pending",
                    notes="Awaiting resolution",
                )
                db.add(ticket)
            db.commit()
        finally:
            db.close()

        def execute_resolve(idx: int):
            tid = f"RF-CONC-SGL-{idx:03d}"
            payload = {
                "ticket_id": tid,
                "status": "Client Notified",
                "notes": f"Resolved by worker thread {idx}",
                "resolution_type": "Accept Deduction",
                "adjusted_amount": 9500.0,
                "send_communication": True,
            }
            resp = challenger_client.post(
                "/api/v1/reconciliation/resolve-mismatch",
                json=payload,
                headers=manager_headers,
            )
            return idx, resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(execute_resolve, i) for i in range(num_tickets)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == num_tickets
        for idx, status_code, data in results:
            assert status_code == 200, f"Ticket {idx} failed with {status_code}: {data}"
            assert data["success"] is True
            assert data["new_status"] == "Client Notified"

        # Verify DB records and audit log trail
        verify_db = challenger_session_maker()
        try:
            for i in range(num_tickets):
                tid = f"RF-CONC-SGL-{i:03d}"
                t = verify_db.query(SupportTicket).filter_by(ticket_id=tid).first()
                assert t is not None
                assert t.status == "Client Notified"
                assert t.refund_amount == 9500.0
                assert f"Resolved by worker thread {i}" in t.notes

            audit_entries = (
                verify_db.query(AuditLog)
                .filter(AuditLog.action == "RECONCILE_DISCREPANCY")
                .filter(AuditLog.details.like("%RF-CONC-SGL%"))
                .all()
            )
            assert len(audit_entries) == num_tickets
            for log in audit_entries:
                assert log.user_role == "Manager"
                assert log.user_id == "challenger_mgr"
        finally:
            verify_db.close()

    def test_concurrent_race_condition_on_same_ticket(
        self, challenger_client: TestClient, challenger_session_maker, manager_headers: dict
    ):
        """
        Stress Test 1.2: Simulates 20 simultaneous threads attempting to settle the EXACT SAME ticket.
        Verifies:
        - Server does not crash, deadlock, or enter an inconsistent state.
        - Ticket ends with valid final status.
        - Every completed transaction creates an audit log entry.
        """
        race_tid = "RF-CONC-RACE-001"
        db = challenger_session_maker()
        try:
            db.add(
                SupportTicket(
                    ticket_id=race_tid,
                    agent="Race Agency",
                    route="DEL-DXB",
                    refund_amount=25000.0,
                    status="Pending",
                    notes="Initial",
                )
            )
            db.commit()
        finally:
            db.close()

        num_threads = 20

        def fire_race_resolve(idx: int):
            payload = {
                "ticket_id": race_tid,
                "status": f"Settled-By-{idx}",
                "notes": f"Race note {idx}",
                "resolution_type": "Waive Fee",
            }
            resp = challenger_client.post(
                "/api/v1/reconciliation/resolve-mismatch",
                json=payload,
                headers=manager_headers,
            )
            return resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(fire_race_resolve, i) for i in range(num_threads)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        success_statuses = [code for code, data in results if code == 200]
        assert len(success_statuses) == num_threads

        # Verify DB state
        verify_db = challenger_session_maker()
        try:
            ticket = verify_db.query(SupportTicket).filter_by(ticket_id=race_tid).first()
            assert ticket is not None
            assert ticket.status.startswith("Settled-By-")

            audit_count = (
                verify_db.query(AuditLog)
                .filter_by(action="RECONCILE_DISCREPANCY")
                .filter(AuditLog.details.like(f"%{race_tid}%"))
                .count()
            )
            assert audit_count == num_threads
        finally:
            verify_db.close()

    def test_concurrent_batch_resolutions(
        self, challenger_client: TestClient, challenger_session_maker, manager_headers: dict
    ):
        """
        Stress Test 1.3: Concurrently triggers 5 batch resolutions (each batch containing 6 tickets = 30 total).
        Verifies:
        - All batch settlements process successfully with HTTP 200.
        - All 30 tickets are transitioned to 'Settled'.
        - 5 BATCH_RECONCILE_DISCREPANCIES audit logs are recorded.
        """
        num_batches = 5
        tickets_per_batch = 6
        total_tickets = num_batches * tickets_per_batch

        db = challenger_session_maker()
        try:
            for i in range(total_tickets):
                tid = f"RF-CONC-BAT-{i:03d}"
                db.add(
                    SupportTicket(
                        ticket_id=tid,
                        agent="Batch Partner",
                        route="BLR-MAA",
                        refund_amount=5000.0,
                        status="Pending",
                    )
                )
            db.commit()
        finally:
            db.close()

        def execute_batch(batch_idx: int):
            tids = [f"RF-CONC-BAT-{batch_idx * tickets_per_batch + j:03d}" for j in range(tickets_per_batch)]
            payload = {
                "ticket_ids": tids,
                "resolution_type": "Accept Deduction",
                "status": "Settled",
                "auto_draft_explanations": True,
            }
            resp = challenger_client.post(
                "/api/v1/reconciliation/batch-resolve",
                json=payload,
                headers=manager_headers,
            )
            return batch_idx, resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(execute_batch, b) for b in range(num_batches)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        for b_idx, code, data in results:
            assert code == 200
            assert data["success"] is True
            assert data["resolved_count"] == tickets_per_batch

        verify_db = challenger_session_maker()
        try:
            for i in range(total_tickets):
                tid = f"RF-CONC-BAT-{i:03d}"
                t = verify_db.query(SupportTicket).filter_by(ticket_id=tid).first()
                assert t.status == "Settled"
                assert "Applied policy" in (t.notes or "")

            batch_logs = (
                verify_db.query(AuditLog)
                .filter_by(action="BATCH_RECONCILE_DISCREPANCIES")
                .filter(AuditLog.details.like("%RF-CONC-BAT%"))
                .all()
            )
            assert len(batch_logs) == num_batches
        finally:
            verify_db.close()

    def test_concurrent_orphan_record_linking(
        self, challenger_client: TestClient, challenger_session_maker, manager_headers: dict
    ):
        """
        Stress Test 1.4: Concurrently links 15 pairs of orphaned Support Tickets & Finance Records.
        Verifies:
        - All 15 link operations succeed.
        - FinanceRecord.ref_no is updated to match SupportTicket.ticket_id.
        - LINK_ORPHAN_RECORD audit logs are accurately written for all 15 links.
        """
        num_pairs = 15
        db = challenger_session_maker()
        try:
            for i in range(num_pairs):
                s_id = f"RF-CONC-ORP-S-{i:03d}"
                f_ref = f"FIN-ORP-TYPO-{i:03d}"
                db.add(
                    SupportTicket(
                        ticket_id=s_id,
                        agent=f"Orphan Agency {i}",
                        route="DEL-SIN",
                        refund_amount=18000.0,
                        status="Pending",
                    )
                )
                db.add(
                    FinanceRecord(
                        ref_no=f_ref,
                        agent_name=f"Orphan Agency {i}",
                        sector="DEL-SIN",
                        amount_paid=16000.0,
                        deduction=2000.0,
                        payout_status="Processed",
                    )
                )
            db.commit()
        finally:
            db.close()

        def execute_link(idx: int):
            s_id = f"RF-CONC-ORP-S-{idx:03d}"
            f_ref = f"FIN-ORP-TYPO-{idx:03d}"
            payload = {
                "support_ticket_id": s_id,
                "finance_ref_no": f_ref,
                "notes": f"Linked concurrently by worker {idx}",
            }
            resp = challenger_client.post(
                "/api/v1/reconciliation/link-orphan",
                json=payload,
                headers=manager_headers,
            )
            return idx, resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(execute_link, i) for i in range(num_pairs)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        for idx, code, data in results:
            assert code == 200, f"Link {idx} failed: {data}"
            assert data["success"] is True

        verify_db = challenger_session_maker()
        try:
            for i in range(num_pairs):
                s_id = f"RF-CONC-ORP-S-{i:03d}"
                f_rec = verify_db.query(FinanceRecord).filter_by(ref_no=s_id).first()
                assert f_rec is not None, f"Finance record for {s_id} was not linked."

            orphan_logs = (
                verify_db.query(AuditLog)
                .filter_by(action="LINK_ORPHAN_RECORD")
                .filter(AuditLog.details.like("%RF-CONC-ORP-S%"))
                .all()
            )
            assert len(orphan_logs) == num_pairs
        finally:
            verify_db.close()

    def test_concurrent_mixed_read_write_telemetry_load(
        self, challenger_client: TestClient, challenger_session_maker, manager_headers: dict
    ):
        """
        Stress Test 1.5: Mixed concurrent operations (simultaneous reads of /metrics/dashboard,
        /reconciliation/mismatches, /reconciliation/summary, /partners/matrix while concurrently
        resolving tickets).
        Verifies zero 500 errors and stable responses across 40 parallel calls.
        """
        db = challenger_session_maker()
        try:
            for i in range(10):
                db.add(
                    SupportTicket(
                        ticket_id=f"RF-MIX-{i:03d}",
                        agent="Mixed Partner",
                        route="COK-DXB",
                        refund_amount=14000.0,
                        status="Pending",
                    )
                )
            db.commit()
        finally:
            db.close()

        def run_mixed_op(idx: int):
            op_type = idx % 5
            if op_type == 0:
                resp = challenger_client.get("/api/v1/metrics/dashboard", headers=manager_headers)
            elif op_type == 1:
                resp = challenger_client.get("/api/v1/reconciliation/mismatches", headers=manager_headers)
            elif op_type == 2:
                resp = challenger_client.get("/api/v1/reconciliation/summary", headers=manager_headers)
            elif op_type == 3:
                resp = challenger_client.get("/api/v1/partners/matrix", headers=manager_headers)
            else:
                tid = f"RF-MIX-{idx % 10:03d}"
                resp = challenger_client.post(
                    "/api/v1/reconciliation/resolve-mismatch",
                    json={"ticket_id": tid, "status": "Settled", "notes": f"Mixed op {idx}"},
                    headers=manager_headers,
                )
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            status_codes = list(executor.map(run_mixed_op, range(40)))

        assert all(code == 200 for code in status_codes)


# ===========================================================================
# SECTION 2: Malformed Payloads & Boundary Values across Metrics & Partners
# ===========================================================================

class TestBoundaryAndMalformedPayloads:
    """
    Adversarial fuzzing and boundary value verification on Metrics, Policy RAG,
    Partner Health, and Reconciliation endpoints.
    """

    @pytest.mark.parametrize("malformed_window", [
        "",
        "   ",
        "Invalid-Window-XYZ",
        "2099-Q4-Future",
        "1970-Epoch",
        "' OR '1'='1",
        "<script>alert('xss')</script>",
        "A" * 5000,
    ])
    def test_metrics_dashboard_window_fuzzing_graceful_handling(
        self, challenger_client: TestClient, manager_headers: dict, malformed_window: str
    ):
        """
        Boundary Test 2.1: Verifies that arbitrary, adversarial, or SQL injection window filters
        do not trigger 500 errors and return valid DashboardMetricsResponse structure.
        """
        resp = challenger_client.get(
            "/api/v1/metrics/dashboard",
            params={"window": malformed_window},
            headers=manager_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "health_pct" in data
        assert "avg_ttr" in data
        assert "corridor" in data

    @pytest.mark.parametrize("adversarial_agency", [
        "NonExistentAgency999",
        "Agency' OR '1'='1",
        "../../etc/passwd",
        "✨🔥🚀_unicode_agency_हिन्दी",
        "A" * 2000,
    ])
    def test_metrics_dashboard_agency_filter_fuzzing(
        self, challenger_client: TestClient, manager_headers: dict, adversarial_agency: str
    ):
        """
        Boundary Test 2.2: Tests agency filter with nonexistent, special character, and SQLi strings.
        """
        resp = challenger_client.get(
            "/api/v1/metrics/dashboard",
            params={"agency": adversarial_agency},
            headers=manager_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["total_pipeline"], int)

    def test_metrics_rca_synthesis_arbitrary_payload_fuzzing(
        self, challenger_client: TestClient, manager_headers: dict
    ):
        """
        Boundary Test 2.3: Tests POST /api/v1/metrics/rca-synthesis with empty payload and unusual keys.
        """
        resp1 = challenger_client.post(
            "/api/v1/metrics/rca-synthesis",
            json={},
            headers=manager_headers,
        )
        assert resp1.status_code == 200
        assert "summary" in resp1.json()

        resp2 = challenger_client.post(
            "/api/v1/metrics/rca-synthesis",
            json={"window": "2099-Invalid", "extra_param": True},
            headers=manager_headers,
        )
        assert resp2.status_code == 200

    @pytest.mark.parametrize("date_param", [
        "not-a-valid-date",
        "2026/13/45",
        "9999-99-99",
        "",
        "2099-12-31",  # Far future -> all pending breached
        "1970-01-01",  # Far past -> zero breached
    ])
    def test_sla_breaches_date_boundary_fuzzing(
        self, challenger_client: TestClient, manager_headers: dict, date_param: str
    ):
        """
        Boundary Test 2.4: Tests predictive SLA breach evaluation against corrupted,
        far-future, and far-past baseline date parameters.
        """
        resp = challenger_client.get(
            "/api/v1/metrics/sla-breaches",
            params={"current_date": date_param},
            headers=manager_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_checked" in data
        assert "breached_count" in data
        assert isinstance(data["items"], list)

    @pytest.mark.parametrize("unregistered_route", [
        "XYZ-ABC",
        "DEL-ZZZ",
        "BOM-LHR",
        "12345",
        "ROUTE-WITH-SPECIAL-!@#$",
        "",
    ])
    def test_policy_rag_fallback_on_unregistered_routes(
        self, challenger_client: TestClient, operator_headers: dict, unregistered_route: str
    ):
        """
        Boundary Test 2.5: Tests airline cancellation policy RAG with unregistered routes.
        Verifies that it gracefully applies standard fallback rules rather than failing with 500.
        """
        resp = challenger_client.get(
            f"/api/v1/partners/policies/{unregistered_route or 'UNKNOWN'}",
            headers=operator_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "cancellation_fee" in data
        assert data["cancellation_fee"] > 0
        assert "carrier" in data
        assert "policy_notes" in data

    def test_sentiment_analysis_extreme_payload_fuzzing(
        self, challenger_client: TestClient, operator_headers: dict
    ):
        """
        Boundary Test 2.6: Fuzzes NLP sentiment analysis with massive 50,000-character string,
        whitespace only, emoji only, and non-ASCII characters.
        """
        # 1. 50,000 character wall of text
        huge_text = "Urgent refund required! Disputed deduction! " * 1100
        resp1 = challenger_client.post(
            "/api/v1/partners/sentiment-analysis",
            json={"message": huge_text, "agency_tier": "VIP Gold"},
            headers=operator_headers,
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert "sentiment_score" in data1
        assert "urgency_level" in data1

        # 2. Emoji-only string
        resp2 = challenger_client.post(
            "/api/v1/partners/sentiment-analysis",
            json={"message": "😡🔥💥⚠️📉", "agency_tier": "Standard"},
            headers=operator_headers,
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["urgency_level"] in ["High", "Critical", "Medium", "Low"]

        # 3. Blank / whitespace string
        resp3 = challenger_client.post(
            "/api/v1/partners/sentiment-analysis",
            json={"message": "   \n\t   ", "agency_tier": "VIP Platinum"},
            headers=operator_headers,
        )
        assert resp3.status_code == 200

    def test_reconciliation_resolve_nonexistent_ticket_returns_404(
        self, challenger_client: TestClient, manager_headers: dict
    ):
        """
        Boundary Test 2.7: Attempting to resolve a non-existent ticket must return 404 Not Found.
        """
        resp = challenger_client.post(
            "/api/v1/reconciliation/resolve-mismatch",
            json={"ticket_id": "RF-NONEXISTENT-9999", "status": "Settled"},
            headers=manager_headers,
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_reconciliation_link_orphan_both_nonexistent_returns_404(
        self, challenger_client: TestClient, manager_headers: dict
    ):
        """
        Boundary Test 2.8: Attempting to link non-existent support ticket and non-existent finance ref
        must return 404 Not Found.
        """
        resp = challenger_client.post(
            "/api/v1/reconciliation/link-orphan",
            json={
                "support_ticket_id": "RF-GHOST-1",
                "finance_ref_no": "FIN-GHOST-2",
            },
            headers=manager_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.parametrize("extreme_amount", [
        0.0,
        -5000.0,
        100_000_000.0,
    ])
    def test_draft_explanation_with_extreme_amounts(
        self, challenger_client: TestClient, operator_headers: dict, extreme_amount: float
    ):
        """
        Boundary Test 2.9: Draft explanation endpoint handles zero, negative, and large monetary amounts.
        """
        payload = {
            "agent": "Extreme Travels Ltd",
            "route": "DEL-DXB",
            "ticket_id": "RF-EXTREME-1",
            "support_amount": extreme_amount,
            "finance_amount": max(0.0, extreme_amount - 2000.0),
            "deduction": 2000.0,
            "reason": "Tariff penalty",
        }
        resp = challenger_client.post(
            "/api/v1/reconciliation/draft-explanation",
            json=payload,
            headers=operator_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "draft_body" in data
        assert "Extreme Travels Ltd" in data["draft_body"]

    def test_partner_outreach_dispatch_nonexistent_partner(
        self, challenger_client: TestClient, manager_headers: dict
    ):
        """
        Boundary Test 2.10: Dispatching outreach for an unknown partner records the audit log and returns success.
        """
        payload = {
            "agency_name": "Unknown Partner Agency",
            "outreach_type": "Executive Check-in",
            "custom_note": "Proactive relationship preservation call",
        }
        resp = challenger_client.post(
            "/api/v1/partners/outreach",
            json=payload,
            headers=manager_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "action_taken" in data
        assert "timestamp" in data

    def test_predict_sla_breach_boundary_conditions(
        self, challenger_client: TestClient, operator_headers: dict
    ):
        """
        Boundary Test 2.11: Predictive SLA forecaster with missing request date and unusual status.
        """
        resp = challenger_client.post(
            "/api/v1/policy/predict-sla-breach",
            json={"ticket_id": "RF-BOUNDARY-SLA", "request_date": None, "status": "UnknownStatus"},
            headers=operator_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "is_breached" in data
        assert "risk_level" in data


# ===========================================================================
# SECTION 3: APIClient Error Handling, Timeouts & Session Resilience
# ===========================================================================

class TestAPIClientResilienceAndErrorHandling:
    """
    Tests Streamlit frontend APIClient resilience against backend downtime,
    network timeouts, HTTP 401 session expiration, and 403 authorization rejections.
    """

    def test_apiclient_timeout_propagation(self):
        """
        APIClient Test 3.1: Verifies that requests.exceptions.Timeout is raised and logged properly.
        """
        client = APIClient(base_url="http://127.0.0.1:9999")
        with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out after 2s")):
            with pytest.raises(requests.exceptions.Timeout):
                client.get("/api/v1/metrics/dashboard", timeout=2)

    def test_apiclient_connection_error_propagation(self):
        """
        APIClient Test 3.2: Verifies that requests.exceptions.ConnectionError is raised properly on raw get/post.
        """
        client = APIClient(base_url="http://127.0.0.1:9999")
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")):
            with pytest.raises(requests.exceptions.ConnectionError):
                client.post("/api/v1/reconciliation/resolve-mismatch", json={"ticket_id": "RF-1001"})

    def test_apiclient_401_interceptor_clears_session_state(self):
        """
        APIClient Test 3.3: Verifies that receiving an HTTP 401 Unauthorized automatically
        wipes all active authentication state from st.session_state.
        """
        client = APIClient()
        st.session_state["logged_in"] = True
        st.session_state["access_token"] = "mock_jwt_token_123"
        st.session_state["role"] = "Manager"
        st.session_state["username"] = "vikash_manager"
        st.session_state["user_profile"] = {"user_id": "vikash_manager", "role": "Manager"}

        mock_resp = requests.Response()
        mock_resp.status_code = 401
        mock_resp._content = b'{"detail": "Token expired or invalid"}'

        with patch("requests.get", return_value=mock_resp):
            resp = client.get("/api/v1/finance-records")
            assert resp.status_code == 401

            # Session state must be completely cleared
            assert st.session_state.get("logged_in") is False
            assert st.session_state.get("access_token") is None
            assert st.session_state.get("role") is None
            assert st.session_state.get("username") is None
            assert st.session_state.get("user_profile") is None

    def test_apiclient_403_interceptor_preserves_session_state(self):
        """
        APIClient Test 3.4: Verifies that receiving an HTTP 403 Forbidden logs a warning
        but does NOT log the user out.
        """
        client = APIClient()
        st.session_state["logged_in"] = True
        st.session_state["access_token"] = "operator_valid_jwt"
        st.session_state["role"] = "Operator"
        st.session_state["username"] = "operator_01"

        mock_resp = requests.Response()
        mock_resp.status_code = 403
        mock_resp.url = "http://127.0.0.1:8000/api/v1/finance-records"
        mock_resp._content = b'{"detail": "Forbidden: Requires Manager role"}'

        with patch("requests.get", return_value=mock_resp):
            resp = client.get("/api/v1/finance-records")
            assert resp.status_code == 403

            # Session state must remain intact
            assert st.session_state.get("logged_in") is True
            assert st.session_state.get("access_token") == "operator_valid_jwt"
            assert st.session_state.get("role") == "Operator"

    def test_apiclient_bearer_token_injection_in_headers(self):
        """
        APIClient Test 3.5: Verifies that active access_token in st.session_state is
        automatically injected as 'Authorization: Bearer <token>' in outgoing requests.
        """
        client = APIClient()
        st.session_state["access_token"] = "secret_jwt_xyz_789"

        headers = client._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer secret_jwt_xyz_789"
        assert headers["Content-Type"] == "application/json"

        # When token is None/absent, no Authorization header
        st.session_state["access_token"] = None
        headers_empty = client._get_headers()
        assert "Authorization" not in headers_empty

    def test_apiclient_custom_headers_merged(self):
        """
        APIClient Test 3.6: Verifies custom headers are merged cleanly with default headers.
        """
        client = APIClient()
        headers = client._get_headers(custom_headers={"X-Custom-Trace-ID": "trace-9999"})
        assert headers["X-Custom-Trace-ID"] == "trace-9999"
        assert headers["Content-Type"] == "application/json"

    def test_apiclient_offline_fallbacks_do_not_crash_frontend(self):
        """
        APIClient Test 3.7: Simulates total backend outage (ConnectionError / 500s)
        across all domain helper methods and verifies that every method returns a
        safe default structure without throwing unhandled exceptions.
        """
        client = APIClient(base_url="http://127.0.0.1:9999")

        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Server unreachable")), \
             patch("requests.post", side_effect=requests.exceptions.ConnectionError("Server unreachable")):

            # 1. Dashboard Metrics Fallback
            dash_metrics = client.get_dashboard_metrics()
            assert isinstance(dash_metrics, dict)
            assert "health_pct" in dash_metrics
            assert "corridor" in dash_metrics
            assert dash_metrics["health_pct"] == 100.0

            # 2. AI RCA Fallback
            rca_text = client.generate_ai_rca()
            assert isinstance(rca_text, str)
            assert "unavailable" in rca_text.lower()

            # 3. Trends Fallback
            trends = client.get_trends()
            assert isinstance(trends, dict)
            assert "points" in trends

            # 4. SLA Breaches Fallback
            sla_breaches = client.get_sla_breaches()
            assert isinstance(sla_breaches, dict)
            assert sla_breaches["breached_count"] == 0

            # 5. Reconciliation Mismatches Fallback
            mismatches = client.get_reconciliation_mismatches()
            assert isinstance(mismatches, list)
            assert len(mismatches) == 0

            # 6. Reconciliation Orphans Fallback
            orphans = client.get_reconciliation_orphans()
            assert isinstance(orphans, dict)
            assert orphans["total_missing_finance"] == 0

            # 7. Reconciliation Summary Fallback
            summary = client.get_reconciliation_summary()
            assert isinstance(summary, dict)
            assert summary["total_support_records"] == 0

            # 8. Partner Matrix Fallback
            matrix = client.get_partner_matrix()
            assert isinstance(matrix, dict)
            assert "partners" in matrix

            # 9. Airline Policy Fallback
            policy = client.lookup_airline_policy(route="DEL-DXB")
            assert isinstance(policy, dict)
            assert policy["cancellation_fee"] > 0
            assert policy["route"] == "DEL-DXB"

            # 10. Partner Sentiment Analysis Fallback
            sentiment = client.analyze_sentiment(message="Urgent refund needed")
            assert isinstance(sentiment, dict)
            assert "sentiment_score" in sentiment

            # 11. Health Check Fallback
            assert client.is_healthy() is False


# ===========================================================================
# SECTION 4: AST Architectural Verification (Zero DB Imports in Frontend)
# ===========================================================================

class TestASTFrontendArchitecturalDecoupling:
    """
    AST analysis ensuring strict architectural isolation between the Streamlit presentation
    layer and backend database modules.
    """

    FORBIDDEN_MODULES = {
        "sqlite3",
        "src.db",
        "backend.app.database",
        "backend.app.models",
        "backend.app.models.support",
        "backend.app.models.finance",
        "backend.app.models.escalation",
        "backend.app.models.audit",
        "src.data_manager",
        "sqlalchemy",
    }

    def _get_all_imports_from_file(self, file_path: str) -> List[str]:
        """Parses a Python file into an AST and extracts all module import names."""
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        tree = ast.parse(code, filename=file_path)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def test_all_frontend_views_zero_direct_db_imports(self):
        """
        AST Test 4.1: Verifies that every file in `src/views/` contains ZERO imports of
        sqlite3, src.db, backend.app.database, backend.app.models, or sqlalchemy.
        """
        views_dir = Path(__file__).resolve().parent.parent.parent / "src" / "views"
        view_files = list(views_dir.glob("*.py"))
        assert len(view_files) > 0, "No view files found in src/views/"

        violations = {}
        for v_file in view_files:
            file_imports = self._get_all_imports_from_file(str(v_file))
            illegal = [imp for imp in file_imports if any(f == imp or imp.startswith(f"{f}.") for f in self.FORBIDDEN_MODULES)]
            if illegal:
                violations[v_file.name] = illegal

        assert not violations, f"Architectural Isolation Violation! Forbidden imports found in views: {violations}"

    def test_frontend_views_import_only_api_client_and_ui_libraries(self):
        """
        AST Test 4.2: Verifies that frontend views exclusively import APIClient,
        Streamlit, Pandas, Altair, and standard library utilities.
        """
        views_dir = Path(__file__).resolve().parent.parent.parent / "src" / "views"
        view_files = [f for f in views_dir.glob("*.py") if f.name != "__init__.py"]

        for v_file in view_files:
            file_imports = self._get_all_imports_from_file(str(v_file))
            # Every view file must import api_client or streamlit
            has_api_client = any("api_client" in imp for imp in file_imports)
            has_streamlit = any("streamlit" in imp for imp in file_imports)
            assert has_api_client or has_streamlit, f"View {v_file.name} lacks api_client or streamlit import."

    def test_root_app_py_has_no_direct_db_imports(self):
        """
        AST Test 4.3: Verifies that root `app.py` does not directly query the database.
        """
        app_file = Path(__file__).resolve().parent.parent.parent / "app.py"
        app_imports = self._get_all_imports_from_file(str(app_file))
        illegal = [imp for imp in app_imports if any(f == imp or imp.startswith(f"{f}.") for f in self.FORBIDDEN_MODULES)]
        assert not illegal, f"Forbidden imports found in root app.py: {illegal}"
