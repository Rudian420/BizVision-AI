"""
Chat copilot — structured LLM I/O for the executive advisor flow.

Mirrors `ml.sustainability.copilot.esg_copilot` and the other module
copilots. Returns a dataclass — the LLM is asked for a *structured*
JSON answer, parsed into a frozen dataclass, and any failure
(timeout / parse error / no API key) falls back to a deterministic
stub so the backend never 500s on a copilot call.

In wave 1 the copilot is *optional* — the `RagResponderAgent` already
produces a valid `AgentResponse` without it. Wave 2 (LangGraph
multi-agent) wraps the responder in this copilot for a fluent
narrative; the structured response shape doesn't change.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from ml.chatbot.data.schema import AgentResponse


@dataclass(frozen=True)
class ChatBriefing:
    """Structured executive briefing for a chatbot response."""

    headline: str
    key_points: tuple[str, ...] = ()
    follow_up_questions: tuple[str, ...] = ()
    cited_sources: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


_FALLBACK_BRIEFING = ChatBriefing(
    headline="Based on indexed business knowledge, the agent surfaced relevant references.",
    key_points=(
        "Top-ranked source is most likely to address the question",
        "Cross-reference with module-specific tools for live data",
    ),
    follow_up_questions=(
        "Would you like the most recent data for this module?",
        "Should I expand to adjacent modules?",
    ),
    cited_sources=(),
    metadata={"source": "stub"},
)


def _build_prompt(response: AgentResponse) -> str:
    """Compose a deterministic prompt — no embedded user content."""
    source_lines = "\n".join(
        f"  [{c.document.doc_id}] {c.document.title}: {c.document.content[:200]}"
        for c in response.sources[:5]
    )
    return "\n".join(
        [
            "You are an executive business advisor with access to indexed knowledge.",
            f"Query ID: {response.query_id}",
            f"Agent: {response.agent_name}",
            f"Retrieved sources ({len(response.sources)}):",
            source_lines or "  (none)",
            "Return JSON with keys: headline (str), key_points (str[]),",
            "follow_up_questions (str[]), cited_sources (str[]).",
            "Keep each field concise and concrete.",
        ]
    )


def brief(
    response: AgentResponse,
    *,
    client_factory=None,
) -> ChatBriefing:
    """Return a structured executive briefing for `response`.

    `client_factory` lets tests inject a stub Anthropic / OpenAI
    client. In production it lazy-imports `anthropic` if
    `ANTHROPIC_API_KEY` is set; otherwise returns the deterministic
    fallback so the backend never depends on the LLM for correctness.
    """
    if client_factory is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return _FALLBACK_BRIEFING
        try:  # pragma: no cover - optional dep
            from anthropic import Anthropic  # type: ignore[import-not-found]

            client_factory = lambda: Anthropic()  # noqa: E731
        except ImportError:
            return _FALLBACK_BRIEFING

    prompt = _build_prompt(response)
    try:
        client = client_factory()
        completion = client.messages.create(  # type: ignore[union-attr]
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        body = completion.content[0].text  # type: ignore[index, union-attr]
        data = json.loads(body)
        return ChatBriefing(
            headline=str(data.get("headline", _FALLBACK_BRIEFING.headline)),
            key_points=tuple(data.get("key_points", _FALLBACK_BRIEFING.key_points)),
            follow_up_questions=tuple(
                data.get("follow_up_questions", _FALLBACK_BRIEFING.follow_up_questions)
            ),
            cited_sources=tuple(
                data.get(
                    "cited_sources",
                    tuple(c.document.doc_id for c in response.sources),
                )
            ),
            metadata={"source": "llm", "model": "claude-haiku-4-5"},
        )
    except Exception:  # noqa: BLE001 - copilot must never crash the request
        return _FALLBACK_BRIEFING
