"""
BizVision AI — Users Router

Self-service profile endpoints for the authenticated user.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.v1.schemas.auth import UserProfileResponse
from src.core.deps import CurrentUser

router = APIRouter()


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get the current user's profile",
)
async def read_current_user(current_user: CurrentUser):
    return UserProfileResponse.model_validate(current_user)
