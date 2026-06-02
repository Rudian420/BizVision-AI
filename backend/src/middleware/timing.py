"""
BizVision AI — Timing Middleware

Measures wall-clock latency for each request and reports it via the
``X-Process-Time-Ms`` response header. Useful for spotting slow ML
inference endpoints during development.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

PROCESS_TIME_HEADER = "X-Process-Time-Ms"


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        response.headers[PROCESS_TIME_HEADER] = f"{elapsed_ms:.2f}"
        return response
