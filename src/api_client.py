"""
BharatTrip REST API Client for Streamlit Frontend.
Provides authenticated HTTP operations with automatic JWT Bearer token injection
from st.session_state, response interceptors for 401/403, and fallback error handling.
"""
import os
import logging
from typing import Any, Dict, List, Optional
import requests

try:
    import streamlit as st
except ImportError:
    class _DummySessionState(dict):
        def __getattr__(self, name):
            return self.get(name, None)
        def __setattr__(self, name, value):
            self[name] = value
    class _DummyStreamlit:
        session_state = _DummySessionState()
    st = _DummyStreamlit()


logger = logging.getLogger("bharattrip.client")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


class APIClient:
    """
    Centralized HTTP client communicating with the BharatTrip FastAPI backend.
    Automatically attaches active JWT access tokens from Streamlit session state.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or BACKEND_URL).rstrip("/")

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Builds default request headers including Bearer authorization if authenticated."""
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Automatically inject Bearer token from Streamlit session state if available
        try:
            if hasattr(st, "session_state") and "access_token" in st.session_state:
                token = st.session_state.get("access_token")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
        except Exception:
            pass

        if custom_headers:
            headers.update(custom_headers)

        return headers

    def _handle_response(self, response: requests.Response) -> requests.Response:
        """
        Intercepts HTTP responses for centralized error handling (e.g. session expiration on 401).
        """
        if response.status_code == 401:
            logger.warning("Received 401 Unauthorized from backend. Clearing active session.")
            try:
                if hasattr(st, "session_state"):
                    st.session_state["logged_in"] = False
                    st.session_state["access_token"] = None
                    st.session_state["role"] = None
                    st.session_state["user_profile"] = None
                    st.session_state["username"] = None
            except Exception:
                pass

        elif response.status_code == 403:
            logger.warning("Received 403 Forbidden from backend on %s", response.url)

        return response

    def _format_url(self, endpoint: str) -> str:
        """Formats complete URL ensuring clean prefix handling."""
        clean_endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{clean_endpoint}"

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15,
        **kwargs,
    ) -> requests.Response:
        """Sends an authenticated GET request."""
        url = self._format_url(endpoint)
        req_headers = self._get_headers(headers)
        try:
            resp = requests.get(url, params=params, headers=req_headers, timeout=timeout, **kwargs)
            return self._handle_response(resp)
        except requests.RequestException as err:
            logger.error("GET error on %s: %s", url, err)
            raise

    def post(
        self,
        endpoint: str,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **kwargs,
    ) -> requests.Response:
        """Sends an authenticated POST request."""
        url = self._format_url(endpoint)
        req_headers = self._get_headers(headers)
        try:
            resp = requests.post(url, json=json, data=data, params=params, headers=req_headers, timeout=timeout, **kwargs)
            return self._handle_response(resp)
        except requests.RequestException as err:
            logger.error("POST error on %s: %s", url, err)
            raise

    def patch(
        self,
        endpoint: str,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15,
        **kwargs,
    ) -> requests.Response:
        """Sends an authenticated PATCH request."""
        url = self._format_url(endpoint)
        req_headers = self._get_headers(headers)
        try:
            resp = requests.patch(url, json=json, data=data, headers=req_headers, timeout=timeout, **kwargs)
            return self._handle_response(resp)
        except requests.RequestException as err:
            logger.error("PATCH error on %s: %s", url, err)
            raise

    def put(
        self,
        endpoint: str,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15,
        **kwargs,
    ) -> requests.Response:
        """Sends an authenticated PUT request."""
        url = self._format_url(endpoint)
        req_headers = self._get_headers(headers)
        try:
            resp = requests.put(url, json=json, data=data, headers=req_headers, timeout=timeout, **kwargs)
            return self._handle_response(resp)
        except requests.RequestException as err:
            logger.error("PUT error on %s: %s", url, err)
            raise

    def delete(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15,
        **kwargs,
    ) -> requests.Response:
        """Sends an authenticated DELETE request."""
        url = self._format_url(endpoint)
        req_headers = self._get_headers(headers)
        try:
            resp = requests.delete(url, headers=req_headers, timeout=timeout, **kwargs)
            return self._handle_response(resp)
        except requests.RequestException as err:
            logger.error("DELETE error on %s: %s", url, err)
            raise

    def is_healthy(self) -> bool:
        """Checks if the FastAPI backend service is reachable and healthy."""
        try:
            resp = self.get("/health", timeout=3)
            return resp.status_code == 200 and resp.json().get("status") == "healthy"
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Core SSOT CRUD: Support Tickets
    # -----------------------------------------------------------------------
    def get_support_tickets(
        self,
        status: Optional[str] = None,
        agent: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """GET /api/v1/support-tickets"""
        params = {"status": status, "agent": agent, "search": search, "skip": skip, "limit": limit}
        params = {k: v for k, v in params.items() if v is not None}
        try:
            resp = self.get("/api/v1/support-tickets", params=params)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.error("get_support_tickets failed: %s", e)
            return []

    def get_support_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/support-tickets/{ticket_id}"""
        try:
            resp = self.get(f"/api/v1/support-tickets/{ticket_id}")
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            logger.error("get_support_ticket failed: %s", e)
            return None

    def create_support_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/v1/support-tickets"""
        resp = self.post("/api/v1/support-tickets", json=ticket_data)
        resp.raise_for_status()
        return resp.json()

    def update_support_ticket(self, ticket_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH /api/v1/support-tickets/{ticket_id}"""
        resp = self.patch(f"/api/v1/support-tickets/{ticket_id}", json=update_data)
        resp.raise_for_status()
        return resp.json()

    def delete_support_ticket(self, ticket_id: str) -> bool:
        """DELETE /api/v1/support-tickets/{ticket_id}"""
        try:
            resp = self.delete(f"/api/v1/support-tickets/{ticket_id}")
            return resp.status_code == 200
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Core SSOT CRUD: Finance Records (Manager Only)
    # -----------------------------------------------------------------------
    def get_finance_records(
        self,
        status: Optional[str] = None,
        agent_name: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """GET /api/v1/finance-records"""
        params = {"status": status, "agent_name": agent_name, "search": search, "skip": skip, "limit": limit}
        params = {k: v for k, v in params.items() if v is not None}
        try:
            resp = self.get("/api/v1/finance-records", params=params)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.error("get_finance_records failed: %s", e)
            return []

    def get_finance_record(self, ref_no: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/finance-records/{ref_no}"""
        try:
            resp = self.get(f"/api/v1/finance-records/{ref_no}")
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            logger.error("get_finance_record failed: %s", e)
            return None

    # -----------------------------------------------------------------------
    # Core SSOT CRUD: Escalations
    # -----------------------------------------------------------------------
    def get_escalations(
        self,
        status: Optional[str] = None,
        agent: Optional[str] = None,
        channel: Optional[str] = None,
        ticket_id: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """GET /api/v1/escalations"""
        params = {"status": status, "agent": agent, "channel": channel, "ticket_id": ticket_id, "search": search, "skip": skip, "limit": limit}
        params = {k: v for k, v in params.items() if v is not None}
        try:
            resp = self.get("/api/v1/escalations", params=params)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.error("get_escalations failed: %s", e)
            return []

    def get_escalation(self, escalation_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/escalations/{escalation_id}"""
        try:
            resp = self.get(f"/api/v1/escalations/{escalation_id}")
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            logger.error("get_escalation failed: %s", e)
            return None

    def update_escalation(self, escalation_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH /api/v1/escalations/{escalation_id}"""
        resp = self.patch(f"/api/v1/escalations/{escalation_id}", json=update_data)
        resp.raise_for_status()
        return resp.json()

    def delete_escalation(self, escalation_id: str) -> bool:
        """DELETE /api/v1/escalations/{escalation_id}"""
        try:
            resp = self.delete(f"/api/v1/escalations/{escalation_id}")
            return resp.status_code == 200
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Operations Metrics & RCA Endpoints (Feature 9)
    # -----------------------------------------------------------------------
    def get_dashboard_metrics(self, window: str = "All (Feb–Jun 2026)", agency: Optional[str] = None) -> Dict[str, Any]:
        """GET /api/v1/metrics/dashboard?window={window}"""
        params = {"window": window}
        if agency:
            params["agency"] = agency
        try:
            resp = self.get("/api/v1/metrics/dashboard", params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("get_dashboard_metrics failed: %s", e)
        return {
            "total_escalations": 0, "avg_ttr": 0.0, "dropped_handoffs": 0,
            "deduction_mismatches": 0, "total_pipeline": 0, "healthy_count": 0, "health_pct": 100.0,
            "financial_exposure_inr": 0.0, "open_escalations": 0, "pending_refunds": 0,
            "carriers": [], "at_risk_partners": [], "trend": [], "root_causes": [], "complaint_distribution": [],
            "corridor": {"intake_claims": 0, "audited_tickets": 0, "dropped_before_sync": 0, "clean_settlements": 0, "mismatch_count": 0}
        }

    def generate_ai_rca(self, window: str = "All") -> str:
        """POST /api/v1/metrics/rca-synthesis"""
        try:
            resp = self.post("/api/v1/metrics/rca-synthesis", json={"window": window})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("executive_summary") or data.get("summary", "")
        except Exception as e:
            logger.error("generate_ai_rca failed: %s", e)
        return "AI RCA synthesis unavailable."

    def get_trends(self, window: str = "All") -> Dict[str, Any]:
        """GET /api/v1/metrics/trends"""
        try:
            resp = self.get("/api/v1/metrics/trends", params={"window": window})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("get_trends failed: %s", e)
        return {"points": [], "summary": {}}

    def get_sla_breaches(self, current_date: str = "2026-06-30") -> Dict[str, Any]:
        """GET /api/v1/metrics/sla-breaches"""
        try:
            resp = self.get("/api/v1/metrics/sla-breaches", params={"current_date": current_date})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("get_sla_breaches failed: %s", e)
        return {"total_checked": 0, "breached_count": 0, "high_risk_count": 0, "items": []}

    # -----------------------------------------------------------------------
    # Reconciliation & HITL Endpoints (Feature 8)
    # -----------------------------------------------------------------------
    def get_reconciliation_mismatches(self, risk_level: Optional[str] = None) -> List[Dict[str, Any]]:
        """GET /api/v1/reconciliation/mismatches"""
        params = {"risk_level": risk_level} if risk_level else None
        try:
            resp = self.get("/api/v1/reconciliation/mismatches", params=params)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.error("get_reconciliation_mismatches failed: %s", e)
            return []

    def get_reconciliation_orphans(self) -> Dict[str, Any]:
        """GET /api/v1/reconciliation/orphans"""
        try:
            resp = self.get("/api/v1/reconciliation/orphans")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("get_reconciliation_orphans failed: %s", e)
        return {"missing_in_finance": [], "missing_in_support": [], "total_missing_finance": 0, "total_missing_support": 0}

    def get_reconciliation_summary(self) -> Dict[str, Any]:
        """GET /api/v1/reconciliation/summary"""
        try:
            resp = self.get("/api/v1/reconciliation/summary")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("get_reconciliation_summary failed: %s", e)
        return {"total_support_records": 0, "total_finance_records": 0, "total_mismatches": 0, "fleet_variance_inr": 0.0}

    def resolve_mismatch(
        self,
        ticket_id: str,
        new_status: str = "Client Notified",
        notes: Optional[str] = None,
        resolution_type: str = "Accept Deduction",
        adjusted_amount: Optional[float] = None,
        send_communication: bool = False,
        communication_draft: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/reconciliation/resolve-mismatch"""
        payload = {
            "ticket_id": ticket_id,
            "status": new_status,
            "notes": notes,
            "resolution_type": resolution_type,
            "adjusted_amount": adjusted_amount,
            "send_communication": send_communication,
            "communication_draft": communication_draft,
        }
        resp = self.post("/api/v1/reconciliation/resolve-mismatch", json=payload)
        resp.raise_for_status()
        return resp.json()

    def draft_reconciliation_explanation(self, mismatch_data: Dict[str, Any]) -> str:
        """POST /api/v1/reconciliation/draft-explanation"""
        payload = {
            "ticket_id": mismatch_data.get("ticket_id") or mismatch_data.get("Ticket ID", ""),
            "agent": mismatch_data.get("agent") or mismatch_data.get("Agent", ""),
            "route": mismatch_data.get("route") or mismatch_data.get("Route", "DEL-DXB"),
            "support_amount": float(mismatch_data.get("support_amount") or mismatch_data.get("Support Amount", 0.0)),
            "finance_amount": float(mismatch_data.get("finance_amount") or mismatch_data.get("Finance Amount", 0.0)),
            "deduction": float(mismatch_data.get("deduction") or mismatch_data.get("Deduction", 0.0)),
            "reason": mismatch_data.get("reason") or mismatch_data.get("Reason", ""),
        }
        try:
            resp = self.post("/api/v1/reconciliation/draft-explanation", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("draft_body") or data.get("draft", "")
        except Exception as e:
            logger.error("draft_reconciliation_explanation failed: %s", e)
        return ""

    def fuzzy_match_orphans(self) -> List[Dict[str, Any]]:
        """POST /api/v1/reconciliation/fuzzy-match-orphans"""
        try:
            resp = self.post("/api/v1/reconciliation/fuzzy-match-orphans")
            if resp.status_code == 200:
                return resp.json().get("matches", [])
        except Exception as e:
            logger.error("fuzzy_match_orphans failed: %s", e)
        return []

    def merge_orphan_linkage(self, support_ticket_id: str, finance_ref_no: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v1/reconciliation/link-orphan"""
        payload = {
            "support_ticket_id": support_ticket_id,
            "finance_ref_no": finance_ref_no,
            "notes": notes,
        }
        resp = self.post("/api/v1/reconciliation/link-orphan", json=payload)
        resp.raise_for_status()
        return resp.json()

    def send_proactive_alert(
        self,
        ticket_id: str,
        agent_name: str,
        route: str,
        stage: str = "Pending Bank Transfer",
        amount: Optional[str] = None,
        deduction: Optional[str] = None,
        channel: str = "WhatsApp",
    ) -> Dict[str, Any]:
        """POST /api/v1/reconciliation/proactive-notification"""
        payload = {
            "ticket_id": ticket_id,
            "agent_name": agent_name,
            "route": route,
            "stage": stage,
            "amount": amount,
            "deduction": deduction,
            "channel": channel,
        }
        resp = self.post("/api/v1/reconciliation/proactive-notification", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """GET /api/v1/audit/logs"""
        try:
            resp = self.get("/api/v1/audit/logs", params={"limit": limit})
            return resp.json() if resp.status_code == 200 else []
        except Exception:
            return []

    # -----------------------------------------------------------------------
    # Partner Health Matrix & Policy RAG (Feature 10)
    # -----------------------------------------------------------------------
    def get_partner_matrix(self) -> Dict[str, Any]:
        """GET /api/v1/partners/matrix"""
        try:
            resp = self.get("/api/v1/partners/matrix")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("get_partner_matrix failed: %s", e)
        return {"summary": {}, "partners": []}

    def get_partner_detail(self, agency_name: str) -> Dict[str, Any]:
        """GET /api/v1/partners/{agency_name}"""
        try:
            resp = self.get(f"/api/v1/partners/{agency_name}")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("get_partner_detail failed: %s", e)
        return {}

    def lookup_airline_policy(self, route: str, carrier: Optional[str] = None) -> Dict[str, Any]:
        """GET /api/v1/policy/airline-penalty?route={route}"""
        params = {"route": route}
        if carrier:
            params["carrier"] = carrier
        try:
            resp = self.get("/api/v1/policy/airline-penalty", params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("lookup_airline_policy failed: %s", e)
        return {
            "route": route,
            "carrier": carrier or "IndiGo / Air India",
            "cancellation_fee": 2000.0,
            "policy_notes": "Standard sector fare policy: flat ₹2,000 deduction.",
            "sla_hours": 24,
            "sector_type": "Domestic",
        }

    def dispatch_partner_outreach(self, agency_name: str, action_type: str = "VIP Reassurance", custom_note: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v1/partners/outreach"""
        try:
            resp = self.post("/api/v1/partners/outreach", json={"agency_name": agency_name, "outreach_type": action_type, "custom_note": custom_note})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("dispatch_partner_outreach failed: %s", e)
        return {"success": False, "message": "Failed to dispatch outreach"}

    def analyze_sentiment(self, message: str, agency_tier: str = "Standard") -> Dict[str, Any]:
        """POST /api/v1/partners/sentiment-analysis"""
        try:
            resp = self.post("/api/v1/partners/sentiment-analysis", json={"message": message, "agency_tier": agency_tier})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("analyze_sentiment failed: %s", e)
        return {
            "sentiment_score": 0.0,
            "urgency_level": "Medium",
            "priority_rank": "P3 - Standard",
            "frustration_category": "Routine Inquiry",
            "recommended_action": "Queue in Fast-Track Triage",
        }

    def predict_sla_breach(self, ticket_id: str, request_date: Optional[str] = None, status: str = "Pending") -> Dict[str, Any]:
        """POST /api/v1/policy/predict-sla-breach"""
        payload = {"ticket_id": ticket_id, "request_date": request_date, "status": status}
        try:
            resp = self.post("/api/v1/policy/predict-sla-breach", json=payload)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("predict_sla_breach failed: %s", e)
        return {"ticket_id": ticket_id, "is_breached": False, "hours_elapsed": 0, "risk_level": "Low", "warning": "OK"}

    # -----------------------------------------------------------------------
    # Ingestion & Triage Endpoints
    # -----------------------------------------------------------------------
    def parse_inbound_message(self, text: str, channel: str = "WhatsApp") -> Dict[str, Any]:
        """LangGraph API for inbound raw messages."""
        try:
            resp = self.post("/api/v1/escalations/resolve", json={
                "raw_message": text,
                "channel": channel,
                "agency_tier": "Standard"
            })
            if resp.status_code == 200:
                data = resp.json()
                entities = data.get("extracted_entities", {})
                entities["priority_rank"] = data.get("priority_rank")
                entities["urgency_level"] = data.get("urgency_level")
                entities["hitl_required"] = data.get("hitl_required")
                entities["hitl_reason"] = data.get("hitl_reason")
                entities["draft_response"] = data.get("draft_response")
                entities["audit_trace"] = data.get("audit_trace")
                return entities
        except Exception as e:
            logger.error("parse_inbound_message failed: %s", e)
        return {"error": "Failed to parse message via LangGraph API"}

    def draft_escalation_response(self, message: str, ssot_status: Optional[Dict[str, Any]] = None) -> str:
        """Drafts an escalation response using SSOT status."""
        ref_id = ssot_status.get("Ticket ID") or ssot_status.get("ticket_id", "Your ticket") if ssot_status else "your inquiry"
        route = ssot_status.get("Route") or ssot_status.get("route", "") if ssot_status else ""
        st_val = ssot_status.get("Status") or ssot_status.get("status", "Pending") if ssot_status else "Under Review"
        route_str = f" ({route})" if route else ""
        return f"Dear Partner, regarding ticket {ref_id}{route_str}: your refund status is currently '{st_val}'. Our operations team is actively processing it. Best regards, BharatTrip Operations."


# Global default client singleton
api_client = APIClient()
