"""
Comprehensive Pytest Suite for Partner Health & Policy RAG REST API (Milestone 3).
Tests Partner Churn Radar, NLP Sentiment Analysis, VIP Retention Matrix,
Airline Fare Policy Lookups, 72h Predictive SLA Breaches, and RBAC Boundaries.
"""
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.schemas.partners import (
    PartnerMatrixResponse,
    PartnerDetailResponse,
    PartnerSentimentAnalysisResponse,
    PartnerOutreachResponse,
    AirlinePolicyResponse,
    PolicyRuleListResponse,
    PredictSLABreachResponse,
)


# ===========================================================================
# 1. Authentication & RBAC Authorization Checks
# ===========================================================================

class TestPartnersRBAC:
    """Verifies RBAC rules: Matrix & Outreach are Manager-only; Policy & Sentiment accessible by Operator/Manager."""

    def test_matrix_unauthenticated_returns_401(self, client: TestClient):
        """Verify unauthenticated requests to partner matrix return 401 Unauthorized."""
        resp = client.get("/api/v1/partners/matrix")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_matrix_operator_returns_403(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role is forbidden (403) from accessing the VIP Partner Matrix."""
        resp = client.get("/api/v1/partners/matrix", headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_outreach_operator_returns_403(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role is forbidden (403) from dispatching VIP retention outreach."""
        payload = {"agency_name": "Peak Journeys", "action_type": "VIP Reassurance"}
        resp = client.post("/api/v1/partners/outreach", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_policies_accessible_by_operator(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role CAN access airline penalty rules (required for tier 1 triage support)."""
        resp = client.get("/api/v1/partners/policies", headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK

    def test_sentiment_accessible_by_operator(self, client: TestClient, operator_auth_headers: dict):
        """Verify Operator role CAN perform NLP sentiment analysis on inbound messages."""
        payload = {"message": "Where is my refund? It's been 2 weeks!", "agency_tier": "VIP"}
        resp = client.post("/api/v1/partners/sentiment-analysis", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK


# ===========================================================================
# 2. Manager Access & Typed Schema Validation
# ===========================================================================

class TestPartnersManagerEndpoints:
    """Verifies that Manager receives typed schema responses for partner intelligence routes."""

    def test_get_partner_matrix_returns_200_and_typed_schema(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/partners/matrix returns valid PartnerMatrixResponse schema."""
        resp = client.get("/api/v1/partners/matrix", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PartnerMatrixResponse.model_validate(data)
        assert validated.total_monitored_agencies >= 0
        assert validated.fleet_sentiment_index >= -1.0
        assert validated.fleet_sentiment_index <= 1.0
        assert isinstance(validated.partners, list)

        for partner in validated.partners:
            assert partner.agency_name
            assert partner.revenue_tier in ["VIP", "Strategic", "Standard"]
            assert partner.risk_status in ["CRITICAL (Immediate Churn Risk)", "ELEVATED (SLA Delay)", "STABLE", "OPTIMAL"]

    def test_get_partner_detail_by_agency(self, client: TestClient, seeded_db: Session, manager_auth_headers: dict):
        """Verify GET /api/v1/partners/{agency_name} returns agency detail schema."""
        resp = client.get("/api/v1/partners/Peak%20Journeys", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PartnerDetailResponse.model_validate(data)
        assert validated.agency_name == "Peak Journeys"
        assert validated.revenue_tier == "VIP"

    def test_post_partner_outreach_returns_200(self, client: TestClient, manager_auth_headers: dict):
        """Verify POST /api/v1/partners/outreach dispatches proactive retention communication."""
        payload = {
            "agency_name": "Peak Journeys",
            "outreach_type": "VIP Reassurance",
            "custom_note": "We have escalated your pending settlements directly to management."
        }
        resp = client.post("/api/v1/partners/outreach", json=payload, headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PartnerOutreachResponse.model_validate(data)
        assert validated.success is True
        assert validated.agency_name == "Peak Journeys"
        assert validated.action_taken is not None

    def test_post_sentiment_analysis(self, client: TestClient, operator_auth_headers: dict):
        """Verify POST /api/v1/partners/sentiment-analysis scores partner frustration accurately."""
        payload = {
            "message": "This is completely unacceptable! We are losing clients due to your delay!",
            "agency_tier": "VIP"
        }
        resp = client.post("/api/v1/partners/sentiment-analysis", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PartnerSentimentAnalysisResponse.model_validate(data)
        assert validated.sentiment_score < 0.0
        assert validated.urgency_level in ["Critical", "High"]
        assert "P0" in validated.priority_rank


# ===========================================================================
# 3. Airline Fare Policy RAG & Predictive SLA Breaches
# ===========================================================================

class TestAirlinePolicyEndpoints:
    """Verifies Airline Fare Policy Knowledge Base and 72-hour predictive breach detection."""

    def test_get_all_policies_returns_200_and_typed_schema(self, client: TestClient, operator_auth_headers: dict):
        """Verify GET /api/v1/partners/policies returns full catalog of airline cancellation tariffs."""
        resp = client.get("/api/v1/partners/policies", headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PolicyRuleListResponse.model_validate(data)
        assert validated.total >= 6
        assert len(validated.items) >= 6

    def test_get_policy_by_route_del_dxb(self, client: TestClient, operator_auth_headers: dict):
        """Verify GET /api/v1/partners/policies/DEL-DXB returns Emirates policy rules."""
        resp = client.get("/api/v1/partners/policies/DEL-DXB", headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = AirlinePolicyResponse.model_validate(data)
        assert validated.carrier == "Emirates"
        assert validated.cancellation_fee == 3500.0
        assert validated.sla_hours == 48

    def test_get_policy_unknown_route_returns_fallback(self, client: TestClient, operator_auth_headers: dict):
        """Verify GET /api/v1/partners/policies/XYZ-ABC returns intelligent domestic/general fallback tariff."""
        resp = client.get("/api/v1/partners/policies/XYZ-ABC", headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = AirlinePolicyResponse.model_validate(data)
        assert validated.cancellation_fee >= 0.0
        assert validated.is_registered is False

    def test_post_predict_sla_breach_high_risk(self, client: TestClient, operator_auth_headers: dict):
        """Verify POST /api/v1/policy/predict-sla-breach flags high latency tickets approaching breach."""
        payload = {
            "ticket_id": "RF-1099",
            "request_date": "01-05-2026",
            "status": "Pending",
            "current_date": "2026-06-30"
        }
        resp = client.post("/api/v1/policy/predict-sla-breach", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        validated = PredictSLABreachResponse.model_validate(data)
        assert validated.ticket_id == "RF-1099"
        assert validated.is_breached is True or validated.risk_level in ["High", "Medium"]


# ===========================================================================
# 4. Edge Cases & Resiliency
# ===========================================================================

class TestPartnersEdgeCases:
    """Verifies edge cases: empty strings, unknown agencies, and missing payload fields."""

    def test_sentiment_analysis_empty_message(self, client: TestClient, operator_auth_headers: dict):
        """Verify empty message does not crash NLP pipeline."""
        payload = {"message": "", "agency_tier": "Standard"}
        resp = client.post("/api/v1/partners/sentiment-analysis", json=payload, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["sentiment_score"] == 0.0

    def test_partner_detail_unregistered_agency(self, client: TestClient, manager_auth_headers: dict):
        """Verify query for agency with zero escalations returns default zero stats rather than 500 error."""
        resp = client.get("/api/v1/partners/Nonexistent%20Agency%20LLC", headers=manager_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["agency_name"] == "Nonexistent Agency LLC"
        assert data["active_escalations"] == 0
