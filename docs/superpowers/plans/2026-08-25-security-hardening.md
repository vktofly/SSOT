# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the SSOT Parser backend by implementing bcrypt password hashing, API rate limiting, and standard security headers.

**Architecture:** Use `passlib` for password hashing, `slowapi` for endpoint rate limiting, and a custom FastAPI middleware for injecting security headers.

**Tech Stack:** Python 3.10+, FastAPI, passlib[bcrypt], slowapi

**Spec:** docs/superpowers/specs/2026-08-25-security-hardening-design.md

## Global Constraints
- Must not break existing Streamlit authentication flows.
- Python packages must be added to `requirements.txt`.

---
### Task 1: Authentication Upgrade

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/app/core/security.py`
- Create: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: Raw passwords.
- Produces: `get_password_hash` and `verify_password` using bcrypt.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_security.py
import pytest
from backend.app.core.security import get_password_hash, verify_password

def test_password_hashing():
    password = "supersecretpassword123"
    hashed = get_password_hash(password)
    assert hashed != password
    # It should be a bcrypt hash (typically starts with $2b$)
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_security.py -v`
Expected: FAIL because `get_password_hash` currently returns a SHA-256 hash (doesn't start with `$2b$`).

- [ ] **Step 3: Write minimal implementation**

Modify `requirements.txt` to add `passlib[bcrypt]`.
Run `pip install passlib[bcrypt]` or `pip install -r requirements.txt`.

Modify `backend/app/core/security.py`:
```python
import time
import json
import base64
import hmac
import hashlib
from typing import Optional, Dict, Any

from passlib.context import CryptContext
from backend.app.config import settings

# retain _urlsafe_b64encode, _urlsafe_b64decode, generate_jwt_token, decode_jwt_token as they are

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Computes bcrypt hash of plaintext password."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plaintext password against bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt backend/app/core/security.py backend/tests/test_security.py
git commit -m "security: Upgrade password hashing to bcrypt"
```

---
### Task 2: Rate Limiting

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/auth.py`
- Create: `backend/tests/test_rate_limiting.py`

**Interfaces:**
- Consumes: `slowapi` library
- Produces: Rate limited endpoints

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rate_limiting.py
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_rate_limiting_mock_login():
    # Send 6 requests, the limit is 5/minute
    for _ in range(5):
        response = client.post("/api/v1/auth/mock-login", json={"role": "Operator"})
        assert response.status_code == 200
    
    # The 6th should be rate limited
    response = client.post("/api/v1/auth/mock-login", json={"role": "Operator"})
    assert response.status_code == 429
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_rate_limiting.py -v`
Expected: FAIL because the 6th request will return 200, not 429.

- [ ] **Step 3: Write minimal implementation**

Modify `requirements.txt` to add `slowapi`.
Run `pip install slowapi`.

Modify `backend/app/main.py`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# Inside create_app(), before or around CORS middleware setup:
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Modify `backend/app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, status, Request
# ... existing imports
from backend.app.main import limiter

@router.post("/mock-login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def mock_login(request: Request, payload: MockLoginRequest):
    # ... existing implementation
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_rate_limiting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt backend/app/main.py backend/app/routers/auth.py backend/tests/test_rate_limiting.py
git commit -m "security: Add slowapi rate limiting to auth endpoint"
```

---
### Task 3: Security Headers

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_security_headers.py`

**Interfaces:**
- Consumes: FastAPI Request/Response
- Produces: Standard security headers in HTTP responses

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_security_headers.py
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_security_headers():
    response = client.get("/")
    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Content-Security-Policy") == "default-src 'self'"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_security_headers.py -v`
Expected: FAIL due to missing headers.

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/main.py`:
```python
# Inside create_app() function, after routers:
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_security_headers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_security_headers.py
git commit -m "security: Add standard HTTP security headers middleware"
```
