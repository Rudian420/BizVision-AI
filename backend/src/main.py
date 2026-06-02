"""
BizVision AI — FastAPI Application Entry Point

Architecture: async-first, domain-driven, modular
All AI modules are independent routers connected via
the Shared Context Bus for cross-module intelligence.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from loguru import logger

from src.api.v1.router import api_router
from src.core.config import settings
from src.core.database import Base, engine
from src.core.logging import setup_logging
from src.core.observability import instrument_app
from src.core.redis import redis_client
from src.middleware.rate_limiter import RateLimitMiddleware
from src.middleware.request_id import RequestIDMiddleware
from src.middleware.timing import TimingMiddleware


# ── ML pre-warm background task (TASK-041) ───────────────────────
# Each `*_USE_REAL_ML=True` module pays a cold-start cost on first
# request (LightGBM grid 180s, Theta 90s, sklearn 80s, SBERT
# 60-300s + 420MB download). The lifespan kicks off these warmups
# concurrently as fire-and-forget background tasks so the server
# starts answering health/auth/non-ML routes immediately. The
# per-module `_get_ranker / _get_policy / ...` locks make a first
# real request safely block on whichever warmup is still in-flight.
async def _prewarm_module(name: str, factory) -> None:
    """Call `factory()` in a worker thread; log + swallow exceptions
    so one module's warmup failure doesn't take the whole startup
    down."""
    import time

    t0 = time.perf_counter()
    try:
        await asyncio.to_thread(factory)
        logger.info(
            "Pre-warm OK: {} ready in {:.1f}s",
            name,
            time.perf_counter() - t0,
        )
    except Exception as exc:
        logger.exception(
            "Pre-warm FAILED for {} after {:.1f}s: {}",
            name,
            time.perf_counter() - t0,
            exc,
        )


def _schedule_ml_prewarm() -> list[asyncio.Task]:
    """Return a list of asyncio.Tasks for every `*_USE_REAL_ML=True`
    module. Caller is responsible for keeping references (so the
    GC doesn't kill them) until shutdown — we attach to `app.state`."""
    tasks: list[asyncio.Task] = []

    if settings.PRICING_USE_REAL_ML:
        from src.services.pricing.inference import (
            get_inference_client as pricing_client,
        )

        tasks.append(
            asyncio.create_task(
                _prewarm_module("pricing", lambda: pricing_client()._get_policy()),
                name="prewarm-pricing",
            )
        )

    if settings.FORECASTING_USE_REAL_ML:
        from src.services.forecasting.inference import (
            get_inference_client as forecasting_client,
        )

        tasks.append(
            asyncio.create_task(
                _prewarm_module(
                    "forecasting",
                    lambda: forecasting_client()._resolve_factory(),
                ),
                name="prewarm-forecasting",
            )
        )

    if settings.SUSTAINABILITY_USE_REAL_ML:
        from src.services.sustainability.inference import (
            get_inference_client as sustainability_client,
        )

        tasks.append(
            asyncio.create_task(
                _prewarm_module(
                    "sustainability",
                    lambda: sustainability_client()._get_scorer(),
                ),
                name="prewarm-sustainability",
            )
        )

    if settings.RECRUITMENT_USE_REAL_ML:
        from src.services.recruitment.inference import (
            get_inference_client as recruitment_client,
        )

        tasks.append(
            asyncio.create_task(
                _prewarm_module(
                    "recruitment-sbert",
                    lambda: recruitment_client()._get_ranker(),
                ),
                name="prewarm-recruitment",
            )
        )

    return tasks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    Handles startup (DB init, cache warm, model preload)
    and graceful shutdown.
    """
    # ── Startup ──────────────────────────────────────────
    setup_logging()

    # Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Connect to Redis
    await redis_client.initialize()

    # Pre-warm ML model registry (prevents cold-start on first request)
    from src.services.shared_context.model_registry import ModelRegistry

    await ModelRegistry.initialize()

    # Fire-and-forget pre-warm of every real-ML inference client.
    # Server starts serving immediately; ML modules warm in background.
    app.state.ml_prewarm_tasks = _schedule_ml_prewarm()
    if app.state.ml_prewarm_tasks:
        logger.info(
            "Scheduled {} ML pre-warm task(s) in background",
            len(app.state.ml_prewarm_tasks),
        )

    yield

    # ── Shutdown ─────────────────────────────────────────
    # Cancel any pre-warm tasks still running
    for task in getattr(app.state, "ml_prewarm_tasks", []):
        if not task.done():
            task.cancel()

    await redis_client.close()
    await engine.dispose()


def create_application() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""

    app = FastAPI(
        title="BizVision AI",
        description="""
        ## Elite SME Decision Intelligence Platform

        BizVision AI provides AI-powered intelligence across 5 business domains:

        - **Recruitment Intelligence** — Semantic candidate ranking with fairness auditing
        - **Smart Pricing Advisor** — RL-powered price optimization with explainability
        - **Profit Forecasting** — Hybrid ensemble forecasting with scenario analysis
        - **Financial Advisory** — Multi-agent RAG chatbot for executive intelligence
        - **ESG Sustainability** — Explainable green business scoring

        All modules share a **Shared Context Bus** for cross-domain intelligence.
        """,
        version="1.0.0",
        docs_url="/api/v1/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/api/v1/redoc" if settings.ENABLE_DOCS else None,
        openapi_url="/api/v1/openapi.json" if settings.ENABLE_DOCS else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # ── Middleware Stack (order matters: outermost wraps innermost) ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    if settings.ENABLE_RATE_LIMITING:
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=100,
            window_seconds=60,
        )

    # ── Observability (Prometheus /metrics + optional OTel) ──
    instrument_app(app)

    # ── API Routes ────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    # ── Health & Status Endpoints ─────────────────────────
    @app.get("/health", tags=["System"])
    async def health_check():
        """Kubernetes/Docker health probe endpoint."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
        }

    @app.get("/ready", tags=["System"])
    async def readiness_check():
        """Readiness probe — checks all dependencies."""
        checks = {}
        try:
            # Check Redis
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"

        all_ok = all(v == "ok" for v in checks.values())
        return {"status": "ready" if all_ok else "degraded", "checks": checks}

    return app


app = create_application()
