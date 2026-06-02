"""
BizVision AI — Authentication Service

Owns the full credential lifecycle: registration, login, access-token
issuance, refresh-token rotation, and revocation. Refresh tokens are
stored (hashed) in Redis with a TTL matching their expiry, enabling
fast O(1) revocation checks without a database round-trip.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.auth import (
    TokenPair,
    TokenRefreshResponse,
    UserLoginResponse,
    UserProfileResponse,
    UserRegisterRequest,
)
from src.core.config import settings
from src.core.redis import redis_client
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.models.user import User

_REFRESH_PREFIX = "refresh:"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Public API ─────────────────────────────────────────────────
    async def register(self, request: UserRegisterRequest) -> UserLoginResponse:
        existing = await self.db.execute(select(User).where(User.email == request.email))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        user = User(
            email=request.email,
            hashed_password=hash_password(request.password),
            full_name=request.full_name,
            company_name=request.company_name,
        )
        self.db.add(user)
        await self.db.flush()  # populate user.id before issuing tokens
        tokens = await self._issue_tokens(user)
        return UserLoginResponse(
            tokens=tokens,
            user=UserProfileResponse.model_validate(user),
        )

    async def login(self, email: str, password: str) -> UserLoginResponse:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        tokens = await self._issue_tokens(user)
        return UserLoginResponse(
            tokens=tokens,
            user=UserProfileResponse.model_validate(user),
        )

    async def refresh(self, refresh_token: str) -> TokenRefreshResponse:
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise self._invalid_refresh() from None

        if payload.get("type") != "refresh":
            raise self._invalid_refresh()

        subject = payload.get("sub")
        if subject is None:
            raise self._invalid_refresh()

        # The token must still be the active one stored for this user.
        stored = await redis_client.get(f"{_REFRESH_PREFIX}{subject}")
        if stored is None or stored != _hash_token(refresh_token):
            raise self._invalid_refresh()

        access_token = create_access_token(subject)
        return TokenRefreshResponse(
            access_token=access_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def revoke_token(self, refresh_token: str, user_id: UUID) -> None:
        """Logout — drop the stored refresh token for this user."""
        await redis_client.delete(f"{_REFRESH_PREFIX}{user_id}")

    # ── Internal helpers ───────────────────────────────────────────
    async def _issue_tokens(self, user: User) -> TokenPair:
        access_token = create_access_token(user.id, extra_claims={"role": user.role.value})
        refresh_token = create_refresh_token(user.id)

        # Store the hashed refresh token keyed by user id (single active
        # session per user; rotation overwrites the previous token).
        await redis_client.set(
            f"{_REFRESH_PREFIX}{user.id}",
            _hash_token(refresh_token),
            ttl_seconds=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    def _invalid_refresh() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
