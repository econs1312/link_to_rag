"""Tests for DELETE /api/v1/documents/{id} and DELETE /api/v1/jobs/{id} endpoints."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_db
from app.models.document import Document, IngestionStatus


def _make_mock_doc(doc_id: str = "doc-uuid-1234") -> Document:
    now = datetime.now(timezone.utc)
    return Document(
        id=doc_id,
        correlation_id="corr-uuid-5678",
        source_url="https://example.com/test-article",
        status=IngestionStatus.COMPLETED,
        title="Test Article",
        author="Test Author",
        created_at=now,
        updated_at=now,
    )


def _mock_session(doc: Document | None = None) -> AsyncMock:
    """Create a mock async DB session with configurable document lookup."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    session.execute = AsyncMock(return_value=mock_result)
    return session


# ─── DELETE /api/v1/documents/{document_id} ─────────────────────────────────


@pytest.mark.asyncio
async def test_delete_document_success():
    """DELETE existing document → 200 with success message."""
    mock_doc = _make_mock_doc("doc-to-delete")
    session = _mock_session(mock_doc)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/v1/documents/doc-to-delete")
            assert resp.status_code == 200
            data = resp.json()
            assert data["deleted_id"] == "doc-to-delete"
            assert "deleted" in data["message"].lower()
            session.delete.assert_called_once_with(mock_doc)
            session.commit.assert_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_document_not_found():
    """DELETE non-existent document → 404."""
    session = _mock_session(doc=None)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/v1/documents/nonexistent-id")
            assert resp.status_code == 404
            data = resp.json()
            assert data["error"] is True
            assert "not found" in data["message"].lower()
    finally:
        app.dependency_overrides.clear()


# ─── DELETE /api/v1/jobs/{job_id} ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_job_success():
    """DELETE existing job → 200 with success message."""
    mock_doc = _make_mock_doc("job-to-delete")
    session = _mock_session(mock_doc)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/v1/jobs/job-to-delete")
            assert resp.status_code == 200
            data = resp.json()
            assert data["deleted_id"] == "job-to-delete"
            assert "deleted" in data["message"].lower()
            session.delete.assert_called_once_with(mock_doc)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_job_not_found():
    """DELETE non-existent job → 404."""
    session = _mock_session(doc=None)

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/v1/jobs/nonexistent-job-id")
            assert resp.status_code == 404
            data = resp.json()
            assert data["error"] is True
            assert "not found" in data["message"].lower()
    finally:
        app.dependency_overrides.clear()
