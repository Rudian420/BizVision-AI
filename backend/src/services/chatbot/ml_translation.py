"""
API ↔ `ml.chatbot` schema translation.

Pure Python, zero heavy ML imports — same architectural seam as
`backend/src/services/sustainability/ml_translation.py` (TASK-018) and
`backend/src/services/pricing/ml_translation.py` (TASK-011). The
backend speaks **Pydantic schemas** (`src.api.v1.schemas.chatbot`);
the ML package speaks **frozen dataclasses**
(`ml.chatbot.data.schema`); this module is the *only* place that
knows about both.

Two of the three chatbot endpoints are model-backed when
`CHATBOT_USE_REAL_ML=True`:
  • `/message` (REST)         → `AgentExecutor.respond(Query)`
  • WS `stream_response`      → same executor + chunked streaming

`/executive-report` stays closed-form / static-catalog in wave 1 —
same posture as pricing's `/elasticity`, forecasting's `/sensitivity`,
and sustainability's `/benchmarks/{industry}`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.api.v1.schemas.chatbot import (
    ChatMessageRequest,
    ChatMessageResponse,
    SourceReference,
)

if TYPE_CHECKING:
    # Imports for type-checker only — keeps this module importable in the
    # backend's lean runtime image where ml/ may not be on sys.path.
    from ml.chatbot.data.schema import (
        AgentResponse as MLAgentResponse,
    )
    from ml.chatbot.data.schema import (
        Query as MLQuery,
    )


# ── API → ml.chatbot ────────────────────────────────────────────────


def api_query_from_message(
    request: ChatMessageRequest,
    *,
    query_id: str | None = None,
    user_id: UUID | None = None,
) -> MLQuery:
    """Build an `ml.chatbot.Query` from a `/message` REST request."""
    from ml.chatbot.data.schema import Query as MLQueryImpl

    return MLQueryImpl(
        query_id=query_id or uuid4().hex,
        text=request.content,
        include_modules=tuple(request.include_modules),
        user_id=str(user_id) if user_id is not None else None,
    )


def api_query_from_ws_payload(
    content: str,
    *,
    include_modules: tuple[str, ...] | list[str] | None = None,
    user_id: UUID | None = None,
    query_id: str | None = None,
) -> MLQuery:
    """Build an `ml.chatbot.Query` from the WS handler's parsed payload.

    The WS path doesn't carry a Pydantic request model — the inbound
    JSON is parsed inline, so this helper takes the raw fields. Same
    output shape as `api_query_from_message`.
    """
    from ml.chatbot.data.schema import Query as MLQueryImpl

    return MLQueryImpl(
        query_id=query_id or uuid4().hex,
        text=content,
        include_modules=tuple(include_modules or ()),
        user_id=str(user_id) if user_id is not None else None,
    )


# ── ml.chatbot → API ────────────────────────────────────────────────


def _ml_chunk_to_source_reference(chunk) -> SourceReference:
    """Translate a single `RetrievedChunk` to an API `SourceReference`.

    The chunk's first sentence (or its first 200 chars) is the
    surfaced `summary` — same heuristic as `ml.chatbot.explainability.
    trace.source_payload`.
    """
    content = chunk.document.content
    summary = content
    for terminator in (". ", "! ", "? "):
        idx = summary.find(terminator)
        if 0 < idx <= 200:
            summary = summary[: idx + 1].strip()
            break
    else:
        summary = summary[:200]
    return SourceReference(
        module=chunk.document.module,
        reference_id=chunk.document.doc_id,
        summary=summary,
    )


def ml_response_to_api(
    *,
    response: MLAgentResponse,
    conversation_id: UUID,
    message_id: UUID | None = None,
    created_at=None,
) -> ChatMessageResponse:
    """Wrap a single `ml.chatbot.AgentResponse` into the `/message`
    API response.

    `created_at` is forwarded if provided so the caller can control
    timestamping; otherwise the Pydantic default fires. `message_id`
    is supplied by the service layer so the persisted row's primary
    key matches the response's `message_id`.
    """
    from datetime import datetime, timezone as _tz

    sources = [_ml_chunk_to_source_reference(c) for c in response.sources]
    return ChatMessageResponse(
        conversation_id=conversation_id,
        message_id=message_id or uuid4(),
        content=response.content,
        created_at=created_at or datetime.now(_tz.utc),
        reasoning_trace=list(response.reasoning_trace),
        sources=sources,
        tokens_used=response.tokens_used,
    )


def ml_response_to_sources_payload(response: MLAgentResponse) -> list[dict]:
    """Translate the response's `sources` tuple into the dict shape
    the persistence layer's `ChatbotMessage.sources` JSONB column
    expects — same fields as the API's `SourceReference` (plus rank +
    score for downstream re-rendering)."""
    out: list[dict] = []
    for chunk in response.sources:
        ref = _ml_chunk_to_source_reference(chunk)
        out.append(
            {
                "module": ref.module,
                "reference_id": ref.reference_id,
                "summary": ref.summary,
                "rank": chunk.rank,
                "score": round(float(chunk.score), 4),
            }
        )
    return out


# ── WS streaming helpers ───────────────────────────────────────────


def chunk_content_for_streaming(content: str) -> list[str]:
    """Split a finished assistant `content` into space-separated tokens
    for the WS typewriter effect.

    Trailing space is preserved on every token (mirrors the mock
    path's `token + " "` shape) so the client can concatenate without
    extra logic. Empty content yields an empty list — the WS handler
    will skip emission and go straight to `complete`.
    """
    if not content:
        return []
    parts = content.split(" ")
    # Re-attach the trailing space so the client's concat is faithful.
    return [(p + " ") if i < len(parts) - 1 else p for i, p in enumerate(parts)]


def ml_response_to_ws_chunks(response: MLAgentResponse) -> list[dict]:
    """Build the full sequence of WS chunks for one agent response.

    Order:
      1. tool_call chunks (one per agent tool call)
      2. token chunks (space-split content)
      3. complete chunk (full response payload)

    The chatbot service's WS handler iterates this list and writes
    each chunk to the socket — same shape the mock branch emits, so
    the client doesn't need to detect which branch ran.
    """
    chunks: list[dict] = []
    for tc in response.tool_calls:
        chunks.append(
            {
                "type": "tool_call",
                "tool": tc.name,
                "status": tc.status,
            }
        )
    for tok in chunk_content_for_streaming(response.content):
        chunks.append(
            {
                "type": "token",
                "content": tok,
                "agent_step": "reasoning",
            }
        )
    chunks.append(
        {
            "type": "complete",
            "content": response.content,
            "reasoning_trace": list(response.reasoning_trace),
            "sources": ml_response_to_sources_payload(response),
        }
    )
    return chunks
