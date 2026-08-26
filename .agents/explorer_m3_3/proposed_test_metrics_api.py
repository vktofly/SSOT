"""
Comprehensive Pytest Suite for Metrics & RCA REST API (Milestone 3).
Tests Cockpit KPIs, AI Root Cause Analysis, Time-Series Trends,
SLA Breach Forecaster, Carrier Performance, and RBAC Bounds.
"""
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.support import SupportTicket
from backend.app.models.escalation import Escalation
from backend.app.schemas.metrics import (
    DashboardMetricsResponse,
    RCAMetricsResponse,
    TrendsResponse,
    SLABreachResponse,
    CarrierPerformanceResponse,
)


# ===========================================================================
# 1. Authentication & RBAC Authorization Checks
# ===========================================================================

class TestMetricsRBAC:
    """Verifies that all metrics endpoints enforce strict Manager-only access."""

    METRICS_ENDPOINTS = [
        "/api/v1/metrics/dashboard",
        "/api/v1/metrics/rca",
        "/api/v1/metrics/trends",
        "/api/v1/metrics/sla-breaches",
        "/api/v1/metrics/carrier-performance",
    ]

    @pytest.mark.parametrize("endpoint", METRICS_ENDPOINTS)
    def test_unauthenticated_request_returns_401(self, client: TestClient, endpoint: str):
        """Verify unauthenticated requests to metrics endpoints return 401 Unauthorized."""
        resp = client.get(endpoint)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("endpoint", METRICS_ENDPOINTS)
    def test_operator_request_returns_403(self, client: TestClient, operator_auth_headers: dict, endpoint: str):
        """Verify Operator role requests to Manager-only metrics endpoints return 403 Forbidden."""
        resp = client.get(endpoint, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# 2. Manager Access & Typed Schema Validation
# ===========================================================================

class TestMetricsManagerEndpoints:
    """Verifies that Manager role successfully receives typed schema responses on all metrics routes."""

    def test_get_dashboard_metrics_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/dashboard returns valid DashboardMetricsResponse schema."""
        resp = client.get("/api/v1/metrics/dashboard", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = DashboardMetricsResponse.model_validate(data)
        assert validated.total_pipeline >= 0
        assert validated.total_escalations >= 0
        assert validated.avg_ttr >= 0.0
        assert 0.0 <= validated.health_pct <= 100.0
        assert validated.window_filter == "All (Feb–Jun 2026)"

    def test_get_dashboard_metrics_with_window_filter(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/dashboard?window=Last%2030%20Days applies temporal scaling."""
        resp = client.get("/api/v1/metrics/dashboard?window=Last 30 Days", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = DashboardMetricsResponse.model_validate(data)
        assert validated.window_filter == "Last 30 Days"

    def test_get_rca_metrics_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/rca returns valid RCAMetricsResponse schema."""
        resp = client.get("/api/v1/metrics/rca", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = RCAMetricsResponse.model_validate(data)
        assert validated.total_escalations >= 0
        assert isinstance(validated.top_agencies, dict)
        assert isinstance(validated.status_breakdown, dict)
        assert len(validated.executive_summary) > 0
        assert validated.avg_days_open >= 0.0

    def test_get_trends_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/trends returns valid TrendsResponse schema with ordered data points."""
        resp = client.get("/api/v1/metrics/trends", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = TrendsResponse.model_validate(data)
        assert isinstance(validated.points, list)
        if validated.points:
            p0 = validated.points[0]
            assert p0.date
            assert p0.total_tickets >= 0

    def test_get_sla_breaches_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/sla-breaches returns valid SLABreachResponse schema."""
        resp = client.get("/api/v1/metrics/sla-breaches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = SLABreachResponse.model_validate(data)
        assert validated.total_checked >= 0
        assert validated.breached_count >= 0
        for item in validated.items:
            assert item.ticket_id
            assert isinstance(item.is_breached, bool)
            assert item.risk_level in ["Low", "Medium", "High", "Resolved"]

    def test_get_carrier_performance_returns_200_and_typed_schema(self, client: TestClient, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/carrier-performance returns valid CarrierPerformanceResponse schema."""
        resp = client.get("/api/v1/metrics/carrier-performance", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = CarrierPerformanceResponse.model_validate(data)
        assert len(validated.carriers) >= 1
        for carrier in validated.carriers:
            assert carrier.carrier
            assert carrier.average_fee >= 0.0
            assert carrier.avg_sla_hours > 0


# ===========================================================================
# 3. Edge Cases & Resiliency Testing
# ===========================================================================

class TestMetricsEdgeCases:
    """Verifies edge cases: empty tables, malformed dates, resolved tickets in SLA checks."""

    def test_metrics_empty_database_returns_valid_fallbacks(self, client: TestClient, manager_auth_headers: dict):
        """Verify empty database returns valid zeroed/fallback metrics schema without throwing exceptions."""
        resp = client.get("/api/v1/metrics/dashboard", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["total_escalations"] == 0
        assert data["total_pipeline"] == 0

    def test_sla_breach_resolved_ticket_is_safe(self, db_session: Session, client: TestClient, manager_auth_headers: dict):
        """Verify resolved tickets (Status='Refund Done' or 'Settled') return is_breached=False and risk_level='Resolved'."""
        ticket = SupportTicket(
            ticket_id="RF-RESOLVED-01",
            agent="Agency Safe",
            request_date="01-01-2026",
            status="Refund Done"
        )
        db_session.add(ticket)
        db_session.commit()

        resp = client.get("/api/v1/metrics/sla-breaches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        items = resp.json().get("items", [])
        resolved_item = next((i for i in items if i.get("ticket_id") == "RF-RESOLVED-01" or i.get("Ticket ID") == "RF-RESOLVED-01"), None)
        assert resolved_item is not None
        assert resolved_item["is_breached"] is False
        assert resolved_item["risk_level"] == "Resolved"

    def test_sla_breach_delayed_ticket_flags_high_risk(self, db_session: Session, client: TestClient, manager_auth_headers: dict):
        """Verify ticket open for >72 hours flags is_breached=True and risk_level='High'."""
        ticket = SupportTicket(
            ticket_id="RF-DELAYED-01",
            agent="Agency Delayed",
            request_date="01-05-2026",  # Deep past date
            status="Pending"
        )
        db_session.add(ticket)
        db_session.commit()

        resp = client.get("/api/v1/metrics/sla-breaches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        items = resp.json().get("items", [])
        delayed_item = next((i for i in items if i.get("ticket_id") == "RF-DELAYED-01" or i.get("Ticket ID") == "RF-DELAYED-01"), None)
        assert delayed_item is not None
        assert delayed_item["is_breached"] is True
        assert delayed_item["risk_level"] == "High"

    def test_sla_breach_malformed_date_handled_gracefully(self, db_session: Session, client: TestClient, manager_auth_headers: dict):
        """Verify corrupted date string in request_date does not cause 500 error."""
        ticket = SupportTicket(
            ticket_id="RF-CORRUPTED-DATE",
            agent="Agency Corrupted",
            request_date="invalid-date-format-99-99-9999",
            status="Pending"
        )
        db_session.add(ticket)
        db_session.commit()

        resp = client.get("/api/v1/metrics/sla-breaches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        items = resp.json().get("items", [])
        corrupted_item = next((i for i in items if i.get("ticket_id") == "RF-CORRUPTED-DATE" or i.get("Ticket ID") == "RF-CORRUPTED-DATE"), None)
        assert corrupted_item is not None
        assert isinstance(corrupted_item["is_breached"], bool)
