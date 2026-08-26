"""
Comprehensive Pytest Suite for Metrics & Telemetry REST API (Milestone 3).
Tests Dashboard Telemetry Calculations, Root Cause Analysis (RCA), Monthly Trends,
SLA Breach Risk Forecasting, Carrier Performance, and RBAC / Security Access.
"""
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.escalation import Escalation
from backend.app.schemas.metrics import (
    DashboardMetricsResponse,
    RCAMetricsResponse,
    RCASynthesisResponse,
    TrendsResponse,
    SLABreachResponse,
    CarrierPerformanceResponse,
)


# ===========================================================================
# 1. Authentication & RBAC Authorization Checks
# ===========================================================================

class TestMetricsRBAC:
    """Verifies that all metrics and analytics endpoints enforce Manager-only RBAC access."""

    METRICS_ENDPOINTS_GET = [
        "/api/v1/metrics/dashboard",
        "/api/v1/metrics/rca",
        "/api/v1/metrics/trends",
        "/api/v1/metrics/sla-breaches",
        "/api/v1/metrics/carrier-performance",
    ]

    @pytest.mark.parametrize("endpoint", METRICS_ENDPOINTS_GET)
    def test_unauthenticated_request_returns_401(self, client: TestClient, endpoint: str):
        """Verify unauthenticated requests to metrics GET endpoints return 401 Unauthorized."""
        resp = client.get(endpoint)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("endpoint", METRICS_ENDPOINTS_GET)
    def test_operator_request_returns_403(self, client: TestClient, operator_auth_headers: dict, endpoint: str):
        """Verify Operator role requests to Manager-only metrics GET endpoints return 403 Forbidden."""
        resp = client.get(endpoint, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_operator_denied_rca_synthesis_post_returns_403(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role is rejected with 403 when requesting on-demand AI RCA synthesis."""
        payload = {"window": "All", "focus_areas": ["Deductions", "Handoffs"]}
        resp = client.post("/api/v1/metrics/rca-synthesis", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# 2. Manager Access & Typed Schema Validation
# ===========================================================================

class TestMetricsManagerEndpoints:
    """Verifies that Manager role receives correctly formatted typed responses across all metrics routes."""

    def test_get_dashboard_metrics_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/dashboard returns valid DashboardMetricsResponse schema."""
        resp = client.get("/api/v1/metrics/dashboard", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = DashboardMetricsResponse.model_validate(data)
        assert validated.total_escalations >= 0
        assert validated.health_pct >= 0.0
        assert validated.corridor is not None
        assert validated.corridor.intake_claims >= 0
        assert len(validated.root_causes) >= 1
        assert len(validated.carriers) >= 1

    def test_get_dashboard_metrics_last_30_days_filter(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/dashboard?window=Last+30+Days filters KPIs proportionally."""
        resp_all = client.get("/api/v1/metrics/dashboard?window=All", headers=manager_auth_headers)
        resp_30 = client.get("/api/v1/metrics/dashboard?window=Last+30+Days", headers=manager_auth_headers)

        assert resp_all.status_code == status.HTTP_200_OK
        assert resp_30.status_code == status.HTTP_200_OK

        data_all = resp_all.json()
        data_30 = resp_30.json()

        # Last 30 days should reflect proportional reduction or specific date scope
        assert data_30["total_escalations"] <= data_all["total_escalations"]

    def test_get_rca_metrics_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/rca returns valid RCAMetricsResponse schema."""
        resp = client.get("/api/v1/metrics/rca", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = RCAMetricsResponse.model_validate(data)
        assert validated.total_escalations >= 0
        assert len(validated.executive_summary) > 10

    def test_post_rca_synthesis_returns_200_and_ai_summary(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify POST /api/v1/metrics/rca-synthesis generates on-demand operational narrative."""
        payload = {"window": "All", "focus_areas": ["Deductions", "Dropped Handoffs"]}
        resp = client.post("/api/v1/metrics/rca-synthesis", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = RCASynthesisResponse.model_validate(data)
        assert len(validated.executive_summary) > 10

    def test_get_trends_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/trends returns valid TrendsResponse schema."""
        resp = client.get("/api/v1/metrics/trends", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = TrendsResponse.model_validate(data)
        assert len(validated.points) >= 1

    def test_get_sla_breaches_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/sla-breaches returns list of high-latency escalations."""
        resp = client.get("/api/v1/metrics/sla-breaches", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = SLABreachResponse.model_validate(data)
        assert isinstance(validated.items, list)
        assert validated.total_checked >= 0

    def test_get_carrier_performance_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/metrics/carrier-performance returns carrier fee comparison."""
        resp = client.get("/api/v1/metrics/carrier-performance", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = CarrierPerformanceResponse.model_validate(data)
        assert len(validated.carriers) >= 1


# ===========================================================================
# 3. Edge Cases & Robustness
# ===========================================================================

class TestMetricsEdgeCases:
    """Verifies edge cases: empty tables, zero-value division, and boundary conditions."""

    def test_dashboard_metrics_empty_database_returns_defaults(self, client: TestClient, manager_auth_headers: dict):
        """Verify metrics calculations succeed with empty database and return safe default values."""
        resp = client.get("/api/v1/metrics/dashboard", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["total_escalations"] == 0
        assert data["health_pct"] >= 0.0

    def test_trends_empty_database(self, client: TestClient, manager_auth_headers: dict):
        """Verify trends response handles empty database without throwing 500 Internal Server Error."""
        resp = client.get("/api/v1/metrics/trends", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert isinstance(data["points"], list)
