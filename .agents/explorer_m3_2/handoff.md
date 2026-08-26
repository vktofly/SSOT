# Frontend Streamlit Views Migration Blueprint (Milestone 3)

## 1. Observation

Direct code examination of `app.py`, `src/api_client.py`, `src/data_manager.py`, `src/db.py`, `src/agents.py`, and `src/views/*` reveals the following architectural couplings:

### 1.1 `app.py` Root App State & Lifecycle Coupling
- **Line 5: `from src.data_manager import load_data`**
- **Lines 59-64**:
  ```python
  if 'support_df' not in st.session_state:
      sup, fin, esc = load_data()
      st.session_state.support_df = sup.copy()
      st.session_state.finance_df = fin.copy()
      st.session_state.escalations_df = esc.copy()
  ```
- **Lines 67-87**: Page functions pass in-memory pandas DataFrames to views:
  - `render_reconciliation(st.session_state.support_df, st.session_state.finance_df)`
  - `render_escalation_triage(st.session_state.escalations_df, st.session_state.support_df)`
  - `render_database_explorer(st.session_state.support_df, st.session_state.finance_df, st.session_state.escalations_df)`
  - `render_partner_matrix(st.session_state.escalations_df, st.session_state.support_df)`

### 1.2 `src/views/dashboard.py` Couplings
- **Lines 12-13**:
  ```python
  from src.agents import analyze_escalations
  from src.data_manager import find_mismatches, find_orphans
  ```
- **Lines 19-65**: `calculate_dashboard_metrics()` calculates KPI metrics by running `find_orphans(support_df, finance_df)` and `find_mismatches(support_df, finance_df)` in the frontend thread.
- **Lines 571-593, 609-687**: Directly computes pandas aggregations and hardcoded mock data for dispute trajectory, root cause breakdown, and complaint distribution charts.
- **Lines 691-698**: Calls `analyze_escalations(escalations_df)` to trigger direct Gemini/OpenAI API generation in the browser process.

### 1.3 `src/views/reconciliation.py` Couplings
- **Lines 12-17**:
  ```python
  from src.agents import (
      draft_reconciliation_message, batch_fuzzy_match_metadata,
      generate_proactive_notification, lookup_airline_penalty
  )
  from src.db import update_support_status, update_ticket_id
  from src.data_manager import find_mismatches, find_orphans
  ```
- **Lines 122, 390, 412**: Calls `update_support_status()` and `update_ticket_id()` from `src.db` to execute direct SQLite queries.
- **Lines 207-212**: Directly calls `draft_reconciliation_message()` from `src.agents`.
- **Lines 317**: Directly calls `batch_fuzzy_match_metadata()` from `src.agents`.
- **Lines 460-468**: Directly calls `generate_proactive_notification()` from `src.agents`.
- **Lines 191-192**: Directly calls `lookup_airline_penalty()` from `src.agents`.

### 1.4 `src/views/partner_matrix.py` Couplings
- **Line 3**: `from src.agents import analyze_partner_sentiment`
- **Lines 17-40**: Loops over `escalations_df.iterrows()` and executes `analyze_partner_sentiment()` per row inside the Streamlit render loop.
- **Lines 41-64**: Computes sentiment indices, category distributions, and churn risk tags on the frontend.

### 1.5 `src/views/ingestion.py` Couplings
- **Lines 16-17**:
  ```python
  from src.agents import parse_informal_message
  from src.db import insert_support_record
  ```
- **Lines 105, 230, 245**: Calls `parse_informal_message()` from `src.agents` for entity extraction and PII redaction.
- **Line 423**: Calls `insert_support_record(new_record)` from `src.db` to write to SQLite.
- **Lines 289-304**: Directly queries `st.session_state.support_df` for pre-match lookups.

### 1.6 `src/views/escalation_triage.py` Couplings
- **Lines 3-4**:
  ```python
  from src.agents import draft_escalation_response, analyze_partner_sentiment
  from src.db import delete_escalation
  ```
