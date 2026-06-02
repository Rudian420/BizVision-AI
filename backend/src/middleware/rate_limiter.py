"""
BizVision AI — Rate Limiting Middleware

Fixed-window rate limiter keyed by client IP. Uses Redis for a
distributed counter when available, and transparently falls back to an
in-process counter (single-worker dev) if Redis is not yet initialised.

Health/readiness probes are exempt.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.core.redis import redis_client

_EXEMPT_PATHS = {"/health", "/ready"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Fallback store: ip -> (window_start_epoch, count)
        self._local: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _hit(self, ip: str) -> tuple[int, int]:
        """Return (current_count, ttl_seconds) for the caller's window."""
        window = int(time.time()) // self.window_seconds
        key = f"ratelimit:{ip}:{window}"
        try:
            count = await redis_client.client.incr(key)
            if count == 1:
                await redis_client.client.expire(key, self.window_seconds)
            ttl = await redis_client.client.ttl(key)
            return int(count), int(ttl if ttl and ttl > 0 else self.window_seconds)
        except Exception:
            # Redis unavailable → in-memory fallback.
            start, count = self._local[ip]
            now_window = int(time.time()) // self.window_seconds
            if now_window != start:
                count = 0
                start = now_window
            count += 1
            self._local[ip] = (start, count)
            ttl = self.window_seconds - (int(time.time()) % self.window_seconds)
            return count, ttl

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        ip = self._client_ip(request)
        count, ttl = await self._hit(ip)

        if count > self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please retry later.",
                    "limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                },
                headers={"Retry-After": str(ttl)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.max_requests - count))
        return response
