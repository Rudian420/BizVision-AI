"""
BizVision AI — Authentication Router

JWT-based stateless authentication with refresh token rotation.
Refresh tokens are stored in Redis to support revocation.
"""

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.auth import (
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserLoginResponse,
    UserProfileResponse,
    UserRegisterRequest,
)
from src.core.database import get_db
from src.core.deps import get_current_user
from src.models.user import User
from src.services.auth.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserLoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.register(request)


@router.post(
    "/login",
    response_model=UserLoginResponse,
    summary="Login and get JWT tokens",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.login(
        email=form_data.username,
        password=form_data.password,
    )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Refresh access token using refresh token",
)
async def refresh_token(
    request: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.refresh(request.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke refresh token (logout)",
)
async def logout(
    request: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AuthService(db)
    await service.revoke_token(request.refresh_token, user_id=current_user.id)


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    return UserProfileResponse.model_validate(current_user)
