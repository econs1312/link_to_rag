import asyncio
import structlog
from arq.connections import RedisSettings
from arq.worker import Retry
from urllib.parse import urlparse
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.db.session import AsyncSessionLocal
from app.services.ingestion_pipeline import IngestionPipelineService
from app.core.exceptions import RateLimitError, CircuitBreakerOpenError


def parse_redis_url(url: str) -> RedisSettings:
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip("/") or 0),
    )


async def process_ingestion_job(ctx: dict, job_id: str, correlation_id: str, webhook_url: str | None = None) -> str:
    """ARQ async worker task for document ingestion."""
    job_try = ctx.get("job_try", 1)

    # Bind trace_id to structlog contextvars for consistent log correlation
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=correlation_id)

    log = logger.bind(job_id=job_id, correlation_id=correlation_id, job_try=job_try)
    log.info("Worker picked up ingestion task", has_webhook=bool(webhook_url))

    async with AsyncSessionLocal() as db:
        pipeline = IngestionPipelineService(db)
        try:
            doc = await pipeline.process_document(job_id, webhook_url=webhook_url)
            log.info("Worker task processed successfully", document_id=doc.id)
            return doc.id

        except RateLimitError as rle:
            log.warning("Worker hit rate limit. Retrying with delay", retry_after=rle.retry_after)
            if job_try < settings.MAX_RETRIES:
                raise Retry(defer=rle.retry_after)
            raise

        except CircuitBreakerOpenError as cbe:
            log.warning(
                "Circuit breaker open for domain. Deferring job retry until cooldown expires",
                domain=cbe.domain,
                cooldown_seconds=settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS,
            )
            if job_try < settings.MAX_RETRIES:
                raise Retry(defer=settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS)
            raise

        except Exception as exc:
            log.error("Worker task error during execution", error=str(exc))
            if job_try < settings.MAX_RETRIES:
                backoff_delay = 2 ** (job_try * 2)  # 2s, 8s, 32s backoff
                log.info("Scheduling task retry", backoff_delay=backoff_delay)
                raise Retry(defer=backoff_delay)
            raise



async def startup(ctx: dict):
    setup_logging()
    logger.info("ARQ Worker starting up...")


async def shutdown(ctx: dict):
    logger.info("ARQ Worker shutting down...")


class WorkerSettings:
    functions = [process_ingestion_job]
    redis_settings = parse_redis_url(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    max_tries = settings.MAX_RETRIES
