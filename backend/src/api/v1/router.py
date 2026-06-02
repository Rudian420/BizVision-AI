"""
BizVision AI — API v1 Master Router

All module routers are assembled here and mounted under /api/v1/.
Each module is an independent domain with its own router, schemas, and services.
"""

from fastapi import APIRouter

from src.api.v1.routes import (
    admin,
    audits,
    auth,
    chatbot,
    forecasting,
    pricing,
    recruitment,
    shared_context,
    sustainability,
    users,
)

api_router = APIRouter()

# ── System Routes ─────────────────────────────────────────────────
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"],
)

# ── AI Intelligence Modules ───────────────────────────────────────
api_router.include_router(
    recruitment.router,
    prefix="/recruitment",
    tags=["Recruitment Intelligence"],
)
api_router.include_router(
    pricing.router,
    prefix="/pricing",
    tags=["Smart Pricing Advisor"],
)
api_router.include_router(
    forecasting.router,
    prefix="/forecasting",
    tags=["Profit Forecasting"],
)
api_router.include_router(
    sustainability.router,
    prefix="/sustainability",
    tags=["Green Business Scorer"],
)
api_router.include_router(
    chatbot.router,
    prefix="/chatbot",
    tags=["Financial Advisory AI"],
)

# ── Cross-Module Intelligence ─────────────────────────────────────
api_router.include_router(
    shared_context.router,
    prefix="/context",
    tags=["Shared Intelligence Context"],
)
api_router.include_router(
    audits.router,
    prefix="/audits",
    tags=["Audit Logs"],
)

# ── Administration ────────────────────────────────────────────────
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Administration"],
)
