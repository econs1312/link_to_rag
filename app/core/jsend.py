"""
JSend Response Helpers — Standardized API response format.

All API responses (success and error) follow the JSend specification:
  - Success: {"status": "success", "data": {...}}
  - Fail:    {"status": "fail", "message": "...", "code": "ERR_...", "trace_id": "..."}
  - Error:   {"status": "error", "message": "...", "code": "ERR_...", "trace_id": "..."}

Reference: skills/12-error-handling-responses.md
"""

from typing import Any, Dict, Optional

import structlog
from fastapi.responses import JSONResponse


def _get_trace_id() -> str:
    """Extract current trace_id from structlog contextvars (set by TraceIDMiddleware)."""
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get("trace_id", "unknown")


def jsend_success(data: Dict[str, Any], status_code: int = 200) -> JSONResponse:
    """Build a JSend success response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "success",
            "data": data,
        },
    )


def jsend_fail(
    message: str,
    code: str,
    status_code: int = 400,
    trace_id: Optional[str] = None,
) -> JSONResponse:
    """Build a JSend fail response (client error — 4xx)."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "fail",
            "message": message,
            "code": code,
            "trace_id": trace_id or _get_trace_id(),
        },
    )


def jsend_error(
    message: str,
    code: str,
    status_code: int = 500,
    trace_id: Optional[str] = None,
) -> JSONResponse:
    """Build a JSend error response (server error — 5xx)."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "message": message,
            "code": code,
            "trace_id": trace_id or _get_trace_id(),
        },
    )
