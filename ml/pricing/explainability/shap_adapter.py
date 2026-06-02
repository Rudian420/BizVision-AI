"""
SHAP adapter for the LightGBM demand model.

Provides post-hoc attribution for `LightGBMGridPolicy` and (by composition
through the elasticity backbone) `PPOPricingPolicy` (RC-003). Mirrors
`ml.recruitment.explainability.shap_adapter`:

  • TreeExplainer for exact, fast attribution
  • Feature-name list aligned with `features.structured.FEATURE_NAMES`
  • Single-prediction + batch APIs
  • A `BiasDecomposition`-style summary is *not* exposed here because
    pricing decisions don't carry a protected-attribute axis — RC-002 is
    recruitment-specific.

The heavy import (`shap`) is lazy and inside `_build_explainer` so this
module imports cleanly without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from ml.pricing.features.structured import FEATURE_NAMES

if TYPE_CHECKING:
    from ml.pricing.models.demand import LightGBMDemandModel


@dataclass(frozen=True)
class PricingSHAPAttribution:
    """Per-row attribution. `shap_values[i]` corresponds to `FEATURE_NAMES[i]`."""

    base_value: float
    shap_values: np.ndarray


class PricingSHAPExplainer:
    """Wraps a fitted `LightGBMDemandModel` with SHAP attribution."""

    def __init__(self, demand_model: LightGBMDemandModel) -> None:
        self._demand = demand_model
        self._explainer: Any | None = None

    def explain(self, x: np.ndarray) -> PricingSHAPAttribution:
        """Explain a single feature row (shape `(n_features,)`)."""
        explainer = self._build_explainer()
        raw = explainer.shap_values(x.reshape(1, -1))
        # shap returns either ndarray or list[ndarray]; standardise.
        values = raw[0] if isinstance(raw, list) else raw[0]
        base = float(
            explainer.expected_value[0]
            if isinstance(explainer.expected_value, (list, np.ndarray))
            else explainer.expected_value
        )
        return PricingSHAPAttribution(
            base_value=base,
            shap_values=np.asarray(values, dtype=np.float64),
        )

    def explain_batch(self, x: np.ndarray) -> np.ndarray:
        """Return an `(n_samples × n_features)` attribution matrix."""
        explainer = self._build_explainer()
        raw = explainer.shap_values(x)
        return np.asarray(raw[0] if isinstance(raw, list) else raw, dtype=np.float64)

    @property
    def feature_names(self) -> tuple[str, ...]:
        return FEATURE_NAMES

    def _build_explainer(self) -> Any:
        if self._explainer is None:
            try:
                import shap
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "PricingSHAPExplainer requires `shap` (in ml/requirements.txt)."
                ) from exc
            self._explainer = shap.TreeExplainer(self._demand.model)
        return self._explainer
