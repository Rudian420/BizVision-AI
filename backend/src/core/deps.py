"""
BizVision AI — Shared FastAPI Dependencies

Reusable dependency-injection callables: authentication (resolve the
current user from a bearer JWT), role gating, and pagination params.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import decode_token
from src.models.user import User, UserRole

# tokenUrl matches the login route mounted at /api/v1/auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from a bearer access token."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise _CREDENTIALS_EXCEPTION
        subject = payload.get("sub")
        if subject is None:
            raise _CREDENTIALS_EXCEPTION
        user_id = UUID(str(subject))
    except (JWTError, ValueError):
        raise _CREDENTIALS_EXCEPTION from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise _CREDENTIALS_EXCEPTION
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Reject disabled accounts."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Gate a route behind the admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(require_admin)]
