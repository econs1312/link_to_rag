from pydantic import BaseModel, HttpUrl, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
import ipaddress
import socket


# Hostnames that are always blocked regardless of DNS resolution
_BLOCKED_HOSTNAMES = {"localhost", "0.0.0.0", "[::]", "[::1]"}


def _is_ssrf_target(hostname: str) -> bool:
    """Check if a hostname resolves to a private/reserved IP address (SSRF protection)."""
    # Block well-known local hostnames
    normalized = hostname.lower().strip(".")
    if normalized in _BLOCKED_HOSTNAMES or normalized.endswith(".local"):
        return True

    try:
        # Resolve hostname to IP(s) — checks the *actual* IP, not just the hostname string
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                return True
    except (socket.gaierror, ValueError):
        # DNS resolution failed — block by default (fail-closed)
        return True

    return False


class IngestRequest(BaseModel):
    url: HttpUrl = Field(..., description="Target URL to extract and process for RAG")
    source_type: Optional[str] = Field(None, description="Optional override for source platform (youtube, web, social)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom metadata tags (tenant_id, category, etc.)")
    webhook_url: Optional[HttpUrl] = Field(
        None,
        description="Optional webhook URL to receive a POST notification when the job completes or fails. Useful for integration with n8n, Make.com, Zapier, etc.",
    )

    @field_validator("url")
    @classmethod
    def block_ssrf_urls(cls, v: HttpUrl) -> HttpUrl:
        """Reject URLs pointing to private/local network addresses to prevent SSRF attacks."""
        hostname = v.host
        if not hostname:
            raise ValueError("URL must contain a valid hostname.")

        if _is_ssrf_target(hostname):
            raise ValueError(
                f"URL com host '{hostname}' bloqueada: endereços privados/locais não são permitidos "
                f"(127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, localhost, etc.)."
            )

        return v


class IngestResponse(BaseModel):
    job_id: str = Field(..., description="Unique job ID for tracking extraction")
    correlation_id: str = Field(..., description="Trace/Correlation ID for logging")
    status: str = Field(..., description="Initial job status (pending)")
    message: str = Field(default="Ingestion job enqueued successfully")


class JobStatusResponse(BaseModel):
    job_id: str
    correlation_id: str
    status: str
    source_url: str
    title: Optional[str] = None
    author: Optional[str] = None
    document_id: Optional[str] = None
    cleaned_markdown: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedContent(BaseModel):
    raw_text: str
    title: str = "Untitled"
    author: str = "Unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_url: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    limit: int = Field(default=5, ge=1, le=50, description="Max number of chunk results to return")
    filter_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filter dictionary")
    search_mode: Literal["hybrid", "vector", "fulltext"] = Field(
        default="hybrid",
        description="Search strategy: 'hybrid' (vector + fulltext + RRF), 'vector' (cosine only), 'fulltext' (tsvector only)",
    )
    rrf_k: int = Field(default=60, ge=1, le=1000, description="RRF constant k (default 60). Higher values reduce the influence of rank position.")


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    chunk_text: str
    score: float
    title: Optional[str] = None
    source_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    query: str
    search_mode: str = Field(default="hybrid", description="Search mode used for this query")
    total_results: int
    results: List[SearchResultItem]


class DeleteResponse(BaseModel):
    message: str
    deleted_id: str

