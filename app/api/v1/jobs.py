from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.document import Document
from app.schemas.ingestion import JobStatusResponse

router = APIRouter()


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get status and details of an ingestion job",
)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(Document.id == job_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found",
        )

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
