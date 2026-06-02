"""
BizVision AI — Async Redis Client

Thin async wrapper around redis.asyncio providing a single shared
connection pool for: caching, refresh-token storage, rate limiting,
and the Shared Context Bus (pub/sub).

The client is lazily initialised on application startup (see lifespan
in main.py) and gracefully closed on shutdown.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from src.core.config import settings


class RedisClient:
    """Lazily-initialised async Redis facade with JSON helpers."""

    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    # ── Lifecycle ──────────────────────────────────────────────────
    async def initialize(self) -> None:
        """Create the connection pool. Safe to call multiple times."""
        if self._client is None:
            self._client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                health_check_interval=30,
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError(
                "Redis client not initialised. Call redis_client.initialize() first."
            )
        return self._client

    # ── Health ─────────────────────────────────────────────────────
    async def ping(self) -> bool:
        return bool(await self.client.ping())

    # ── Key/Value (string) ─────────────────────────────────────────
    async def get(self, key: str) -> str | None:
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        await self.client.set(key, value, ex=ttl_seconds)

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return await self.client.delete(*keys)

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(key))

    # ── JSON convenience helpers ───────────────────────────────────
    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        return json.loads(raw) if raw is not None else None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        await self.set(key, json.dumps(value, default=str), ttl_seconds=ttl_seconds)

    # ── Pub/Sub (Shared Context Bus) ───────────────────────────────
    async def publish(self, channel: str, message: Any) -> int:
        payload = json.dumps(message, default=str)
        return await self.client.publish(channel, payload)


# Module-level singleton imported across the app.
redis_client = RedisClient()
