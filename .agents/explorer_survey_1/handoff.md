# Codebase Survey & Architectural Inventory Report

## 1. Observation

### 1.1 Directory & File Structure
The repository at `c:\Users\vikash\Documents\SSOT_Parser` contains the following layout:
- **Application Entry & Config**:
  - `app.py` (175 lines): Monolithic Streamlit application containing mock authentication, session state management, page declarations (`st.Page`), and role-based navigation (`st.navigation`).
  - `.streamlit/config.toml` (8 lines): Streamlit dark theme settings (`#00F0FF` cyan accent, `#0F172A` background).
  - `requirements.txt` (5 lines): `streamlit>=1.39.0`, `pandas>=2.0.0`, `google-genai>=0.3.0`, `requests>=2.30.0`.
  - `.env` (1 line): `GEMINI_API_KEY`.
  - `Dockerfile` (22 lines): Python 3.11-slim container running `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`.
  - `package.json` & `playwright.config.ts`: Dev configuration for `@playwright/test` v1.62.1.
  - `take_screenshot.py` & `inspect_dom.py`: Playwright automation scripts for UI capture.
- **Core Modules (`src/`)**:
  - `src/config.py` (35 lines): API key resolution (`os.environ`, `.env`, `st.secrets`) and Gemini client creation (`genai.Client`).
  - `src/db.py` (83 lines): Direct SQLite connection management and parameterized SQL execution (`insert_support_record`, `update_support_status`, `delete_escalation`, `update_ticket_id`) accessing `data/ssot.db`.
  - `src/data_manager.py` (193 lines): `clean_money_string`, `load_data` (`@st.cache_data`), `seed_from_csv`, `find_mismatches` (using `difflib.get_close_matches`), `find_orphans`.
  - `src/agents.py` (642 lines): LLM prompts and agent routines (`redact_pii`, `parse_informal_message`, `draft_reconciliation_message`, `analyze_escalations`, `fuzzy_match_metadata`, `batch_fuzzy_match_metadata`, `draft_escalation_response`, `generate_proactive_notification`, `analyze_partner_sentiment`, `lookup_airline_penalty`, `predict_sla_breach`).
  - `src/ui_components.py` (20 lines) & `src/views/__init__.py` (17 lines): Module re-export layers.
  - `src/assets/style.css` (242 lines): Glassmorphic styling, CSS variables, DLP selection controls, and metric overrides.
- **Modular Views (`src/views/`)**:
  - `src/views/dashboard.py` (802 lines): Operations Dashboard (`render_dashboard`) with health gauge, KPI stat cards, Material pipeline stepper, carrier SLA health, interactive Altair dispute charts, Pareto complaint analysis, and Copilot chat.
  - `src/views/ingestion.py` (453 lines): Ingestion Agent view (`render_ingestion`) with single message playground, CSV/JSON drag-and-drop batch upload, incoming queue, and staged Human-In-The-Loop review & database commit.
  - `src/views/reconciliation.py` (538 lines): Reconciliation Agent view (`render_reconciliation`) with deduction mismatch audits, AI email drafting, orphaned ticket cross-ledger AI linkage, and proactive notification bot.
  - `src/views/database_explorer.py` (138 lines): Database Explorer (`render_database_explorer`) with multi-table search, Junior role DLP masking (`mask_sensitive_data`), and CSV export.
  - `src/views/escalation_triage.py` (120 lines): Escalation Triage (`render_escalation_triage`) with queue management, NLP urgency scoring, SSOT cross-lookup, and AI response drafting.
  - `src/views/partner_matrix.py` (125 lines): Partner Health Matrix (`render_partner_matrix`) with B2B partner health scores, VIP vs Standard tier tracking, and fast outreach.
- **Data Store (`data/`)**:
  - `data/Support_Tracker.csv` (759 lines): Inbound refund requests logged by Support.
  - `data/Finance_Tracker.csv` (693 lines): Actual banking payouts logged by Finance.
  - `data/Escalations.csv` (159 lines): Partner complaints log.
  - `data/Read_Me.csv` (42 lines): Process documentation and known operational extract limitations.
  - `data/ssot.db` (192,512 bytes): SQLite database with tables `support_tracker` (760 rows), `finance_tracker` (690 rows), and `escalations` (155 rows).
