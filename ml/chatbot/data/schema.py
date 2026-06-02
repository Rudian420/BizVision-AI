"""
Chatbot data schemas.

Pure dataclasses — no heavy imports. Mirrors `ml.sustainability.data.schema`
and the other module schemas so the cross-module pattern stays
recognisable: every package's `data` sub-module holds frozen
dataclasses; loaders produce a `*Corpus` container; downstream code
consumes these without dragging in numpy / torch at import time.

The shape mirrors the API contract
(`src.api.v1.schemas.chatbot`) one-to-one so the backend translation
layer is a thin field rename — same posture as forecasting (TASK-016)
and sustainability (TASK-018).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    """One indexed document chunk — the unit of retrieval.

    `module` lets the router classify which BizVision module the chunk
    relates to (recruitment / pricing / forecasting / sustainability /
    general); the retriever returns chunks regardless, the agent uses
    `module` for tool-routing.
    """

    doc_id: str
    title: str
    content: str
    module: str = "general"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Corpus:
    """A complete document collection — what `embed_corpus` consumes."""

    documents: tuple[Document, ...]

    def __len__(self) -> int:
        return len(self.documents)

    def by_module(self, module: str) -> tuple[Document, ...]:
        return tuple(d for d in self.documents if d.module == module)


@dataclass(frozen=True)
class Query:
    """One user question to the chatbot — the retrieval input."""

    query_id: str
    text: str
    include_modules: tuple[str, ...] = ()
    user_id: str | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    """One scored chunk returned by the retriever."""

    document: Document
    score: float
    rank: int


@dataclass(frozen=True)
class ToolCall:
    """One typed tool invocation in an agent's reasoning trace."""

    name: str
    arguments: dict[str, str] = field(default_factory=dict)
    status: str = "completed"  # "completed" | "failed" | "skipped"


@dataclass(frozen=True)
class AgentResponse:
    """Structured output of a `BaseAgent.respond` call.

    Mirrors what the backend translation layer wraps into the
    `/chatbot/message` Pydantic response — same posture as the other
    module result dataclasses (ForecastResult, ESGScoreResult, etc.).
    """

    query_id: str
    content: str
    reasoning_trace: tuple[str, ...] = ()
    sources: tuple[RetrievedChunk, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    tokens_used: int = 0
    agent_name: str = ""


@dataclass(frozen=True)
class GoldenExample:
    """One labeled (query, expected-doc-ids, expected-module) example
    used by the benchmark harness — see `evaluation/benchmark.py`."""

    query: Query
    relevant_doc_ids: tuple[str, ...]
    expected_module: str
    expected_keywords: tuple[str, ...] = ()
