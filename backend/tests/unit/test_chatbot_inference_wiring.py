"""Offline tests for the chatbot inference orchestrator.

Verifies the wiring (request translation → agent call → response
translation) for the model-backed endpoint without booting any
heavy ML backbone. We inject a hand-rolled BaseAgent stub;
`/executive-report` is closed-form and lives in the service layer.

Mirrors `test_sustainability_inference_wiring.py` (TASK-018) for the
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

pytest.importorskip("ml.chatbot.agents.base")

from ml.chatbot.agents.base import BaseAgent  # noqa: E402
from ml.chatbot.data.schema import (  # noqa: E402
    AgentResponse,
    Document,
    RetrievedChunk,
    ToolCall,
)
from src.services.chatbot.inference import (  # noqa: E402
    ChatbotInferenceClient,
    get_inference_client,
    reset_inference_client,
)


class StubAgent(BaseAgent):
    """Sentinel agent: returns a fixed response and records the last
    Query so tests can verify translation."""

    def __init__(
        self,
        *,
        content: str = "Stub answer.",
        sources: tuple[RetrievedChunk, ...] = (),
        tool_calls: tuple[ToolCall, ...] = (),
        tokens_used: int = 7,
    ) -> None:
        self._content = content
        self._sources = sources
        self._tool_calls = tool_calls
        self._tokens = tokens_used
        self.last_query = None

    @property
    def name(self) -> str:
        return "StubAgent"

    def respond(self, query) -> AgentResponse:
        self.last_query = query
        return AgentResponse(
            query_id=query.query_id,
            content=self._content,
            reasoning_trace=("stub-step-1", "stub-step-2"),
            sources=self._sources,
            tool_calls=self._tool_calls,
            tokens_used=self._tokens,
            agent_name=self.name,
        )


def _chunk(doc_id: str, content: str = "x", *, rank: int = 0, score: float = 0.5):
    return RetrievedChunk(
        document=Document(doc_id=doc_id, title="t", content=content, module="general"),
        score=score,
        rank=rank,
    )


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_inference_client(None)
    yield
    reset_inference_client(None)


# ── respond ─────────────────────────────────────────────────────────


def test_respond_returns_agent_response_with_content():
    agent = StubAgent(content="Real-ML answer.", tokens_used=24)
    client = ChatbotInferenceClient(executor=agent)
    response = client.respond("How do I price my SKU?")
    assert response.content == "Real-ML answer."
    assert response.tokens_used == 24
    assert response.reasoning_trace == ("stub-step-1", "stub-step-2")


def test_respond_passes_text_to_agent_via_query():
    agent = StubAgent()
    client = ChatbotInferenceClient(executor=agent)
    user = uuid4()
    client.respond(
        "Question about ESG.",
        include_modules=("sustainability",),
        user_id=user,
    )
    assert agent.last_query is not None
    assert agent.last_query.text == "Question about ESG."
    assert agent.last_query.include_modules == ("sustainability",)
    assert agent.last_query.user_id == str(user)


def test_respond_with_no_modules_passes_empty_tuple():
    agent = StubAgent()
    client = ChatbotInferenceClient(executor=agent)
    client.respond("Hi")
    assert agent.last_query.include_modules == ()


def test_respond_uses_provided_query_id():
    agent = StubAgent()
    client = ChatbotInferenceClient(executor=agent)
    client.respond("Hi", query_id="explicit-qid")
    assert agent.last_query.query_id == "explicit-qid"


def test_respond_surfaces_sources_and_tool_calls():
    chunk = _chunk("d-1", "Hiring takes time.", rank=0, score=0.97)
    tool = ToolCall(name="rag_retrieve", arguments={"k": "3"}, status="completed")
    agent = StubAgent(sources=(chunk,), tool_calls=(tool,))
    client = ChatbotInferenceClient(executor=agent)
    response = client.respond("How long to hire?")
    assert len(response.sources) == 1
    assert response.sources[0].document.doc_id == "d-1"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "rag_retrieve"


def test_respond_to_query_dispatches_prebuilt_query():
    """The convenience overload accepts an `ml.chatbot.Query` directly."""
    from ml.chatbot.data.schema import Query

    agent = StubAgent()
    client = ChatbotInferenceClient(executor=agent)
    query = Query(query_id="q-fixed", text="explicit", include_modules=("pricing",))
    client.respond_to_query(query)
    assert agent.last_query is query


# ── source tracking + singleton ─────────────────────────────────────


def test_source_is_uninitialised_when_executor_injected():
    """Injection-path clients never run the registry/bootstrap loader."""
    client = ChatbotInferenceClient(executor=StubAgent())
    client.respond("anything")
    assert client.source == "uninitialised"


def test_get_inference_client_returns_same_singleton_per_process():
    a = get_inference_client()
    b = get_inference_client()
    assert a is b


def test_reset_inference_client_replaces_singleton():
    a = get_inference_client()
    reset_inference_client(None)
    b = get_inference_client()
    assert a is not b


def test_get_inference_client_starts_uninitialised():
    """Singleton construction is cheap; source stays 'uninitialised'
    until respond() triggers lazy load."""
    client = get_inference_client()
    assert client.source == "uninitialised"


def test_reset_inference_client_with_explicit_replacement():
    """Passing an instance replaces the singleton with that exact instance."""
    replacement = ChatbotInferenceClient(executor=StubAgent(content="Custom."))
    reset_inference_client(replacement)
    assert get_inference_client() is replacement
    response = get_inference_client().respond("hi")
    assert response.content == "Custom."
