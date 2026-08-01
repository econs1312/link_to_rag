"""
Security & Multi-Tenancy Module.

Provides API Key authentication and Tenant ID extraction for API routes.

Config:
  settings.API_KEYS: comma-separated list of valid API keys (e.g. "key_tenant_a,key_tenant_b").
  If settings.API_KEYS is not set or empty, authentication is bypassed (dev mode).

Headers supported:
  X-API-Key or Authorization: Bearer <key>  -> API Key Validation
  X-Tenant-ID                               -> Tenant Isolation ID
"""

from typing import Optional
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.logging import logger

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def get_allowed_api_keys() -> set[str]:
    """Parse comma-separated API keys from settings."""
    if not settings.API_KEYS:
        return set()
    return {k.strip() for k in settings.API_KEYS.split(",") if k.strip()}


async def verify_api_key(
    request: Request,
    api_key_header_val: Optional[str] = Security(api_key_header),
    bearer_credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[str]:
    """
    Validates API Key if settings.API_KEYS is configured.
    Returns the validated API key string.
    """
    allowed_keys = get_allowed_api_keys()

    # If no API keys configured in environment, allow all requests (Dev Mode)
    if not allowed_keys:
        return None

    # Check X-API-Key header first, then Bearer token
    provided_key = api_key_header_val
    if not provided_key and bearer_credentials:
        provided_key = bearer_credentials.credentials

    if not provided_key or provided_key not in allowed_keys:
        logger.warning(
            "API Key authentication failed",
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Provide X-API-Key header or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_key


def extract_tenant_id(request: Request) -> Optional[str]:
    """Extract optional X-Tenant-ID header from incoming request for multi-tenancy tagging."""
    tenant_id = request.headers.get("X-Tenant-ID") or request.headers.get("x-tenant-id")
    return tenant_id.strip() if tenant_id else None
