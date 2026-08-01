from typing import Any, Dict, Optional


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=404, details=details)


class ExtractionError(AppException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=502, details=details)


class RateLimitError(AppException):
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message=message, status_code=429, details=details)
        self.retry_after = retry_after


class CircuitBreakerOpenError(AppException):
    def __init__(self, domain: str, message: Optional[str] = None):
        msg = message or f"Circuit breaker open for domain '{domain}' due to consecutive failures."
        super().__init__(message=msg, status_code=503, details={"domain": domain})


class DatabaseError(AppException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=500, details=details)
