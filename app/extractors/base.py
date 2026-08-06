from abc import ABC, abstractmethod
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.schemas.ingestion import ExtractedContent
from app.core.circuit_breaker import circuit_breaker
from app.core.logging import logger


class BaseExtractor(ABC):
    """Abstract Base Extractor enforcing common extraction contract and circuit breaker checks."""

    @abstractmethod
    async def extract(self, url: str) -> ExtractedContent:
        """Extract content from target URL."""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=32),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def extract_with_retry(self, url: str) -> ExtractedContent:
        """Extract content with automatic retry on transient network errors."""
        logger.debug("Attempting extraction with retry", target_url=url)
        return await self.extract(url)

    def validate_url_access(self, url: str) -> None:
        """Enforces circuit breaker rules before attempting extraction."""
        circuit_breaker.check_domain(url)

    def record_success(self, url: str) -> None:
        circuit_breaker.record_success(url)

    def record_failure(self, url: str, is_block_or_rate_limit: bool = True, status_code: int | None = None) -> None:
        circuit_breaker.record_failure(url, is_block_or_rate_limit=is_block_or_rate_limit, status_code=status_code)

