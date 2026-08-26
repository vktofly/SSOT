# Handoff Report: Milestone 2 — Authentication & RBAC Layer Investigation

## 1. Observation

### Codebase Inspection & Runtime Test Observations
1. **Test Failure in Existing Auth Suite**:
   Running `pytest backend/tests/test_auth.py -v` yields 1 failure:
   ```
   FAILED backend/tests/test_auth.py::test_rbac_operator_denied_manager_endpoints_returns_403
   AssertionError: Expected 403 Forbidden for Operator on /api/v1/finance-records, got 200
   assert 200 == 403
   ```
   - In `backend/app/routers/finance.py` lines 20-30, endpoints have `db: Session = Depends(get_db)` but NO role verification dependency (`Depends(require_role(["Manager"]))`).

2. **Missing Core Security & Auth Router Modules**:
   - Directory `backend/app/core/` does not exist.
   - Files `backend/app/core/security.py`, `backend/app/core/rbac.py`, and `backend/app/core/dlp.py` are absent.
   - File `backend/app/routers/auth.py` and schema `backend/app/schemas/auth.py` are absent.
   - In `backend/app/main.py` lines 63-67, only `support_router`, `finance_router`, and `escalations_router` are registered.

3. **Frontend Legacy Mock Authentication**:
   - `app.py` lines 55-88 contains an in-memory hardcoded dictionary `MOCK_USERS = {"manager": ..., "operator": ...}` with local SHA256 password hashing.
   - `app.py` does not issue or store JWT bearer tokens.
   - `src/api_client.py` and `src/auth.py` do not exist.

4. **Python Environment Package Constraints**:
   - Inspecting installed modules reveals: `jose: NOT available`, `jwt: NOT available`, `passlib: NOT available`, `bcrypt: NOT available`.
   - Standard library `hmac`, `hashlib`, `json`, `base64` are fully functional and already used for HS256 JWT operations in `backend/tests/conftest.py` lines 43–84 and `backend/tests/test_auth.py` lines 20–49.

---

## 2. Logic Chain

1. **Root Cause of RBAC Test Failure (Observation 1)**:
   - `test_rbac_operator_denied_manager_endpoints_returns_403` expects `/api/v1/finance-records` to return HTTP 403 when called with `Authorization: Bearer <operator_token>`.
   - Because `finance.py` currently has no role guard, any request (authenticated or unauthenticated) receives HTTP 200. Adding `require_role(["Manager"])` dependency resolves this failure immediately.

2. **Zero-Dependency Cryptographic Token Engine (Observation 4)**:
   - Because third-party JWT packages (`python-jose`, `PyJWT`) are not in the environment, `backend/app/core/security.py` must implement standard RFC 7519 HMAC-SHA256 (HS256) encoding/decoding using Python's built-in `hmac`, `hashlib`, `json`, and `base64`.
   - This provides 100% interoperability with `backend/tests/conftest.py`'s `generate_jwt_token` and eliminates external dependency installation risks.

3. **End-to-End Auth & Session Decoupling (Observations 2 & 3)**:
   - Backend needs:
     - `POST /api/v1/auth/mock-login`: Validates role (`Manager` or `Operator`), generates signed JWT token with 24h expiration, returns `TokenResponse`.
     - `GET /api/v1/auth/me`: Validates `Authorization: Bearer <token>`, returns `UserProfile`.
     - `POST /api/v1/auth/refresh`: Issues renewed JWT for active sessions.
     - `require_role(["Manager"])` and `require_role(["Operator", "Manager"])` dependencies.
   - Frontend needs:
     - `src/api_client.py`: Centralized HTTP client attaching Bearer token to all requests, with automatic 401 handling (session reset) and 403 handling (permission denied).
     - `src/auth.py`: Manages `st.session_state` tokens and provides `render_login_gate()`.
     - `app.py`: Replaces old password gateway with Identity Gateway supporting 1-click Role Login ("Login as Manager", "Login as Operator") and integrates `st.navigation` role isolation.

