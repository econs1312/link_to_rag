"""
Application Exception Hierarchy.

Each exception class carries an `error_code` string used in JSend error responses
so API consumers can programmatically react to specific error types.
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base exception for application errors."""

    error_code: str = "ERR_APP"

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
    error_code = "ERR_NOT_FOUND"

    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=404, details=details)


class ExtractionError(AppException):
    error_code = "ERR_EXTRACTION"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=502, details=details)


class RateLimitError(AppException):
    error_code = "ERR_RATE_LIMIT"

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message=message, status_code=429, details=details)
        self.retry_after = retry_after


class CircuitBreakerOpenError(AppException):
    error_code = "ERR_CIRCUIT_BREAKER"

    def __init__(self, domain: str, message: Optional[str] = None):
        msg = message or f"Circuit breaker open for domain '{domain}' due to consecutive failures."
        super().__init__(message=msg, status_code=503, details={"domain": domain})


class DatabaseError(AppException):
    error_code = "ERR_DATABASE"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=500, details=details)


class TenantAccessDeniedError(AppException):
    """Raised when a tenant tries to access a resource belonging to another tenant."""
    error_code = "ERR_TENANT_ACCESS_DENIED"

    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        # Return 404 (not 403) to avoid revealing resource existence (skill 09 §3)
        super().__init__(message=message, status_code=404, details=details)
