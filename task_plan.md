# 📋 BharatTrip Project Task Plan

## Milestone 1: Problem Definition & Data Audit
- [x] Extract and reconcile `Support_Tracker.csv` (600 rows) against `Finance_Tracker.csv` (500 rows)
- [x] Identify root causes: 100 dropped handoffs, 149 deduction mismatches, off-tracker messaging leaks
- [x] Benchmark escalation resolution time (Avg: 16.4 days)

## Milestone 2: Solution Architecture & Operating Model
- [x] Design Single Source of Truth (SSOT) SQLite/PostgreSQL schema with unified `Global_Ticket_ID`
- [x] Define Human-In-The-Loop (HITL) boundary: AI parses and drafts, humans approve payouts/actions
- [x] Establish Role-Based Access Control (RBAC) & Data Loss Prevention (DLP) specifications

## Milestone 3: AI Prototype Implementation
- [x] Build Operations Telemetry Dashboard with dynamic KPI cards
- [x] Build Event-Driven Ingestion Agent with PII redaction and route validation guardrails
- [x] Build Automated Reconciliation Agent with short-payment email drafting
- [x] Build Cross-Department Database Explorer with global search
- [x] Implement Audit Logging for all operator approvals

## Milestone 4: Deliverables & Verification
- [x] Finalize 3-page Business Case & Solution Proposal (`deliverables/write_up.pdf`)
- [x] Generate System Architecture and Telemetry Visuals (`deliverables/architecture.png`, `deliverables/metrics.png`)
- [x] Export Complete Prompt History (`deliverables/prompt_history.txt`)
- [x] End-to-end user acceptance testing across both `Manager` and `Operator` personas
- [x] Pre-flight shipping checklist & deployment configuration verified

## Milestone 5: Future Expansion Roadmap
- [x] 1. Proactive Agent Notification Bot (Bi-directional WhatsApp/Email status pusher)
- [x] 2. Predictive SLA Breach Forecaster ($\ge 72$h latency early warning)
- [x] 3. Airline Policy RAG Engine (Carrier penalty tier lookup)
- [x] 4. Direct Banking Gateway Bridge (B2B RazorpayX / Cashfree webhook)
- [x] 5. Partner Frustration & Priority Scoring (NLP urgency classifier)
## Milestone 6: Multi-Page Operations Suite
- [x] Modern `st.navigation` Declarative URL Router (`/dashboard`, `/partners`, `/database`, `/ingestion`, `/reconciliation`, `/triage`)
- [x] Partner Health & Churn Risk Matrix (`/partners`) with VIP retention radar and outreach dispatch
## Milestone 7: Codebase Modularization & Architecture
- [x] Extracted 1,000+ line monolithic `ui_components.py` into dedicated `src/views/` package:
  - [`src/views/dashboard.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/dashboard.py)
  - [`src/views/ingestion.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/ingestion.py)
  - [`src/views/reconciliation.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/reconciliation.py)
  - [`src/views/database_explorer.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/database_explorer.py)
  - [`src/views/escalation_triage.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/escalation_triage.py)
  - [`src/views/partner_matrix.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/partner_matrix.py)
## Milestone 8: Coding Standards Enforcement
- [x] Standardized `src/db.py` with context managers, parameterized execution, and typing
- [x] Standardized `src/data_manager.py` with named constants, type annotations, and immutability
- [x] Verified full unit test pass suite (5/5 tests passing in 1.012s)

## Milestone 9: Frontend UI & Accessibility Engineering
- [x] Refactored [`src/views/ingestion.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/ingestion.py) to meet `frontend-ui-engineering` standards:
  - Eliminated arbitrary inline CSS for native Streamlit design tokens
  - Structured HITL form into grouped containers with field tooltips
  - Replaced text-only confidence scores with visual progress meters
  - Enhanced queue empty states and guarded against accidental item discard
- [x] Verified full unit test pass suite (5/5 tests passing in 0.894s)

## Milestone 10: Frontend Patterns & Reactive Ingestion Playground
- [x] Upgraded [`src/views/ingestion.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/ingestion.py) with modern `frontend-patterns`:
  - Interactive Custom Payload Injector with live JSON extraction preview
  - Multi-channel stream filtering (`WhatsApp`, `Email`, `Portal`, `Phone`, `OTA API`)
  - Optimistic toast notifications on batch parsing, single ingest, and SSOT commits
  - Normalized container data flow with distinct ID tracking across streams
- [x] Verified full unit test pass suite (5/5 tests passing in 1.170s)

## Milestone 11: Drag-and-Drop Batch File Ingestion
- [x] Implemented multi-format file uploader (`.csv` and `.json`) in [`src/views/ingestion.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/ingestion.py):
  - Automatic column mapping for `text`, `message`, `raw_text`, `channel`
  - Validated preview data table with live row count
  - One-click bulk enqueue to live inbound webhook stream
  - Dynamic `importlib.reload` in [`app.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/app.py) for instantaneous view updates
