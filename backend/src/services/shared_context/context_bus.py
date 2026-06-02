"""
BizVision AI — Shared Context Bus

The cross-module intelligence backbone. When any module completes an
analysis it publishes a typed signal here; other modules (and the
executive chatbot) subscribe to enrich their own reasoning.

Transport is Redis pub/sub plus a capped per-user "recent signals" list
so the frontend and chatbot can pull the latest cross-module state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.core.logging import get_logger
from src.core.redis import redis_client

logger = get_logger(__name__)

_CHANNEL = "bizvision:context"
_RECENT_PREFIX = "context:recent:"  # per-user capped list
_MAX_RECENT = 50


class SharedContextBus:
    """Static facade — modules publish/consume cross-domain signals."""

    @classmethod
    async def publish(
        cls,
        event_type: str,
        payload: dict[str, Any],
        user_id: str,
    ) -> str:
        """Publish a cross-module signal. Returns the generated signal id.

        Designed to be safe to run as a FastAPI background task: failures
        are logged, never raised, so a context-bus hiccup can't break the
        primary response.
        """
        signal_id = str(uuid4())
        envelope = {
            "signal_id": signal_id,
            "event_type": event_type,
            "user_id": user_id,
            "payload": payload,
            "emitted_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await redis_client.publish(_CHANNEL, envelope)
            key = f"{_RECENT_PREFIX}{user_id}"
            await redis_client.client.lpush(key, json.dumps(envelope, default=str))
            await redis_client.client.ltrim(key, 0, _MAX_RECENT - 1)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Context bus publish failed ({}): {}", event_type, exc)
        return signal_id

    @classmethod
    async def recent_signals(cls, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent cross-module signals for a user."""
        try:
            key = f"{_RECENT_PREFIX}{user_id}"
            raw = await redis_client.client.lrange(key, 0, max(0, limit - 1))
            return [json.loads(item) for item in raw]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Context bus read failed: {}", exc)
            return []
