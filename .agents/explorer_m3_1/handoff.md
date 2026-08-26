# Milestone 3 Architecture Blueprint & Handoff Report

## 1. Observation
Direct observations from codebase investigation of monolithic calculations and backend dependencies:

### 1.1 Existing Calculation Logic in `src/views/` & `src/data_manager.py`
1. **Reconciliation & Discrepancy Matching (`src/data_manager.py:91-146`)**:
   - Scans records from `support_tracker` and `finance_tracker`.
   - Match Key: Exact match on `SupportTicket.ticket_id == FinanceRecord.ref_no`.
   - Typo Fallback: Lexical fuzzy match via `difflib.get_close_matches(ref, support_ids, n=1, cutoff=0.7)`.
   - Money Sanitization: `clean_money_string` strips currency symbols (`₹`), commas, `INR`, and whitespace.
   - Discrepancy Condition: `support_amount != finance_amount`.
   - Deduction: `f_row['Deduction (INR)']` or `support_amount - finance_amount`.
   - Risk Assessment:
     - `High Risk`: If `support_amount > 0` and `abs(support_amount - finance_amount) / support_amount > 0.20` (20% variance threshold) OR if `support_amount == 0 and finance_amount > 0`.
     - `Normal Risk`: Discrepancy <= 20%.
   - Return payload per mismatch: `ticket_id`, `finance_ref_no`, `agent`, `route`, `support_amount`, `finance_amount`, `deduction`, `reason`, `risk_level`.

2. **Orphaned Ticket Detection (`src/data_manager.py:148-192`)**:
   - `missing_in_finance`: Support tickets whose `ticket_id` is missing in Finance `ref_no` (and has no `difflib` match >= 0.7).
   - `missing_in_support`: Finance records whose `ref_no` is missing in Support `ticket_id` (and has no `difflib` match >= 0.7).
   - Unlogged Agent Risk Score: If an agent has `> 2` unlogged tickets in `missing_in_finance`, tagged with `risk_level = 'High'`, `risk_note = f"Agent '{agent}' has {count} unlogged payouts."`, else `risk_level = 'Normal'`.

3. **Operations Dashboard Metrics (`src/views/dashboard.py:19-66, 468-506, 609-687`)**:
   - `total_escalations = len(escalations_df)`
   - `avg_ttr = round(pd.to_numeric(escalations_df['Days Open']).mean(), 1)` (baseline default: 16.4 days)
   - `dropped_handoffs = len(missing_in_finance)` (100 in baseline)
   - `deduction_mismatches = len(mismatches_list)` (149 in baseline)
   - `total_pipeline = len(support_df)` (600 in baseline)
   - `healthy_count = max(0, total_pipeline - dropped_handoffs - deduction_mismatches)`
   - `health_pct = round((healthy_count / total_pipeline) * 100, 1)` (58.5% in baseline)
   - Financial Exposure: ₹14.8 Lakhs contested deduction variances.
   - Settlement Corridor nodes: Intake (600) -> Support Audit (500, -100 dropped) -> Banking Payout (351 clean, 149 mismatches).
   - Dispute Trajectory (Monthly): Feb (12, ₹2.4L), Mar (28, ₹5.6L), Apr (41, ₹8.2L), May (56, ₹11.2L), Jun (78, ₹14.8L).
   - Root Causes: Deductions (149, ₹14.8L), Dropped (100, ₹9.2L), Off-Tracker (42, ₹3.4L), Carrier (24, ₹1.8L).
   - Pareto Categories: Silent Delay (61), Ghost Ticket (32), Short Payout (21), Unlogged Msg (17), No Reason (5).
   - Carrier Health: IndiGo (92%, ₹600, 24h), SpiceJet (84%, ₹800, 36h), Air India (78%, ₹1,200, 48h), Emirates (69%, ₹1,800, 72h).

