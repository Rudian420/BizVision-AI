"""
ESG copilot — structured LLM I/O for the sustainability advisor.

Mirrors `ml.forecasting.copilot.forecast_copilot` and
`ml.pricing.copilot.pricing_copilot`. Returns a dataclass — same
posture: the LLM is asked for a *structured* JSON answer, parsed into
a frozen dataclass, and any failure (timeout / parse error / no API
key) falls back to a deterministic stub so the backend never 500s on a
copilot call.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from ml.sustainability.data.schema import ESGScoreResult


@dataclass(frozen=True)
class ESGCopilotBriefing:
    """Structured executive briefing on an ESG assessment."""

    headline: str
    key_findings: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    regulatory_flags: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


_FALLBACK_BRIEFING = ESGCopilotBriefing(
    headline="ESG profile within industry norms — incremental improvements available.",
    key_findings=(
        "Per-pillar scores roughly track industry median",
        "No critical-risk flags triggered",
    ),
    risks=(
        "Scope 3 supply-chain emissions exposure",
        "Governance disclosure gaps for SMEs",
    ),
    recommended_actions=(
        "Publish a DEI transparency report (high-impact / low effort)",
        "Procure renewable energy contracts for Scope 2 reduction",
        "Add independent board members for governance uplift",
    ),
    regulatory_flags=(),
    metadata={"source": "stub"},
)


def _build_prompt(result: ESGScoreResult) -> str:
    """Compose a deterministic prompt — no embedded user content."""
    p = result.pillar_scores
    return "\n".join(
        [
            "You are an executive ESG analyst.",
            f"Company: {result.company_name} ({result.industry})",
            f"Composite score: {p.composite:.1f} / 100",
            f"Sub-scores: E={p.environmental:.1f}, S={p.social:.1f}, G={p.governance:.1f}",
            f"Risk level: {result.risk_level}",
            f"Industry percentile: {result.industry_percentile:.1f}",
            "Return JSON with keys: headline (str), key_findings (str[]),",
            "risks (str[]), recommended_actions (str[]),",
            "regulatory_flags (str[]). Keep each field concise.",
        ]
    )


def brief(
    result: ESGScoreResult,
    *,
    client_factory=None,
) -> ESGCopilotBriefing:
    """Return a structured executive briefing for `result`.

    `client_factory` lets tests inject a stub Anthropic / OpenAI client.
    In production it lazy-imports `anthropic` if `ANTHROPIC_API_KEY` is
    set; otherwise returns the deterministic fallback.
    """
    if client_factory is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return _FALLBACK_BRIEFING
        try:  # pragma: no cover - optional dep
            from anthropic import Anthropic  # type: ignore[import-not-found]

            client_factory = lambda: Anthropic()  # noqa: E731
        except ImportError:
            return _FALLBACK_BRIEFING

    prompt = _build_prompt(result)
    try:
        client = client_factory()
        response = client.messages.create(  # type: ignore[union-attr]
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        body = response.content[0].text  # type: ignore[index, union-attr]
        data = json.loads(body)
        return ESGCopilotBriefing(
            headline=str(data.get("headline", _FALLBACK_BRIEFING.headline)),
            key_findings=tuple(data.get("key_findings", _FALLBACK_BRIEFING.key_findings)),
            risks=tuple(data.get("risks", _FALLBACK_BRIEFING.risks)),
            recommended_actions=tuple(
                data.get(
                    "recommended_actions", _FALLBACK_BRIEFING.recommended_actions
                )
            ),
            regulatory_flags=tuple(
                data.get("regulatory_flags", _FALLBACK_BRIEFING.regulatory_flags)
            ),
            metadata={"source": "llm", "model": "claude-haiku-4-5"},
        )
    except Exception:  # noqa: BLE001 - copilot must never crash the request
        return _FALLBACK_BRIEFING
