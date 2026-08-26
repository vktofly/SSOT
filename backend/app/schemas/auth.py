"""
Pydantic schemas for authentication and authorization.
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field


class MockLoginRequest(BaseModel):
    """Request payload for mock OAuth / testing login."""
    role: Literal["Manager", "Operator"] = Field(
        ...,
        description="User role to authenticate as ('Manager' or 'Operator')."
    )
    username: Optional[str] = Field(
        None,
        description="Optional custom username identifier."
    )


class LoginRequest(BaseModel):
    """Standard username and password login request."""
    username: str = Field(..., description="Username or email.")
    password: str = Field(..., description="Plaintext password.")


class UserProfile(BaseModel):
    """Authenticated user profile details."""
    user_id: str = Field(..., description="Unique user identifier.")
    email: str = Field(..., description="User email address.")
    name: str = Field(..., description="Full display name.")
    role: str = Field(..., description="Role ('Manager' or 'Operator').")


class TokenResponse(BaseModel):
    """OAuth 2.0 / JWT bearer token response."""
    access_token: str = Field(..., description="Signed HS256 JWT access token.")
    token_type: str = Field("bearer", description="Token type identifier.")
    expires_in: int = Field(..., description="Token lifespan in seconds.")
    user_profile: UserProfile = Field(..., description="Authenticated user profile.")


class RefreshTokenRequest(BaseModel):
    """Refresh token request payload."""
    refresh_token: Optional[str] = Field(None, description="Optional refresh token string.")
