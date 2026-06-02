"""
Deterministic narrative generator — turns a `PricingSHAPAttribution`
(or a bare `PriceRecommendation`) into a sentence-level rationale a
merchant can read in plain English.

We use a template rather than an LLM here because the *narrative for an
explanation* must be reproducible (no temperature). The pricing
*copilot* (separate module) uses an LLM for the conversational layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from ml.pricing.features.structured import FEATURE_NAMES

if TYPE_CHECKING:
    from ml.pricing.data.schema import PriceRecommendation
    from ml.pricing.explainability.shap_adapter import PricingSHAPAttribution


# Plain-language phrasing keyed by feature name.
_PHRASE: dict[str, tuple[str, str]] = {
    # (positive_phrase, negative_phrase)
    "price": (
        "Higher price boosted predicted revenue",
        "Higher price suppressed predicted revenue",
    ),
    "price_log": ("Multiplicative scale of price helped", "Multiplicative scale of price hurt"),
    "competitor_price_gap": (
        "Premium over competitors was tolerated",
        "Premium over competitors hurt demand",
    ),
    "competitor_price_log": (
        "Competitor price level was favourable",
        "Competitor price level was unfavourable",
    ),
    "season_sin": (
        "Seasonal cycle (sine) was favourable",
        "Seasonal cycle (sine) was unfavourable",
    ),
    "season_cos": (
        "Seasonal cycle (cosine) was favourable",
        "Seasonal cycle (cosine) was unfavourable",
    ),
    "promotion_flag": ("Promotion lifted predicted demand", "No promotion in effect"),
    "has_competitor": (
        "Competitor data was available",
        "No competitor data — used neutral imputation",
    ),
}


@dataclass(frozen=True)
class PricingNarrative:
    headline: str
    bullets: tuple[str, ...]
    recommended_price: float
    expected_revenue: float
    sub_scores: dict[str, float] = field(default_factory=dict)


def render_narrative(
    *,
    recommendation: PriceRecommendation,
    attribution: PricingSHAPAttribution | None = None,
    top_k: int = 4,
) -> PricingNarrative:
    """Render a SHAP-aware narrative; falls back to the policy rationale
    when no attribution is supplied (e.g. PPO without SHAP)."""
    bullets: list[str] = []

    if attribution is not None:
        abs_shap = np.abs(attribution.shap_values)
        order = np.argsort(-abs_shap)[: max(1, top_k)]
        for i in order:
            idx = int(i)
            if idx >= len(FEATURE_NAMES):
                continue
            feat = FEATURE_NAMES[idx]
            sval = float(attribution.shap_values[idx])
            sign = "+" if sval >= 0 else "−"
            pos_phrase, neg_phrase = _PHRASE.get(feat, (feat, feat))
            phrase = pos_phrase if sval >= 0 else neg_phrase
            bullets.append(f"{sign} {phrase} (Δ {sval:+.3f})")
        headline = (
            f"Recommended price: {recommendation.recommended_price:.2f} — "
            f"expected revenue {recommendation.expected_revenue:,.0f}."
        )
    else:
        headline = recommendation.rationale or (
            f"Recommended price: {recommendation.recommended_price:.2f}."
        )

    return PricingNarrative(
        headline=headline,
        bullets=tuple(bullets),
        recommended_price=float(recommendation.recommended_price),
        expected_revenue=float(recommendation.expected_revenue),
        sub_scores=dict(recommendation.sub_scores),
    )
