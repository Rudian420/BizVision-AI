"""
RAG-augmented response agent.

The wave-1 responder is *templated, not generative*: it cites the
top-k retrieved chunks verbatim and produces a deterministic answer
of the form:

    Based on the indexed business knowledge, the top relevant
    references for your question are:
      • [doc_id]: title — first 80 chars of content
      • ...

    Source-grounded summary: <first chunk's content, sentence-bounded>

This is intentional for wave 1 — the AS-005 benchmark measures
*retrieval* quality, not generation; coupling them would make the
benchmark hard to interpret. Wave 2 wraps the same retriever in an
LLM call via `ml.chatbot.copilot.chat_copilot.brief`.
"""

from __future__ import annotations

from ml.chatbot.agents.base import BaseAgent
from ml.chatbot.data.schema import AgentResponse, Query, ToolCall
from ml.chatbot.retrieval.rag import RagRetriever


def _first_sentence(text: str, *, max_chars: int = 220) -> str:
    """Return the first complete sentence (period/!/?) or up to `max_chars`."""
    for terminator in (". ", "! ", "? "):
        idx = text.find(terminator)
        if 0 < idx <= max_chars:
            return text[: idx + 1].strip()
    return text[:max_chars].strip()


class RagResponderAgent(BaseAgent):
    """Retrieval-augmented templated response generator."""

    def __init__(
        self,
        retriever: RagRetriever,
        *,
        top_k: int = 3,
        module_filter: str | None = None,
    ) -> None:
        if not retriever.is_indexed:
            raise ValueError(
                "retriever must be indexed before RagResponderAgent is used"
            )
        self._retriever = retriever
        self._top_k = top_k
        self._module_filter = module_filter

    @property
    def name(self) -> str:
        return f"RagResponder(k={self._top_k})"

    @property
    def retriever(self) -> RagRetriever:
        return self._retriever

    def respond(self, query: Query) -> AgentResponse:
        module_filter = (
            self._module_filter
            if self._module_filter is not None
            else (query.include_modules[0] if query.include_modules else None)
        )
        chunks = self._retriever.retrieve(
            query, top_k=self._top_k, module_filter=module_filter
        )

        if not chunks:
            return AgentResponse(
                query_id=query.query_id,
                content="I couldn't find relevant indexed knowledge for your question.",
                reasoning_trace=(
                    "Embedded query",
                    "Retrieved 0 chunks from the vector store",
                ),
                sources=(),
                tool_calls=(),
                tokens_used=0,
                agent_name=self.name,
            )

        bullets = "\n".join(
            f"  • [{c.document.doc_id}] {c.document.title} — "
            f"{_first_sentence(c.document.content, max_chars=140)}"
            for c in chunks
        )
        summary = _first_sentence(chunks[0].document.content)
        body = (
            "Based on the indexed business knowledge, the top relevant "
            f"references for your question are:\n{bullets}\n\n"
            f"Source-grounded summary: {summary}"
        )
        # Token estimate — bag-of-words approximation; harmless for thesis
        # reporting and a useful upper bound for backend budget tracking.
        tokens_used = max(1, len(body.split()))

        return AgentResponse(
            query_id=query.query_id,
            content=body,
            reasoning_trace=(
                f"Embedded query with {self._retriever.embedder.name}",
                f"Retrieved top-{self._top_k} chunks "
                + (f"filtered to module '{module_filter}'" if module_filter else "across all modules"),
                f"Composed templated answer citing {len(chunks)} source(s)",
            ),
            sources=chunks,
            tool_calls=(
                ToolCall(
                    name="rag_retrieve",
                    arguments={
                        "top_k": str(self._top_k),
                        "module_filter": module_filter or "(none)",
                    },
                    status="completed",
                ),
            ),
            tokens_used=tokens_used,
            agent_name=self.name,
        )
