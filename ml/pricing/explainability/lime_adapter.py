"""
LIME adapter for the LightGBM demand model.

Provides a *second* post-hoc attribution view (the first is the
TreeExplainer-based `PricingSHAPExplainer` in `shap_adapter.py`).
The thesis claim is that LIME and SHAP, computed independently from
the same fitted model and asked the same question
("which features drove this single recommendation?"), give us
robustness-of-explanation evidence:

  • If the two agree on the top contributors and their signs, the
    explanation is more defensible.
  • If they disagree, that's flagged as an explainer-divergence
    surface for the user to interrogate.

LIME's core idea is different from SHAP's: it perturbs the input
locally, scores each perturbation with the real model, then fits a
sparse linear surrogate around the original point. The surrogate's
coefficients are the per-feature attributions returned here.

The heavy import (`lime.lime_tabular`) is lazy and inside
`_build_explainer` so this module imports cleanly without it.

Mirrors `ml.pricing.explainability.shap_adapter`:
  • LimeTabularExplainer fit against a small "training-like" sample
    of the engineered feature space
  • Feature-name list aligned with `features.structured.FEATURE_NAMES`
  • Single-prediction API (LIME's natural granularity)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from ml.pricing.features.structured import FEATURE_NAMES

if TYPE_CHECKING:
    from ml.pricing.models.demand import LightGBMDemandModel


@dataclass(frozen=True)
class PricingLIMEAttribution:
    """Per-row LIME attribution. `weights[i]` corresponds to
    `FEATURE_NAMES[i]` and is the coefficient of that feature in the
    local linear surrogate (positive = pushes demand up at this point,
    negative = pushes demand down). `intercept` is the surrogate's
    intercept term."""

    intercept: float
    weights: np.ndarray


class PricingLIMEExplainer:
    """Wraps a fitted `LightGBMDemandModel` with LIME attribution.

    LIME needs a "background" sample of the feature space to fit its
    perturbation distribution. We accept the sample at construction —
    the policy's `_build_bootstrap_policy` already builds an
    `(n_observations, n_features)` matrix during fit, so the same
    matrix can be reused without re-training.
    """

    def __init__(
        self,
        demand_model: LightGBMDemandModel,
        background: np.ndarray,
        *,
        num_samples: int = 500,
        num_features: int | None = None,
    ) -> None:
        self._demand = demand_model
        self._background = np.asarray(background, dtype=np.float64)
        self._num_samples = max(50, int(num_samples))
        # LIME's `num_features` selects the top-K most-attributing
        # features in the surrogate; default = all features so the
        # caller gets a dense vector and downstream code does its own
        # top-K selection.
        self._num_features = num_features if num_features is not None else len(FEATURE_NAMES)
        self._explainer: Any | None = None

    def explain(self, x: np.ndarray) -> PricingLIMEAttribution:
        """Explain a single feature row (shape `(n_features,)`).

        Returns a `PricingLIMEAttribution` with the surrogate's
        intercept + per-feature weights aligned with `FEATURE_NAMES`.
        """
        explainer = self._build_explainer()
        # LIME wants a `predict_fn(2d_array) → 1d_predictions` for a
        # regressor. The LightGBM booster's `.predict` already has
        # that shape.
        predict_fn = self._demand.model.predict
        exp = explainer.explain_instance(
            data_row=np.asarray(x, dtype=np.float64),
            predict_fn=predict_fn,
            num_features=self._num_features,
            num_samples=self._num_samples,
        )
        # `exp.as_map()` returns `{label: [(feature_idx, weight), ...]}`.
        # For a regressor the label is `1` (LIME wraps it consistently).
        label = next(iter(exp.as_map().keys()))
        weights = np.zeros(len(FEATURE_NAMES), dtype=np.float64)
        for idx, w in exp.as_map()[label]:
            if 0 <= int(idx) < len(FEATURE_NAMES):
                weights[int(idx)] = float(w)
        intercept = float(exp.intercept[label]) if hasattr(exp, "intercept") else 0.0
        return PricingLIMEAttribution(intercept=intercept, weights=weights)

    @property
    def feature_names(self) -> tuple[str, ...]:
        return FEATURE_NAMES

    def _build_explainer(self) -> Any:
        if self._explainer is None:
            try:
                from lime.lime_tabular import LimeTabularExplainer
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "PricingLIMEExplainer requires `lime` (in ml/requirements.txt)."
                ) from exc
            self._explainer = LimeTabularExplainer(
                training_data=self._background,
                feature_names=list(FEATURE_NAMES),
                mode="regression",
                discretize_continuous=False,
                # Deterministic perturbations so tests + the
                # frontend's "stable across page refresh" expectation
                # hold without freezing the model.
                random_state=42,
            )
        return self._explainer
