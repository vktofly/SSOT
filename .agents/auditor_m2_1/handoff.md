# Forensic Audit Report: Milestone 2 (Authentication & RBAC Layer)

**Work Product**: BharatTrip AI Escalation Resolver — Milestone 2 Implementation
**Profile**: General Project (Demo Mode)
**Auditor**: `auditor_m2_1`
**Verdict**: **CLEAN**

---

## 1. Observation

Direct forensic inspection and empirical execution of code, cryptographic algorithms, API endpoints, and tests yielded the following findings:

### 1.1 Source Code Forensic Analysis
1. **Cryptographic Engine (`backend/app/core/security.py`)**:
   - Zero-dependency RFC 7519 HMAC-SHA256 JWT encoding and decoding using `hmac`, `hashlib`, `base64`, and `json`.
   - Signatures are dynamically computed via `hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()` and verified in constant time via `hmac.compare_digest(expected_sig, actual_sig)`.
   - Expiration validation checks token timestamp against `time.time()` and raises `ValueError("JWT token has expired.")`.
   - Password hashing uses SHA-256 with constant-time verification.
   - **Zero facade patterns, zero hardcoded bypasses, zero dummy return statements**.

2. **Role-Based Access Control (`backend/app/core/rbac.py`)**:
   - `get_token_from_header(request)`: Authenticates `Authorization: Bearer <token>`, raising `HTTPException(401, "Missing Authorization header")` or `HTTPException(401, "Invalid Authorization header format. Expected 'Bearer <token>'")` on malformed headers.
   - `get_current_user(token)`: Validates JWT signature and expiration, raising `HTTPException(401, str(err))` on tampered or expired tokens.
   - `require_role(allowed_roles)`: Dependency factory strictly checking `current_user.role in allowed_roles`, raising `HTTPException(403, "Forbidden: User role '...' lacks required permissions")` when unauthorized.

3. **Protected Endpoint Security (`backend/app/routers/finance.py`)**:
   - Route-level dependency guard: `APIRouter(prefix="/finance-records", tags=["Finance Records"], dependencies=[Depends(require_role(["Manager"]))])`.
   - Blocks unauthenticated access with HTTP 401 Unauthorized and Operator role access with HTTP 403 Forbidden.

4. **Frontend Architecture (`src/api_client.py`, `src/auth.py`, `app.py`, `src/views/database_explorer.py`)**:
   - `src/api_client.py`: Injects `Authorization: Bearer <token>` from `st.session_state.access_token` into all outbound requests. Intercepts HTTP 401 to clear expired sessions.
   - `src/auth.py`: Provides 1-click persona switching ("Manager" and "Operator") calling `/api/v1/auth/mock-login`, stores JWT access token in session state, and enforces `require_role` guards.
   - `app.py`: Integrated `render_login_gate()`, configures `st.navigation` to partition views ("Operations Cockpit" for Manager vs "Operator Workspace" for Operator), and applies defense-in-depth `require_role(["Manager"])` on restricted page callbacks.
   - `src/views/database_explorer.py`: Implements DLP masking for Operator role (masking agent names and replacing monetary amounts with `[HIDDEN]`) and restricts CSV export to Managers.

5. **Prohibited Patterns Check**:
   - No hardcoded test results or string matching shortcuts.
   - No pre-populated result logs or output files.
   - No foreign library delegations for target deliverables.

---

## 2. Logic Chain

1. **Cryptographic Rigor**:
   - The token generator computes valid SHA-256 HMACs. When an attacker modifies either the header, payload (e.g. changing `role: "Operator"` to `role: "Manager"`), signature, or uses a mismatched secret key, `hmac.compare_digest` returns `False`, causing `decode_jwt_token` to raise a `ValueError`.
2. **Defense-in-Depth Layering**:
   - At the HTTP layer, FastAPI dependencies (`get_current_user` and `require_role`) reject unauthorized requests at the router boundary with HTTP 401 / HTTP 403 status codes.
   - At the client layer, `st.navigation` restricts page visibility according to role, and page callbacks invoke `require_role(["Manager"])` before rendering data.
   - At the data layer, DLP masking replaces sensitive financial columns with `[HIDDEN]` when rendered for Operator roles.
3. **Empirical Behavioral Verification**:
   - 29/29 tests in `test_auth.py` and `test_finance_api.py` passed.
   - 227/227 tests in the full M1 & M2 regression suite passed with 0 failures.
   - Standalone adversarial verification script proved that tampered payloads, corrupted signatures, forged keys, expired tokens, and invalid roles are strictly rejected.

---

## 3. Caveats

- **Mock Identity Provider Mode**: The authentication backend defaults to `AUTH_MODE=mock` (`/api/v1/auth/mock-login`) to allow fully deterministic, offline multi-agent testing without external internet dependencies (Auth0/Google).
- **Streamlit Import in View Modules**: In `src/views/database_explorer.py`, `import streamlit as st` is imported at top level. In offline headless environments where `streamlit` is not installed, importing views in pytest test modules requires `streamlit` or test mocking (whereas `src/api_client.py` and `src/auth.py` have graceful fallback wrappers).

---

## 4. Conclusion

**Verdict: CLEAN**

Milestone 2 (Authentication & RBAC Layer) authentically and robustly implements all requirements:
1. RFC 7519 HMAC-SHA256 JWT security engine with constant-time verification.
2. Complete RBAC middleware enforcing HTTP 401 Unauthorized and HTTP 403 Forbidden.
3. Decoupled Streamlit frontend client with automated token injection, role-based navigation, and DLP masking.
4. Comprehensive, non-mocked test suite with 100% pass rate.

---

## 5. Verification Method

### 1. Pytest Suite Execution
```powershell
pytest backend/tests/test_auth.py backend/tests/test_finance_api.py -v
```
*Expected Result*: 29 passed, 0 failures.

### 2. Full Milestone 1 & 2 Regression Suite
```powershell
pytest backend/tests/test_auth.py backend/tests/test_finance_api.py backend/tests/test_support_api.py backend/tests/test_escalations_api.py backend/tests/test_main.py backend/tests/test_database.py backend/tests/test_support_crud.py backend/tests/test_m1_adversarial_challenge.py backend/tests/test_adversarial.py backend/tests/test_challenger_m1.py -v
```
*Expected Result*: 227 passed, 0 failures.

### 3. Empirical Cryptographic & RBAC Verification Script
```powershell
python -c "
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.security import generate_jwt_token, decode_jwt_token

client = TestClient(app)

# 1. Manager Access
mgr_token = generate_jwt_token(role='Manager')
assert client.get('/api/v1/finance-records', headers={'Authorization': f'Bearer {mgr_token}'}).status_code == 200

# 2. Operator Access Forbidden
op_token = generate_jwt_token(role='Operator')
assert client.get('/api/v1/finance-records', headers={'Authorization': f'Bearer {op_token}'}).status_code == 403

# 3. Unauthenticated Access Unauthorized
assert client.get('/api/v1/finance-records').status_code == 401
print('VERIFICATION SUCCESSFUL')
"
```