- [x] Verified full unit test pass suite (5/5 tests passing in 0.908s)

## Milestone 12: Telemetry Dashboard & AI RCA Studio
- [x] Upgraded [`src/views/dashboard.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/dashboard.py) with executive analytics:
  - Interactive Feb–June monthly escalation spike trajectory chart
  - Primary root cause discrepancy distribution chart (82.7% concentration)
  - Multi-tab AI RCA workspace (*Executive Summary*, *Financial Leakage*, *SLA Forecast*)
  - Theme-compliant native badges and automated module reload in [`app.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/app.py)
- [x] Verified full unit test pass suite (5/5 tests passing in 1.325s)

## Milestone 13: Partner Complaint Pareto & Churn Risk Analytics
- [x] Integrated real-dataset complaint analytics in [`src/views/dashboard.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/dashboard.py):
  - Top 5 At-Risk Agency breakdown table (*Peak Journeys*, *BlueJet Tours*, *TripHub*, *GoFly Holidays*, *Metro Yatra*)
  - 5-category Complaint Theme Pareto distribution chart
  - Automated calculation of silent delay & ghost handoff concentration (72.6%)
- [x] Verified full unit test pass suite (5/5 tests passing in 1.236s)

## Milestone 14: Visual Hierarchy & Interactive Telemetry Chips
- [x] Applied `designing-beautiful-websites` system to [`src/views/dashboard.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/dashboard.py):
  - Interactive window filter chips (`All`, `Last 30 Days`, `Q1`, `Q2`) with dynamic KPI re-computation
  - Glassmorphic metric cards with micro-trend badges (`↑ 6.5x climb`, `8.2x SLA gap`)
  - Elevated section containers and fast-track navigation callouts
- [x] Verified full unit test pass suite (5/5 tests passing in 1.299s)

## Milestone 15: Distinctive B2B Operations Microcopy & Signal Palette
- [x] Applied `frontend-design` principles to [`src/views/dashboard.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/dashboard.py):
  - Aviation corridor status headers and active-voice action labels ("Reconcile Short Payments")
  - Precise domain figures (₹14,80,000+ contested balances, 16.4-day latency benchmarks)
  - Clear signal color palettes for clean settlements, dropped handoffs, and deduction mismatches
- [x] Verified full unit test pass suite (5/5 tests passing in 1.261s)

## Milestone 16: 3-Hop Pipeline Flight Corridor Graphical Diagram
- [x] Implemented signature visual corridor in [`src/views/dashboard.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/dashboard.py):
  - 3 connected workflow stages (*1. Inbound Intake*, *2. Support Validation*, *3. Finance Settlement*)
  - Real-time dropped handoff warning corridors (100 missing tickets flagged in red)
  - Finance settlement variance callouts (149 deduction mismatches / ₹14.8L contested)
- [x] Verified full unit test pass suite (5/5 tests passing in 0.956s)

## Milestone 17: Side-by-Side Ledger Cards & Reconciliation HITL Refactor
- [x] Refactored [`src/views/reconciliation.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/reconciliation.py) with design standards:
  - Eliminated arbitrary inline CSS tags for native Streamlit tokens and alert badges
  - Side-by-side ledger cards comparing Support vs. Finance payout details
  - Integrated live Airline Fare Rules expanders (Indigo, Air India, SpiceJet, Emirates)
  - Added multi-agent filtering and one-click bulk merge for AI entity resolution
- [x] Verified full unit test pass suite (5/5 tests passing in 0.936s)

## Milestone 18: Database Explorer UI Engineering & Search Hardening
- [x] Refactored [`src/views/database_explorer.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/database_explorer.py):
  - Hardened global search with `regex=False` to eliminate regex warnings on special characters
  - Dynamic multi-table search hit counters (`Found N matching records across 3 tables`)
  - Clean native header tokens, role-based DLP masking, and instant module reloading in [`app.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/app.py)
- [x] Verified full unit test pass suite (5/5 tests passing in 0.913s)

## Milestone 19: Visual-First Dashboard UI/UX Streamlining
- [x] Redesigned [`src/views/dashboard.py`](file:///c:/Users/vikash/Documents/SSOT_Parser/src/views/dashboard.py) for high glanceability:
  - Replaced long descriptive paragraphs with 3 compact executive cards (*Core Discrepancy*, *Financial Leakage*, *Recovery Projection*)
  - Streamlined 3-Hop Pipeline corridor into clean metric badges
  - Moved deep AI LLM synthesis into on-demand collapsible expander
  - Tightened chart captions and typography for a crisp 5-second glance test
- [x] Verified full unit test pass suite (5/5 tests passing in 0.947s)
