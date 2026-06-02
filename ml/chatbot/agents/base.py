"""
Uniform `BaseAgent` interface.

One ABC matching the rest of the package's single-role posture
(`ESGScorer`, `ForecastModel`, `RankingModel`). Wave 1 ships:

  • `KeywordRouterAgent` — classifies which BizVision module a query
    targets (deterministic keyword rules, no learned parameters).
  • `RagResponderAgent` — RAG-augmented response generator (uses the
    retriever's top-k chunks + a deterministic templated answer).

The wave-2 LangGraph multi-agent system (ML-011) plugs in behind this
same ABC — different `respond()` implementation, same `AgentResponse`
shape, no harness changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ml.chatbot.data.schema import AgentResponse, Query


class BaseAgent(ABC):
    """Produces an `AgentResponse` for a single query."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def respond(self, query: Query) -> AgentResponse:
        """Return a structured response for a query.

        Implementations may consult a retriever, a tool registry, or
        an LLM — the contract is just the output shape.
        """
