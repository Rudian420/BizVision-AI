"""
Forecast copilot — structured LLM I/O for the executive briefing.

Mirrors `ml.pricing.copilot.pricing_copilot` and
`ml.recruitment.copilot.recruiter_copilot`. Returns a dataclass — same
posture: the LLM is asked for a *structured* JSON answer, parsed into
a frozen dataclass, and any failure (timeout / parse error / no API
key) falls back to a deterministic stub so the backend never 500s on a
copilot call.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from ml.forecasting.data.schema import ForecastResult


@dataclass(frozen=True)
class CopilotBriefing:
    """Structured executive briefing on a forecast."""

    headline: str
    drivers: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


_FALLBACK_BRIEFING = CopilotBriefing(
    headline="Forecast indicates steady upward trajectory under base assumptions.",
    drivers=(
        "Underlying linear trend",
        "Weekly + yearly seasonal cycle",
    ),
    risks=(
        "Tail uncertainty grows with horizon",
        "Model assumes stable seasonality",
    ),
    recommended_actions=(
        "Re-check forecast monthly against rolling-origin backtest",
        "Stress-test the bear scenario against working-capital plans",
    ),
    metadata={"source": "stub"},
)


def _build_prompt(result: ForecastResult, mape: float | None) -> str:
    """Compose a deterministic prompt — no embedded user content."""
    mape_line = f"Backtest MAPE: {mape:.3f}\n" if mape is not None else ""
    lines = [
        "You are an executive forecasting analyst.",
        f"Model: {result.model_name}",
        f"Horizon: {result.horizon_days} days",
        f"End value: {result.end_value:,.2f}",
        f"Cumulative: {result.cumulative_value:,.2f}",
        mape_line,
        "Return JSON with keys: headline (str), drivers (str[]),",
        "risks (str[]), recommended_actions (str[]). Keep each",
        "field concise and concrete.",
    ]
    return "\n".join(lines)


def brief(
    result: ForecastResult,
    mape: float | None = None,
    *,
    client_factory=None,
) -> CopilotBriefing:
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

    prompt = _build_prompt(result, mape)
    try:
        client = client_factory()
        response = client.messages.create(  # type: ignore[union-attr]
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        body = response.content[0].text  # type: ignore[index, union-attr]
        data = json.loads(body)
        return CopilotBriefing(
            headline=str(data.get("headline", _FALLBACK_BRIEFING.headline)),
            drivers=tuple(data.get("drivers", _FALLBACK_BRIEFING.drivers)),
            risks=tuple(data.get("risks", _FALLBACK_BRIEFING.risks)),
            recommended_actions=tuple(
                data.get("recommended_actions", _FALLBACK_BRIEFING.recommended_actions)
            ),
            metadata={"source": "llm", "model": "claude-haiku-4-5"},
        )
    except Exception:  # noqa: BLE001 - copilot must never crash the request
        return _FALLBACK_BRIEFING
