from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.exceptions import AppException
from app.db.session import init_db
from app.api.v1.ingest import router as ingest_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.search import router as search_router
from app.api.v1.upload import router as upload_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Initializing Link-to-Text Ingestion Service...")
    try:
        await init_db()
    except Exception as exc:
        logger.warning("Database startup initialization skipped/failed", error=str(exc))
    yield
    logger.info("Application shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Microservice for extracting web/video/social content, structuring Markdown, chunking and pgvector search.",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.error(
        "Application exception caught",
        path=request.url.path,
        status_code=exc.status_code,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "details": exc.details,
        },
    )


# Include Routers
app.include_router(ingest_router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(jobs_router, prefix="/api/v1", tags=["Jobs"])
app.include_router(search_router, prefix="/api/v1", tags=["Search"])
app.include_router(upload_router, prefix="/api/v1", tags=["Upload"])


import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Mount static directory
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
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }

