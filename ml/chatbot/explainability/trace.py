"""
Reasoning-trace + source-attribution helpers.

Builds the API-facing `reasoning_trace` + `sources` payloads from an
`AgentResponse`. Same role as the deterministic narrative generators
in the other ML packages — produce an interpretation that the backend
can persist into the `interpretation` column without an LLM call.

The chatbot is different in that its response *already* carries a
structured reasoning trace from the agents themselves. This module
adds shape conversion + a one-line summary string for the
`interpretation` column.
"""

from __future__ import annotations

from ml.chatbot.data.schema import AgentResponse


def trace_summary(response: AgentResponse, *, max_chars: int = 300) -> str:
    """One-line interpretation suitable for the persistence layer.

    Composes the agent name + first reasoning step + the number of
    sources cited. Always returns a non-empty string so the
    `interpretation` column never has to be NULL.
    """
    first_step = response.reasoning_trace[0] if response.reasoning_trace else "no reasoning recorded"
    n_sources = len(response.sources)
    n_tools = len(response.tool_calls)
    summary = (
        f"{response.agent_name}: {first_step} · "
        f"cited {n_sources} source(s), used {n_tools} tool(s)."
    )
    if len(summary) > max_chars:
        return summary[: max_chars - 1] + "…"
    return summary


def source_payload(response: AgentResponse) -> list[dict[str, object]]:
    """Translate the response's `sources` tuple into a JSON-friendly list.

    Shape matches what the backend translation layer maps to the API's
    `SourceReference[]`: `{"module", "reference_id", "summary", "rank",
    "score"}`. The `summary` is the first sentence of the chunk's
    content — same `_first_sentence` helper as the RAG responder uses.
    """
    out: list[dict[str, object]] = []
    for chunk in response.sources:
        summary = chunk.document.content
        for terminator in (". ", "! ", "? "):
            idx = summary.find(terminator)
            if 0 < idx <= 200:
                summary = summary[: idx + 1].strip()
                break
        else:
            summary = summary[:200]
        out.append(
            {
                "module": chunk.document.module,
                "reference_id": chunk.document.doc_id,
                "summary": summary,
                "rank": chunk.rank,
                "score": round(chunk.score, 4),
            }
        )
    return out


def tool_call_payload(response: AgentResponse) -> list[dict[str, object]]:
    """Translate `tool_calls` into a JSON-friendly list for the API."""
    return [
        {"name": tc.name, "arguments": dict(tc.arguments), "status": tc.status}
        for tc in response.tool_calls
    ]
