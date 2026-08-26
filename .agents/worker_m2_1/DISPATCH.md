## 2026-08-25T14:20:05Z

You are Worker M2 for Milestone 2 (Authentication & RBAC Layer).
Your working directory is c:\Users\vikash\Documents\SSOT_Parser\.agents\worker_m2_1.
Your project root is c:\Users\vikash\Documents\SSOT_Parser.
You MUST read c:\Users\vikash\Documents\SSOT_Parser\.agents\ORIGINAL_REQUEST.md before starting work.
Also read c:\Users\vikash\Documents\SSOT_Parser\PROJECT.md, c:\Users\vikash\Documents\SSOT_Parser\TEST_INFRA.md, and the explorer reports at:
- c:\Users\vikash\Documents\SSOT_Parser\.agents\explorer_m2_1\handoff.md
- c:\Users\vikash\Documents\SSOT_Parser\.agents\explorer_m2_2\handoff.md
- c:\Users\vikash\Documents\SSOT_Parser\.agents\explorer_m2_3\handoff.md

Your tasks:
1. Implement Backend Security & RBAC:
   - `backend/app/core/security.py`: HS256 JWT encoding, decoding, token expiration validation using python standard library (hmac, hashlib, base64, json).
   - `backend/app/core/rbac.py`: `get_current_user` dependency extracting and validating Bearer token; `require_role(allowed_roles: List[str])` dependency factory returning HTTP 403 when role is not in allowed roles.
   - `backend/app/schemas/auth.py`: `MockLoginRequest`, `TokenResponse`, `UserProfile` Pydantic models.
   - `backend/app/routers/auth.py`: `POST /api/v1/auth/mock-login`, `GET /api/v1/auth/me`.
   - Mount auth router in `backend/app/main.py`.
   - Apply `require_role(["Manager"])` protection to `backend/app/routers/finance.py`.
2. Implement Frontend Authentication & Client:
   - `src/api_client.py`: APIClient class with methods (get, post, patch, put, delete), automatic Bearer token header injection from `st.session_state.access_token`, error interceptors for 401/403.
   - `src/auth.py`: `init_auth_state()`, `login_mock(role, username)`, `logout()`, `require_auth()`, `require_role()`.
   - `app.py`: Replace legacy mock form with modern Identity Gateway supporting 1-click Mock OAuth for Manager & Operator personas, JWT session state management, and role-based `st.navigation`.
   - `src/views/database_explorer.py`: Update DLP role check to `'Operator'`.
3. Verify test suite:
   `python -m pytest backend/tests/test_auth.py backend/tests/test_database.py backend/tests/test_main.py backend/tests/test_support_api.py backend/tests/test_finance_api.py backend/tests/test_escalations_api.py backend/tests/test_support_crud.py -v`
4. Verify 100% tests pass with 0 failures and 0 errors.
5. Write your complete handoff report to `c:\Users\vikash\Documents\SSOT_Parser\.agents\worker_m2_1\handoff.md` and notify parent via send_message.
