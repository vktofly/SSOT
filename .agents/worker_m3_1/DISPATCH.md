## 2026-08-25T15:10:21Z

You are worker_m3_1.
Your working directory: c:\Users\vikash\Documents\SSOT_Parser\.agents\worker_m3_1
Project workspace root: c:\Users\vikash\Documents\SSOT_Parser
Authoritative User Request: c:\Users\vikash\Documents\SSOT_Parser\.agents\ORIGINAL_REQUEST.md
Project Architecture: c:\Users\vikash\Documents\SSOT_Parser\PROJECT.md
Testing Infrastructure: c:\Users\vikash\Documents\SSOT_Parser\TEST_INFRA.md

Milestone 3 Explorer Blueprints & Proposed Files:
- Backend Architecture: c:\Users\vikash\Documents\SSOT_Parser\.agents\explorer_m3_1\builder.py
- Frontend Decoupling: c:\Users\vikash\Documents\SSOT_Parser\.agents\explorer_m3_2\handoff.md
- Schemas & Tests: c:\Users\vikash\Documents\SSOT_Parser\.agents\explorer_m3_3\handoff.md (and artifacts in `.agents/explorer_m3_3/proposed_*`)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

YOUR ASSIGNMENT: Implement Milestone 3 (Business Logic Decoupling & REST API) across Backend and Frontend:
1. Backend Schemas (`backend/app/schemas/`):
   - Implement `reconciliation.py` (`MismatchItem`, `OrphanResponse`, `ReconciliationSummary`, `ResolveMismatchRequest`, `ResolveMismatchResponse`, `LinkOrphanRequest`, `LinkOrphanResponse`, `DraftExplanationRequest`, `DraftExplanationResponse`, `ProactiveNotificationRequest`, `ProactiveNotificationResponse`).
   - Implement `metrics.py` (`DashboardSummary`, `CorridorNode`, `MonthlyTrendItem`, `RootCauseItem`, `ParetoItem`, `CarrierHealthItem`, `DashboardMetricsResponse`, `RCASynthesisResponse`).
   - Implement `partners.py` (`FleetSummary`, `PartnerHealthItem`, `PartnerMatrixResponse`, `PartnerDetailResponse`, `AirlinePolicyResponse`, `PredictSLABreachRequest`, `PredictSLABreachResponse`).
   - Export all schemas in `backend/app/schemas/__init__.py`.

2. Backend Services (`backend/app/services/`):
   - Implement `reconciliation.py`: DB-backed mismatch calculations, orphan detection with fuzzy match fallback, mismatch resolution with audit logging, orphan linking with audit logging, discrepancy explanation drafting, proactive notification generation.
   - Implement `metrics.py`: DB-backed KPI telemetry calculations (total escalations, avg TTR, dropped handoffs, deduction mismatches, health percentage, financial exposure, settlement corridor, dispute trends, root cause distributions, carrier health metrics) and RCA synthesis (with Gemini / offline rule fallback).
   - Implement `partner_health.py`: B2B partner sentiment monitoring, tier classification, churn risk tagging, fleet summary.
   - Implement `policy.py`: Airline fare dispute penalty matrix (DEL-DXB, BLR-MAA, DEL-SIN, DEL-BOM, COK-DXB, MAA-CMB, domestic/intl fallbacks) and predictive SLA breach forecaster (72h threshold).

3. Backend REST Routers (`backend/app/routers/`):
   - Implement `reconciliation.py`: `/api/v1/reconciliation/mismatches` (GET, Manager only), `/api/v1/reconciliation/orphans` (GET, Manager only), `/api/v1/reconciliation/resolve-mismatch` (POST, Manager only), `/api/v1/reconciliation/link-orphan` (POST, Manager only), `/api/v1/reconciliation/draft-explanation` (POST, authenticated), `/api/v1/reconciliation/proactive-notification` (POST, authenticated).
   - Implement `metrics.py`: `/api/v1/metrics/dashboard` (GET, Manager only), `/api/v1/metrics/rca` (GET, Manager only).
   - Implement `partners.py`: `/api/v1/partners/matrix` (GET, Manager only), `/api/v1/partners/{agency_name}` (GET, Manager only), `/api/v1/policy/airline-penalty` (GET, authenticated), `/api/v1/policy/predict-sla-breach` (POST, authenticated).
   - Register all routers in `backend/app/main.py`.

4. Frontend API Client & Streamlit Views Decoupling:
   - Extend `src/api_client.py` with typed helper methods for all new endpoints.
   - Refactor `src/views/dashboard.py`, `src/views/reconciliation.py`, `src/views/partner_matrix.py`, `src/views/ingestion.py`, `src/views/escalation_triage.py`, `src/views/database_explorer.py` to fetch data and trigger actions via `src/api_client.py` instead of direct DB/CSV reads or local in-memory computations.
   - Update `app.py` to pass zero arguments to view functions and eliminate `load_data()` from `app.py`.

5. Testing & Verification:
   - Implement/copy test suites: `backend/tests/test_reconciliation_api.py`, `backend/tests/test_metrics_api.py`, `backend/tests/test_partners_api.py`.
   - Run `pytest backend/tests/ -v` and ensure 100% of tests pass across all suites.

6. Handoff:
   - Write your complete implementation report to `c:\Users\vikash\Documents\SSOT_Parser\.agents\worker_m3_1\handoff.md`.
   - Send completion message to parent when done.
