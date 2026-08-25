# SSOT Parser Security Hardening Design

## Overview
This document outlines the architectural changes to harden the SSOT Parser backend, adhering to the `security-and-hardening` skill guidelines. It addresses broken authentication, missing rate limiting, and missing security headers.

## 1. Authentication Upgrade (bcrypt)

### Current State
`backend/app/core/security.py` uses raw `hashlib.sha256` for password hashing, which is vulnerable to brute-force and rainbow table attacks.

### Proposed Changes
- Add `passlib[bcrypt]` to `requirements.txt`.
- Modify `backend/app/core/security.py`:
  - Instantiate `pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")`.
  - Update `get_password_hash(password: str) -> str` to return `pwd_context.hash(password)`.
  - Update `verify_password(plain_password: str, hashed_password: str) -> bool` to return `pwd_context.verify(plain_password, hashed_password)`.

## 2. Rate Limiting

### Current State
No rate limiting is enforced on API endpoints, leaving the application vulnerable to credential stuffing and DoS attacks.

### Proposed Changes
- Add `slowapi` to `requirements.txt`.
- Modify `backend/app/main.py`:
  - Import `Limiter` and `_rate_limit_exceeded_handler` from `slowapi`.
  - Initialize `limiter = Limiter(key_func=get_remote_address)`.
  - Add the limiter to the application state: `app.state.limiter = limiter`.
  - Register the exception handler: `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`.
- Modify `backend/app/routers/auth.py`:
  - Inject the `Request` object into the `/mock-login` endpoint.
  - Decorate the endpoint with `@limiter.limit("5/minute")`.

## 3. Security Headers

### Current State
FastAPI responses lack standard security headers, exposing the application to clickjacking, MIME-sniffing, and XSS.

### Proposed Changes
- Modify `backend/app/main.py`:
  - Implement a custom middleware `@app.middleware("http")`.
  - The middleware will append the following headers to every response:
    - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `Content-Security-Policy: default-src 'self'`
