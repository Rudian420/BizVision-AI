"""Offline tests for the chatbot API↔ml.chatbot translation layer.

Pure-Python — no DB, no FastAPI fixtures. Verifies that the schema
translation builds Query dataclasses cleanly, projects
RetrievedChunks into SourceReferences with first-sentence summaries,
and chunks streaming content faithfully.

Mirrors `test_sustainability_translation.py` (TASK-018) for the
chatbot equivalent (TASK-020).
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

pytest.importorskip("ml.chatbot.data.schema")

from ml.chatbot.data.schema import (  # noqa: E402
    AgentResponse,
    Document,
    RetrievedChunk,
    ToolCall,
)
from src.api.v1.schemas.chatbot import ChatMessageRequest  # noqa: E402
from src.services.chatbot.ml_translation import (  # noqa: E402
    api_query_from_message,
    api_query_from_ws_payload,
    chunk_content_for_streaming,
    ml_response_to_api,
    ml_response_to_sources_payload,
    ml_response_to_ws_chunks,
)


def _agent_response(
    *,
    content: str = "Stub response content.",
    sources: tuple[RetrievedChunk, ...] = (),
    tool_calls: tuple[ToolCall, ...] = (),
    tokens_used: int = 12,
) -> AgentResponse:
    return AgentResponse(
        query_id="q-1",
        content=content,
        reasoning_trace=("step 1", "step 2"),
        sources=sources,
        tool_calls=tool_calls,
        tokens_used=tokens_used,
        agent_name="StubAgent",
    )


def _chunk(doc_id: str, content: str, *, rank: int = 0, score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        document=Document(doc_id=doc_id, title="t", content=content, module="general"),
        score=score,
        rank=rank,
    )


# ── api_query_from_message ─────────────────────────────────────────


def test_query_from_message_passes_through_text_and_modules():
    request = ChatMessageRequest(
        content="How do I price my product?", include_modules=["pricing", "general"]
    )
    user = uuid4()
    query = api_query_from_message(request, user_id=user)
    assert query.text == "How do I price my product?"
    assert query.include_modules == ("pricing", "general")
    assert query.user_id == str(user)
    assert query.query_id  # generated UUID hex


def test_query_from_message_uses_provided_query_id():
    request = ChatMessageRequest(content="x")
    query = api_query_from_message(request, query_id="custom-id")
    assert query.query_id == "custom-id"


def test_query_from_message_handles_empty_modules():
    request = ChatMessageRequest(content="x")
    query = api_query_from_message(request)
    assert query.include_modules == ()


def test_query_from_ws_payload_handles_list_modules():
    user = uuid4()
    query = api_query_from_ws_payload(
        "raw content", include_modules=["pricing"], user_id=user
    )
    assert query.text == "raw content"
    assert query.include_modules == ("pricing",)
    assert query.user_id == str(user)


def test_query_from_ws_payload_handles_none_user():
    query = api_query_from_ws_payload("hi")
    assert query.user_id is None
    assert query.include_modules == ()


# ── ml_response_to_api ─────────────────────────────────────────────


def test_response_to_api_preserves_content_and_reasoning_trace():
    response = _agent_response(content="Hello executive.", tokens_used=42)
    conv_id = uuid4()
    api = ml_response_to_api(response=response, conversation_id=conv_id)
    assert api.conversation_id == conv_id
    assert api.content == "Hello executive."
    assert api.reasoning_trace == ["step 1", "step 2"]
    assert api.tokens_used == 42


def test_response_to_api_uses_provided_message_id():
    response = _agent_response()
    conv_id = uuid4()
    msg_id = uuid4()
    api = ml_response_to_api(
        response=response, conversation_id=conv_id, message_id=msg_id
    )
    assert api.message_id == msg_id


def test_response_to_api_chunks_summarize_to_first_sentence():
    """Source summary uses the chunk content's first sentence (period
    terminator), capped at 200 chars."""
    chunk = _chunk(
        "d-1",
        "Hiring takes time. Plenty of words come after the period.",
    )
    response = _agent_response(sources=(chunk,))
    api = ml_response_to_api(response=response, conversation_id=uuid4())
    assert len(api.sources) == 1
    assert api.sources[0].module == "general"
    assert api.sources[0].reference_id == "d-1"
    assert api.sources[0].summary == "Hiring takes time."


def test_response_to_api_falls_back_to_200_chars_when_no_terminator():
    content = "a" * 250  # no sentence terminator
    chunk = _chunk("d-2", content)
    response = _agent_response(sources=(chunk,))
    api = ml_response_to_api(response=response, conversation_id=uuid4())
    assert len(api.sources[0].summary) == 200


def test_response_to_api_empty_sources_yields_empty_list():
    response = _agent_response()
    api = ml_response_to_api(response=response, conversation_id=uuid4())
    assert api.sources == []


# ── ml_response_to_sources_payload ─────────────────────────────────


def test_sources_payload_includes_rank_and_score():
    chunk = _chunk("d-1", "Hiring takes time. More text.", rank=2, score=0.873_45)
    response = _agent_response(sources=(chunk,))
    payload = ml_response_to_sources_payload(response)
    assert payload[0]["module"] == "general"
    assert payload[0]["reference_id"] == "d-1"
    assert payload[0]["summary"] == "Hiring takes time."
    assert payload[0]["rank"] == 2
    assert payload[0]["score"] == pytest.approx(0.8735, rel=1e-3)


def test_sources_payload_round_trips_through_jsonb_friendly_types():
    """Each entry must be a plain dict (not a dataclass) so the
    ChatbotMessage.sources JSONB column can serialise it."""
    chunk = _chunk("d-1", "Hello.")
    response = _agent_response(sources=(chunk,))
    payload = ml_response_to_sources_payload(response)
    assert isinstance(payload, list)
    assert isinstance(payload[0], dict)


# ── chunk_content_for_streaming ────────────────────────────────────


def test_chunk_content_for_streaming_preserves_trailing_spaces():
    """Every token except the last carries a trailing space — matches
    the mock branch's `token + ' '` shape so clients can concatenate
    without adding spaces themselves."""
    tokens = chunk_content_for_streaming("hello world friend")
    assert tokens == ["hello ", "world ", "friend"]


def test_chunk_content_for_streaming_empty_returns_empty_list():
    assert chunk_content_for_streaming("") == []


def test_chunk_content_for_streaming_single_token():
    """One-token content emits exactly one chunk, no trailing space."""
    assert chunk_content_for_streaming("one") == ["one"]


# ── ml_response_to_ws_chunks ───────────────────────────────────────


def test_ws_chunks_order_tool_then_tokens_then_complete():
    tc = ToolCall(name="rag_retrieve", arguments={"k": "3"}, status="completed")
    response = _agent_response(content="one two", tool_calls=(tc,))
    chunks = ml_response_to_ws_chunks(response)
    types = [c["type"] for c in chunks]
    assert types == ["tool_call", "token", "token", "complete"]
    # tool_call chunk carries the tool name
    assert chunks[0]["tool"] == "rag_retrieve"
    # final complete carries the full content + reasoning trace
    assert chunks[-1]["content"] == "one two"
    assert chunks[-1]["reasoning_trace"] == ["step 1", "step 2"]


def test_ws_chunks_empty_content_skips_token_emission():
    response = _agent_response(content="")
    chunks = ml_response_to_ws_chunks(response)
    types = [c["type"] for c in chunks]
    assert types == ["complete"]
