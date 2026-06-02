"""
Template-driven narrative generator.

Converts a `SHAPAttribution` (and optionally an ensemble `ScoreDetail`)
into plain-English rationale that a non-technical recruiter can read.
We deliberately use a deterministic template rather than an LLM here:
the narrative for an *explanation* must be reproducible. The recruiter
*copilot* (separate module) uses an LLM for the conversational layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from ml.recruitment.features.structured import FEATURE_NAMES

if TYPE_CHECKING:
    from ml.recruitment.explainability.shap_adapter import SHAPAttribution
    from ml.recruitment.models.base import ScoreDetail


# Human-readable phrasing keyed by feature name.
_PHRASE: dict[str, tuple[str, str]] = {
    # (positive_phrase, negative_phrase)
    "years_experience": ("Strong relevant tenure", "Limited tenure for this role"),
    "education_rank": ("Education exceeds requirement", "Education below typical bar"),
    "required_skill_overlap": ("Covers most required skills", "Misses several required skills"),
    "preferred_skill_overlap": ("Covers preferred skills too", "Few preferred skills"),
    "total_skill_count": ("Broad skill profile", "Narrow skill profile"),
    "min_years_met": ("Meets the minimum tenure bar", "Below the minimum tenure bar"),
    "location_match": ("Location-compatible", "Location concern"),
    "has_education": ("Education is documented", "Education not detected"),
}


@dataclass(frozen=True)
class NarrativeExplanation:
    candidate_id: str
    one_liner: str
    bullets: tuple[str, ...]
    composite_score: float
    sub_scores: dict[str, float] = field(default_factory=dict)


def render_narrative(
    attribution: SHAPAttribution,
    *,
    top_k: int = 4,
    composite_score: float | None = None,
    score_detail: ScoreDetail | None = None,
) -> NarrativeExplanation:
    """Render a SHAP attribution as a recruiter-facing summary.

    The top-k features by absolute SHAP value become bullets; the largest
    positive driver also seeds a one-line headline.
    """
    abs_shap = np.abs(attribution.shap_values)
    order = np.argsort(-abs_shap)[: max(1, top_k)]

    bullets: list[str] = []
    top_positive_phrase: str | None = None

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
        if sval > 0 and top_positive_phrase is None:
            top_positive_phrase = pos_phrase

    score = (
        composite_score
        if composite_score is not None
        else (attribution.base_value + float(attribution.shap_values.sum()))
    )
    one_liner = f"{top_positive_phrase or 'Mixed profile'} — composite score {score:.2f}."

    return NarrativeExplanation(
        candidate_id=attribution.candidate_id,
        one_liner=one_liner,
        bullets=tuple(bullets),
        composite_score=float(score),
        sub_scores=dict(score_detail.sub_scores) if score_detail else {},
    )