- **Lines 71-85**: Filters `support_df` in memory to check SSOT status.
- **Line 88**: Calls `analyze_partner_sentiment()` from `src.agents`.
- **Line 102**: Calls `draft_escalation_response()` from `src.agents`.
- **Line 115**: Calls `delete_escalation()` from `src.db` to delete from SQLite directly.

### 1.7 `src/views/database_explorer.py` Couplings
- **Lines 77-80**: Requires raw `support_df`, `finance_df`, and `escalations_df` as input arguments.
- **Lines 98-105**: Executes global search via pandas filtering across in-memory DataFrames.
- **Lines 11-30**: Performs manual string masking in the frontend rather than relying on backend RBAC/DLP.

### 1.8 `src/api_client.py` Current State
- Already implements authenticated HTTP methods (`get`, `post`, `patch`, `put`, `delete`, `is_healthy`, token injection from `st.session_state.access_token`, 401 interceptor clearing session state).
- Currently lacks domain-specific helper methods for Metrics, Reconciliation, Partner Matrix, Ingestion, and CRUD entity abstractions.

---

## 2. Logic Chain

1. **Decoupled Architecture Mandate**: Per `PROJECT.md` Feature 11 and `ORIGINAL_REQUEST.md` Requirement R2, Streamlit must act purely as a presentation layer. No frontend module may import `src.db` or `sqlite3`, nor perform local CSV/SQLite persistence or standalone LLM calls via `src.agents`.
2. **Centralized Data Access (`APIClient`)**: By encapsulating all HTTP calls in `src/api_client.py`, all network timeouts, bearer authentication headers, payload serialization, and response code error handling are centralized in one place.
3. **Session State Normalization**: Removing `load_data()` from `app.py` eliminates in-memory divergence where changes in one session or direct DB updates are not reflected in stale session state DataFrames.
4. **Resilient Error Handling**: Wrapping all API client interactions in Streamlit views with standard error banners and retry prompts ensures the UI remains operable even during transient backend disconnects or role permission denials (403 Forbidden).
5. **View Signature Decoupling**: Simplifying view entrypoints (`render_dashboard()`, `render_reconciliation()`, `render_partner_matrix()`, `render_ingestion()`, `render_escalation_triage()`, `render_database_explorer()`) to take zero arguments makes `app.py` declarative and modular.

---

## 3. Detailed Refactoring Blueprint

### 3.1 `src/api_client.py` Extended Method Specifications

The following typed domain methods must be added to `APIClient`:

