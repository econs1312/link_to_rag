from abc import ABC, abstractmethod
from app.schemas.ingestion import ExtractedContent
from app.core.circuit_breaker import circuit_breaker


class BaseExtractor(ABC):
    """Abstract Base Extractor enforcing common extraction contract and circuit breaker checks."""

    @abstractmethod
    async def extract(self, url: str) -> ExtractedContent:
        """Extract content from target URL."""
        pass

    def validate_url_access(self, url: str) -> None:
        """Enforces circuit breaker rules before attempting extraction."""
        circuit_breaker.check_domain(url)

    def record_success(self, url: str) -> None:
        circuit_breaker.record_success(url)

    def record_failure(self, url: str, is_block_or_rate_limit: bool = True) -> None:
        circuit_breaker.record_failure(url, is_block_or_rate_limit=is_block_or_rate_limit)
