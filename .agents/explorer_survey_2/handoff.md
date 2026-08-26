# Comprehensive Survey & Specification: OAuth, RBAC & Backend Decoupling (R1 & R2)

## 1. Observation

### 1.1 Existing Architecture & Codebase Baseline
Direct inspection of the current repository reveals the following monolithic structure:

- **Monolithic Frontend (`app.py:55-88, 144-154`)**:
  - Contains hardcoded mock SHA-256 credentials in `MOCK_USERS` (`app.py:55-58`):
    ```python
    MOCK_USERS = {
        "manager": {"password_hash": get_hash("admin123"), "role": "Manager"},
        "operator": {"password_hash": get_hash("agent123"), "role": "Junior"}
    }
    ```
  - Role-based navigation is implemented using `st.navigation` (`app.py:144-154`):
    * Manager sees: `Operations Cockpit` (`dashboard_p`, `partners_p`, `database_p`) and `AI Workflows & HITL` (`ingestion_p`, `reconciliation_p`, `triage_p`).
    * Operator (labeled `"Junior"` in `app.py:57`) sees only: `Operator Workspace` (`ingestion_p`, `triage_p`).
  - Data mutability is held directly in Streamlit session state (`st.session_state.support_df`, `finance_df`, `escalations_df`) loaded at startup via `load_data()` (`app.py:99-105`).

- **Direct SQLite & CSV Data Layer (`src/db.py`, `src/data_manager.py`)**:
  - `src/db.py:12-83` executes raw parameter-less or manual parameter SQLite queries on `data/ssot.db` using Python's standard `sqlite3` driver (`get_connection()`).
  - `src/data_manager.py:28-90` reads raw CSV files (`data/Support_Tracker.csv`, `data/Finance_Tracker.csv`, `data/Escalations.csv`) on first run, sanitizes money strings, and executes `df.to_sql("...", conn, if_exists="replace")`.
  - Discrepancy matching (`find_mismatches` in `src/data_manager.py:91-147`) and orphan detection (`find_orphans` in `src/data_manager.py:148-193`) run directly inside the Streamlit client thread.

- **Embedded LLM Logic (`src/agents.py:1-638`)**:
  - `parse_informal_message` (`src/agents.py:19-110`): PII redaction and entity extraction via Gemini API (`gemini-3.5-flash`) or OpenAI fallback (`gpt-4o-mini`).
  - `draft_reconciliation_message` (`src/agents.py:111-152`): Generates dispute explanation copy.
  - `analyze_escalations` (`src/agents.py:153-226`): Aggregates stats and drafts executive RCA summaries.
  - `analyze_partner_sentiment` (`src/agents.py:458-561`): NLP sentiment and urgency classification.
  - `lookup_airline_penalty` (`src/agents.py:563-595`): Carrier policy RAG engine.
  - `predict_sla_breach` (`src/agents.py:596-638`): Latency forecaster.

- **Current Raw CSV Schemas (`data/`)**:
  - `data/Support_Tracker.csv`: Columns `[Ticket ID, Agent, Route, Refund Amount (INR), Request Date, Last Updated, Status, Handled By, Channel, Notes]`.
  - `data/Finance_Tracker.csv`: Columns `[Ref No, Agent Name, Sector, Amount Paid (INR), Deduction (INR), Received On, Processed On, Payout Status, Approved By, Remarks]`.
  - `data/Escalations.csv`: Columns `[Escalation ID, Raised On, Related Ticket / Ref, Raised By, Agent / Team, Channel, Complaint, Status, Resolved On, Days Open]`.

---

## 2. Logic Chain

### 2.1 R1: OAuth & RBAC Design in Streamlit Frontend

#### 2.1.1 OAuth Flow Architecture
To replace the mock login form (`app.py:60-89`) with enterprise-grade OAuth (Google OAuth 2.0 / Auth0 OpenID Connect) while retaining 100% testability:
1. **Authorization Code Flow with PKCE**:
   - Streamlit initiates auth by generating a state/nonce and rendering an OAuth redirect link or button (`Login with Google / Corporate SSO`).
   - The user authenticates with the Identity Provider (IdP) and is redirected back to the callback URL with an `authorization_code`.
   - The frontend forwards the authorization code to the FastAPI backend at `POST /api/v1/auth/oauth/callback`.
   - The FastAPI backend exchanges the authorization code for tokens, verifies the ID token / user info, creates an internal signed JWT access token containing claims (`sub`, `email`, `role`, `name`), and returns it to the Streamlit app.
