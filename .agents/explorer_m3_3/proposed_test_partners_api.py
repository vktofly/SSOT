"""
Comprehensive Pytest Suite for Partner Health Matrix & Airline Policy REST API (Milestone 3).
Tests Partner Telemetry, Churn Risk Matrix, Sentiment Analysis, Proactive Outreach,
Airline Fare Policy RAG lookups, and RBAC / Security Bounds.
"""
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.schemas.partners import (
    PartnerMatrixResponse,
    PartnerSentimentAnalysisResponse,
    PartnerOutreachResponse,
    PolicyRuleResponse,
    PolicyRuleListResponse,
)


# ===========================================================================
# 1. Authentication & RBAC Authorization Checks
# ===========================================================================

class TestPartnersRBAC:
    """Verifies that all partner matrix and outreach endpoints enforce strict Manager-only access."""

    PARTNERS_ENDPOINTS = [
        "/api/v1/partners/matrix",
        "/api/v1/partners/policies",
    ]

    @pytest.mark.parametrize("endpoint", PARTNERS_ENDPOINTS)
    def test_unauthenticated_request_returns_401(self, client: TestClient, endpoint: str):
        """Verify unauthenticated requests to partner endpoints return 401 Unauthorized."""
        resp = client.get(endpoint)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_operator_request_to_matrix_returns_403(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role requests to Partner Matrix return 403 Forbidden."""
        resp = client.get("/api/v1/partners/matrix", headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_operator_request_to_outreach_returns_403(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role requests to trigger partner outreach return 403 Forbidden."""
        payload = {"agency_name": "Peak Journeys", "outreach_type": "VIP Reassurance"}
        resp = client.post("/api/v1/partners/outreach", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# 2. Manager Access & Typed Schema Validation
# ===========================================================================

class TestPartnersManagerEndpoints:
    """Verifies that Manager role successfully receives typed schema responses on all partner routes."""

    def test_get_partner_matrix_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/partners/matrix returns valid PartnerMatrixResponse schema."""
        resp = client.get("/api/v1/partners/matrix", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PartnerMatrixResponse.model_validate(data)
        assert validated.total_monitored_agencies >= 0
        assert validated.critical_vips_at_risk >= 0
        assert -1.0 <= validated.fleet_sentiment_index <= 1.0
        assert len(validated.dominant_complaint) > 0

        for partner in validated.partners:
            assert partner.agency_name
            assert partner.revenue_tier in ["VIP", "Strategic", "Standard"]
            assert -1.0 <= partner.sentiment_index <= 1.0
            assert partner.risk_status

    def test_post_sentiment_analysis_returns_200_and_typed_schema(self, client: TestClient, manager_auth_headers: dict):
        """Verify POST /api/v1/partners/sentiment-analysis evaluates tone and returns typed schema."""
        payload = {
            "message": "We have been waiting for two weeks. If refund is not processed today, our lawyer will file a police complaint.",
            "agency_name": "Peak Journeys",
            "agency_tier": "VIP"
        }
        resp = client.post("/api/v1/partners/sentiment-analysis", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PartnerSentimentAnalysisResponse.model_validate(data)
        assert validated.urgency_level == "Critical"
        assert validated.priority_rank == "P0 - Immediate"
        assert validated.sentiment_score < -0.6
        assert "Legal" in validated.frustration_category

    def test_post_partner_outreach_action(self, client: TestClient, manager_auth_headers: dict):
        """Verify POST /api/v1/partners/outreach dispatches action and returns confirmation schema."""
        payload = {
            "agency_name": "Peak Journeys",
            "outreach_type": "VIP Reassurance",
            "custom_note": "Account manager phone outreach scheduled."
        }
        resp = client.post("/api/v1/partners/outreach", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PartnerOutreachResponse.model_validate(data)
        assert validated.success is True
        assert validated.agency_name == "Peak Journeys"
        assert validated.outreach_type == "VIP Reassurance"

    def test_get_all_policy_rules(self, client: TestClient, manager_auth_headers: dict):
        """Verify GET /api/v1/partners/policies returns registered airline fare policies."""
        resp = client.get("/api/v1/partners/policies", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PolicyRuleListResponse.model_validate(data)
        assert validated.total >= 6
        assert any(p.route == "DEL-DXB" for p in validated.items)

    @pytest.mark.parametrize("route,expected_carrier,expected_fee,expected_sla", [
        ("DEL-DXB", "Emirates", 3500.0, 48),
        ("BLR-MAA", "IndiGo", 1500.0, 24),
        ("DEL-SIN", "Singapore Airlines", 4000.0, 48),
        ("DEL-BOM", "Air India", 2000.0, 24),
        ("COK-DXB", "Air India Express", 3000.0, 48),
        ("MAA-CMB", "SriLankan Airlines", 2500.0, 48),
    ])
    def test_get_policy_rule_by_route(self, client: TestClient, manager_auth_headers: dict, route: str, expected_carrier: str, expected_fee: float, expected_sla: int):
        """Verify GET /api/v1/partners/policies/{route} returns exact carrier and fee for registered sectors."""
        resp = client.get(f"/api/v1/partners/policies/{route}", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PolicyRuleResponse.model_validate(data)
        assert validated.route == route
        assert validated.carrier == expected_carrier
        assert validated.cancellation_fee == expected_fee
        assert validated.sla_hours == expected_sla
        assert validated.is_registered is True


# ===========================================================================
# 3. Edge Cases & Boundary Resiliency
# ===========================================================================

class TestPartnersEdgeCases:
    """Verifies edge cases: unregistered international/domestic routes, case-insensitivity, and sentiment edge cases."""

    def test_policy_lookup_unregistered_international_route(self, client: TestClient, manager_auth_headers: dict):
        """Verify unregistered international route (e.g. BOM-LHR) falls back to default international policy."""
        resp = client.get("/api/v1/partners/policies/BOM-LHR", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PolicyRuleResponse.model_validate(data)
        assert validated.cancellation_fee == 3500.0
        assert validated.sla_hours == 48
        assert validated.sector_type == "International"
        assert validated.is_registered is False

    def test_policy_lookup_unregistered_domestic_route(self, client: TestClient, manager_auth_headers: dict):
        """Verify unregistered domestic route (e.g. PNQ-GOI) falls back to default domestic policy."""
        resp = client.get("/api/v1/partners/policies/PNQ-GOI", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PolicyRuleResponse.model_validate(data)
        assert validated.cancellation_fee == 2000.0
        assert validated.sla_hours == 24
        assert validated.sector_type == "Domestic"
        assert validated.is_registered is False

    def test_policy_lookup_case_insensitive_and_whitespace(self, client: TestClient, manager_auth_headers: dict):
        """Verify lowercase and whitespace sector query (' del-dxb ') matches 'DEL-DXB' correctly."""
        resp = client.get("/api/v1/partners/policies/ del-dxb ", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["route"] == "DEL-DXB"
        assert data["carrier"] == "Emirates"

    def test_sentiment_analysis_empty_message_returns_baseline(self, client: TestClient, manager_auth_headers: dict):
        """Verify empty message returns Low urgency, P3 Standard rank, and positive/neutral score."""
        payload = {"message": "", "agency_tier": "Standard"}
        resp = client.post("/api/v1/partners/sentiment-analysis", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["urgency_level"] == "Low"
        assert data["priority_rank"] == "P3 - Standard"
        assert data["sentiment_score"] >= 0.0

    def test_sentiment_analysis_routine_inquiry(self, client: TestClient, manager_auth_headers: dict):
        """Verify routine status inquiry returns Medium urgency and Information Request category."""
        payload = {"message": "Hi, could you please provide a status update on RF-1001?", "agency_tier": "Standard"}
        resp = client.post("/api/v1/partners/sentiment-analysis", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["urgency_level"] == "Medium"
        assert data["frustration_category"] == "Information Request"
