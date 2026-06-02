"""Health/readiness probes (requires DB + Redis via the app lifespan)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert "version" in body


async def test_ready(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["redis"] == "ok"


async def test_openapi_served(client):
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "BizVision AI"