2. **Session State Management in Streamlit**:
   - `st.session_state.auth_token`: Holds the JWT bearer token.
   - `st.session_state.user`: Dict containing `{"user_id": str, "email": str, "name": str, "role": "Manager" | "Operator"}`.
   - `st.session_state.logged_in`: Boolean flag (`True` if valid token is present).
   - A global HTTP client wrapper in Streamlit (`src/api_client.py`) injects `Authorization: Bearer <auth_token>` into every request to the FastAPI backend.
3. **Mock OAuth for Local Development & Automated Verification**:
   - Controlled via environment variable `AUTH_MODE=mock` (or `ENABLE_MOCK_OAUTH=true`).
   - When enabled, the login screen displays a "Mock OAuth Gateway" with one-click persona selector:
     * `[Login as Manager (Aditi M.)]` -> requests `POST /api/v1/auth/mock-login?role=Manager`.
     * `[Login as Operator (Vikram T.)]` -> requests `POST /api/v1/auth/mock-login?role=Operator`.
   - Enables headless Playwright/pytest test scripts to authenticate instantly without human captcha or external network dependencies.

#### 2.1.2 RBAC Matrix & Guards

| Feature / View | Endpoint / Action | Manager Role | Operator Role | Guard Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **Identity Gateway** | `/` (Unauthenticated) | Redirect to Login | Redirect to Login | Top-level auth check |
| **Metrics Dashboard** | `GET /api/v1/metrics/dashboard` | Full Access | ⛔ Access Denied | Hidden in Nav + API 403 Forbidden |
| **Partner Health Matrix** | `GET /api/v1/partners/matrix` | Full Access | ⛔ Access Denied | Hidden in Nav + API 403 Forbidden |
| **Database Explorer** | `GET /api/v1/database/records` | Full Unmasked View | ⛔ Access Denied | Hidden in Nav + API 403 Forbidden |
| **Raw SSOT CSV Export**| `GET /api/v1/database/export` | ✅ Download Enabled | ⛔ Export Disabled | UI Button Hidden + API 403 Forbidden |
| **Ingestion Agent** | `POST /api/v1/ingestion/parse` | ✅ Full Access | ✅ Full Access | Shared Workspace |
| **Ingestion Commit** | `POST /api/v1/support-tickets` | ✅ Full Access | ✅ Full Access | Shared Workspace |
| **Reconciliation HITL** | `GET /api/v1/reconciliation/*` | ✅ Full Access | ⛔ Access Denied | Hidden in Nav + API 403 Forbidden |
| **Escalation Triage** | `GET /api/v1/escalations/*` | ✅ Full Access | ✅ Full Access | Shared Workspace |
| **AI Discrepancy Batch**| `POST /api/v1/reconciliation/batch`| ✅ Full Access | ⛔ Access Denied | API 403 Forbidden |
| **Financial Figures** | Data Display | Raw Values | Masked (`[HIDDEN]`)| Serializer / DLP Masking |

---

### 2.2 R2: Backend Decoupling & SQLite Database Migration

