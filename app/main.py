"""
L2RAG Application Entry Point.

Configures FastAPI with:
  - TraceID middleware for request correlation
  - CORS middleware
  - Global JSend exception handlers (skill 12)
  - API router registration
  - Static file serving + health check
"""

import os
import traceback
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.exceptions import AppException, RateLimitError
from app.core.jsend import jsend_success, jsend_fail, jsend_error
from app.core.trace_middleware import TraceIDMiddleware
from app.db.session import init_db
from app.api.v1.ingest import router as ingest_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.search import router as search_router
from app.api.v1.upload import router as upload_router
from app.api.v1.analytics import router as analytics_router


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Initializing Link-to-Text Ingestion Service...")
    try:
        await init_db()
    except Exception as exc:
        logger.warning("Database startup initialization skipped/failed", error=str(exc))

    # Security warning for dev mode
    if not settings.API_KEYS:
        logger.warning(
            "ATENÇÃO: API_KEYS não configurada. A API está a correr sem autenticação.",
            environment=settings.ENVIRONMENT,
        )

    yield
    logger.info("Application shutting down...")


# ─────────────────────────────────────────────────────────────────────────────
# App instance
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Microservice for extracting web/video/social content, structuring Markdown, chunking and pgvector search.",
    lifespan=lifespan,
)

# Trace ID Middleware (must be added before CORS so it runs on every request)
app.add_middleware(TraceIDMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Global Exception Handlers (JSend format — skill 12)
# ─────────────────────────────────────────────────────────────────────────────

def _get_trace_id() -> str:
    """Extract current trace_id from structlog contextvars."""
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get("trace_id", "unknown")


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle all application-level exceptions in JSend format."""
    trace_id = _get_trace_id()

    logger.error(
        "Application exception caught",
        path=request.url.path,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        trace_id=trace_id,
    )

    response = jsend_fail(
        message=exc.message,
        code=exc.error_code,
        status_code=exc.status_code,
        trace_id=trace_id,
    )

    # Add Retry-After header for rate limit errors
    if isinstance(exc, RateLimitError):
        response.headers["Retry-After"] = str(exc.retry_after)

    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors (422) in JSend format.

    Skill 12 §2: Map to a clean, readable format instead of FastAPI's verbose default array.
    """
    trace_id = _get_trace_id()

    # Build human-readable error summary
    error_details = []
    for err in exc.errors():
        field = " → ".join(str(loc) for loc in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        error_details.append(f"{field}: {msg}")

    message = "; ".join(error_details) if error_details else "Erro de validação nos dados enviados."

    logger.warning(
        "Request validation error",
        path=request.url.path,
        errors=error_details,
        trace_id=trace_id,
    )

    return jsend_fail(
        message=message,
        code="ERR_VALIDATION",
        status_code=422,
        trace_id=trace_id,
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """
    Handle SQLAlchemy database errors.

    Skill 12 §2: NEVER leak database structure details (table names, columns)
    in the HTTP response. Log the full traceback internally.
    """
    trace_id = _get_trace_id()

    # Log full details internally (never in HTTP response)
    logger.error(
        "Database error caught by global handler",
        path=request.url.path,
        error_type=type(exc).__name__,
        error=str(exc),
        trace_id=trace_id,
        exc_info=True,
    )

    return jsend_error(
        message="Erro interno de base de dados. Tente novamente mais tarde.",
        code="ERR_DATABASE",
        status_code=500,
        trace_id=trace_id,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Reformat FastAPI's default HTTPException to JSend format."""
    trace_id = _get_trace_id()

    return jsend_fail(
        message=str(exc.detail),
        code=f"ERR_HTTP_{exc.status_code}",
        status_code=exc.status_code,
        trace_id=trace_id,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for unhandled exceptions.

    Skill 12 §3: Log CRITICAL with full traceback internally,
    return generic error message to client.
    """
    trace_id = _get_trace_id()

    logger.critical(
        "Unhandled exception caught by global handler",
        path=request.url.path,
        error_type=type(exc).__name__,
        error=str(exc),
        trace_id=trace_id,
        traceback=traceback.format_exc(),
    )

    return jsend_error(
        message="Erro interno inesperado. Contacte o suporte se o problema persistir.",
        code="ERR_INTERNAL",
        status_code=500,
        trace_id=trace_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(ingest_router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(jobs_router, prefix="/api/v1", tags=["Jobs"])
app.include_router(search_router, prefix="/api/v1", tags=["Search"])
app.include_router(upload_router, prefix="/api/v1", tags=["Upload"])
app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics"])


# ─────────────────────────────────────────────────────────────────────────────
# Static files + Health
# ─────────────────────────────────────────────────────────────────────────────

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
async def serve_ui():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Link-to-RAG API is running"}


@app.get("/health", tags=["Health"])
async def health_check():
    return jsend_success({
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    })
