# E2E Test Infra: BharatTrip AI Escalation Resolver

## Test Philosophy
- Opaque-box, requirement-driven testing. Derived strictly from `ORIGINAL_REQUEST.md` and user specifications.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinatorial Testing + Real-World Workload Testing.
- Zero network reliance for deterministic CI: All tests utilize mock OAuth provider and local LLM fallbacks.

## Feature Inventory & Test Mapping
| # | Feature | Requirement Source | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Pairwise) | Tier 4 (Scenario) |
|---|---|---|:---:|:---:|:---:|:---:|
| 1 | SQLite DB & SQLAlchemy Models | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 2 | CSV-to-SQLite Hydration | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 3 | Core Data CRUD Endpoints | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 4 | OAuth 2.0 & Mock Auth Provider | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 5 | JWT Security & RBAC Guards | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 6 | Streamlit Auth & Session Mgmt | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 7 | Streamlit Role Route Security | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 8 | Discrepancy & Recon Services | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 9 | Operations Metrics & RCA API | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 10 | Partner Health & Policy RAG | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 11 | Streamlit UI REST Decoupling | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 12 | LangGraph Typed AgentState | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 13 | Specialized Multi-Agent Nodes | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 14 | Guardrail Reflection & HITL | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 15 | FastAPI Multi-Agent Resolve API| ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- **Test Runner**: Pytest (`pytest backend/tests -v --tb=short`)
- **Pass/Fail Semantics**: All test assertions must pass with exit code 0.
- **Directory Layout**:
  - `backend/tests/test_auth.py`: OAuth, Mock OAuth tokens, JWT validation, and RBAC endpoint permissions.
  - `backend/tests/test_database.py`: SQLAlchemy models, `seed_db.py` hydration, data normalization, and constraints.
  - `backend/tests/test_support_crud.py`: Support ticket CRUD operations, filtering, pagination, and status transitions.
  - `backend/tests/test_reconciliation.py`: Deduction mismatch logic, orphan detection, and settlement endpoints.
  - `backend/tests/test_metrics_partners.py`: KPI computations, partner health scoring, and airline policy RAG lookup.
  - `backend/tests/test_langgraph_workflow.py`: AgentState mutations, node routing, guardrail reflections, HITL triggers, and SSE streaming.
  - `backend/tests/test_e2e_scenarios.py`: Full end-to-end multi-agent resolution and business lifecycle scenarios.
  - `backend/tests/test_adversarial.py`: Prompt injections, invalid payload fuzzing, offline LLM fallback, and concurrency locks.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|---|---|---|
| 1 | Routine Status Inquiry | Auth, Support CRUD, Routing Node, SSOT Lookup, Response Gen | Medium |
| 2 | High-Deduction Cancellation Dispute | Auth, Recon Service, Policy RAG Node, Discrepancy Matching, Response Gen | High |
| 3 | Urgent P0 Churn Threat VIP Escalation | Auth, RBAC, Sentiment Node (P0), SLA Forecaster, HITL Flagging, Audit Log | High |
| 4 | Unstructured Informal WhatsApp Ingestion | Auth, Ingestion Endpoint, PII Redaction, Route Whitelist, Staged Commit | Medium |
| 5 | End-to-End Operator vs Manager Workflow | Full RBAC Route Guarding, Data Masking, CSV Export, Batch Settlement | High |

## Coverage Thresholds
- Tier 1: Feature Coverage (≥5 tests per feature)
- Tier 2: Boundary & Corner Cases (≥5 tests per feature)
- Tier 3: Cross-Feature Combinations (Pairwise matrix across Auth, DB, Recon, and LangGraph)
- Tier 4: Real-World Scenarios (≥5 full end-to-end integration scenarios)
- Total planned test cases: ≥ 100 tests.
