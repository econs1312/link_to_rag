import time
from typing import Dict
from urllib.parse import urlparse
from app.core.config import settings
from app.core.exceptions import CircuitBreakerOpenError
from app.core.logging import logger


class DomainCircuitBreaker:
    """Tracks domain failures and opens circuit breaker after thresholds are exceeded."""

    def __init__(
        self,
        max_failures: int = settings.CIRCUIT_BREAKER_FAILURES,
        cooldown_seconds: int = settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    ):
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        # Domain -> {"failure_count": int, "open_until": float}
        self._domain_stats: Dict[str, dict] = {}

    def _extract_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.lower() or "unknown"

    def check_domain(self, url: str) -> None:
        domain = self._extract_domain(url)
        stats = self._domain_stats.get(domain)

        if not stats:
            return

        now = time.time()
        if stats.get("open_until", 0) > now:
            logger.warning(
                "Circuit breaker open for domain",
                domain=domain,
                cooldown_remaining=int(stats["open_until"] - now),
            )
            raise CircuitBreakerOpenError(domain=domain)

        # Cooldown period has passed, reset stats if open_until expired
        if stats.get("open_until", 0) > 0 and stats["open_until"] <= now:
            self._domain_stats[domain] = {"failure_count": 0, "open_until": 0}

    def record_success(self, url: str) -> None:
        domain = self._extract_domain(url)
        if domain in self._domain_stats:
            self._domain_stats[domain] = {"failure_count": 0, "open_until": 0}

    def record_failure(self, url: str, is_block_or_rate_limit: bool = True) -> None:
        if not is_block_or_rate_limit:
            return

        domain = self._extract_domain(url)
        stats = self._domain_stats.setdefault(domain, {"failure_count": 0, "open_until": 0})
        stats["failure_count"] += 1

        logger.info(
            "Recorded domain extraction failure",
            domain=domain,
            failure_count=stats["failure_count"],
        )

        if stats["failure_count"] >= self.max_failures:
            open_until = time.time() + self.cooldown_seconds
            stats["open_until"] = open_until
            logger.error(
                "Circuit breaker tripped open for domain",
                domain=domain,
                cooldown_seconds=self.cooldown_seconds,
            )


circuit_breaker = DomainCircuitBreaker()
