"""SHAP + deterministic narrative explainability for pricing recommendations."""

from ml.pricing.explainability.narrative import (
    PricingNarrative,
    render_narrative,
)
from ml.pricing.explainability.shap_adapter import (
    PricingSHAPAttribution,
    PricingSHAPExplainer,
)

__all__ = [
    "PricingNarrative",
    "PricingSHAPAttribution",
    "PricingSHAPExplainer",
    "render_narrative",
]
