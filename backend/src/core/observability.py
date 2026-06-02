"""
BizVision AI — Observability

Prometheus metrics (request count + latency histogram) exposed at `/metrics`,
plus an optional OpenTelemetry tracing hook. Everything is guarded so the app
still boots if the optional libraries aren't installed in a given environment.
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )

    _HAS_PROM = True
except ImportError:  # pragma: no cover
    _HAS_PROM = False


if _HAS_PROM:
    REQUEST_COUNT = Counter(
        "bizvision_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "bizvision_http_request_duration_seconds",
        "HTTP request latency (seconds)",
        ["method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record per-request count and latency. Uses the route template as the
    `path` label to avoid high-cardinality metrics from path params."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        if _HAS_PROM:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
            REQUEST_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
        return response


def instrument_app(app: FastAPI) -> None:
    """Attach metrics middleware + `/metrics` endpoint, and OTel if available."""
    if not _HAS_PROM:
        logger.warning("prometheus_client not installed — /metrics disabled.")
        return

    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    _maybe_setup_tracing(app)
    logger.info("Observability enabled: /metrics live.")


def _maybe_setup_tracing(app: FastAPI) -> None:
    """Best-effort OpenTelemetry FastAPI instrumentation (no-op if absent)."""
    if settings.is_development:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing instrumented.")
    except ImportError:  # pragma: no cover
        logger.info("OpenTelemetry not installed — tracing skipped.")