4. **DLP Field Masking for Operator Role**:
   - `backend/app/core/dlp.py` provides regex-based PII masking for emails (`j***@domain.com`), phone numbers (`+91-XXXXX-1234`), and 16-digit card/account numbers (`XXXX-XXXX-XXXX-1234`).
   - When Operator requests support tickets or escalations, customer contact info and internal financial annotations are redacted.
   - Manager receives full unmasked data for audit compliance and reconciliation.

---

## 3. Caveats

- **Mock OAuth vs Real Identity Providers**: `AUTH_MODE=mock` is implemented as the primary deterministic provider per `TEST_INFRA.md` zero-network requirement. The architecture supports OAuth 2.0 PKCE extensions when cloud credentials (`AUTH0_DOMAIN`, `GOOGLE_CLIENT_ID`) are supplied in `.env`.
- **Streamlit Execution Environment**: Streamlit is installed under Python 3.14 on this machine, while FastAPI and Pytest run under Python 3.13. All created modules in `src/` must remain pure Python without version-specific syntax.

---

## 4. Conclusion

Milestone 2 implementation is completely mapped with zero blockers. Worker M2 should execute the following bounded tasks:

### Task Breakdown for Worker M2:

1. **Create `backend/app/core/security.py`**:
   - HS256 JWT encoding (`create_access_token`) and decoding (`decode_access_token`).
   - Token expiration, signature verification, and standard claims validation.

2. **Create `backend/app/schemas/auth.py`**:
   - `UserProfile`, `LoginRequest`, `TokenResponse`, `RefreshTokenRequest`.

3. **Create `backend/app/core/rbac.py`**:
   - `get_current_user`, `require_role(allowed_roles: List[str])`, `require_manager`, `require_operator`, `require_authenticated`.
   - Returns 401 on missing/invalid/expired token; returns 403 on role mismatch.

4. **Create `backend/app/core/dlp.py`**:
   - Regex-based PII masking (`mask_pii_string`, `mask_support_ticket`, `mask_finance_record`).

5. **Create `backend/app/routers/auth.py` & Register in `backend/app/main.py`**:
   - Endpoints: `POST /api/v1/auth/mock-login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/refresh`.
   - Add `app.include_router(auth_router, prefix=api_prefix)` in `main.py`.

6. **Apply RBAC Dependencies to Routers**:
   - `backend/app/routers/finance.py`: All endpoints guarded by `Depends(require_role(["Manager"]))`.
   - `backend/app/routers/support.py` & `backend/app/routers/escalations.py`: Guarded by `Depends(require_role(["Manager", "Operator"]))`.

7. **Create `src/api_client.py` & `src/auth.py`**:
   - `src/api_client.py`: Authenticated REST client using `requests`.
   - `src/auth.py`: Session state token handling, role verification, and login gate UI.

8. **Update `app.py`**:
   - Replace old password gateway with `src.auth.render_login_gate()`.
   - Configure role-based `st.navigation` (Manager: 6 views; Operator: 2 views).

9. **Expand Pytest Suite in `backend/tests/test_auth.py` & `backend/tests/test_streamlit_auth.py`**:
   - Add test cases for token refresh, DLP field masking, and Streamlit auth state verification.

---

## 5. Verification Method

### Automated Commands
1. **Run Auth & RBAC Pytest Suite**:
   ```powershell
   pytest backend/tests/test_auth.py -v
   ```
   *Success criteria*: 100% tests pass (17+ tests, 0 failures).

2. **Run Full Backend Regression Test Suite**:
   ```powershell
   pytest backend/tests/ -v
   ```
   *Success criteria*: All M1 and M2 tests pass.

3. **Verify Streamlit Auth Verification Script**:
   ```powershell
   pytest backend/tests/test_streamlit_auth.py -v
   ```

### Invalidation Conditions
- If any Operator request to `/api/v1/finance-records` returns HTTP 200 instead of 403 Forbidden.
- If an unauthenticated request to `/api/v1/auth/me` returns HTTP 200 instead of 401 Unauthorized.
- If an expired token is accepted without raising 401.
