"""
BizVision AI — Request ID Middleware

Attaches a unique correlation ID to every request so logs and responses
can be traced end-to-end. Honours an inbound ``X-Request-ID`` header if
the caller supplies one, otherwise generates a UUID4.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        # Expose to downstream handlers via request.state.
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