```python
class APIClient:
    # Existing base HTTP methods (get, post, patch, put, delete, is_healthy) ...

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
        resp = self.get("/api/v1/support-tickets", params=params)
        return resp.json() if resp.status_code == 200 else []

    def get_support_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/support-tickets/{ticket_id}"""
        resp = self.get(f"/api/v1/support-tickets/{ticket_id}")
        return resp.json() if resp.status_code == 200 else None

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
        resp = self.delete(f"/api/v1/support-tickets/{ticket_id}")
        return resp.status_code == 200

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
        resp = self.get("/api/v1/finance-records", params=params)
        return resp.json() if resp.status_code == 200 else []

    def get_finance_record(self, ref_no: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/finance-records/{ref_no}"""
        resp = self.get(f"/api/v1/finance-records/{ref_no}")
        return resp.json() if resp.status_code == 200 else None

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
        resp = self.get("/api/v1/escalations", params=params)
        return resp.json() if resp.status_code == 200 else []

    def get_escalation(self, escalation_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/escalations/{escalation_id}"""
        resp = self.get(f"/api/v1/escalations/{escalation_id}")
        return resp.json() if resp.status_code == 200 else None

    def update_escalation(self, escalation_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH /api/v1/escalations/{escalation_id}"""
        resp = self.patch(f"/api/v1/escalations/{escalation_id}", json=update_data)
        resp.raise_for_status()
        return resp.json()

    def delete_escalation(self, escalation_id: str) -> bool:
        """DELETE /api/v1/escalations/{escalation_id}"""
        resp = self.delete(f"/api/v1/escalations/{escalation_id}")
        return resp.status_code == 200

    # -----------------------------------------------------------------------
    # Operations Metrics & RCA Endpoints (Feature 9)
    # -----------------------------------------------------------------------
    def get_dashboard_metrics(self, window: str = "All (Feb–Jun 2026)") -> Dict[str, Any]:
        """GET /api/v1/metrics/dashboard?window={window}"""
        resp = self.get("/api/v1/metrics/dashboard", params={"window": window})
        if resp.status_code == 200:
            return resp.json()
        return {
            "total_escalations": 0, "avg_ttr": 0.0, "dropped_handoffs": 0,
            "deduction_mismatches": 0, "total_pipeline": 0, "healthy_count": 0, "health_pct": 100.0,
            "carriers": [], "at_risk_partners": [], "trend": [], "root_causes": [], "complaint_distribution": []
        }

    def generate_ai_rca(self, window: str = "All") -> str:
        """POST /api/v1/metrics/rca-synthesis"""
        resp = self.post("/api/v1/metrics/rca-synthesis", json={"window": window})
        if resp.status_code == 200:
            return resp.json().get("summary", "")
        return "AI RCA synthesis unavailable."

    # -----------------------------------------------------------------------
    # Reconciliation & HITL Endpoints (Feature 8)
    # -----------------------------------------------------------------------
    def get_reconciliation_mismatches(self) -> List[Dict[str, Any]]:
        """GET /api/v1/reconciliation/mismatches"""
        resp = self.get("/api/v1/reconciliation/mismatches")
        return resp.json() if resp.status_code == 200 else []

    def get_reconciliation_orphans(self) -> Dict[str, List[Dict[str, Any]]]:
        """GET /api/v1/reconciliation/orphans"""
        resp = self.get("/api/v1/reconciliation/orphans")
        if resp.status_code == 200:
            return resp.json()
        return {"missing_in_finance": [], "missing_in_support": []}

    def resolve_mismatch(self, ticket_id: str, new_status: str, notes: str) -> Dict[str, Any]:
        """POST /api/v1/reconciliation/resolve-mismatch"""
        payload = {"ticket_id": ticket_id, "status": new_status, "notes": notes}
        resp = self.post("/api/v1/reconciliation/resolve-mismatch", json=payload)
        resp.raise_for_status()
        return resp.json()

    def draft_reconciliation_explanation(self, mismatch_data: Dict[str, Any]) -> str:
        """POST /api/v1/reconciliation/draft-explanation"""
        resp = self.post("/api/v1/reconciliation/draft-explanation", json=mismatch_data)
        return resp.json().get("draft", "") if resp.status_code == 200 else ""

    def fuzzy_match_orphans(self) -> List[Dict[str, Any]]:
        """POST /api/v1/reconciliation/fuzzy-match-orphans"""
        resp = self.post("/api/v1/reconciliation/fuzzy-match-orphans")
        return resp.json().get("matches", []) if resp.status_code == 200 else []

    def merge_orphan_linkage(self, support_ticket_id: str, finance_ref_no: str) -> Dict[str, Any]:
        """POST /api/v1/reconciliation/merge-orphan"""
        payload = {"support_ticket_id": support_ticket_id, "finance_ref_no": finance_ref_no}
        resp = self.post("/api/v1/reconciliation/merge-orphan", json=payload)
        resp.raise_for_status()
        return resp.json()

    def send_proactive_alert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/v1/reconciliation/proactive-alert"""
        resp = self.post("/api/v1/reconciliation/proactive-alert", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """GET /api/v1/audit/logs"""
        resp = self.get("/api/v1/audit/logs", params={"limit": limit})
        return resp.json() if resp.status_code == 200 else []

    # -----------------------------------------------------------------------
    # Partner Health Matrix & Policy RAG (Feature 10)
    # -----------------------------------------------------------------------
    def get_partner_matrix(self) -> Dict[str, Any]:
        """GET /api/v1/partners/matrix"""
        resp = self.get("/api/v1/partners/matrix")
        if resp.status_code == 200:
            return resp.json()
        return {"summary": {}, "partners": []}

    def lookup_airline_policy(self, route: str, carrier: Optional[str] = None) -> Dict[str, Any]:
        """GET /api/v1/partners/policy?route={route}"""
        params = {"route": route}
        if carrier:
            params["carrier"] = carrier
        resp = self.get("/api/v1/partners/policy", params=params)
        return resp.json() if resp.status_code == 200 else {}

    def dispatch_partner_outreach(self, agency_name: str, action_type: str) -> Dict[str, Any]:
        """POST /api/v1/partners/outreach"""
        resp = self.post("/api/v1/partners/outreach", json={"agency_name": agency_name, "action_type": action_type})
        return resp.json() if resp.status_code == 200 else {}

    # -----------------------------------------------------------------------
    # Ingestion & Triage Endpoints
    # -----------------------------------------------------------------------
    def parse_inbound_message(self, text: str, channel: str = "WhatsApp") -> Dict[str, Any]:
        """POST /api/v1/ingestion/parse"""
        resp = self.post("/api/v1/ingestion/parse", json={"text": text, "channel": channel})
        resp.raise_for_status()
        return resp.json()

    def draft_escalation_response(self, message: str, ssot_status: Dict[str, Any]) -> str:
        """POST /api/v1/escalations/draft-response"""
        resp = self.post("/api/v1/escalations/draft-response", json={"message": message, "ssot_status": ssot_status})
        return resp.json().get("draft", "") if resp.status_code == 200 else ""
```

