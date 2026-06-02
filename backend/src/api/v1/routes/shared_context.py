"""
BizVision AI — Shared Context Router

Read access to the cross-module intelligence bus: the executive chatbot
and the frontend dashboard pull recent signals emitted by the analysis
modules from here.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.core.deps import CurrentUser
from src.services.shared_context.context_bus import SharedContextBus
from src.services.shared_context.model_registry import ModelRegistry

router = APIRouter()


@router.get(
    "/signals",
    summary="Recent cross-module intelligence signals",
    description="Returns the most recent Shared Context Bus signals for the current user.",
)
async def get_recent_signals(
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=50),
):
    signals = await SharedContextBus.recent_signals(str(current_user.id), limit=limit)
    return {"count": len(signals), "signals": signals}


@router.get(
    "/models",
    summary="ML model registry status",
    description="Reports which module models have been warmed in this process.",
)
async def get_model_status(current_user: CurrentUser):
    return ModelRegistry.status()
