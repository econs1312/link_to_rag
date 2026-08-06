"""Tests for TraceIDMiddleware — X-Trace-ID generation and propagation."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_trace_id_generated_when_absent():
    """Request without X-Trace-ID header → middleware generates a valid UUIDv4 and returns it."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200

        trace_id = resp.headers.get("X-Trace-ID")
        assert trace_id is not None, "X-Trace-ID header must be present in response"

        # Validate it's a proper UUID
        parsed = uuid.UUID(trace_id, version=4)
        assert str(parsed) == trace_id


@pytest.mark.asyncio
async def test_trace_id_propagated_when_provided():
    """Request with X-Trace-ID header → middleware echoes the same value."""
    custom_trace_id = "aaaaaaaa-bbbb-4ccc-dddd-eeeeeeeeeeee"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health", headers={"X-Trace-ID": custom_trace_id})
        assert resp.status_code == 200

        returned_trace_id = resp.headers.get("X-Trace-ID")
        assert returned_trace_id == custom_trace_id


@pytest.mark.asyncio
async def test_trace_id_unique_across_requests():
    """Each request without an explicit X-Trace-ID gets a different generated ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp1 = await ac.get("/health")
        resp2 = await ac.get("/health")

        trace1 = resp1.headers.get("X-Trace-ID")
        trace2 = resp2.headers.get("X-Trace-ID")

        assert trace1 is not None
        assert trace2 is not None
        assert trace1 != trace2, "Each request must receive a unique trace ID"
