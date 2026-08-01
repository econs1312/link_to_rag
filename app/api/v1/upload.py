"""
Upload endpoint: accepts PDF, DOCX, and image files for extraction and RAG ingestion.

Flow:
  1. Validate file type and size.
  2. Extract text via FileExtractor (pymupdf / python-docx / Tesseract / OpenAI Vision).
  3. Create a Document record in the DB (reusing the same model as URL ingestion).
  4. Run the ingestion pipeline (clean → chunk → embed → save) via BackgroundTask.
  5. Return 202 Accepted with job_id for polling.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.document import Document, IngestionStatus
from app.schemas.ingestion import IngestResponse
from app.core.logging import logger
from app.extractors.file_extractor import extract_file_content, detect_file_type, SUPPORTED_EXTENSIONS
from app.services.text_cleaner import TextCleanerService
from app.services.chunker import ChunkingService
from app.services.embedding import EmbeddingService
from app.models.document import DocumentChunk

router = APIRouter()

# 50 MB max upload size
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

ALLOWED_EXTENSIONS_DISPLAY = ", ".join(sorted(SUPPORTED_EXTENSIONS.keys()))


@router.post(
    "/upload",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a file (PDF, DOCX, image) for text extraction and RAG ingestion",
    description=(
        "Accepts PDF, DOCX, PNG, JPG, TIFF, BMP, GIF, WEBP files. "
        "Text is extracted using pymupdf (PDF), python-docx (DOCX), or "
        "Tesseract OCR / OpenAI Vision (images). "
        "The document is then chunked, embedded and stored in pgvector for semantic search."
    ),
)
async def upload_file(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(..., description="File to upload (PDF, DOCX, or image)"),
    category: Optional[str] = Form(None, description="Optional metadata category tag"),
    webhook_url: Optional[str] = Form(None, description="Optional webhook URL for job completion notification"),
):
    # ── 1. Validate file type ────────────────────────────────────────────────
    file_type = detect_file_type(file.filename or "", file.content_type)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type: '{file.filename}' (MIME: {file.content_type}). "
                f"Supported extensions: {ALLOWED_EXTENSIONS_DISPLAY}"
            ),
        )

    # ── 2. Read and validate size ────────────────────────────────────────────
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size // 1024 // 1024} MB). Maximum allowed: 50 MB.",
        )

    correlation_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    filename = file.filename or f"upload_{job_id}"

    log = logger.bind(
        job_id=job_id,
        correlation_id=correlation_id,
        filename=filename,
        file_type=file_type,
        file_size_kb=file_size // 1024,
    )
    log.info("File upload received, creating ingestion job")

    # ── 3. Create Document record ────────────────────────────────────────────
    document = Document(
        id=job_id,
        correlation_id=correlation_id,
        source_url=f"file://{filename}",
        source_type=f"file_{file_type}",
        title=filename,
        metadata_info={
            "filename": filename,
            "file_type": file_type,
            "file_size_bytes": file_size,
            "content_type": file.content_type,
            **({"category": category} if category else {}),
        },
        status=IngestionStatus.PENDING,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # ── 4. Enqueue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_file_upload,
        job_id=job_id,
        file_bytes=file_bytes,
        filename=filename,
        content_type=file.content_type,
        webhook_url=webhook_url,
    )

    return IngestResponse(
        job_id=job_id,
        correlation_id=correlation_id,
        status=document.status.value,
        message=f"File '{filename}' accepted for processing. Poll /api/v1/jobs/{job_id} for status.",
    )


async def _process_file_upload(
    job_id: str,
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str],
    webhook_url: Optional[str] = None,
) -> None:
    """Background task: extract → clean → chunk → embed → save to DB."""
    from app.db.session import AsyncSessionLocal
    from app.models.document import Document, DocumentChunk, IngestionStatus
    from sqlalchemy import select

    log = logger.bind(job_id=job_id, filename=filename)

    async with AsyncSessionLocal() as db:
        try:
            # Mark as PROCESSING
            stmt = select(Document).where(Document.id == job_id)
            res = await db.execute(stmt)
            doc = res.scalar_one_or_none()
            if not doc:
                log.error("Document record not found in DB for file upload job")
                return

            doc.status = IngestionStatus.PROCESSING
            await db.commit()

            # Extract content
            log.info("Starting file content extraction")
            extracted = await extract_file_content(file_bytes, filename, content_type)

            doc.title = extracted.title
            doc.author = extracted.author
            doc.raw_text = extracted.raw_text
            if not doc.metadata_info:
                doc.metadata_info = {}
            doc.metadata_info.update(extracted.metadata)

            # Clean + frontmatter
            cleaned_text = TextCleanerService.clean_text(extracted.raw_text)
            doc.cleaned_markdown = TextCleanerService.format_with_frontmatter(extracted, cleaned_text)

            # Chunk
            chunker = ChunkingService()
            chunks_data = chunker.create_chunks(doc.cleaned_markdown)
            log.info("File content chunked", num_chunks=len(chunks_data))

            # Embed
            embedding_svc = EmbeddingService()
            chunk_texts = [c["chunk_text"] for c in chunks_data]
            embeddings = await embedding_svc.generate_embeddings(chunk_texts)

            # Save chunks
            for idx, chunk_info in enumerate(chunks_data):
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=chunk_info["chunk_index"],
                    chunk_text=chunk_info["chunk_text"],
                    embedding=embeddings[idx] if idx < len(embeddings) else None,
                )
                db.add(chunk_obj)

            doc.status = IngestionStatus.COMPLETED
            await db.commit()
            log.info("File upload ingestion pipeline completed")

            # Webhook notification
            if webhook_url:
                from app.services.webhook import fire_webhook
                await fire_webhook(webhook_url, {
                    "job_id": job_id,
                    "status": "completed",
                    "title": doc.title,
                    "filename": filename,
                    "document_id": doc.id,
                })

        except Exception as exc:
            await db.rollback()
            log.error("File upload ingestion pipeline failed", error=str(exc))
            try:
                stmt_retry = select(Document).where(Document.id == job_id)
                res_retry = await db.execute(stmt_retry)
                doc_retry = res_retry.scalar_one_or_none()
                if doc_retry:
                    doc_retry.status = IngestionStatus.FAILED
                    doc_retry.error_message = str(exc)[:1000]
                    await db.commit()
            except Exception as db_exc:
                log.error("Failed to update status to FAILED", db_error=str(db_exc))

            if webhook_url:
                from app.services.webhook import fire_webhook
                await fire_webhook(webhook_url, {
                    "job_id": job_id,
                    "status": "failed",
                    "filename": filename,
                    "error": str(exc),
                })
