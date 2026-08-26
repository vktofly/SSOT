"""
Adversarial Challenge Test Suite for Milestone 2:
Authentication, RBAC Integration, Concurrency, Token Lifecycle & DLP Security.

Evaluated Dimensions:
1. Concurrent Mock Logins, Race Conditions & Claim Isolation
2. Token Refresh Lifecycle, Consecutive Chains & Expiration Boundaries
3. Data Loss Prevention (DLP) Masking & Least-Privilege Leak Resistance
4. Mock Login Fuzzing, Malformed Payloads & Edge Cases
5. Cryptographic Signature Tampering & Algorithm Confusion Resistance
6. Header Injection & Case-Insensitive Auth Scheme Handling
7. Multi-Endpoint RBAC Matrix Verification
"""
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

# Mock streamlit in headless backend test runner
if "streamlit" not in sys.modules:
    dummy_st = MagicMock()
    dummy_st.session_state = {}
    sys.modules["streamlit"] = dummy_st

# Load database_explorer directly to isolate DLP logic without triggering full UI view tree
_db_explorer_path = Path(__file__).resolve().parent.parent.parent / "src" / "views" / "database_explorer.py"
_spec = importlib.util.spec_from_file_location("database_explorer_mod", str(_db_explorer_path))
_db_explorer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_db_explorer)
mask_sensitive_data = _db_explorer.mask_sensitive_data

import concurrent.futures
import json
import time
import base64
import hmac
import hashlib
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.core.security import generate_jwt_token, decode_jwt_token
from backend.app.core.rbac import get_current_user
from backend.app.schemas.auth import UserProfile


# ---------------------------------------------------------------------------
# Section 1: Concurrent Mock Logins & Claim Isolation
# ---------------------------------------------------------------------------

def test_concurrent_mock_logins_high_throughput(client: TestClient):
    """
    Stress-tests the mock login endpoint under high concurrency (50 parallel threads).
    Verifies zero HTTP 500 errors, proper token structure, and claim integrity.
    """
    num_requests = 50
    roles = ["Manager" if i % 2 == 0 else "Operator" for i in range(num_requests)]
    usernames = [f"stress_user_{i:03d}" for i in range(num_requests)]

    def make_login_request(idx: int):
        role = roles[idx]
        username = usernames[idx]
        resp = client.post("/api/v1/auth/mock-login", json={"role": role, "username": username})
        return idx, resp

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_login_request, i) for i in range(num_requests)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == num_requests
    for idx, resp in results:
        assert resp.status_code == 200, f"Request {idx} failed with {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_profile"]["user_id"] == usernames[idx]
        assert data["user_profile"]["role"] == roles[idx]

        # Verify cryptographic claims match requested identity
        claims = decode_jwt_token(data["access_token"])
        assert claims["sub"] == usernames[idx]
        assert claims["role"] == roles[idx]


def test_concurrent_token_uniqueness_across_sessions(client: TestClient):
    """
    Verifies that simultaneous logins for different personas produce unique tokens
    and do not experience cross-talk or race condition overwrites.
    """
    issued_tokens = set()
    num_requests = 30

    def get_token(i: int):
        resp = client.post("/api/v1/auth/mock-login", json={"role": "Manager", "username": f"user_unique_{i}"})
        return resp.json()["access_token"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        tokens = list(executor.map(get_token, range(num_requests)))

    for tok in tokens:
        issued_tokens.add(tok)

    # All 30 tokens for 30 distinct usernames must be distinct
    assert len(issued_tokens) == num_requests


def test_concurrent_mixed_operations_stress(client: TestClient):
    """
    Stress-tests mixed concurrent operations: Logins, Refreshes, and User Profile calls.
    Verifies server stability and zero race-condition failures.
    """
    def run_op(idx: int):
        # 1. Login
        role = "Manager" if idx % 2 == 0 else "Operator"
        login_res = client.post("/api/v1/auth/mock-login", json={"role": role, "username": f"mixed_user_{idx}"})
        if login_res.status_code != 200:
            return False, "login failed"
        token = login_res.json()["access_token"]

        # 2. Get profile
        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        if me_res.status_code != 200:
            return False, "me failed"

        # 3. Refresh
        ref_res = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"})
        if ref_res.status_code != 200:
            return False, "refresh failed"

        return True, "ok"

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(run_op, range(30)))

    for success, msg in results:
        assert success is True, f"Mixed concurrent operation failed: {msg}"


# ---------------------------------------------------------------------------
# Section 2: Token Refresh Lifecycle & Boundary Conditions
# ---------------------------------------------------------------------------

