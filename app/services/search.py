from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func, or_
from app.models.document import Document, DocumentChunk
from app.services.embedding import EmbeddingService
from app.schemas.ingestion import SearchResultItem, SearchResponse


class VectorSearchService:
    """Executes hybrid vector + full-text search against PostgreSQL + pgvector."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()

    async def search(
        self,
        query: str,
        limit: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchResponse:
        # Generate query vector
        query_embedding = await self.embedding_service.generate_query_embedding(query)

        # 1. Cosine similarity query using pgvector operator (<=>)
        # Note: 1 - (embedding <=> query_embedding) = Cosine Similarity Score
        cosine_distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        similarity_score = (1 - cosine_distance).label("score")

        stmt = (
            select(
                DocumentChunk,
                Document.title,
                Document.source_url,
                Document.metadata_info,
                similarity_score,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .order_by(cosine_distance.asc())
            .limit(limit)
        )

        if filter_metadata:
            for key, val in filter_metadata.items():
                stmt = stmt.where(Document.metadata_info[key].astext == str(val))

        result = await self.db.execute(stmt)
        rows = result.all()

        items: List[SearchResultItem] = []
        for row in rows:
            chunk: DocumentChunk = row[0]
            title: str = row[1]
            source_url: str = row[2]
            metadata: dict = row[3] or {}
            score: float = float(row[4]) if row[4] is not None else 0.0

            items.append(
                SearchResultItem(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.chunk_text,
                    score=round(score, 4),
                    title=title,
                    source_url=source_url,
                    metadata=metadata,
                )
            )

        return SearchResponse(
            query=query,
            total_results=len(items),
            results=items,
        )
