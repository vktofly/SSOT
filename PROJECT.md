# Project: BharatTrip AI Escalation Resolver Architectural Upgrade

## Architecture
The BharatTrip AI Escalation Resolver is upgraded from a monolithic Streamlit application to a decoupled, production-ready enterprise architecture:
1. **Frontend Presentation Layer**: Streamlit web application running purely as a client interface. Implements OAuth authentication, session token management, and role-based page navigation (Manager vs Operator) using `src/api_client.py` for all data interactions.
2. **Backend API Service**: Standalone FastAPI service (`backend/app/`) exposing REST endpoints for authentication, CRUD operations on SSOT data, analytics, reconciliation, and escalation resolution.
3. **Data Layer**: SQLite database (`data/ssot.db`) managed through SQLAlchemy ORM models (`SupportTicket`, `FinanceRecord`, `Escalation`, `AuditLog`) with automated hydration/seeding from CSV baselines.
4. **AI & Multi-Agent Layer**: LangGraph `StateGraph` multi-agent workflow separating concerns across specialized nodes (PII extraction, sentiment & routing, SSOT/policy lookups, response generation, guardrail reflection, and HITL interrupt).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---|---|---|---|
| 1 | Database ORM Models & SQLite Migration | SQLAlchemy models for Support, Finance, Escalation, AuditLog tables with typed schemas | M1 | Survey R2 |
| 2 | CSV-to-SQLite Hydration Script | Automated ingestion pipeline `seed_db.py` normalizing money strings and keys | M1 | Survey R2 |
| 3 | Core Data CRUD Endpoints | FastAPI REST endpoints for Support Tickets, Finance Records, and Escalations | M1 | Survey R2 |
| 4 | OAuth 2.0 & Mock Auth Provider | PKCE OAuth authentication with Mock OAuth provider (`AUTH_MODE=mock`) for automated testing | M2 | Survey R1 |
| 5 | JWT Security & RBAC Middleware | Signed JWT bearer tokens with `get_current_user` and `require_role(["Manager"])` guards | M2 | Survey R1 |
| 6 | Streamlit Auth & Session Management | Token storage in `st.session_state` and global authenticated `api_client.py` | M2 | Survey R1 |
| 7 | Streamlit Role-Based Route Security | `st.navigation` route guards segregating Manager vs Operator views with DLP field masking | M2 | Survey R1 |
| 8 | Discrepancy & Reconciliation Services | Backend service for ledger mismatch detection and orphaned ticket cross-matching | M3 | Survey R2 |
| 9 | Operations Metrics & RCA Endpoints | Backend KPI aggregations and executive AI Root Cause Analysis endpoints | M3 | Survey R2 |
| 10 | Partner Health Matrix & Policy RAG | B2B partner sentiment monitoring and airline penalty knowledge base endpoints | M3 | Survey R2 |
| 11 | Streamlit UI Frontend Decoupling | Refactor all `src/views/*` to consume FastAPI REST APIs via `api_client.py` | M3 | Survey R2 |
| 12 | LangGraph Typed State Schema | `AgentState` TypedDict capturing inbounds, extraction, routing, SSOT lookups, response, and audit trace | M4 | Survey R3 |
| 13 | Specialized Multi-Agent Nodes | PII extraction, sentiment & routing, SSOT lookup, reconciliation lookup, policy RAG, response generator | M4 | Survey R3 |
| 14 | Guardrail Reflection & HITL Interrupt | Self-checking guardrails against hallucinations/PII leakage, with HITL pause state for operator review | M4 | Survey R3 |
| 15 | FastAPI Multi-Agent Integration | `/api/v1/escalations/resolve` and SSE `/api/v1/escalations/resolve/stream` endpoints | M4 | Survey R3 |
| 16 | Comprehensive 4-Tier E2E Test Suite | Automated Pytest suite covering unit, integration, RBAC, and real-world workflows | M5 / Test Track | Survey R1-R3 |
| 17 | Adversarial Coverage Hardening | Tier 5 adversarial stress testing (injections, network faults, corrupted payloads, concurrency) | M5 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| M1 | Backend Foundation & SQLite Migration | FastAPI structure, SQLAlchemy models, `seed_db.py`, and core CRUD endpoints | none | DONE |
| M2 | Authentication & RBAC Layer | OAuth PKCE / Mock OAuth, JWT verification, Streamlit auth & role navigation guards | M1 | DONE |
| M3 | Business Logic Decoupling & REST API | Reconciliation, metrics, partner health, policy services, and Streamlit view API migration | M1, M2 | IN_PROGRESS |
| M4 | LangGraph Multi-Agent Orchestration | StateGraph workflow, specialized agent nodes, guardrails, HITL, and FastAPI resolve API | M1, M3 | PLANNED |
| M5 | Final Milestone: 100% E2E Pass & Hardening | Pass 100% E2E test suite (Tiers 1-4) + Tier 5 adversarial coverage hardening | M1, M2, M3, M4, Test Track | PLANNED |