- **Tests (`tests/`)**:
  - `tests/test_partner_sentiment.py` (34 lines): Unittest testing `analyze_partner_sentiment`.
  - `tests/test_roadmap_agents.py` (27 lines): Unittest testing `lookup_airline_penalty` and `predict_sla_breach`.

### 1.2 Current Authentication & Access Control
- Located in `app.py:50-89`:
  - Static dictionary `MOCK_USERS`:
    - `"manager"`: SHA-256 hash of `admin123`, role `"Manager"`.
    - `"operator"`: SHA-256 hash of `agent123`, role `"Junior"`.
  - Authentication flow: `check_password()` intercepts rendering, displays a Streamlit login form, verifies SHA-256 hash, and populates `st.session_state.logged_in`, `st.session_state.role`, `st.session_state.username`.
  - RBAC Routing (`app.py:144-154`):
    - `Manager`: Access to "Operations Cockpit" (`dashboard`, `partners`, `database`) and "AI Workflows & HITL" (`ingestion`, `reconciliation`, `triage`). Default page: `dashboard`.
    - `Junior` / Operator: Access restricted to "Operator Workspace" (`ingestion`, `triage`). Default page: `triage`.
  - View-level RBAC:
    - `src/views/database_explorer.py:112`: Masks Agent names and hides monetary values (`[HIDDEN]`) for `Junior` role; disables SSOT export button.
    - `src/views/reconciliation.py:491`: Disables audit log CSV download for non-managers.

### 1.3 Data Hydration & Storage Layer
- Located in `src/data_manager.py` and `src/db.py`:
  - Seeding (`src/data_manager.py:46-90`): Reads baseline CSVs skipping metadata headers (`skiprows=1`), strips currency formatting via `clean_money_string`, capitalizes identifiers (`Ticket ID`, `Ref No`), and executes `to_sql` on `data/ssot.db`.
  - SQLite Schema:
    - `support_tracker`: `['Ticket ID', 'Agent', 'Route', 'Refund Amount (INR)', 'Request Date', 'Last Updated', 'Status', 'Handled By', 'Channel', 'Notes']`
    - `finance_tracker`: `['Ref No', 'Agent Name', 'Sector', 'Amount Paid (INR)', 'Deduction (INR)', 'Received On', 'Processed On', 'Payout Status', 'Approved By', 'Remarks']`
    - `escalations`: `['Escalation ID', 'Raised On', 'Ticket ID', 'Raised By', 'Agent', 'Channel', 'Message', 'Status', 'Resolved On', 'Days Open']`
  - In-memory State: `app.py:100-104` loads all three tables into `st.session_state.support_df`, `st.session_state.finance_df`, `st.session_state.escalations_df` as Pandas DataFrames.
  - Mutations: Updates from UI are written both to in-memory DataFrames and SQLite via functions in `src/db.py` (`insert_support_record`, `update_support_status`, `delete_escalation`, `update_ticket_id`).

### 1.4 AI / Agent Functions & Models
- Located in `src/agents.py`:
  - LLM Provider: Primary is Google Gemini (`gemini-3.5-flash` via `google-genai` SDK), with HTTP fallback to OpenAI (`gpt-4o-mini` via `requests`) if API key begins with `sk-`. Mock fallbacks activate when no API key is configured.
  - Key Agents:
    1. **PII Guardrail** (`redact_pii`, line 9): RegEx masking for phones, emails, credit cards before LLM ingestion.
    2. **Ingestion Agent** (`parse_informal_message`, line 19): Extracts JSON entities from unstructured text, validates flight route against a 13-route whitelist, sets `confidence_score` and `needs_human_review`.
    3. **Reconciliation Discrepancy Agent** (`draft_reconciliation_message`, line 111): Drafts 3-sentence polite explanatory emails to travel agencies regarding airline cancellation deductions.
    4. **Executive RCA Agent** (`analyze_escalations`, line 153): Generates bulleted operational summary from pre-aggregated Pandas metrics.
    5. **Cross-Ledger Entity Matcher** (`fuzzy_match_metadata` & `batch_fuzzy_match_metadata`, lines 227-360): Matches orphaned support tickets and finance records using agent name, sector, and amounts.
    6. **Customer Response Agent** (`draft_escalation_response`, line 361): Generates empathetic replies based on SSOT ticket status.
    7. **Partner Sentiment & Priority Classifier** (`analyze_partner_sentiment`, line 458): Categorizes message urgency (Critical/High/Med/Low) and priority rank (P0 to P3) combining rule-based heuristics and optional LLM refinement.
    8. **Airline Policy RAG** (`lookup_airline_penalty`, line 572): Lookups for cancellation penalties and SLAs in `AIRLINE_POLICY_KB`.
    9. **SLA Forecaster** (`predict_sla_breach`, line 596): Rule-based 72-hour breach risk detector.