4. **Partner Health & Churn Matrix (`src/views/partner_matrix.py:15-75`)**:
   - Tier Classification: `VIP` if agency name contains `"peak"`, `"nomad"`, `"global"`, `"royal"`, `"zenith"` else `Standard`.
   - Sentiment & Priority Matrix (`src/agents.py:458-560`):
     - Critical keywords (`legal`, `court`, `threat`, `fraud`, `police`, `consumer`, `2 hafte`, `two weeks`) -> Urgency: Critical, Sentiment: -0.85, Frustration: "Legal / Severe Churn Risk".
     - High keywords (`urgent`, `immediately`, `angry`, `escalat`, `unacceptable`) -> Urgency: High, Sentiment: -0.55, Frustration: "Prolonged Delay / Frustration".
     - Medium (`?`, `status`, `update`) -> Urgency: Medium, Sentiment: -0.15, Frustration: "Information Request".
     - Low (other) -> Urgency: Low, Sentiment: +0.10, Frustration: "Routine Inquiry".
     - Priority Mapping:
       - VIP + (Critical | High) -> `P0 - Immediate`
       - Critical (Standard) -> `P1 - Urgent`
       - High (VIP) -> `P1 - Urgent` | High (Standard) -> `P2 - Elevated`
       - Medium (VIP) -> `P2 - Elevated` | Medium (Standard) -> `P3 - Standard`
       - Low -> `P3 - Standard`
   - Agency Risk Classification:
     - `CRITICAL (Immediate Churn Risk)`: VIP and (avg_sentiment < -0.4 or active_escalations >= 3).
     - `ELEVATED (SLA Delay)`: avg_sentiment < -0.3 or active_escalations >= 4.
     - `STABLE`: otherwise.

5. **Airline Policy RAG & SLA Forecaster (`src/agents.py:562-638`)**:
   - Policy Knowledge Base:
     - `DEL-DXB`: Emirates, Cancellation Fee ₹3,500, SLA 48h
     - `BLR-MAA`: IndiGo, Cancellation Fee ₹1,500, SLA 24h
     - `DEL-SIN`: Singapore Airlines, Cancellation Fee ₹4,000, SLA 48h
     - `DEL-BOM`: Air India, Cancellation Fee ₹2,000, SLA 24h
     - `COK-DXB`: Air India Express, Cancellation Fee ₹3,000, SLA 48h
     - `MAA-CMB`: SriLankan Airlines, Cancellation Fee ₹2,500, SLA 48h
     - International Fallback: ₹3,500, SLA 48h; Domestic Fallback: ₹2,000, SLA 24h.
   - Predictive SLA Breach Forecaster:
     - Calculates elapsed hours between `Request Date` and `current_date` (2026-06-30).
     - If status is open/pending and elapsed hours >= 72h -> `is_breached = True`, `risk_level = "High"`.

---

## 2. Logic Chain
1. **From Monolithic View Logic to Stateless Services**: Streamlit views currently perform in-memory pandas slicing, raw sqlite updates, and mock session state caching. Decoupling requires refactoring this domain logic into dedicated backend services in `backend/app/services/` (`reconciliation.py`, `metrics.py`, `partner_health.py`, `policy.py`).
2. **From Direct SQLite Calls to SQLAlchemy ORM**: Backend services interact with SQLite via SQLAlchemy `Session` dependencies, ensuring typed queries, thread safety, and ACID transactional integrity.
3. **From Frontend Action Handlers to Secure FastAPI Routers**: The business operations are exposed as REST endpoints in `backend/app/routers/` (`reconciliation.py`, `metrics.py`, `partners.py`), guarded by JWT validation and RBAC (`require_manager` vs `require_operator`).
4. **From Client Mutations to Audit Logs**: All state transitions (e.g. resolving a mismatch, linking an orphan ticket) atomically insert structured records into the `audit_logs` table.
5. **From Monolithic Presentation to REST Client**: Streamlit view components in `src/views/*` are updated to fetch data and trigger mutations purely through HTTP calls via `src/api_client.py`.

---

## 3. Caveats
1. **Seeded Baseline Data vs Mock Tests**: The SQLite database seeded from `data/Support_Tracker.csv` contains 733 records with real-world prices (e.g. RF-1001 = 29,100 INR), whereas prototype unit tests may test with smaller mock fixtures. Services must operate uniformly on both full database tables and test fixtures.
2. **LLM Connectivity Fallback**: When `GEMINI_API_KEY` / `OPENAI_API_KEY` is unavailable, services must seamlessly fallback to deterministic rule-based algorithms (offline sentiment keywords, offline policy lookups, templated draft messages).
3. **RBAC Guard Enforcement**: Manager routes (`/api/v1/reconciliation/*`, `/api/v1/metrics/*`, `/api/v1/partners/*`) must strictly return HTTP 403 Forbidden when invoked by users with role `Operator`.

---

## 4. Conclusion & Architectural Blueprint

### 4.1 Backend Services Architecture (`backend/app/services/`)