## Interface Contracts

### 1. Authentication & RBAC (`/api/v1/auth/*`)
- `POST /api/v1/auth/mock-login`: `{ "role": "Manager" | "Operator", "username": Optional[str] }` -> `{ "access_token": str, "token_type": "bearer", "expires_in": int, "user_profile": { "user_id": str, "email": str, "name": str, "role": str } }`
- `GET /api/v1/auth/me`: Headers `Authorization: Bearer <token>` -> `UserProfile`
- Role Permissions:
  - Manager: Full access to all endpoints (`/api/v1/metrics/*`, `/api/v1/reconciliation/*`, `/api/v1/partners/*`, `/api/v1/database/*`).
  - Operator: Access restricted to `/api/v1/support-tickets/*`, `/api/v1/escalations/*`, `/api/v1/ingestion/*`. Any access to Manager routes returns HTTP 403 Forbidden.

### 2. Core SSOT Data API (`/api/v1/*`)
- `GET /api/v1/support-tickets`: Query params `status, agent, search, skip, limit` -> `List[SupportTicketResponse]`
- `POST /api/v1/support-tickets`: Body `SupportTicketCreate` -> `SupportTicketResponse` (HTTP 201)
- `GET /api/v1/finance-records`: (Manager only) Query params `status, search, skip, limit` -> `List[FinanceRecordResponse]`
- `GET /api/v1/reconciliation/mismatches`: (Manager only) -> `List[MismatchItem]`
- `GET /api/v1/reconciliation/orphans`: (Manager only) -> `OrphanResponse`

### 3. LangGraph Multi-Agent Workflow (`/api/v1/escalations/resolve`)
- `POST /api/v1/escalations/resolve`:
  - Request: `{ "raw_message": str, "channel": str, "agency_name": Optional[str], "agency_tier": Optional[str] }`
  - Response: `{ "escalation_id": str, "priority_rank": str, "urgency_level": str, "extracted_entities": dict, "ssot_status": Optional[dict], "draft_response": str, "hitl_required": bool, "audit_trace": List[dict] }`
- `POST /api/v1/escalations/resolve/stream`: SSE stream yielding node events (`node_start`, `node_complete`, `state_delta`, `final_result`).

## Code Layout
```
SSOT_Parser/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI application entrypoint & middleware
│   │   ├── config.py                # Environment & Pydantic BaseSettings
│   │   ├── database.py              # SQLAlchemy engine & session factory
│   │   ├── core/                    # Security, JWT, RBAC dependencies, DLP masking
│   │   ├── models/                  # SQLAlchemy ORM models (support, finance, escalation, audit)
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── routers/                 # API route controllers (auth, support, finance, escalations, recon, metrics, ingestion)
│   │   ├── services/                # Business logic services
│   │   ├── agents/                  # LangGraph multi-agent workflow, nodes & state
│   │   └── scripts/
│   │       └── seed_db.py           # Database migration & CSV hydration
│   └── tests/                       # Pytest test suite (unit, integration, API, adversarial)
├── src/
│   ├── api_client.py                # Authenticated HTTP client for Streamlit
│   ├── auth.py                      # Frontend OAuth & session helper
│   ├── ui_components.py             # UI helpers & styling components
│   └── views/                       # Streamlit view modules (dashboard, ingestion, recon, triage, etc.)
├── data/
│   ├── ssot.db                      # Primary SQLite database
│   ├── Support_Tracker.csv          # Baseline seed CSV
│   ├── Finance_Tracker.csv          # Baseline seed CSV
│   └── Escalations.csv              # Baseline seed CSV
├── app.py                           # Streamlit UI presentation entrypoint
├── requirements.txt                 # Root project dependencies
└── PROJECT.md                       # Single source of truth for project architecture
```