---

## 2. Logic Chain

1. **Monolithic Coupling**:
   - `app.py` directly executes data loading (`load_data()`), auth verification (`check_password()`), and UI rendering.
   - The UI components (`src/views/*.py`) directly import backend functions from `src/agents.py`, `src/db.py`, and `src/data_manager.py` and mutate `st.session_state` and SQLite simultaneously.
   - Therefore, decoupling into a standalone FastAPI service (per R2) requires exposing endpoints for:
     - Authentication & User Profile / Role Verification
     - Support, Finance, and Escalation CRUD operations
     - Discrepancy & Orphan calculation
     - Ingestion parsing, reconciliation email drafting, and escalation responses.

2. **Database & Data Layer Migration**:
   - Currently, raw SQLite queries and Pandas `to_sql` operations exist in `src/db.py` and `src/data_manager.py`.
   - Migration to SQLAlchemy models (per R2) will require defining ORM models for `SupportTracker`, `FinanceTracker`, and `Escalation` with typed columns, primary keys, and relationships, replacing `sqlite3.connect()` calls with a SQLAlchemy session dependency (`get_db`).

3. **Multi-Agent Orchestration Evolution**:
   - Currently, `src/agents.py` is a flat script with procedural helper functions.
   - Upgrading to LangGraph (per R3) involves creating a structured state graph with specialized nodes:
     - `RouterNode`: Classifies message channel, intent, and agency tier.
     - `ExtractionNode`: Performs PII redaction and structured entity extraction.
     - `PolicyRAGNode`: Queries carrier rules and SSOT ticket state.
     - `ResponseGenNode`: Formulates explanation or escalation response.
     - `HITLNode`: Flags low confidence (<80%) or high variance for human approval before committing.

4. **Authentication Architecture**:
   - Currently, mock authentication resides inside `app.py` using SHA-256 password hashing.
   - Upgrading to OAuth (per R1) requires an authentication provider flow in Streamlit, issuing JWT or session tokens that are passed to FastAPI Authorization headers for RBAC enforcement.

---

## 3. Caveats

- **No Caveats on Codebase Exploration**: All source files, schemas, and test suites have been inspected.
- Note: Environment Python 3.14 includes all required dependencies (`streamlit`, `pandas`, `google-genai`, `requests`, `altair`, `uvicorn`, `starlette`), where unit tests run and pass.

---

## 4. Conclusion

The prototype is well-structured in its UI layer (`src/views/`) and analytical logic, but tightly coupled as a monolithic Streamlit application. The migration paths required for production readiness are:
1. **R1 (Auth & RBAC)**: Replace `check_password()` in `app.py` with OAuth integration; enforce role checks on both Streamlit page routing and FastAPI endpoints.
2. **R2 (FastAPI & SQLAlchemy)**: Build a FastAPI service with SQLAlchemy models for `support_tracker`, `finance_tracker`, and `escalations`; convert Streamlit views to REST API client calls; add pytest test suite.
3. **R3 (LangGraph Orchestration)**: Refactor `src/agents.py` into a multi-node LangGraph state machine executed via FastAPI endpoints with execution trace logging.

---

## 5. Verification Method

To independently verify the survey findings:
1. **Execute existing unit tests**:
   ```bash
   python -m unittest discover -s tests -p "test_*.py"
   ```
2. **Inspect SQLite Schema**:
   ```bash
   python -c "import sqlite3; conn=sqlite3.connect('data/ssot.db'); cur=conn.cursor(); print([t[0] for t in cur.execute('SELECT name FROM sqlite_master WHERE type=\'table\'').fetchall()])"
   ```
3. **Inspect Application Entrypoint & Routes**:
   - Inspect `app.py` lines 50-89 for mock authentication and lines 126-154 for Streamlit page navigation.
4. **Inspect Agent Functions**:
   - Inspect `src/agents.py` lines 19, 111, 227, 361, 458, 572, 596.