#### 2.2.1 Target FastAPI Application Directory Layout
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application factory, CORS, exception handlers
│   ├── config.py                   # Pydantic BaseSettings (DB_URL, JWT_SECRET, ALGORITHM, GEMINI_API_KEY, AUTH_MODE)
│   ├── database.py                 # SQLAlchemy engine, SessionLocal, get_db dependency
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py             # JWT token creation/verification, password hashing
│   │   ├── dependencies.py         # get_current_user, require_role(["Manager"])
│   │   └── dlp.py                  # PII redaction and financial masking utility
│   ├── models/                     # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── support.py              # SupportTicket ORM model
│   │   ├── finance.py              # FinanceRecord ORM model
│   │   ├── escalation.py           # Escalation ORM model
│   │   └── audit.py                # AuditLog ORM model
│   ├── schemas/                    # Pydantic validation & serialization models
│   │   ├── __init__.py
│   │   ├── auth.py                 # Token, TokenPayload, UserProfile, MockLoginRequest
│   │   ├── support.py              # SupportTicketBase, Create, Update, Response
│   │   ├── finance.py              # FinanceRecordResponse
│   │   ├── escalation.py           # EscalationResponse, EscalationDraftRequest, EscalationResolveRequest
│   │   ├── reconciliation.py       # MismatchResponse, OrphanResponse, ReconcileTicketRequest, BatchReconcileRequest
│   │   ├── ingestion.py            # ParseMessageRequest, ExtractedEntityResponse, BatchIngestRequest
│   │   ├── partner.py              # PartnerStatsResponse, PartnerMatrixResponse, SentimentScoreResponse
│   │   └── metrics.py              # DashboardMetricsResponse, RcaSummaryResponse
│   ├── routers/                    # FastAPI APIRouters
│   │   ├── __init__.py
│   │   ├── auth.py                 # /api/v1/auth/*
│   │   ├── support.py              # /api/v1/support-tickets/*
│   │   ├── finance.py              # /api/v1/finance-records/*
│   │   ├── escalations.py          # /api/v1/escalations/*
│   │   ├── reconciliation.py       # /api/v1/reconciliation/*
│   │   ├── ingestion.py            # /api/v1/ingestion/*
│   │   ├── metrics.py              # /api/v1/metrics/*
│   │   └── partners.py             # /api/v1/partners/*
│   ├── services/                   # Pure business logic and LLM/agent dispatch
│   │   ├── __init__.py
│   │   ├── reconciliation_service.py # Mismatch analysis, fuzzy matching, orphan checks
│   │   ├── ingestion_service.py    # Entity parsing, PII redaction
│   │   ├── escalation_service.py   # Sentiment classification, response drafting
│   │   └── metrics_service.py      # KPI aggregation, RCA summarizer
│   └── scripts/
│       ├── __init__.py
│       └── seed_db.py              # Automated CSV-to-SQLite hydration & normalization
└── tests/                          # Backend Pytest Test Suite
    ├── __init__.py
    ├── conftest.py                 # In-memory SQLite session fixtures, test client, mock tokens
    ├── test_auth.py                # Tests login, JWT verification, RBAC guards
    ├── test_support_api.py         # Tests CRUD operations on support tickets
    ├── test_reconciliation_api.py  # Tests mismatch and orphan detection endpoints
    ├── test_escalations_api.py     # Tests escalation queue and resolution
    ├── test_ingestion_api.py       # Tests entity extraction and record commits
    └── test_metrics_api.py         # Tests dashboard KPI calculations
```

---

### 2.3 Comprehensive Data Models & Schemas

#### 2.3.1 SQLAlchemy ORM Models (`backend/app/models/`)

```python
# backend/app/models/support.py
from sqlalchemy import Column, String, Float, Text, DateTime
from backend.app.database import Base

class SupportTicket(Base):
    __tablename__ = "support_tracker"

    ticket_id = Column("Ticket ID", String(50), primary_key=True, index=True)
    agent = Column("Agent", String(150), nullable=False, index=True)
    route = Column("Route", String(50), nullable=True)
    refund_amount = Column("Refund Amount (INR)", Float, default=0.0)
    request_date = Column("Request Date", String(30), nullable=True)
    last_updated = Column("Last Updated", String(30), nullable=True)
    status = Column("Status", String(50), default="Pending", index=True)
    handled_by = Column("Handled By", String(100), nullable=True)
    channel = Column("Channel", String(50), default="WhatsApp")
    notes = Column("Notes", Text, nullable=True)

# backend/app/models/finance.py
from sqlalchemy import Column, String, Float, Text
from backend.app.database import Base

class FinanceRecord(Base):
    __tablename__ = "finance_tracker"

    ref_no = Column("Ref No", String(50), primary_key=True, index=True)
    agent_name = Column("Agent Name", String(150), nullable=False, index=True)
    sector = Column("Sector", String(50), nullable=True)
    amount_paid = Column("Amount Paid (INR)", Float, default=0.0)
    deduction = Column("Deduction (INR)", Float, default=0.0)
    received_on = Column("Received On", String(30), nullable=True)
    processed_on = Column("Processed On", String(30), nullable=True)
    payout_status = Column("Payout Status", String(50), default="Pending Payout", index=True)
    approved_by = Column("Approved By", String(100), nullable=True)
    remarks = Column("Remarks", Text, nullable=True)

# backend/app/models/escalation.py
from sqlalchemy import Column, String, Float, Text, ForeignKey
from backend.app.database import Base

class Escalation(Base):
    __tablename__ = "escalations"

    escalation_id = Column("Escalation ID", String(50), primary_key=True, index=True)
    raised_on = Column("Raised On", String(30), nullable=True)
    ticket_id = Column("Ticket ID", String(50), nullable=True, index=True)
    raised_by = Column("Raised By", String(50), default="Agent")
    agent = Column("Agent", String(150), nullable=False, index=True)
    channel = Column("Channel", String(50), default="Email")
    message = Column("Message", Text, nullable=False)
    status = Column("Status", String(50), default="Open", index=True)
    resolved_on = Column("Resolved On", String(30), nullable=True)
    days_open = Column("Days Open", Float, default=0.0)

