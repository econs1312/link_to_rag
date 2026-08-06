"""
Redis-backed Rate Limiter — Sliding window counter per API key / tenant / IP.

Uses redis.asyncio (sub-module of redis>=5.0.0, already in requirements).
Fails open in dev mode: if Redis is unavailable, logs a warning and allows the request.

Config (via .env):
  RATE_LIMIT_MAX=50            # Max requests per window
  RATE_LIMIT_WINDOW_SECONDS=60 # Window duration in seconds

Reference: skills/09-security-auth-tenant.md
"""

from typing import Optional

from fastapi import Request, Depends
import structlog

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import RateLimitError
from app.core.security import verify_api_key, extract_tenant_id


class RateLimiter:
    """
    Sliding window counter rate limiter backed by Redis.

    Usage as a FastAPI dependency:
        rate_limiter = RateLimiter(max_requests=50, window_seconds=60)

        @router.post("/endpoint")
        async def my_endpoint(..., _rl=Depends(rate_limiter)):
            ...
    """

    def __init__(
        self,
        max_requests: int = settings.RATE_LIMIT_MAX,
        window_seconds: int = settings.RATE_LIMIT_WINDOW_SECONDS,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(
        self,
        request: Request,
        api_key: Optional[str] = Depends(verify_api_key),
    ) -> None:
        """FastAPI dependency — checks rate limit and raises RateLimitError if exceeded."""
        # Determine the rate limit key: API key > tenant_id > client IP
        tenant_id = extract_tenant_id(request)
        identifier = api_key or tenant_id or self._get_client_ip(request)
        redis_key = f"l2rag:ratelimit:{identifier}"

        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
            )

            try:
                # Atomic INCR + conditional EXPIRE (sliding window counter)
                pipe = client.pipeline(transaction=True)
                pipe.incr(redis_key)
                pipe.ttl(redis_key)
                results = await pipe.execute()

                current_count: int = results[0]
                ttl: int = results[1]

                # Set expiry only on first request in the window
                if ttl == -1:
                    await client.expire(redis_key, self.window_seconds)

                if current_count > self.max_requests:
                    retry_after = max(ttl, 1)
                    logger.warning(
                        "Rate limit exceeded",
                        identifier=identifier,
                        current_count=current_count,
                        max_requests=self.max_requests,
                        retry_after=retry_after,
                    )
                    raise RateLimitError(
                        message=f"Rate limit excedido. Máximo de {self.max_requests} requisições por {self.window_seconds} segundos.",
                        retry_after=retry_after,
                    )
            finally:
                await client.aclose()

        except RateLimitError:
            # Re-raise rate limit errors (don't swallow them)
            raise
        except Exception as exc:
            # Fail open: if Redis is down, allow the request (dev mode resilience)
            logger.warning(
                "Rate limiter Redis unavailable, allowing request (fail-open)",
                error=str(exc),
                redis_url=settings.REDIS_URL[:20] + "...",
            )

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP from request, supporting X-Forwarded-For behind proxies."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# Default rate limiter instance for use in endpoint Depends()
rate_limiter = RateLimiter()