---

### 3.2 View-by-View Refactoring Blueprints

#### 1. `app.py` Refactoring
- **Action**: Remove `load_data()` from `app.py`.
- **Change**: Replace DataFrame-passing page wrappers with zero-argument invocations:
  ```python
  def page_dashboard():
      require_role(["Manager"])
      render_dashboard()

  def page_ingestion():
      render_ingestion()

  def page_reconciliation():
      require_role(["Manager"])
      render_reconciliation()

  def page_triage():
      render_escalation_triage()

  def page_database():
      render_database_explorer()

  def page_partners():
      require_role(["Manager"])
      render_partner_matrix()
  ```

#### 2. `src/views/dashboard.py` Refactoring
- **Action**: Remove imports of `src.agents` and `src.data_manager`. Import `from src.api_client import api_client`.
- **Blueprint**:
  - `render_dashboard()` fetches `metrics = api_client.get_dashboard_metrics(window=selected_window)`.
  - If `metrics` is empty / backend unreachable, displays `st.error("⚠️ Backend API unavailable. Unable to load live metrics.")` with retry button.
  - KPI Hero Gauge and Stat Cards bind to `metrics["health_pct"]`, `metrics["total_escalations"]`, `metrics["avg_ttr"]`, `metrics["deduction_mismatches"]`, `metrics["healthy_count"]`, `metrics["total_pipeline"]`.
  - `render_analytics()` binds directly to `metrics["at_risk_partners"]`, `metrics["trend"]`, `metrics["root_causes"]`, and `metrics["complaint_distribution"]`.
  - `run_ai_rca()` calls `api_client.generate_ai_rca(window=selected_window)`.

#### 3. `src/views/reconciliation.py` Refactoring
- **Action**: Remove imports of `src.agents`, `src.db`, and `src.data_manager`. Import `from src.api_client import api_client`.
- **Blueprint**:
  - Signature becomes `def render_reconciliation() -> None:`.
  - Fetches `raw_mismatches = api_client.get_reconciliation_mismatches()`.
  - Fetches `orphans = api_client.get_reconciliation_orphans()` (`missing_in_finance = orphans["missing_in_finance"]`, `missing_in_support = orphans["missing_in_support"]`).
  - Approval action in `render_mismatch_studio()` calls `api_client.resolve_mismatch(ticket_id, new_status="Client Notified", notes=...)`.
  - AI email draft calls `api_client.draft_reconciliation_explanation(mismatch_record)`.
  - Fare rules lookup calls `api_client.lookup_airline_policy(route_str)`.
  - AI fuzzy matching calls `api_client.fuzzy_match_orphans()`.
  - Linkage merge calls `api_client.merge_orphan_linkage(support_ticket_id, finance_ref_no)`.
  - Proactive dispatch calls `api_client.send_proactive_alert(...)`.
  - Audit log table fetches `api_client.get_audit_logs()`.

