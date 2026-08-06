"""
Analytics API endpoint.

Provides real-time system metrics, ingestion counts, source distributions,
and status breakdown from PostgreSQL.

Multi-tenancy (skill 09 §3):
  When X-Tenant-ID header is present, all analytics are scoped to that tenant.
  Without tenant_id, returns global analytics (dev mode).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.db.session import get_db
from app.models.document import Document, DocumentChunk, IngestionStatus
from app.core.security import verify_api_key, extract_tenant_id

router = APIRouter()


def _apply_tenant_filter(stmt, tenant_id: Optional[str]):
    """Add tenant_id filter to a query when present."""
    if tenant_id:
        return stmt.where(Document.metadata_info["tenant_id"].astext == tenant_id)
    return stmt


@router.get(
    "/analytics",
    summary="Get real-time ingestion analytics and vector DB statistics",
    description="Returns total document counts, status breakdown, source distribution, total chunks, and recent jobs log.",
)
async def get_analytics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    tenant_id = extract_tenant_id(request)

    # 1. Total documents
    stmt_total = select(func.count(Document.id))
    stmt_total = _apply_tenant_filter(stmt_total, tenant_id)
    res_total = await db.execute(stmt_total)
    total_docs = res_total.scalar_one() or 0

    # 2. Status breakdown
    stmt_status = select(Document.status, func.count(Document.id)).group_by(Document.status)
    stmt_status = _apply_tenant_filter(stmt_status, tenant_id)
    res_status = await db.execute(stmt_status)
    status_counts = {s.value: 0 for s in IngestionStatus}
    for row in res_status.all():
        status_val = row[0].value if hasattr(row[0], "value") else str(row[0])
        status_counts[status_val] = row[1]

    # 3. Source type breakdown
    stmt_sources = select(
        func.coalesce(Document.source_type, "web"),
        func.count(Document.id)
    ).group_by(Document.source_type)
    stmt_sources = _apply_tenant_filter(stmt_sources, tenant_id)
    res_sources = await db.execute(stmt_sources)
    source_counts = {row[0]: row[1] for row in res_sources.all()}

    # 4. Total chunks count (join through document for tenant filtering)
    if tenant_id:
        stmt_chunks = (
            select(func.count(DocumentChunk.id))
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.metadata_info["tenant_id"].astext == tenant_id)
        )
    else:
        stmt_chunks = select(func.count(DocumentChunk.id))
    res_chunks = await db.execute(stmt_chunks)
    total_chunks = res_chunks.scalar_one() or 0

    # 5. Recent failed jobs (last 5)
    stmt_failed = (
        select(Document)
        .where(Document.status == IngestionStatus.FAILED)
        .order_by(desc(Document.created_at))
        .limit(5)
    )
    stmt_failed = _apply_tenant_filter(stmt_failed, tenant_id)
    res_failed = await db.execute(stmt_failed)
    recent_failed = [
        {
            "id": doc.id,
            "title": doc.title or doc.source_url,
            "source_url": doc.source_url,
            "error_message": doc.error_message or "Unknown error",
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in res_failed.scalars().all()
    ]

    # 6. Recent completed jobs (last 5)
    stmt_completed = (
        select(Document)
        .where(Document.status == IngestionStatus.COMPLETED)
        .order_by(desc(Document.created_at))
        .limit(5)
    )
    stmt_completed = _apply_tenant_filter(stmt_completed, tenant_id)
    res_completed = await db.execute(stmt_completed)
    recent_completed = [
        {
            "id": doc.id,
            "title": doc.title or "Untitled",
            "source_type": doc.source_type or "web",
            "source_url": doc.source_url,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in res_completed.scalars().all()
    ]

    return {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "status_breakdown": status_counts,
        "source_breakdown": source_counts,
        "recent_failed": recent_failed,
        "recent_completed": recent_completed,
    }
