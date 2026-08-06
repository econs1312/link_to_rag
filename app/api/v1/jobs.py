"""
Jobs & Documents API — Status polling, export, and deletion.

Multi-tenancy (skill 09 §3):
  - All read/delete operations validate tenant_id ownership.
  - If tenant_id doesn't match, returns 404 (not 403) to avoid revealing resource existence.
  - In dev mode (no API_KEYS / no tenant_id), tenant filtering is skipped for convenience.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Literal

from app.db.session import get_db
from app.models.document import Document
from app.schemas.ingestion import JobStatusResponse, DeleteResponse
from app.core.exceptions import NotFoundError
from app.core.logging import logger
from app.core.security import verify_api_key, extract_tenant_id

router = APIRouter()


# ── Tenant-aware query helper ────────────────────────────────────────────────

async def _get_document_with_tenant_check(
    doc_id: str,
    request: Request,
    db: AsyncSession,
    resource_label: str = "Document",
) -> Document:
    """
    Fetch a document by ID with tenant isolation (skill 09 §3).

    If tenant_id is present in the request, the query also filters by it.
    Returns 404 if not found OR if tenant doesn't match (to avoid revealing existence).
    """
    tenant_id = extract_tenant_id(request)

    stmt = select(Document).where(Document.id == doc_id)

    # Apply tenant filter when tenant_id is present
    if tenant_id:
        stmt = stmt.where(Document.metadata_info["tenant_id"].astext == tenant_id)

    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise NotFoundError(
            message=f"{resource_label} with ID '{doc_id}' not found",
            details={resource_label.lower() + "_id": doc_id},
        )

    return doc


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get status and details of an ingestion job",
)
async def get_job_status(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    doc = await _get_document_with_tenant_check(job_id, request, db, resource_label="Job")

    return JobStatusResponse(
        job_id=doc.id,
        correlation_id=doc.correlation_id,
        status=doc.status.value,
        source_url=doc.source_url,
        title=doc.title,
        author=doc.author,
        document_id=doc.id if doc.status.value == "completed" else None,
        cleaned_markdown=doc.cleaned_markdown or doc.raw_text,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get(
    "/documents/{doc_id}/export",
    summary="Export document content in the specified format (md, txt, json)",
    responses={
        200: {"description": "Document content in the requested format"},
        404: {"description": "Document not found"},
        400: {"description": "Document not yet completed"},
    },
)
async def export_document(
    doc_id: str,
    request: Request,
    format: Literal["md", "txt", "json"] = Query(default="md", description="Export format: md (Markdown), txt (plain text), json (full metadata + content)"),
    db: AsyncSession = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """Download the extracted and cleaned content of an ingested document.

    - **md**: Returns the cleaned Markdown with YAML frontmatter
    - **txt**: Returns plain text (frontmatter stripped)
    - **json**: Returns full document metadata + content as JSON
    """
    doc = await _get_document_with_tenant_check(doc_id, request, db, resource_label="Document")

    if doc.status.value not in ("completed",):
        raise HTTPException(
            status_code=400,
            detail=f"Document is not yet completed (current status: {doc.status.value}). Try again after processing finishes.",
        )

    content_md = doc.cleaned_markdown or doc.raw_text or ""
    safe_title = (doc.title or doc_id).replace("/", "-").replace("\\", "-")[:60]

    if format == "json":
        return JSONResponse(
            content={
                "document_id": doc.id,
                "title": doc.title,
                "author": doc.author,
                "source_url": doc.source_url,
                "source_type": doc.source_type,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "metadata": doc.metadata_info or {},
                "content_markdown": content_md,
                "raw_text": doc.raw_text or "",
            },
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.json"'},
        )

    if format == "txt":
        import re
        # Strip YAML frontmatter block (--- ... ---) for plain text export
        plain_text = re.sub(r"^---\n.*?\n---\n", "", content_md, flags=re.DOTALL).strip()
        return PlainTextResponse(
            content=plain_text,
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.txt"'},
        )

    # Default: Markdown
    return PlainTextResponse(
        content=content_md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteResponse,
    summary="Delete a document and all its chunks/vectors",
    responses={
        200: {"description": "Document successfully deleted"},
        404: {"description": "Document not found"},
    },
)
async def delete_document(
    document_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """Remove a document and cascade-delete all associated chunks and embeddings."""
    doc = await _get_document_with_tenant_check(document_id, request, db, resource_label="Document")

    logger.info("Deleting document and associated chunks", document_id=document_id)
    await db.delete(doc)
    await db.commit()

    return DeleteResponse(
        message="Document and all associated chunks deleted successfully",
        deleted_id=document_id,
    )


@router.delete(
    "/jobs/{job_id}",
    response_model=DeleteResponse,
    summary="Delete a job and all its associated data",
    responses={
        200: {"description": "Job successfully deleted"},
        404: {"description": "Job not found"},
    },
)
async def delete_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """Remove a job record and cascade-delete all associated chunks and embeddings."""
    doc = await _get_document_with_tenant_check(job_id, request, db, resource_label="Job")

    logger.info("Deleting job and associated data", job_id=job_id)
    await db.delete(doc)
    await db.commit()

    return DeleteResponse(
        message="Job and all associated data deleted successfully",
        deleted_id=job_id,
    )
