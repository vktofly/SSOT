"""
Authentication Router providing Mock OAuth login, JWT issuance, profile retrieval, and token refresh.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.config import settings
from backend.app.core.security import generate_jwt_token
from backend.app.core.rbac import get_current_user
from backend.app.schemas.auth import (
    MockLoginRequest,
    TokenResponse,
    UserProfile,
    RefreshTokenRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/mock-login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def mock_login(payload: MockLoginRequest):
    """
    Simulates OAuth 2.0 PKCE / Mock Identity Provider login for deterministic testing and rapid persona switching.
    """
    role = payload.role
    if role not in ("Manager", "Operator"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid role: Must be 'Manager' or 'Operator'",
        )

    user_id = payload.username or ("user_mgr_01" if role == "Manager" else "user_op_01")
    email = "manager@bharattrip.com" if role == "Manager" else "operator@bharattrip.com"
    name = "Manager User" if role == "Manager" else "Operator User"

    user_profile = UserProfile(user_id=user_id, email=email, name=name, role=role)
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    token = generate_jwt_token(
        claims={"sub": user_id, "email": email, "name": name, "role": role},
        role=role,
        exp_delta=expires_in,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user_profile=user_profile,
    )


@router.get("/me", response_model=UserProfile, status_code=status.HTTP_200_OK)
def get_current_user_profile(current_user: UserProfile = Depends(get_current_user)):
    """
    Returns the authenticated user profile derived from the validated JWT Bearer token.
    """
    return current_user


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def refresh_token(
    current_user: UserProfile = Depends(get_current_user),
    payload: RefreshTokenRequest = None,
):
    """
    Issues a renewed JWT access token for active authenticated sessions.
    """
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    new_token = generate_jwt_token(
        claims={
            "sub": current_user.user_id,
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role,
        },
        role=current_user.role,
        exp_delta=expires_in,
    )
    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        expires_in=expires_in,
        user_profile=current_user,
    )
