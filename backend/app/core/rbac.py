"""
Role-Based Access Control (RBAC) and JWT Authentication Dependencies for FastAPI.
"""
from typing import List
from fastapi import Depends, HTTPException, Request, status

from backend.app.core.security import decode_jwt_token
from backend.app.schemas.auth import UserProfile


def get_token_from_header(request: Request) -> str:
    """
    Extracts the Bearer token from the HTTP Authorization header.
    
    Raises:
        HTTPException(401): If header is missing, empty, or improperly formatted.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token cannot be empty",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def get_current_user(token: str = Depends(get_token_from_header)) -> UserProfile:
    """
    Validates the Bearer token and returns the authenticated UserProfile.
    
    Raises:
        HTTPException(401): If token is invalid, signature mismatched, malformed, or expired.
    """
    try:
        payload = decode_jwt_token(token)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub", "user_01")
    role = payload.get("role", "Operator")
    email = payload.get("email", f"{user_id}@bharattrip.com")
    name = payload.get("name", user_id)

    return UserProfile(user_id=user_id, email=email, name=name, role=role)


def require_role(allowed_roles: List[str]):
    """
    FastAPI dependency factory enforcing that the authenticated user possesses one of the allowed roles.
    
    Args:
        allowed_roles: List of permitted role names (e.g. ["Manager"]).
        
    Returns:
        Dependency callable returning UserProfile or raising HTTP 403 Forbidden.
    """
    def role_checker(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: User role '{current_user.role}' lacks required permissions. Required: {allowed_roles}",
            )
        return current_user

    return role_checker


# Convenient RBAC shorthands
require_manager = require_role(["Manager"])
require_operator = require_role(["Operator", "Manager"])