# backend/app/models/audit.py
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from backend.app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(String(100), nullable=False)
    user_role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
```

#### 2.3.2 Pydantic Schemas (`backend/app/schemas/`)

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_profile: "UserProfile"

class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str
    role: Literal["Manager", "Operator"]

class MockLoginRequest(BaseModel):
    role: Literal["Manager", "Operator"]
    username: Optional[str] = None

# backend/app/schemas/support.py
from pydantic import BaseModel, Field
from typing import Optional

class SupportTicketBase(BaseModel):
    ticket_id: str = Field(..., alias="Ticket ID")
    agent: str = Field(..., alias="Agent")
    route: Optional[str] = Field(None, alias="Route")
    refund_amount: float = Field(0.0, alias="Refund Amount (INR)")
    request_date: Optional[str] = Field(None, alias="Request Date")
    last_updated: Optional[str] = Field(None, alias="Last Updated")
    status: str = Field("Pending", alias="Status")
    handled_by: Optional[str] = Field(None, alias="Handled By")
    channel: str = Field("WhatsApp", alias="Channel")
    notes: Optional[str] = Field(None, alias="Notes")

    class Config:
        populate_by_name = True
        from_attributes = True

class SupportTicketCreate(SupportTicketBase):
    pass

class SupportTicketUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    refund_amount: Optional[float] = None
    handled_by: Optional[str] = None

# backend/app/schemas/reconciliation.py
from pydantic import BaseModel
from typing import List, Optional

class MismatchItem(BaseModel):
    ticket_id: str
    finance_ref_no: str
    agent: str
    route: str
    support_amount: float
    finance_amount: float
    deduction: float
    reason: str
    risk_level: str

class OrphanResponse(BaseModel):
    missing_in_finance: List[dict]
    missing_in_support: List[dict]

class ReconcileTicketRequest(BaseModel):
    ticket_id: str
    action: str = "notify_client"
    reason: str
    notes: Optional[str] = None

class BatchReconcileRequest(BaseModel):
    ticket_ids: List[str]
```

---

### 2.4 REST API Interface Contract

All endpoints require `Authorization: Bearer <token>` unless marked Public.

