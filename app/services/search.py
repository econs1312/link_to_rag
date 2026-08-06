"""
Hybrid Search Service — Vector (Cosine) + Full-Text (tsvector/tsquery) + RRF.

Implements three search modes:
  - 'vector':   Cosine similarity via pgvector (<=>).
  - 'fulltext':  PostgreSQL tsvector/tsquery with ts_rank_cd ranking.
  - 'hybrid':    Combines both via Reciprocal Rank Fusion (RRF).

Reference: skills/07-rag-retrieval-search.md
"""

from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.document import Document, DocumentChunk
from app.services.embedding import EmbeddingService
from app.schemas.ingestion import SearchResultItem, SearchResponse
from app.core.logging import logger


@dataclass
class _RankedChunk:
    """Internal struct holding chunk data with its rank position from a single search pass."""
    chunk_id: str
    document_id: str
    chunk_index: int
    chunk_text: str
    title: Optional[str]
    source_url: Optional[str]
    metadata: Optional[Dict[str, Any]]
    rank: int  # 1-based rank position in the source result set


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
        search_mode: Literal["hybrid", "vector", "fulltext"] = "hybrid",
        rrf_k: int = 60,
    ) -> SearchResponse:
        """
        Execute search with the specified mode.

        Args:
            query: User search query string.
            limit: Max number of results to return.
            filter_metadata: Optional metadata key-value filter on Document.
            search_mode: 'hybrid' | 'vector' | 'fulltext'.
            rrf_k: RRF constant k (default 60, per literature standard).
        """
        log = logger.bind(query=query[:100], limit=limit, search_mode=search_mode)

        if search_mode == "vector":
            items = await self._vector_search(query, limit, filter_metadata)
            log.info("Vector-only search completed", results=len(items))

        elif search_mode == "fulltext":
            items = await self._fulltext_search(query, limit, filter_metadata)
            log.info("Full-text-only search completed", results=len(items))

        else:  # hybrid
            items = await self._hybrid_search(query, limit, filter_metadata, rrf_k)
            log.info("Hybrid search (RRF) completed", results=len(items))

        return SearchResponse(
            query=query,
            search_mode=search_mode,
            total_results=len(items),
            results=items,
        )

    # ── Vector Search (Cosine Similarity via pgvector) ───────────────────────

    async def _vector_search(
        self,
        query: str,
        limit: int,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResultItem]:
        """Cosine similarity search using pgvector's <=> operator."""
        query_embedding = await self.embedding_service.generate_query_embedding(query)

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
            .where(DocumentChunk.embedding.isnot(None))
            .order_by(cosine_distance.asc())
            .limit(limit)
        )

        stmt = self._apply_metadata_filter(stmt, filter_metadata)
        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            SearchResultItem(
                chunk_id=row[0].id,
                document_id=row[0].document_id,
                chunk_index=row[0].chunk_index,
                chunk_text=row[0].chunk_text,
                score=round(float(row[4]), 4) if row[4] is not None else 0.0,
                title=row[1],
                source_url=row[2],
                metadata=row[3] or {},
            )
            for row in rows
        ]

    # ── Full-Text Search (tsvector/tsquery + ts_rank_cd) ─────────────────────

    async def _fulltext_search(
        self,
        query: str,
        limit: int,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResultItem]:
        """PostgreSQL full-text search using tsvector/tsquery with ts_rank_cd ranking."""
        ts_query = func.plainto_tsquery("simple", query)
        rank_score = func.ts_rank_cd(DocumentChunk.search_vector, ts_query).label("score")

        stmt = (
            select(
                DocumentChunk,
                Document.title,
                Document.source_url,
                Document.metadata_info,
                rank_score,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.search_vector.isnot(None))
            .where(DocumentChunk.search_vector.op("@@")(ts_query))
            .order_by(rank_score.desc())
            .limit(limit)
        )

        stmt = self._apply_metadata_filter(stmt, filter_metadata)
        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            SearchResultItem(
                chunk_id=row[0].id,
                document_id=row[0].document_id,
                chunk_index=row[0].chunk_index,
                chunk_text=row[0].chunk_text,
                score=round(float(row[4]), 4) if row[4] is not None else 0.0,
                title=row[1],
                source_url=row[2],
                metadata=row[3] or {},
            )
            for row in rows
        ]

    # ── Hybrid Search (RRF = Reciprocal Rank Fusion) ─────────────────────────

    async def _hybrid_search(
        self,
        query: str,
        limit: int,
        filter_metadata: Optional[Dict[str, Any]] = None,
        rrf_k: int = 60,
    ) -> List[SearchResultItem]:
        """
        Combine vector and full-text results using Reciprocal Rank Fusion.

        Formula per chunk:
            rrf_score = Σ  1 / (k + rank_i)

        where rank_i is the 1-based position in each result set.
        Chunks appearing in both sets get scores summed.
        """
        # Fetch 2x limit from each source for better fusion coverage
        fetch_limit = limit * 2

        # Run both searches concurrently via the async engine
        vector_ranked = await self._vector_ranked(query, fetch_limit, filter_metadata)
        fulltext_ranked = await self._fulltext_ranked(query, fetch_limit, filter_metadata)

        # ── RRF Fusion ───────────────────────────────────────────────────────
        # score_map: chunk_id -> cumulative rrf score
        score_map: Dict[str, float] = {}
        # chunk_data: chunk_id -> _RankedChunk (keep first occurrence's data)
        chunk_data: Dict[str, _RankedChunk] = {}

        for ranked in vector_ranked:
            rrf_score = 1.0 / (rrf_k + ranked.rank)
            score_map[ranked.chunk_id] = score_map.get(ranked.chunk_id, 0.0) + rrf_score
            if ranked.chunk_id not in chunk_data:
                chunk_data[ranked.chunk_id] = ranked

        for ranked in fulltext_ranked:
            rrf_score = 1.0 / (rrf_k + ranked.rank)
            score_map[ranked.chunk_id] = score_map.get(ranked.chunk_id, 0.0) + rrf_score
            if ranked.chunk_id not in chunk_data:
                chunk_data[ranked.chunk_id] = ranked

        # Sort by RRF score descending, take top `limit`
        sorted_ids = sorted(score_map.keys(), key=lambda cid: score_map[cid], reverse=True)[:limit]

        return [
            SearchResultItem(
                chunk_id=chunk_data[cid].chunk_id,
                document_id=chunk_data[cid].document_id,
                chunk_index=chunk_data[cid].chunk_index,
                chunk_text=chunk_data[cid].chunk_text,
                score=round(score_map[cid], 6),
                title=chunk_data[cid].title,
                source_url=chunk_data[cid].source_url,
                metadata=chunk_data[cid].metadata,
            )
            for cid in sorted_ids
        ]

    # ── Internal: Ranked result fetchers ─────────────────────────────────────

    async def _vector_ranked(
        self,
        query: str,
        limit: int,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[_RankedChunk]:
        """Fetch vector search results as ranked chunks."""
        query_embedding = await self.embedding_service.generate_query_embedding(query)
        cosine_distance = DocumentChunk.embedding.cosine_distance(query_embedding)

        stmt = (
            select(
                DocumentChunk,
                Document.title,
                Document.source_url,
                Document.metadata_info,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.embedding.isnot(None))
            .order_by(cosine_distance.asc())
            .limit(limit)
        )

        stmt = self._apply_metadata_filter(stmt, filter_metadata)
        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            _RankedChunk(
                chunk_id=row[0].id,
                document_id=row[0].document_id,
                chunk_index=row[0].chunk_index,
                chunk_text=row[0].chunk_text,
                title=row[1],
                source_url=row[2],
                metadata=row[3] or {},
                rank=idx + 1,
            )
            for idx, row in enumerate(rows)
        ]

    async def _fulltext_ranked(
        self,
        query: str,
        limit: int,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[_RankedChunk]:
        """Fetch full-text search results as ranked chunks."""
        ts_query = func.plainto_tsquery("simple", query)
        rank_score = func.ts_rank_cd(DocumentChunk.search_vector, ts_query)

        stmt = (
            select(
                DocumentChunk,
                Document.title,
                Document.source_url,
                Document.metadata_info,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.search_vector.isnot(None))
            .where(DocumentChunk.search_vector.op("@@")(ts_query))
            .order_by(rank_score.desc())
            .limit(limit)
        )

        stmt = self._apply_metadata_filter(stmt, filter_metadata)
        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            _RankedChunk(
                chunk_id=row[0].id,
                document_id=row[0].document_id,
                chunk_index=row[0].chunk_index,
                chunk_text=row[0].chunk_text,
                title=row[1],
                source_url=row[2],
                metadata=row[3] or {},
                rank=idx + 1,
            )
            for idx, row in enumerate(rows)
        ]

    # ── Shared: Metadata filter ──────────────────────────────────────────────

    @staticmethod
    def _apply_metadata_filter(stmt, filter_metadata: Optional[Dict[str, Any]]):
        """Apply optional JSONB metadata key-value filters to a SELECT statement."""
        if filter_metadata:
            for key, val in filter_metadata.items():
                stmt = stmt.where(Document.metadata_info[key].astext == str(val))
        return stmt
