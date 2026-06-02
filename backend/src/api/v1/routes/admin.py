"""
BizVision AI — Administration Router

Admin-only operational endpoints. Gated behind the ADMIN role via the
``AdminUser`` dependency.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.core.deps import AdminUser
from src.core.redis import redis_client
from src.services.shared_context.model_registry import ModelRegistry

router = APIRouter()


@router.get(
    "/health/deep",
    summary="Deep dependency health check (admin)",
    description="Reports the live status of Redis and the ML model registry.",
)
async def deep_health(admin: AdminUser):
    try:
        redis_ok = await redis_client.ping()
    except Exception:
        redis_ok = False

    return {
        "requested_by": str(admin.id),
        "redis": "ok" if redis_ok else "error",
        "models": ModelRegistry.status(),
    }


@router.post(
    "/models/warm",
    summary="Force ML model registry warm-up (admin)",
)
async def warm_models(admin: AdminUser):
    await ModelRegistry.initialize()
    return {"status": "warmed", "models": ModelRegistry.status()}