#### 1. `backend/app/services/reconciliation.py`
- `calculate_mismatches_from_db(db: Session, risk_level_filter: Optional[str] = None) -> List[dict]`
- `calculate_orphans_from_db(db: Session) -> Tuple[List[dict], List[dict]]`
- `resolve_discrepancy(db: Session, ticket_id: str, new_status: str, notes: Optional[str], user_id: str, user_role: str) -> dict`
- `link_orphan_ticket(db: Session, support_ticket_id: str, finance_ref_no: str, user_id: str, user_role: str) -> dict`
- `draft_discrepancy_explanation(agent: str, route: str, ticket_id: str, support_amt: float, finance_amt: float, deduction: float, reason: str) -> str`
- `generate_lifecycle_notification(ticket_id: str, agent_name: str, route: str, stage: str, amount: Optional[str], deduction: Optional[str], channel: str) -> dict`

#### 2. `backend/app/services/metrics.py`
- `calculate_dashboard_telemetry(db: Session, window_filter: str = "All (Feb–Jun 2026)", agency_filter: Optional[str] = None) -> dict`
- `generate_rca_synthesis_report(db: Session, force_refresh: bool = False) -> dict`

#### 3. `backend/app/services/partner_health.py`
- `get_partner_health_matrix_data(db: Session) -> dict`
- `get_partner_agency_detail(db: Session, agency_name: str) -> dict`
- `analyze_partner_sentiment_scoring(text: str, agency_tier: str = "Standard") -> dict`

#### 4. `backend/app/services/policy.py`
- `lookup_airline_fare_policy(route: str, carrier: Optional[str] = None) -> dict`
- `evaluate_sla_breach_risk(ticket: dict, current_date: str = "2026-06-30") -> dict`

---

### 4.2 Pydantic Schemas (`backend/app/schemas/`)

#### 1. `backend/app/schemas/reconciliation.py`
- `MismatchItem` (`ticket_id: str`, `finance_ref_no: str`, `agent: str`, `route: str`, `support_amount: float`, `finance_amount: float`, `deduction: float`, `reason: str`, `risk_level: str`)
- `OrphanResponse` (`missing_in_finance: List[dict]`, `missing_in_support: List[dict]`, `total_missing_in_finance: int`, `total_missing_in_support: int`)
- `ResolveMismatchRequest` (`ticket_id: str`, `new_status: str`, `notes: Optional[str]`)
- `ResolveMismatchResponse` (`success: bool`, `ticket_id: str`, `status: str`, `notes: Optional[str], audit_id: Optional[int]`, `message: str`)
- `LinkOrphanRequest` (`support_ticket_id: str`, `finance_ref_no: str`)
- `LinkOrphanResponse` (`success: bool`, `merged_ticket_id: str`, `audit_id: Optional[int]`, `message: str`)
- `DraftExplanationRequest` & `DraftExplanationResponse`
- `ProactiveNotificationRequest` & `ProactiveNotificationResponse`

#### 2. `backend/app/schemas/metrics.py`
- `DashboardSummary` (`total_escalations: int`, `avg_ttr: float`, `dropped_handoffs: int`, `deduction_mismatches: int`, `total_pipeline: int`, `healthy_count: int`, `health_pct: float`, `financial_exposure_inr: float`, `manual_hours_saved: int`, `automation_rate_pct: float`)
- `CorridorNode` (`intake_claims: int`, `audited_tickets: int`, `dropped_before_sync: int`, `clean_settlements: int`, `mismatch_count: int`)
- `MonthlyTrendItem` (`month: str`, `disputes: int`, `value_lakhs: float`)
- `RootCauseItem` (`cause: str`, `count: int`, `value_lakhs: float`)
- `ParetoItem` (`category: str`, `count: int`)
- `CarrierHealthItem` (`name: str`, `type: str`, `type_color: str`, `fee: str`, `sla: str`, `pct: int`)
- `DashboardMetricsResponse`
- `RCASynthesisResponse` (`executive_summary: str`, `key_findings: List[RCAFindingItem]`, `projected_outcome: str`, `generated_at: str`)

#### 3. `backend/app/schemas/partners.py`
- `FleetSummary` (`total_monitored_agencies: int`, `critical_vips_count: int`, `fleet_sentiment_index: float`, `dominant_complaint: str`)
- `PartnerHealthItem` (`agency_name: str`, `revenue_tier: str`, `active_escalations: int`, `sentiment_index: float`, `primary_bottleneck: str`, `risk_status: str`)
- `PartnerMatrixResponse` (`fleet_summary: FleetSummary`, `partners: List[PartnerHealthItem]`)
- `PartnerDetailResponse` (`agency_name: str`, `tier: str`, `active_escalations: int`, `sentiment_index: float`, `risk_status: str`, `primary_bottleneck: str`, `recent_messages: List[str]`, `associated_tickets: List[str]`, `recommended_action: str`)
- `AirlinePolicyResponse` (`route: str`, `carrier: str`, `cancellation_fee: float`, `policy_notes: str`, `sla_hours: int`)
- `PredictSLABreachRequest` & `PredictSLABreachResponse`

