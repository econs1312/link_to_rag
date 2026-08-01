import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_db
from app.models.document import Document, IngestionStatus


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_ingest_and_job_status_flow():
    now = datetime.now(timezone.utc)
    # Mock Document model instance
    mock_doc = Document(
        id="test-job-uuid-1234",
        correlation_id="test-corr-uuid-5678",
        source_url="https://example.com/test-article",
        status=IngestionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )

    # Mock DB Session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            with patch("app.api.v1.ingest.get_redis_pool", side_effect=Exception("Redis offline mock")), \
                 patch("app.services.ingestion_pipeline.IngestionPipelineService.process_document", new_callable=AsyncMock):
                # 1. Post Ingestion
                payload = {
                    "url": "https://example.com/test-article",
                    "metadata": {"category": "technology", "tenant_id": "tenant-123"},
                }
                ingest_resp = await ac.post("/api/v1/ingest", json=payload)
                assert ingest_resp.status_code == 202
                data = ingest_resp.json()
                assert "job_id" in data
                assert "correlation_id" in data

                # 2. Get Job Status
                job_id = data["job_id"]
                mock_doc.id = job_id
                status_resp = await ac.get(f"/api/v1/jobs/{job_id}")
                assert status_resp.status_code == 200
                status_data = status_resp.json()
                assert status_data["job_id"] == job_id
                assert status_data["source_url"] == "https://example.com/test-article"
    finally:
        app.dependency_overrides.clear()

