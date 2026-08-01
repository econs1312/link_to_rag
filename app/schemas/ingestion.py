from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class IngestRequest(BaseModel):
    url: HttpUrl = Field(..., description="Target URL to extract and process for RAG")
    source_type: Optional[str] = Field(None, description="Optional override for source platform (youtube, web, social)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom metadata tags (tenant_id, category, etc.)")


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
    total_results: int
    results: List[SearchResultItem]
