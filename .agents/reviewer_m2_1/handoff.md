# Milestone 2 Review & Adversarial Challenge Report: Authentication & RBAC Layer

## 1. Observation

Direct code analysis, adversarial stress tests, and automated pytest execution yielded the following observations:

1. **Security & Cryptography Engine (`backend/app/core/security.py`)**:
   - `generate_jwt_token()` generates standard RFC 7519 HS256 JWT tokens using standard library `hmac`, `hashlib`, `base64`, `json`.
   - `decode_jwt_token()` verifies HMAC-SHA256 signatures with constant-time equality check (`hmac.compare_digest`), parses JSON claims, and strictly validates expiration (`exp < now`).
   - `get_password_hash()` and `verify_password()` provide SHA-256 password hashing with constant-time comparison.

2. **RBAC & Authorization Dependencies (`backend/app/core/rbac.py`)**:
   - `get_token_from_header()` extracts Bearer tokens and rejects missing, empty, or malformed headers with HTTP 401.
   - `get_current_user()` returns a validated `UserProfile(user_id, email, name, role)` or raises HTTP 401 on invalid/expired tokens.
   - `require_role(allowed_roles)` dependency factory enforces role authorization, raising HTTP 403 Forbidden when an unauthorized role attempts access.

3. **Authentication Schemas & Router (`backend/app/schemas/auth.py`, `backend/app/routers/auth.py`, `backend/app/main.py`)**:
   - `MockLoginRequest` validates persona roles (`Literal["Manager", "Operator"]`).
   - `POST /api/v1/auth/mock-login` generates valid 24h JWT tokens and profiles.
   - `GET /api/v1/auth/me` returns current user profile using `Depends(get_current_user)`.
   - `POST /api/v1/auth/refresh` renews tokens for active sessions.
   - Registered under `/api/v1` in `backend/app/main.py`.

4. **Finance Router RBAC Route Guard (`backend/app/routers/finance.py`)**:
   - Guarded at the router level via `dependencies=[Depends(require_role(["Manager"]))]`.
   - Rejects unauthenticated requests with HTTP 401 and Operator requests with HTTP 403.

5. **Frontend API Client & Auth Gate (`src/api_client.py`, `src/auth.py`, `app.py`, `src/views/database_explorer.py`)**:
   - `src/api_client.py`: Centralized HTTP client automatically injecting `Authorization: Bearer <token>` from `st.session_state.access_token` and intercepting 401 responses to clear session state.
   - `src/auth.py`: Provides `login_mock`, `logout`, `require_role`, and modern `render_login_gate` UI with 1-click Manager/Operator persona cards.
   - `app.py`: Gated behind `render_login_gate()`. Partitions `st.navigation` views into "Operations Cockpit" + "AI Workflows & HITL" for Manager, and "Operator Workspace" for Operator. Adds defensive `require_role(["Manager"])` checks in page functions.
   - `src/views/database_explorer.py`: Applies `mask_sensitive_data()` for Operator role, masking agent names and hiding financial numbers with `[HIDDEN]`. Guards CSV export for Manager role only.

6. **Integrity & Test Verification**:
   - Verified zero facade implementations, zero hardcoded test fixtures in production code, and zero integrity violations.
   - Executed `pytest backend/tests/test_auth.py backend/tests/test_finance_api.py -v`: 29 passed in 1.84s.
   - Executed full M1 & M2 regression suite (10 test files): 227 passed in 54.15s.

---

## 2. Logic Chain

1. **Authentication Integrity**: `decode_jwt_token` recomputes the HMAC signature across `header_b64.payload_b64` on every incoming token and compares it using `hmac.compare_digest`. Any header manipulation (e.g. `alg: none`) or payload tampering (e.g. changing `role: "Operator"` to `role: "Manager"`) produces an HMAC mismatch and is immediately rejected with HTTP 401.
2. **Defense-in-Depth Authorization**:
   - Layer 1 (Backend API): Route-level dependency `require_role(["Manager"])` on `/api/v1/finance-records` ensures direct HTTP requests without Manager credentials receive HTTP 403 Forbidden.
   - Layer 2 (Frontend Routing): Streamlit `st.navigation` restricts page listing based on `st.session_state.role`.
   - Layer 3 (Frontend Page Guards): Page execution functions invoke `require_role(["Manager"])` as a secondary barrier.
   - Layer 4 (DLP Masking): Data explorer views mask sensitive columns for Operator roles even when reading shared datasets.
3. **Requirement & Architecture Conformance**: All items specified in `PROJECT.md` Feature 4 (OAuth/Mock Auth), Feature 5 (JWT & RBAC), Feature 6 (Streamlit Auth), and Feature 7 (Route Security) are fully realized and verified against `ORIGINAL_REQUEST.md`.

---

## 3. Caveats

- **Mock Identity Provider Mode**: The default mode operates via deterministic mock provider (`AUTH_MODE=mock`), satisfying offline hermetic testing. Production Auth0/Google OAuth credentials can be attached via `.env` without modifying the core token verification pipeline.
- **Future Milestone Dependencies**: Tests in `test_metrics_partners.py`, `test_reconciliation.py`, and `test_e2e_scenarios.py` belong to Milestone 3 (Business Logic & Reconciliation) and Milestone 4 (LangGraph Workflow); their failures reflect planned future milestone scope.

---

## 4. Conclusion

**Verdict: APPROVE**

Milestone 2 (Authentication & RBAC Layer) satisfies all architectural, functional, cryptographic, and security requirements without defects or integrity violations.

---

## 5. Verification Method

### Automated Test Verification Commands

```powershell
# 1. Milestone 2 Auth & Finance API Test Suite (29 tests)
pytest backend/tests/test_auth.py backend/tests/test_finance_api.py -v

# 2. Complete M1 & M2 Regression Test Suite (227 tests)
pytest backend/tests/test_auth.py backend/tests/test_finance_api.py backend/tests/test_support_api.py backend/tests/test_escalations_api.py backend/tests/test_main.py backend/tests/test_database.py backend/tests/test_support_crud.py backend/tests/test_m1_adversarial_challenge.py backend/tests/test_adversarial.py backend/tests/test_challenger_m1.py -v
```
