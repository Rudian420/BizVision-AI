"""
BizVision AI — Authentication Schemas

Request/response models for register, login, token refresh, and profile.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.models.user import UserRole


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None = None
    company_name: str | None = None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime


class UserLoginResponse(BaseModel):
    """Returned on successful register/login: tokens + user profile."""

    tokens: TokenPair
    user: UserProfileResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