---

### 4.3 REST API Routers (`backend/app/routers/`)

#### 1. `backend/app/routers/reconciliation.py`
- `GET /api/v1/reconciliation/mismatches` (Guards: `require_manager`, `get_db`) -> `List[MismatchItem]`
- `GET /api/v1/reconciliation/orphans` (Guards: `require_manager`, `get_db`) -> `OrphanResponse`
- `POST /api/v1/reconciliation/resolve-mismatch` (Guards: `require_manager`, `get_db`) -> `ResolveMismatchResponse`
- `POST /api/v1/reconciliation/link-orphan` (Guards: `require_manager`, `get_db`) -> `LinkOrphanResponse`
- `POST /api/v1/reconciliation/draft-explanation` (Guards: `get_current_user`) -> `DraftExplanationResponse`
- `POST /api/v1/reconciliation/proactive-notification` (Guards: `get_current_user`) -> `ProactiveNotificationResponse`

#### 2. `backend/app/routers/metrics.py`
- `GET /api/v1/metrics/dashboard` (Guards: `require_manager`, `get_db`) -> `DashboardMetricsResponse`
- `GET /api/v1/metrics/rca` (Guards: `require_manager`, `get_db`) -> `RCASynthesisResponse`

#### 3. `backend/app/routers/partners.py`
- `GET /api/v1/partners/matrix` (Guards: `require_manager`, `get_db`) -> `PartnerMatrixResponse`
- `GET /api/v1/partners/{agency_name}` (Guards: `require_manager`, `get_db`) -> `PartnerDetailResponse`
- `GET /api/v1/policy/airline-penalty` (Guards: `get_current_user`) -> `AirlinePolicyResponse`
- `POST /api/v1/policy/predict-sla-breach` (Guards: `get_current_user`) -> `PredictSLABreachResponse`

---

### 4.4 App Registration (`backend/app/main.py`)
Include routers under `settings.API_V1_PREFIX`:
```python
from backend.app.routers.reconciliation import router as reconciliation_router
from backend.app.routers.metrics import router as metrics_router
from backend.app.routers.partners import router as partners_router

app.include_router(reconciliation_router, prefix=api_prefix)
app.include_router(metrics_router, prefix=api_prefix)
app.include_router(partners_router, prefix=api_prefix)
```

---

### 4.5 Streamlit View Decoupling Migration Plan (`src/views/*`)
1. **`src/views/reconciliation.py`**:
   - Replace local `find_mismatches` with `api_client.get('/api/v1/reconciliation/mismatches')`.
   - Replace local `find_orphans` with `api_client.get('/api/v1/reconciliation/orphans')`.
   - Replace direct DB status update with `api_client.post('/api/v1/reconciliation/resolve-mismatch', json={'ticket_id': tid, 'new_status': 'Client Notified', 'notes': ...})`.
   - Replace direct DB merge with `api_client.post('/api/v1/reconciliation/link-orphan', json={'support_ticket_id': s_id, 'finance_ref_no': f_id})`.
   - Replace local penalty lookup with `api_client.get('/api/v1/policy/airline-penalty', params={'route': ...})`.
2. **`src/views/dashboard.py`**:
   - Replace `calculate_dashboard_metrics` with `api_client.get('/api/v1/metrics/dashboard', params={'window': selected_window})`.
   - Replace `run_ai_rca` with `api_client.get('/api/v1/metrics/rca')`.
3. **`src/views/partner_matrix.py`**:
   - Replace local aggregation with `api_client.get('/api/v1/partners/matrix')`.
   - Replace agency drill-down with `api_client.get(f'/api/v1/partners/{selected_agency}')`.

---

## 5. Verification Method

1. **Unit & Domain Tests**:
   - `pytest backend/tests/test_reconciliation.py`
   - `pytest backend/tests/test_metrics_partners.py`
2. **FastAPI Endpoints Verification**:
   - Manager Auth: `GET /api/v1/reconciliation/mismatches` -> HTTP 200 OK
   - Operator Auth: `GET /api/v1/reconciliation/mismatches` -> HTTP 403 Forbidden
   - Manager Auth: `GET /api/v1/metrics/dashboard` -> HTTP 200 OK
   - Operator Auth: `GET /api/v1/metrics/dashboard` -> HTTP 403 Forbidden
   - Manager Auth: `GET /api/v1/partners/matrix` -> HTTP 200 OK
3. **Full Pytest Suite**:
   - `pytest backend/tests/` (verifying 100% pass across all test tiers).