#### 4. `src/views/partner_matrix.py` Refactoring
- **Action**: Remove import of `src.agents`. Import `from src.api_client import api_client`.
- **Blueprint**:
  - Signature becomes `def render_partner_matrix() -> None:`.
  - Fetches `data = api_client.get_partner_matrix()`.
  - Telemetry cards render `data["summary"]["monitored_agencies"]`, `data["summary"]["critical_vips"]`, `data["summary"]["fleet_sentiment"]`, `data["summary"]["dominant_complaint"]`.
  - Leaderboard renders `pd.DataFrame(data["partners"])`.
  - Fast-track action buttons trigger `api_client.dispatch_partner_outreach(selected_agency, action_type="VIP Reassurance")`.

#### 5. `src/views/ingestion.py` Refactoring
- **Action**: Remove imports of `src.agents` and `src.db`. Import `from src.api_client import api_client`.
- **Blueprint**:
  - Inbound raw message test and parse buttons call `api_client.parse_inbound_message(custom_text, custom_channel)`.
  - Pre-match lookup calls `api_client.get_support_tickets(search=ref_id_val)`.
  - Committing to SSOT calls `api_client.create_support_ticket(new_record)`.

#### 6. `src/views/escalation_triage.py` Refactoring
- **Action**: Remove imports of `src.agents` and `src.db`. Import `from src.api_client import api_client`.
- **Blueprint**:
  - Signature becomes `def render_escalation_triage() -> None:`.
  - Fetches escalations via `api_client.get_escalations(search=search_query)`.
  - Cross-references ticket status with `api_client.get_support_ticket(ticket_id)`.
  - AI response draft calls `api_client.draft_escalation_response(msg_text, status_dict)`.
  - "Approve & Send" calls `api_client.delete_escalation(escalation_id)` or `api_client.update_escalation(escalation_id, {"status": "Resolved"})`.

#### 7. `src/views/database_explorer.py` Refactoring
- **Action**: Remove parameters `support_df, finance_df, escalations_df`. Import `from src.api_client import api_client`.
- **Blueprint**:
  - Signature becomes `def render_database_explorer() -> None:`.
  - Fetches records on demand via:
    - `api_client.get_support_tickets(search=search_query)`
    - `api_client.get_finance_records(search=search_query)` (if Manager; if Operator, tab indicates Manager-only or shows masked items)
    - `api_client.get_escalations(search=search_query)`
  - Masking is provided by backend DLP with frontend safety fallback.

---

## 4. Caveats

- Backend endpoints for `/api/v1/reconciliation/*`, `/api/v1/metrics/*`, and `/api/v1/partners/*` are being developed in parallel (Milestone 3 backend track).
- During test and verification, if the backend server is running in mock mode or standalone, `APIClient` methods should provide graceful defaults to avoid rendering crashes.

---

## 5. Conclusion

1. Direct CSV reads, local SQLite calls (`src.db`), and frontend LLM invocations (`src.agents`) across all 6 views in `src/views/` can be decoupled into clean, typed REST calls via `src/api_client.py`.
2. `app.py` state initialization can be stripped of local DataFrame loads, enabling true multi-user, synchronized client-server operation.
3. Adding the specified ~20 domain methods to `APIClient` provides a clean contract matching backend routers.

---

## 6. Verification Method

1. **Verify No Direct DB / Local Ingestion Imports**:
   ```powershell
   python -c "import ast, glob; [print(f, [n.names[0].name for n in ast.walk(ast.parse(open(f, encoding='utf-8').read())) if isinstance(n, (ast.Import, ast.ImportFrom)) if hasattr(n, 'module') and n.module in ['src.db', 'src.data_manager']]) for f in glob.glob('src/views/*.py')]"
   ```
2. **Verify Streamlit View Signatures**:
   Confirm that all functions in `src/views/__init__.py` can be called without requiring local DataFrames.
3. **Verify API Client Integration Test**:
   Execute backend test suite:
   ```powershell
   pytest backend/tests/ -v
   ```
