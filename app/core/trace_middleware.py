"""
Trace ID Middleware — Correlates every HTTP request with a unique X-Trace-ID.

- Reads the incoming ``X-Trace-ID`` header; generates a UUIDv4 when absent.
- Binds ``trace_id`` into ``structlog.contextvars`` so every log message
  emitted during the request lifecycle carries the correlation value.
- Echoes the ``X-Trace-ID`` header back in the HTTP response.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import structlog


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Middleware that injects / propagates X-Trace-ID across request lifecycle."""

    HEADER_NAME = "X-Trace-ID"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Read or generate trace_id
        trace_id = request.headers.get(self.HEADER_NAME) or str(uuid.uuid4())

        # 2. Bind to structlog contextvars (automatically attached to all logs)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        try:
            response: Response = await call_next(request)
        finally:
            # 3. Clean up contextvars after request completes
            structlog.contextvars.clear_contextvars()

        # 4. Echo trace_id in response header
        response.headers[self.HEADER_NAME] = trace_id
        return response