| Method | Path | Auth / Role | Description | Request Body | Response (200 / 201) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/oauth/login` | Public | Initiates OAuth redirect | None | `{"auth_url": str, "state": str}` |
| `POST` | `/api/v1/auth/oauth/callback` | Public | Exchanges auth code for JWT | `{"code": str, "state": str}` | `Token` schema |
| `POST` | `/api/v1/auth/mock-login` | Public (Dev/Test)| Instant persona token | `MockLoginRequest` | `Token` schema |
| `GET` | `/api/v1/auth/me` | Any Authenticated | Current user & role profile | None | `UserProfile` |
| `GET` | `/api/v1/support-tickets` | Any Authenticated | List/search support tickets | Query: `status, agent, search, skip, limit` | `List[SupportTicketBase]` |
| `POST` | `/api/v1/support-tickets` | Any Authenticated | Create/commit support ticket | `SupportTicketCreate` | `SupportTicketBase` |
| `GET` | `/api/v1/support-tickets/{ticket_id}` | Any Authenticated | Single ticket by ID | None | `SupportTicketBase` |
| `PATCH`| `/api/v1/support-tickets/{ticket_id}` | Any Authenticated | Update status/notes | `SupportTicketUpdate` | `SupportTicketBase` |
| `GET` | `/api/v1/finance-records` | Manager Only | List finance settlements | Query: `status, search, skip, limit` | `List[FinanceRecordResponse]` |
| `GET` | `/api/v1/reconciliation/mismatches` | Manager Only | Discrepancy mismatch audit | Query: `risk_level, min_diff` | `List[MismatchItem]` |
| `GET` | `/api/v1/reconciliation/orphans` | Manager Only | Missing tickets audit | None | `OrphanResponse` |
| `POST` | `/api/v1/reconciliation/reconcile` | Manager Only | Settle single discrepancy | `ReconcileTicketRequest` | `{"success": bool, "ticket_id": str}` |
| `POST` | `/api/v1/reconciliation/batch` | Manager Only | Settle batch discrepancies | `BatchReconcileRequest` | `{"reconciled_count": int}` |
| `POST` | `/api/v1/reconciliation/draft` | Manager Only | AI deduction message draft | `DraftMessageRequest` | `{"draft_message": str}` |
| `GET` | `/api/v1/escalations` | Any Authenticated | Active escalations queue | Query: `status, agent, search` | `List[EscalationResponse]` |
| `POST` | `/api/v1/escalations/{id}/draft` | Any Authenticated | Draft personalized AI reply | None | `{"draft_message": str}` |
| `POST` | `/api/v1/escalations/{id}/resolve`| Any Authenticated | Resolve & delete from queue | `ResolveEscalationRequest` | `{"success": bool}` |
| `POST` | `/api/v1/ingestion/parse` | Any Authenticated | Parse informal message | `{"text": str, "channel": str}` | `ExtractedEntityResponse` |
| `POST` | `/api/v1/ingestion/batch-upload`| Any Authenticated | Parse batch CSV/JSON file | Multipart File Upload | `List[ExtractedEntityResponse]` |
| `GET` | `/api/v1/metrics/dashboard` | Manager Only | Aggregated KPI metrics | Query: `window_filter` | `DashboardMetricsResponse` |
| `POST` | `/api/v1/metrics/ai-rca` | Manager Only | Executive AI Root Cause Analysis | None | `RcaSummaryResponse` |
| `GET` | `/api/v1/partners/matrix` | Manager Only | Partner churn telemetry & NLP | None | `PartnerMatrixResponse` |
| `GET` | `/api/v1/policies/{route}` | Any Authenticated | Airline tariff & penalty lookup | Query: `carrier` | `AirlinePolicyResponse` |
| `GET` | `/api/v1/database/export` | Manager Only | Export clean SSOT CSV | None | `StreamingResponse (text/csv)` |

---

### 2.5 Database Hydration & Seeding Strategy (`seed_db.py`)

1. **Schema Initialization**:
   - `Base.metadata.create_all(bind=engine)` creates `support_tracker`, `finance_tracker`, `escalations`, and `audit_logs` tables.
2. **CSV Ingestion Pipeline**:
   - Skips metadata headers (row 0 in `Support_Tracker.csv`, `Finance_Tracker.csv`, `Escalations.csv`).
   - Cleans monetary fields via regex/strip (`clean_money_string`).
   - Normalizes Ticket IDs (`str.strip().str.upper()`).
   - Maps CSV columns to ORM fields:
     * `data/Escalations.csv`: `"Related Ticket / Ref"` -> `ticket_id`, `"Agent / Team"` -> `agent`, `"Complaint"` -> `message`.
     * `data/Finance_Tracker.csv`: `"Ref No"` -> `ref_no`, `"Agent Name"` -> `agent_name`, `"Amount Paid (INR)"` -> `amount_paid`, `"Deduction (INR)"` -> `deduction`.
     * `data/Support_Tracker.csv`: `"Ticket ID"` -> `ticket_id`, `"Agent"` -> `agent`, `"Refund Amount (INR)"` -> `refund_amount`.
3. **Execution Mode**:
   - Runs automatically on FastAPI startup if tables are empty, or explicitly via `python -m backend.app.scripts.seed_db`.

---

### 2.6 Streamlit Presentation-Layer Architecture (`src/api_client.py`)

In the decoupled architecture, `src/data_manager.py` and `src/db.py` are deprecated in the Streamlit frontend. Instead, a lightweight API Client is introduced:

```python
# src/api_client.py
import os
import requests
import streamlit as st
from typing import Dict, Any, Optional

API_BASE_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000/api/v1")

