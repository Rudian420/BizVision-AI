"""
Shared pytest fixtures.

`client` boots the real ASGI app through its lifespan (DB table creation,
Redis connect, model-registry warm-up) and yields an httpx AsyncClient. It
therefore requires Postgres + Redis to be reachable — these tests are marked
`integration` and run in CI where service containers are provided.
"""

from __future__ import annotations

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def client():
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
def unique_email() -> str:
    from uuid import uuid4

    return f"user-{uuid4().hex[:10]}@bizvision.test"