def test_token_refresh_lifecycle_and_claim_preservation(client: TestClient, manager_auth_headers: dict):
    """
    Verifies that refreshing a token preserves the exact role and user metadata.
    """
    login_resp = client.post("/api/v1/auth/mock-login", json={"role": "Manager", "username": "lead_director_01"})
    assert login_resp.status_code == 200
    orig_token = login_resp.json()["access_token"]
    orig_claims = decode_jwt_token(orig_token)

    # Request refresh
    refresh_resp = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {orig_token}"})
    assert refresh_resp.status_code == 200
    refreshed_data = refresh_resp.json()
    new_token = refreshed_data["access_token"]

    new_claims = decode_jwt_token(new_token)
    assert new_claims["sub"] == "lead_director_01"
    assert new_claims["role"] == "Manager"
    assert new_claims["email"] == orig_claims["email"]


def test_consecutive_token_refresh_chain(client: TestClient):
    """
    Adversarial test: Chained refreshes (Token A -> Token B -> Token C -> Token D).
    Verifies no claim degradation or authorization decay across multiple cycles.
    """
    login_resp = client.post("/api/v1/auth/mock-login", json={"role": "Manager", "username": "chain_user_01"})
    current_token = login_resp.json()["access_token"]

    for cycle in range(5):
        refresh_resp = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {current_token}"})
        assert refresh_resp.status_code == 200, f"Cycle {cycle} failed: {refresh_resp.text}"
        current_token = refresh_resp.json()["access_token"]
        claims = decode_jwt_token(current_token)
        assert claims["sub"] == "chain_user_01"
        assert claims["role"] == "Manager"

    # Use final token to access protected finance route
    finance_resp = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {current_token}"})
    assert finance_resp.status_code == 200


