# DISPATCH — Explorer M2 (Instance 3)
Working directory: c:\Users\vikash\Documents\SSOT_Parser\.agents\explorer_m2_3
Project root: c:\Users\vikash\Documents\SSOT_Parser
Original Request: c:\Users\vikash\Documents\SSOT_Parser\.agents\ORIGINAL_REQUEST.md
Project Plan: c:\Users\vikash\Documents\SSOT_Parser\PROJECT.md
Test Plan: c:\Users\vikash\Documents\SSOT_Parser\TEST_INFRA.md

Task:
Investigate Milestone 2: Authentication & RBAC Layer (FastAPI Backend + Streamlit Frontend).
1. Read ORIGINAL_REQUEST.md (§R1) and PROJECT.md (§Feature Inventory #4-7 and Interface Contract #1).
2. Inspect backend auth requirements:
   - `backend/app/core/security.py` (JWT encoding/decoding, password hashing if needed).
   - `backend/app/routers/auth.py` (`POST /api/v1/auth/mock-login`, `GET /api/v1/auth/me`).
   - `backend/app/core/rbac.py` or dependencies (`get_current_user`, `require_role(["Manager"])`, `require_role(["Operator", "Manager"])`).
   - Protecting finance endpoints with Manager-only RBAC; protecting support and escalation endpoints with authenticated role RBAC.
3. Inspect frontend auth requirements:
   - `src/auth.py` and `src/api_client.py` for token handling.
   - `app.py` replacement of old `check_password()` with OAuth/Mock OAuth login flow and role-based `st.navigation` routing.
4. Review existing test cases in `backend/tests/test_auth.py`.
5. Propose concrete implementation plan in `c:\Users\vikash\Documents\SSOT_Parser\.agents\explorer_m2_3\handoff.md` and notify parent.