def get_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = st.session_state.get("auth_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def api_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    return requests.get(f"{API_BASE_URL}{endpoint}", headers=get_headers(), params=params)

def api_post(endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> requests.Response:
    return requests.post(f"{API_BASE_URL}{endpoint}", headers=get_headers(), json=json_data)

def api_patch(endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> requests.Response:
    return requests.patch(f"{API_BASE_URL}{endpoint}", headers=get_headers(), json=json_data)

def api_delete(endpoint: str) -> requests.Response:
    return requests.delete(f"{API_BASE_URL}{endpoint}", headers=get_headers())
```

---

## 3. Caveats

1. **Legacy Column Renaming**: The raw CSV `data/Escalations.csv` has column header `"Related Ticket / Ref"` with format `RF-XXXX (revised)` or `RF XXXX`. The database migration script must strip whitespace and normalize foreign key references so joins between `escalations` and `support_tracker` remain consistent.
2. **Missing Dates in CSVs**: Several rows in `Support_Tracker.csv` and `Finance_Tracker.csv` contain hand-typed date strings like `30/05/26` mixed with `30-05-2026` or missing date values. In the SQLite model, these should be stored as `String(30)` or normalized with `pd.to_datetime(errors='coerce')` during ingestion.
3. **Mock OAuth Scope**: Mock OAuth provider generates signed JWT tokens with standard HMAC-SHA256 (`secret_key`) so that local testing does not require live Auth0/Google credentials, while production deployments can swap in Google/Auth0 public JWKS verification by updating `AUTH_MODE=google` or `AUTH_MODE=auth0` in `config.py`.

---

## 4. Conclusion

- **R1 (OAuth & RBAC)**: Replace the hardcoded `app.py:55-88` authentication with an OAuth 2.0 PKCE flow integrated with FastAPI token issuance. Streamlit session state will maintain JWT tokens, and page navigation will enforce strict route guards (preventing Operators from seeing Dashboard, Database Explorer, Partner Matrix, or Reconciliation HITL).
- **R2 (Backend Decoupling & SQLite)**: Extract all data logic into a production-grade FastAPI application with SQLAlchemy ORM models, Pydantic schemas, and structured REST endpoints. All CSV datasets will be seeded into `data/ssot.db` with clean schema constraints, and Streamlit will operate strictly as a presentation client communicating via `src/api_client.py`.
- **Dependencies Required**:
  - Backend: `fastapi>=0.110.0`, `uvicorn>=0.28.0`, `sqlalchemy>=2.0.0`, `pydantic>=2.6.0`, `pydantic-settings>=2.2.0`, `python-jose[cryptography]>=3.3.0`, `passlib[bcrypt]>=1.7.4`, `python-multipart>=0.0.9`, `httpx>=0.27.0`, `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`.
  - Frontend: `streamlit>=1.39.0`, `requests>=2.31.0`, `pandas>=2.0.0`, `altair>=5.0.0`.

---

## 5. Verification Method

### 5.1 FastAPI Backend Automated Pytest Suite (`backend/tests/`)

Run the test suite with:
```bash
pytest backend/tests -v
```

Test implementation blueprint (`backend/tests/test_api.py`):
```python
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_mock_oauth_login():
    """Verify mock OAuth token issuance for Manager and Operator."""
    resp = client.post("/api/v1/auth/mock-login", json={"role": "Manager"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user_profile"]["role"] == "Manager"

def test_rbac_manager_access_dashboard():
    """Verify Manager can access metrics dashboard."""
    token_resp = client.post("/api/v1/auth/mock-login", json={"role": "Manager"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = client.get("/api/v1/metrics/dashboard", headers=headers)
    assert resp.status_code == 200
    assert "total_escalations" in resp.json()

def test_rbac_operator_denied_dashboard():
    """Verify Operator is denied access to metrics dashboard (403 Forbidden)."""
    token_resp = client.post("/api/v1/auth/mock-login", json={"role": "Operator"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = client.get("/api/v1/metrics/dashboard", headers=headers)
    assert resp.status_code == 403

def test_crud_support_ticket_sqlite():
    """Verify creating and reading support records directly from SQLite via API."""
    token_resp = client.post("/api/v1/auth/mock-login", json={"role": "Operator"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "Ticket ID": "RF-TEST-999",
        "Agent": "Pytest Agency",
        "Route": "DEL-BOM",
        "Refund Amount (INR)": 5000.0,
        "Status": "Processing",
        "Channel": "WhatsApp",
        "Notes": "Pytest verification ticket"
    }
    create_resp = client.post("/api/v1/support-tickets", json=payload, headers=headers)
    assert create_resp.status_code == 201
    
    get_resp = client.get("/api/v1/support-tickets/RF-TEST-999", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["Agent"] == "Pytest Agency"
```

### 5.2 Streamlit Frontend & RBAC Verification Script

Run E2E Playwright verification:
```bash
npx playwright test e2e/auth_rbac.spec.ts
```

Verification assertions:
1. Navigating to `http://localhost:8501` without session redirects to `/` displaying Identity Gateway.
2. Clicking "Mock OAuth: Login as Operator" navigates to Operator Workspace containing only `Ingestion Agent` and `Escalation Triage`.
3. Navigating directly to `http://localhost:8501/dashboard` as Operator triggers 403 error banner and blocks dashboard KPI rendering.
4. Logging in as Manager renders both `Operations Cockpit` and `AI Workflows & HITL` sections, with active export buttons.
