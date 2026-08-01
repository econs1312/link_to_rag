import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.document import Document, DocumentChunk, IngestionStatus
from app.extractors.router import link_router
from app.services.text_cleaner import TextCleanerService
from app.services.chunker import ChunkingService
from app.services.embedding import EmbeddingService
from app.core.exceptions import AppException
from app.core.logging import logger


class IngestionPipelineService:
    """Orchestrates extraction, text cleaning, frontmatter generation, chunking, embedding, and DB persistence."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.chunker = ChunkingService()
        self.embedding_service = EmbeddingService()

    async def process_document(self, document_id: str, webhook_url: str | None = None) -> Document:
        # 1. Fetch document from DB
        stmt = select(Document).where(Document.id == document_id)
        res = await self.db.execute(stmt)
        doc = res.scalar_one_or_none()

        if not doc:
            raise AppException(f"Document with ID {document_id} not found in database", status_code=404)

        log = logger.bind(
            document_id=doc.id,
            correlation_id=doc.correlation_id,
            target_url=doc.source_url,
        )

        try:
            log.info("Starting document ingestion pipeline")

            # Update status to PROCESSING
            doc.status = IngestionStatus.PROCESSING
            await self.db.commit()

            # 2. Select extractor and execute extraction
            extractor = link_router.get_extractor(doc.source_url, source_type=doc.source_type)
            log.info("Selected extractor strategy", extractor=extractor.__class__.__name__)

            extracted_content = await extractor.extract(doc.source_url)

            # Update title and author if extracted
            doc.title = extracted_content.title
            doc.author = extracted_content.author
            doc.raw_text = extracted_content.raw_text

            # Merge metadata
            if not doc.metadata_info:
                doc.metadata_info = {}
            doc.metadata_info.update(extracted_content.metadata)

            # 3. Clean text & add Frontmatter
            cleaned_text = TextCleanerService.clean_text(extracted_content.raw_text)
            doc.cleaned_markdown = TextCleanerService.format_with_frontmatter(extracted_content, cleaned_text)

            # 4. Chunking
            chunks_data = self.chunker.create_chunks(doc.cleaned_markdown)
            log.info("Created text chunks", num_chunks=len(chunks_data))

            # 5. Embeddings
            chunk_texts = [c["chunk_text"] for c in chunks_data]
            embeddings = await self.embedding_service.generate_embeddings(chunk_texts)

            # 6. Create DocumentChunk records
            for idx, chunk_info in enumerate(chunks_data):
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=chunk_info["chunk_index"],
                    chunk_text=chunk_info["chunk_text"],
                    embedding=embeddings[idx] if idx < len(embeddings) else None,
                )
                self.db.add(chunk_obj)

            # 7. Update status to COMPLETED
            doc.status = IngestionStatus.COMPLETED
            await self.db.commit()
            await self.db.refresh(doc)

            log.info("Document ingestion pipeline completed successfully")

            # Fire webhook notification on success (best-effort)
            if webhook_url:
                from app.services.webhook import fire_webhook
                await fire_webhook(str(webhook_url), {
                    "job_id": doc.id,
                    "status": "completed",
                    "title": doc.title,
                    "source_url": doc.source_url,
                    "document_id": doc.id,
                })

            return doc

        except Exception as exc:
            await self.db.rollback()

            log.error("Ingestion pipeline failed", error=str(exc))

            # Re-fetch document after rollback to avoid DetachedInstanceError
            try:
                stmt_retry = select(Document).where(Document.id == document_id)
                res_retry = await self.db.execute(stmt_retry)
                doc_retry = res_retry.scalar_one_or_none()
                if doc_retry:
                    doc_retry.status = IngestionStatus.FAILED
                    doc_retry.error_message = str(exc)[:1000]  # Truncate to avoid DB overflow
                    await self.db.commit()
            except Exception as db_exc:
                log.error("Failed to update document status to FAILED after pipeline error", db_error=str(db_exc))

            # Fire webhook notification on failure (best-effort)
            if webhook_url:
                from app.services.webhook import fire_webhook
                await fire_webhook(str(webhook_url), {
                    "job_id": document_id,
                    "status": "failed",
                    "error": str(exc),
                })

            raise