def test_refresh_with_expired_token_rejected_401(client: TestClient, mock_expired_token: str):
    """
    Verifies that attempting to refresh an expired token returns 401 Unauthorized.
    """
    resp = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {mock_expired_token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json().get("detail", "").lower()


def test_refresh_with_tampered_token_rejected_401(client: TestClient, mock_manager_token: str):
    """
    Verifies that attempting to refresh a signature-tampered token returns 401 Unauthorized.
    """
    parts = mock_manager_token.split(".")
    tampered_sig = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    resp = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {tampered_token}"})
    assert resp.status_code == 401


def test_refreshed_operator_token_cannot_access_manager_routes(client: TestClient):
    """
    Verifies that an Operator who refreshes their token remains an Operator and is forbidden (403)
    from accessing Manager-restricted endpoints.
    """
    op_login = client.post("/api/v1/auth/mock-login", json={"role": "Operator", "username": "op_test_ref"})
    op_token = op_login.json()["access_token"]

    # Refresh operator token
    refresh_resp = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {op_token}"})
    assert refresh_resp.status_code == 200
    refreshed_op_token = refresh_resp.json()["access_token"]

    # Try accessing manager endpoint
    fin_resp = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {refreshed_op_token}"})
    assert fin_resp.status_code == 403


# ---------------------------------------------------------------------------
# Section 3: DLP Masking Validation & Leak Prevention
# ---------------------------------------------------------------------------

def test_dlp_masking_comprehensive_financial_columns():
    """
    Verifies that all sensitive financial columns are masked to '[HIDDEN]'
    and cannot be leaked to Operator views.
    """
    df = pd.DataFrame({
        "Ticket ID": ["RF-1001", "RF-1002"],
        "Agent": ["Peak Journeys Pvt Ltd", "GoFly Holidays"],
        "Agent Name": ["Peak Journeys", "GoFly"],
        "Support Amount": [15000.0, 8500.50],
        "Finance Amount": [14000.0, 8000.00],
        "Amount Paid (INR)": [14000, 8000],
        "Refund Amount (INR)": [15000, 8500],
        "Route": ["DEL-BOM", "BLR-MAA"],
    })

    masked = mask_sensitive_data(df)

    # Financial columns must all be '[HIDDEN]'
    assert (masked["Support Amount"] == "[HIDDEN]").all()
    assert (masked["Finance Amount"] == "[HIDDEN]").all()
    assert (masked["Amount Paid (INR)"] == "[HIDDEN]").all()
    assert (masked["Refund Amount (INR)"] == "[HIDDEN]").all()

    # Raw numbers must not exist in masked text representation
    masked_str = masked.to_string()
    assert "15000" not in masked_str
    assert "14000" not in masked_str
    assert "8500" not in masked_str
    assert "8000" not in masked_str


def test_dlp_masking_agent_names_pii():
    """
    Verifies Agent and Agent Name PII masking:
    - Long names are partially masked (e.g. 'Pe***d')
    - Short names (<= 3 chars) are fully masked ('***')
    """
    df = pd.DataFrame({
        "Agent": ["Aditi M.", "Sky", "Go", "A", "International Travel Agency Corp"],
        "Agent Name": ["Vikash Kumar", "Om", "XYZ", "B", "Bharat Travels"],
    })

    masked = mask_sensitive_data(df)

    # Check long name masking
    assert masked["Agent"].iloc[0] == "Ad***."
    assert masked["Agent Name"].iloc[0] == "Vi***r"
    assert masked["Agent"].iloc[4].startswith("In***")

    # Check short names (<= 3 chars)
    assert masked["Agent"].iloc[1] == "***"
    assert masked["Agent"].iloc[2] == "***"
    assert masked["Agent"].iloc[3] == "***"
    assert masked["Agent Name"].iloc[1] == "***"
    assert masked["Agent Name"].iloc[2] == "***"
    assert masked["Agent Name"].iloc[3] == "***"


def test_dlp_masking_edge_cases_and_robustness():
    """
    Adversarial test: Tests mask_sensitive_data with unusual DataFrame structures:
    - Empty DataFrame
    - DataFrame with missing sensitive columns
    - None / NaN values in sensitive columns
    - Numeric values in Agent name columns
    """
    # 1. Empty DataFrame
    empty_df = pd.DataFrame()
    masked_empty = mask_sensitive_data(empty_df)
    assert masked_empty.empty

    # 2. DataFrame with no sensitive columns
    safe_df = pd.DataFrame({"Status": ["Pending", "Closed"], "Route": ["DEL-DXB", "BOM-LHR"]})
    masked_safe = mask_sensitive_data(safe_df)
    assert list(masked_safe.columns) == ["Status", "Route"]

    # 3. None / NaN in Agent column
    nan_df = pd.DataFrame({
        "Agent": [None, float("nan"), "Normal Agency"],
        "Support Amount": [None, float("nan"), 1000.0],
    })
    masked_nan = mask_sensitive_data(nan_df)
    assert masked_nan["Support Amount"].tolist() == ["[HIDDEN]", "[HIDDEN]", "[HIDDEN]"]
    assert masked_nan["Agent"].iloc[2] == "No***y"

    # 4. Numeric values in Agent column
    num_df = pd.DataFrame({"Agent": [12345, 99]})
    masked_num = mask_sensitive_data(num_df)
    assert masked_num["Agent"].iloc[0] == "12***5"
    assert masked_num["Agent"].iloc[1] == "***"


def test_dlp_non_destructive_for_operational_metadata():
    """
    Verifies that DLP masking preserves operational columns (Route, Ticket ID, Status, Remarks)
    unaltered so Operators can still triage workflows.
    """
    df = pd.DataFrame({
        "Ticket ID": ["RF-101", "RF-102"],
        "Route": ["DEL-BOM", "BLR-MAA"],
        "Status": ["Pending", "Refund Done"],
        "Remarks": ["Need review", "Approved"],
        "Agent": ["Aditi Travel", "Bharat Tours"],
        "Amount Paid (INR)": [5000, 10000],
    })
    masked = mask_sensitive_data(df)
    assert masked["Ticket ID"].tolist() == ["RF-101", "RF-102"]
    assert masked["Route"].tolist() == ["DEL-BOM", "BLR-MAA"]
    assert masked["Status"].tolist() == ["Pending", "Refund Done"]
    assert masked["Remarks"].tolist() == ["Need review", "Approved"]
    assert masked["Amount Paid (INR)"].tolist() == ["[HIDDEN]", "[HIDDEN]"]


# ---------------------------------------------------------------------------
# Section 4: Mock Login Fuzzing, Invalid Payloads & Edge Cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_role", [
    "Admin",
    "SuperAdmin",
    "operator",   # case sensitivity
    "MANAGER",    # case sensitivity
    "Guest",
    "",
    " ",
    "Root",
    "123",
    None,
])
def test_mock_login_rejects_invalid_roles(client: TestClient, invalid_role):
    """
    Verifies that any role other than exact 'Manager' or 'Operator' is rejected with 422.
    """
    payload = {"role": invalid_role} if invalid_role is not None else {}
    resp = client.post("/api/v1/auth/mock-login", json=payload)
    assert resp.status_code == 422


