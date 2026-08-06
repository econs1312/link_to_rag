import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status, BackgroundTasks, Request

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from arq.connections import create_pool, RedisSettings
from urllib.parse import urlparse
from app.db.session import get_db
from app.models.document import Document, IngestionStatus
from app.schemas.ingestion import IngestRequest, IngestResponse
from app.core.config import settings
from app.core.logging import logger
from app.core.security import verify_api_key, extract_tenant_id
from app.services.ingestion_pipeline import IngestionPipelineService

router = APIRouter()


async def get_redis_pool():
    parsed = urlparse(settings.REDIS_URL)
    return await create_pool(
        RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password,
            database=int(parsed.path.lstrip("/") or 0),
        )
    )


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue link for extraction and RAG ingestion",
)
async def enqueue_ingestion(
    payload: IngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    # Use trace_id from the TraceIDMiddleware (bound in structlog contextvars)
    ctx_vars = structlog.contextvars.get_contextvars()
    correlation_id = ctx_vars.get("trace_id") or str(uuid.uuid4())

    url_str = str(payload.url)
    tenant_id = extract_tenant_id(request)

    metadata = dict(payload.metadata or {})
    if tenant_id:
        metadata["tenant_id"] = tenant_id

    log = logger.bind(correlation_id=correlation_id, target_url=url_str, tenant_id=tenant_id)
    log.info("Received ingestion request", source_type=payload.source_type)

    # 1. Create initial Document record in DB
    job_id = str(uuid.uuid4())
    document = Document(
        id=job_id,
        correlation_id=correlation_id,
        source_url=url_str,
        source_type=payload.source_type,
        metadata_info=metadata,
        status=IngestionStatus.PENDING,
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    # 2. Enqueue job into ARQ Redis Queue (or fallback to background tasks if Redis is unavailable)
    webhook_url_str = str(payload.webhook_url) if payload.webhook_url else None
    try:
        redis_pool = await get_redis_pool()
        await redis_pool.enqueue_job("process_ingestion_job", job_id, correlation_id, webhook_url_str)
        await redis_pool.close()
        log.info("Job successfully enqueued to ARQ Redis", job_id=job_id)
    except Exception as exc:
        log.warning("Redis enqueue failed. Falling back to in-process FastAPI BackgroundTasks", error=str(exc))
        
        async def run_pipeline_fallback(doc_id: str, wh_url: str | None = None):
            from app.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as local_db:
                pipeline = IngestionPipelineService(local_db)
                await pipeline.process_document(doc_id, webhook_url=wh_url)

        background_tasks.add_task(run_pipeline_fallback, job_id, webhook_url_str)

    return IngestResponse(
        job_id=job_id,
        correlation_id=correlation_id,
        status=document.status.value,
        message="Ingestion job enqueued successfully",
    )

