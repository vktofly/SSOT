# Milestone 2 Investigation Report: Frontend Authentication & RBAC Layer

## 1. Observation

### 1.1 Legacy Authentication in `app.py`
- **File & Lines**: `app.py:50-89`
- **Observed Code**:
```python
55: MOCK_USERS = {
56:     "manager": {"password_hash": get_hash("admin123"), "role": "Manager"},
57:     "operator": {"password_hash": get_hash("agent123"), "role": "Junior"}
58: }
```
```python
80: if submit:
81:     if username in MOCK_USERS and MOCK_USERS[username]["password_hash"] == get_hash(password):
82:         st.session_state.logged_in = True
83:         st.session_state.role = MOCK_USERS[username]["role"]
84:         st.session_state.username = username
85:         st.rerun()
```
- **Finding**: Authentication is purely in-memory and local. It does not call the FastAPI backend, does not receive or store any JWT access token in `st.session_state`, and uses the legacy role name `"Junior"` for operators instead of `"Operator"`.

### 1.2 Missing Frontend Client & Auth Modules
- **File Paths Checked**: `src/auth.py` and `src/api_client.py`
- **Observed Result**: `find_by_name` returned 0 matches in `src/`. Neither module exists in the current repository.

### 1.3 Role Inconsistency in Streamlit Views
- **File & Lines**: `src/views/database_explorer.py:112`
- **Observed Code**:
```python
112: if st.session_state.get('role') == 'Junior':
113:     st.warning("**Junior Role Active**: Sensitive financial amounts and PII are masked by DLP policy.")
114:     support_view = mask_sensitive_data(support_view)
115:     finance_view = mask_sensitive_data(finance_view)
116:     escalations_view = mask_sensitive_data(escalations_view)
```
- **Finding**: Role masking checks `'Junior'`, which fails to trigger when the standard role is `'Operator'`.

### 1.4 Export Guard in Views
- **File & Lines**: `src/views/database_explorer.py:63-74` and `src/views/reconciliation.py:22-32` (line 491)
- **Observed Code**:
```python
63: if st.session_state.get('role') == 'Manager':
64:     csv = support_df.to_csv(index=False).encode('utf-8')
65:     st.download_button("Export Unified SSOT", data=csv, ...)
66: else:
67:     st.caption("Export reserved for Managers.")
```
- **Finding**: CSV export restrictions correctly check `'Manager'` role.

### 1.5 Current Navigation Architecture in `app.py`
- **File & Lines**: `app.py:126-170`
- **Observed Code**:
```python
144: if st.session_state.role == "Manager":
145:     nav_dict = {
146:         "Operations Cockpit": [dashboard_p, partners_p, database_p],
147:         "AI Workflows & HITL": [ingestion_p, reconciliation_p, triage_p]
148:     }
149: else:
150:     nav_dict = {
151:         "Operator Workspace": [ingestion_p, triage_p]
152:     }
153: pg = st.navigation(nav_dict)
```
- **Finding**: Role-based navigation partitions pages into sections. However, direct function entrypoints lack secondary defense-in-depth role guards (`require_role`), and operator default routing needs explicit configuration.

---

## 2. Logic Chain

1. **Decoupled Architecture Requirement** (`ORIGINAL_REQUEST §R1`, `PROJECT.md §1`):
   - The Streamlit frontend must act purely as a client interface. It must authenticate against the FastAPI backend (`POST /api/v1/auth/mock-login` or OAuth callback) and acquire a standard signed JWT bearer token.
2. **Missing Infrastructure Gap**:
   - Because `src/auth.py` and `src/api_client.py` are absent, frontend components cannot make authenticated HTTP requests or manage JWT tokens.
3. **Frontend Auth Helper Design (`src/auth.py`)**:
   - `init_auth_state()`: Initializes `logged_in`, `access_token`, `user_profile`, `role`, `username` in `st.session_state`.
   - `login_mock(role: str, username: Optional[str])`: Sends POST request via `src/api_client.py` to `/api/v1/auth/mock-login`. On success, stores `access_token` and `user_profile` in `st.session_state`, sets `role = user_profile["role"]`, and triggers `st.rerun()`.
   - `login_oauth(provider: str)` & `handle_oauth_callback()`: Supports Google/Auth0 PKCE authorization URLs and URL query parameter (`code`, `state`) exchange.
   - `logout()`: Clears token state, resets session state, and redirects to login.
   - `require_auth()` and `require_role(allowed_roles)`: Page-level guards that prevent execution if unauthenticated or unauthorized.
4. **Centralized API Client Design (`src/api_client.py`)**:
   - Wrapper around HTTP requests to `BACKEND_URL` (default: `http://127.0.0.1:8000`).
   - Automatically injects `Authorization: Bearer <token>` from `st.session_state.access_token`.
   - Intercepts 401 Unauthorized errors to automatically invalidate session state and redirect to login.
   - Intercepts 403 Forbidden errors to handle permission errors gracefully.
5. **Modern Identity Gateway in `app.py`**:
   - Replaces the legacy username/password password form with an enterprise Identity Gateway:
     - Card 1: **Manager Persona** (`manager@bharattrip.com`) -> 1-click mock login with full Operations Cockpit & Financial Reconciliation access.
     - Card 2: **Operator Persona** (`operator@bharattrip.com`) -> 1-click mock login with Ingestion & Triage Workspace access.
     - Fallback OAuth buttons for Auth0/Google when `AUTH_MODE != "mock"`.
6. **Role-Based Navigation & Page Route Guards**:
   - Manager sees 6 pages across 2 sections ("Operations Cockpit", "AI Workflows & HITL") with default `dashboard`.
   - Operator sees 3 pages in 1 section ("Operator Workspace": `triage`, `ingestion`, `database`) with default `triage`.
   - Restricted page functions (`page_dashboard`, `page_partners`, `page_reconciliation`) call `require_role(["Manager"])` as defense-in-depth against direct execution.
7. **DLP & Data Masking Alignment**:
   - In `src/views/database_explorer.py`, update role check from `'Junior'` to `'Operator'`.
   - Operators see masked PII (`Agent` / `Agent Name` -> `Ad***.`), masked financial values (`Amount Paid`, `Refund Amount`, `Deduction` -> `[HIDDEN]`), and disabled CSV export buttons.

---

## 3. Caveats

1. **FastAPI Auth Endpoint Dependency**: `src/auth.py` and `src/api_client.py` rely on the backend router `/api/v1/auth/mock-login` (developed in M2 parallel task). Frontend client can implement graceful fallback if backend is unreachable during unit tests.
2. **Streamlit Query Params in 1.36+**: Handling OAuth callbacks in Streamlit utilizes `st.query_params`. Query parameters must be cleared with `st.query_params.clear()` immediately upon token exchange to prevent repeat exchanges on subsequent reruns.
3. **Local In-Memory Cache**: `st.session_state` is per-browser session. Closing the browser or clearing cookies terminates the active JWT token session as expected for security compliance.

---

## 4. Conclusion

The frontend authentication and RBAC layer must be refactored into two new modules and updated in `app.py` and view files:

1. **Create `src/auth.py`**:
   - Manage `st.session_state.access_token`, `st.session_state.user_profile`, `st.session_state.role`, `st.session_state.logged_in`.
   - Provide `login_mock`, `login_oauth`, `handle_oauth_callback`, `logout`, `require_auth`, `require_role`.
2. **Create `src/api_client.py`**:
   - Authenticated HTTP client communicating with `${BACKEND_URL}/api/v1`.
   - Auto-attach `Bearer` token from session state and intercept 401/403 responses.
3. **Update `app.py`**:
   - Replace legacy `check_password()` and `MOCK_USERS` with modern Identity Gateway calling `src/auth.py`.
   - Configure `st.navigation` with Manager vs Operator sections and enforce `require_role(["Manager"])` on restricted views.
4. **Update `src/views/database_explorer.py`**:
   - Change `st.session_state.get('role') == 'Junior'` to `'Operator'` to activate PII and financial amount DLP masking.

---

## 5. Verification Method

1. **Unit & API Verification**:
   - Run Pytest backend auth suite:
     ```powershell
     pytest backend/tests/test_auth.py -v
     ```
2. **Streamlit Component & Session Verification**:
   - Inspect `src/auth.py`, `src/api_client.py`, `app.py`, and `src/views/database_explorer.py`.
   - Verify `st.session_state.access_token` and `st.session_state.user_profile` are properly set upon mock login.
3. **RBAC Route Security Verification**:
   - Launch Streamlit application:
     ```powershell
     streamlit run app.py --server.headless true --server.port 8501
     ```
   - Log in as **Operator** (`operator@bharattrip.com`):
     - Confirm sidebar displays only "Operator Workspace" (`triage`, `ingestion`, `database`).
     - Confirm Metrics Dashboard, Partner Health Matrix, and Reconciliation are hidden.
     - Navigate to Database Explorer: confirm financial amounts show `[HIDDEN]` and Agent names are masked.
     - Confirm CSV export button is disabled or hidden.
   - Log in as **Manager** (`manager@bharattrip.com`):
     - Confirm sidebar displays "Operations Cockpit" and "AI Workflows & HITL" with all 6 pages.
     - Confirm full visibility of financial amounts and active CSV export buttons.