@pytest.mark.parametrize("malicious_username", [
    "user' OR '1'='1",
    "<script>alert('xss')</script>",
    "admin\x00nullbyte",
    "../../etc/passwd",
    "A" * 10000,  # Buffer stress
    "🔥💥✨_unicode_user_हिन्दी",
])
def test_mock_login_handles_adversarial_usernames_safely(client: TestClient, malicious_username: str):
    """
    Verifies that SQL injection, XSS vectors, null bytes, and oversized strings in username
    do not crash the server and are safely encapsulated in token claims.
    """
    resp = client.post("/api/v1/auth/mock-login", json={"role": "Operator", "username": malicious_username})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_profile"]["user_id"] == malicious_username

    # Verify claim decoding is stable
    claims = decode_jwt_token(data["access_token"])
    assert claims["sub"] == malicious_username


def test_mock_login_extra_fields_cannot_escalate_privilege(client: TestClient):
    """
    Adversarial test: Attacker submits payload with extra fields trying to overwrite claims
    e.g. {"role": "Operator", "is_admin": True, "permissions": ["ALL"]}.
    Verifies extra fields are discarded and cannot alter issued claims.
    """
    payload = {
        "role": "Operator",
        "username": "attacker_op",
        "is_admin": True,
        "is_superuser": True,
        "permissions": ["all_access"],
    }
    resp = client.post("/api/v1/auth/mock-login", json=payload)
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    claims = decode_jwt_token(token)

    assert claims["role"] == "Operator"
    assert "is_admin" not in claims
    assert "permissions" not in claims


def test_mock_login_invalid_http_methods(client: TestClient):
    """
    Verifies that GET, PUT, DELETE, PATCH to /mock-login return 405 Method Not Allowed.
    """
    assert client.get("/api/v1/auth/mock-login").status_code == 405
    assert client.put("/api/v1/auth/mock-login").status_code == 405
    assert client.delete("/api/v1/auth/mock-login").status_code == 405
    assert client.patch("/api/v1/auth/mock-login").status_code == 405


# ---------------------------------------------------------------------------
# Section 5: Cryptographic & Security Edge Cases
# ---------------------------------------------------------------------------

def test_jwt_algorithm_none_attack_rejected(client: TestClient):
    """
    Adversarial test: Simulates alg: 'none' attack where attacker strips signature.
    """
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": "admin_hacker",
        "role": "Manager",
        "email": "hacker@evil.com",
        "exp": int(time.time()) + 3600,
    }
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("utf-8").rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")

    # alg: none token has empty or missing signature
    unsigned_token = f"{h_b64}.{p_b64}."
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {unsigned_token}"})
    assert resp.status_code == 401

    with pytest.raises(ValueError):
        decode_jwt_token(unsigned_token)


def test_jwt_signature_with_wrong_secret_rejected(client: TestClient):
    """
    Adversarial test: Token signed with unauthorized secret key is rejected.
    """
    fake_token = generate_jwt_token(
        claims={"sub": "forged_manager", "role": "Manager"},
        role="Manager",
        secret="wrong-unauthorized-secret-key-12345"
    )
    resp = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {fake_token}"})
    assert resp.status_code == 401
    assert "invalid jwt signature" in resp.json().get("detail", "").lower() or "signature" in resp.json().get("detail", "").lower()


def test_exact_expiration_second_boundary():
    """
    Boundary test: Checks token behavior 1 second before expiration and 1 second after expiration.
    """
    # 1 second in future -> valid
    valid_token = generate_jwt_token(exp_delta=2)
    claims = decode_jwt_token(valid_token)
    assert claims["role"] == "Operator"

    # Expired 1 second in past -> ValueError
    expired_token = generate_jwt_token(exp_delta=-1)
    with pytest.raises(ValueError, match="expired"):
        decode_jwt_token(expired_token)


# ---------------------------------------------------------------------------
# Section 6: Header Injection & Auth Scheme Case Insensitivity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("header_value", [
    "bearer {token}",
    "BEARER {token}",
    "Bearer  {token}",   # Multiple spaces
])
def test_bearer_scheme_case_insensitivity_and_spacing(client: TestClient, mock_manager_token: str, header_value: str):
    """
    Verifies that the auth middleware robustly parses 'bearer', 'BEARER', and extra spaces.
    """
    auth_header = header_value.format(token=mock_manager_token)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": auth_header})
    assert resp.status_code == 200
    assert resp.json()["role"] == "Manager"


def test_multiple_tokens_in_header_rejected(client: TestClient, mock_manager_token: str, mock_operator_token: str):
    """
    Verifies that sending multiple tokens separated by spaces returns 401.
    """
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {mock_manager_token} {mock_operator_token}"})
    assert resp.status_code == 401
