"""
Comprehensive Pytest Suite for Reconciliation REST API (Milestone 3).
Tests Discrepancy & Reconciliation Services, Mismatch & Orphan Detection,
Resolution Actions, Batch Settle, and RBAC / Security Bounds.
"""
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.audit import AuditLog
from backend.app.schemas.reconciliation import (
    MismatchItem,
    MismatchListResponse,
    OrphanResponse,
    ReconciliationSummary,
    ResolveMismatchResponse,
    BatchResolveMismatchesResponse,
    AIEntityResolutionResponse,
    DraftReconciliationMessageResponse,
)


# ===========================================================================
# 1. Authentication & RBAC Authorization Checks
# ===========================================================================

class TestReconciliationRBAC:
    """Verifies that all reconciliation endpoints enforce strict Manager-only access."""

    RECON_ENDPOINTS_GET = [
        "/api/v1/reconciliation/mismatches",
        "/api/v1/reconciliation/orphans",
        "/api/v1/reconciliation/summary",
    ]

    @pytest.mark.parametrize("endpoint", RECON_ENDPOINTS_GET)
    def test_unauthenticated_request_returns_401(self, client: TestClient, endpoint: str):
        """Verify unauthenticated requests to reconciliation GET endpoints return 401 Unauthorized."""
        resp = client.get(endpoint)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("endpoint", RECON_ENDPOINTS_GET)
    def test_operator_request_returns_403(self, client: TestClient, operator_auth_headers: dict, endpoint: str):
        """Verify Operator role requests to Manager-only reconciliation GET endpoints return 403 Forbidden."""
        resp = client.get(endpoint, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_operator_denied_resolve_post_returns_403(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role is rejected with 403 when trying to settle a discrepancy."""
        payload = {"ticket_id": "RF-1001", "resolution_type": "Accept Deduction", "status": "Settled"}
        resp = client.post("/api/v1/reconciliation/resolve", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_operator_denied_batch_resolve_returns_403(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role is rejected with 403 when attempting batch reconciliation."""
        payload = {"ticket_ids": ["RF-1001", "RF-1002"], "resolution_type": "Accept Deduction"}
        resp = client.post("/api/v1/reconciliation/batch-resolve", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# 2. Manager Access & Typed Schema Validation
# ===========================================================================

class TestReconciliationManagerEndpoints:
    """Verifies that Manager role successfully receives typed schema responses on all reconciliation routes."""

    def test_get_mismatches_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/reconciliation/mismatches returns list of valid MismatchItem schemas."""
        resp = client.get("/api/v1/reconciliation/mismatches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Validate against Pydantic schema
        for item in data:
            validated = MismatchItem.model_validate(item)
            assert validated.ticket_id
            assert validated.support_amount >= 0.0
            assert validated.finance_amount >= 0.0
            assert validated.risk_level in ["Normal", "High"]

    def test_get_orphans_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/reconciliation/orphans returns valid OrphanResponse schema."""
        resp = client.get("/api/v1/reconciliation/orphans", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = OrphanResponse.model_validate(data)
        assert isinstance(validated.missing_in_finance, list)
        assert isinstance(validated.missing_in_support, list)
        assert validated.total_missing_finance >= 0
        assert validated.total_missing_support >= 0

    def test_get_summary_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/reconciliation/summary returns valid ReconciliationSummary schema."""
        resp = client.get("/api/v1/reconciliation/summary", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = ReconciliationSummary.model_validate(data)
        assert validated.total_support_records >= 0
        assert validated.total_finance_records >= 0
        assert validated.total_mismatches >= 0
        assert validated.fleet_variance_inr >= 0.0

    def test_resolve_mismatch_single_ticket(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify POST /api/v1/reconciliation/resolve settles discrepancy and creates audit log."""
        payload = {
            "ticket_id": "RF-1001",
            "resolution_type": "Accept Deduction",
            "status": "Settled",
            "notes": "Deduction accepted per airline tariff rules",
            "send_communication": True,
            "communication_draft": "We have accepted the cancellation penalty."
        }
        resp = client.post("/api/v1/reconciliation/resolve", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = ResolveMismatchResponse.model_validate(data)
        assert validated.success is True
        assert validated.ticket_id == "RF-1001"
        assert validated.new_status == "Settled"

        # Verify DB mutation
        ticket = seeded_db.query(SupportTicket).filter_by(ticket_id="RF-1001").first()
        assert ticket.status == "Settled"
        assert "Deduction accepted" in (ticket.notes or "")

        # Verify Audit Log entry
        audit = seeded_db.query(AuditLog).filter_by(action="RECONCILE_DISCREPANCY").first()
        assert audit is not None

    def test_batch_resolve_mismatches(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify POST /api/v1/reconciliation/batch-resolve updates multiple tickets simultaneously."""
        payload = {
            "ticket_ids": ["RF-1001", "RF-1002"],
            "resolution_type": "Accept Deduction",
            "status": "Client Notified",
            "auto_draft_explanations": True
        }
        resp = client.post("/api/v1/reconciliation/batch-resolve", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = BatchResolveMismatchesResponse.model_validate(data)
        assert validated.success is True
        assert validated.resolved_count >= 1

    def test_draft_reconciliation_message_endpoint(self, client: TestClient, manager_auth_headers: dict):
        """Verify POST /api/v1/reconciliation/draft-message returns valid AI draft communication schema."""
        payload = {
            "ticket_id": "RF-1001",
            "agent": "Peak Journeys",
            "route": "DEL-DXB",
            "support_amount": 15000.0,
            "finance_amount": 11500.0,
            "deduction": 3500.0,
            "reason": "Carrier penalty"
        }
        resp = client.post("/api/v1/reconciliation/draft-message", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = DraftReconciliationMessageResponse.model_validate(data)
        assert validated.ticket_id == "RF-1001"
        assert "3500" in validated.draft_body or "3,500" in validated.draft_body or "penalty" in validated.draft_body.lower()


# ===========================================================================
# 3. Edge Cases & Resiliency Testing
# ===========================================================================

class TestReconciliationEdgeCases:
    """Verifies edge cases: empty data, zero values, fuzzy matches, high risk scoring, and invalid payloads."""

    def test_mismatches_empty_database(self, client: TestClient, manager_auth_headers: dict):
        """Verify empty database returns empty mismatch list and zero summary without crashing."""
        resp = client.get("/api/v1/reconciliation/mismatches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []

        summary_resp = client.get("/api/v1/reconciliation/summary", headers=manager_auth_headers)
        assert summary_resp.status_code == status.HTTP_200_OK
        summary = summary_resp.json()
        assert summary["total_mismatches"] == 0
        assert summary["fleet_variance_inr"] == 0.0

    def test_resolve_nonexistent_ticket_returns_404(self, client: TestClient, manager_auth_headers: dict):
        """Verify resolving a non-existent ticket ID returns 404 Not Found."""
        payload = {"ticket_id": "RF-NONEXISTENT", "resolution_type": "Accept Deduction", "status": "Settled"}
        resp = client.post("/api/v1/reconciliation/resolve", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_resolve_invalid_payload_returns_422(self, client: TestClient, manager_auth_headers: dict):
        """Verify missing required ticket_id field returns 422 Unprocessable Entity."""
        payload = {"resolution_type": "Accept Deduction"}  # missing ticket_id
        resp = client.post("/api/v1/reconciliation/resolve", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_zero_amount_support_ticket_safe_division(self, db_session: Session, client: TestClient, manager_auth_headers: dict):
        """Verify zero refund amount in support record does not cause ZeroDivisionError and flags High risk."""
        s = SupportTicket(ticket_id="RF-ZERO-01", agent="Agency A", refund_amount=0.0, status="Pending")
        f = FinanceRecord(ref_no="RF-ZERO-01", agent_name="Agency A", amount_paid=2500.0, deduction=0.0, payout_status="Refund Done")
        db_session.add_all([s, f])
        db_session.commit()

        resp = client.get("/api/v1/reconciliation/mismatches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        items = resp.json()
        zero_item = next((i for i in items if i.get("ticket_id") == "RF-ZERO-01" or i.get("Ticket ID") == "RF-ZERO-01"), None)
        assert zero_item is not None
        assert zero_item.get("risk_level") == "High" or zero_item.get("Risk Level") == "High"

    def test_exact_amounts_produces_zero_mismatches(self, db_session: Session, client: TestClient, manager_auth_headers: dict):
        """Verify identical support and finance amounts generate no mismatch entries."""
        s = SupportTicket(ticket_id="RF-MATCH-01", agent="Agency A", refund_amount=5000.0, status="Refund Done")
        f = FinanceRecord(ref_no="RF-MATCH-01", agent_name="Agency A", amount_paid=5000.0, deduction=0.0, payout_status="Refund Done")
        db_session.add_all([s, f])
        db_session.commit()

        resp = client.get("/api/v1/reconciliation/mismatches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 0
