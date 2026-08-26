"""
Cryptographic security module providing zero-dependency HS256 JWT encoding,
decoding, signature validation, token expiration, and password hashing
using Python's standard library (hmac, hashlib, base64, json).
"""
import time
import json
import base64
import hmac
import hashlib
from typing import Optional, Dict, Any

from backend.app.config import settings


def _urlsafe_b64encode(data: bytes) -> str:
    """Encodes bytes to base64url string without trailing '=' padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(s: str) -> bytes:
    """Decodes base64url string into bytes, restoring required '=' padding."""
    padding = "=" * (4 - len(s) % 4) if len(s) % 4 != 0 else ""
    return base64.urlsafe_b64decode(s + padding)


def generate_jwt_token(
    claims: Optional[Dict[str, Any]] = None,
    role: str = "Operator",
    secret: Optional[str] = None,
    exp_delta: Optional[int] = None,
) -> str:
    """
    Generates an RFC 7519 HMAC-SHA256 (HS256) signed JWT bearer token.
    
    Args:
        claims: Optional dictionary of custom JWT claims to merge.
        role: User role ("Manager" or "Operator").
        secret: Optional custom secret key. Defaults to settings.JWT_SECRET.
        exp_delta: Optional expiration delta in seconds. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.
        
    Returns:
        A three-segment dot-separated JWT token string (header.payload.signature).
    """
    secret_key = secret or getattr(settings, "JWT_SECRET", "super-secret-key-bharattrip-ssot-2026")
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    delta = exp_delta if exp_delta is not None else (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    default_sub = "user_mgr_01" if role == "Manager" else "user_op_01"
    default_email = "manager@bharattrip.com" if role == "Manager" else "operator@bharattrip.com"
    default_name = "Manager User" if role == "Manager" else "Operator User"

    payload = {
        "sub": default_sub,
        "email": default_email,
        "name": default_name,
        "role": role,
        "iat": now,
        "exp": now + delta,
    }
    if claims:
        payload.update(claims)
        if "iat" not in claims:
            payload["iat"] = now
        if "exp" not in claims and exp_delta is not None:
            payload["exp"] = now + exp_delta

    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    header_b64 = _urlsafe_b64encode(header_json)
    payload_b64 = _urlsafe_b64encode(payload_json)

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _urlsafe_b64encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_jwt_token(token: str, secret: Optional[str] = None) -> dict:
    """
    Decodes, cryptographically verifies, and checks expiration of an HS256 JWT token.
    
    Args:
        token: Dot-separated JWT token string.
        secret: Optional secret key. Defaults to settings.JWT_SECRET.
        
    Returns:
        Decoded payload claims dictionary.
        
    Raises:
        ValueError: If token format is invalid, signature mismatch, corrupted payload, or expired.
    """
    if not token or not isinstance(token, str):
        raise ValueError("Invalid JWT token: token must be a non-empty string.")

    secret_key = secret or getattr(settings, "JWT_SECRET", "super-secret-key-bharattrip-ssot-2026")
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT token format: expected 3 segments.")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(
        secret_key.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()

    try:
        actual_sig = _urlsafe_b64decode(sig_b64)
    except Exception as err:
        raise ValueError(f"Malformed signature encoding: {err}")

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid JWT signature: HMAC mismatch.")

    try:
        payload_json = _urlsafe_b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)
    except Exception as err:
        raise ValueError(f"Malformed JWT payload: {err}")

    if "exp" in payload and payload["exp"] < int(time.time()):
        raise ValueError("JWT token has expired.")

    return payload


def get_password_hash(password: str) -> str:
    """Computes SHA-256 hex digest of plaintext password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of plaintext password against hash."""
    return hmac.compare_digest(get_password_hash(plain_password), hashed_password)
