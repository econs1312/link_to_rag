from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.ingestion import SearchRequest, SearchResponse
from app.services.search import VectorSearchService

router = APIRouter()


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Execute hybrid vector and full-text search over ingested chunks",
)
async def search_chunks(
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    search_service = VectorSearchService(db)
    return await search_service.search(
        query=payload.query,
        limit=payload.limit,
        filter_metadata=payload.filter_metadata,
    )
