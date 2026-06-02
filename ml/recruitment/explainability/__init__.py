"""SHAP + LIME + narrative explainability for recruitment rankings."""

from ml.recruitment.explainability.lime_adapter import LIMERecruitmentExplainer
from ml.recruitment.explainability.narrative import (
    NarrativeExplanation,
    render_narrative,
)
from ml.recruitment.explainability.shap_adapter import SHAPRecruitmentExplainer

__all__ = [
    "LIMERecruitmentExplainer",
    "NarrativeExplanation",
    "SHAPRecruitmentExplainer",
    "render_narrative",
]
