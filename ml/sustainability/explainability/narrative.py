"""
Deterministic narrative generator for ESG score results.

Same role as the forecasting / pricing narrative adapters: produce a
plain-language interpretation that the backend can persist into the
`interpretation` column without an LLM call. The copilot
(`copilot/esg_copilot.py`) is the LLM-powered upgrade for the
executive-style briefing; this is the low-latency one used per request.
"""

from __future__ import annotations

from ml.sustainability.data.schema import ESGScoreResult


def narrate(result: ESGScoreResult) -> str:
    """Return a 1-3 sentence narrative summary of an ESG score result."""
    pillars = result.pillar_scores
    composite = pillars.composite

    if composite >= 75:
        framing = "strong overall"
    elif composite >= 55:
        framing = "above-average overall"
    elif composite >= 35:
        framing = "below-average overall"
    else:
        framing = "critically weak overall"

    lowest_pillar, lowest_value = min(
        (
            ("Environmental", pillars.environmental),
            ("Social", pillars.social),
            ("Governance", pillars.governance),
        ),
        key=lambda kv: kv[1],
    )

    top_features = result.top_features[:2] if result.top_features else ()
    drivers_text = ""
    if top_features:
        names = ", ".join(name for name, _ in top_features)
        drivers_text = f" Top contributing features: {names}."

    return (
        f"{result.company_name} ({result.industry}) shows a {framing} ESG "
        f"profile (composite {composite:.1f}, {result.risk_level} risk). "
        f"{lowest_pillar} is the weakest pillar at {lowest_value:.1f}.{drivers_text}"
    )
