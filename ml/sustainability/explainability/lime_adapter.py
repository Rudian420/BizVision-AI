"""
LIME adapter for the multi-label ESG classifier.

Mirrors `ml.pricing.explainability.lime_adapter` (TASK-044): we
already have a linear-SHAP closed-form path
(`shap_adapter.shap_values_for_pillar`); LIME gives us a *second,
independent* explainer to render side-by-side.

Why bother when SHAP is already closed-form for a linear model?
- For a *linear* logistic head, SHAP and LIME *should* largely agree
  because the local surrogate LIME fits is itself linear, so it
  converges to roughly `weights · (x_perturbed - x_anchor)` — but
  the perturbation distribution + the sampling of the surrogate
  produce small disagreements that are themselves interesting
  (sensitivity to perturbation scale, robustness of the headline
  driver).
- When (not if) the sustainability arm grows a non-linear classifier
  (gradient-boosted chain), the LIME path is the *only* model-
  agnostic explainer we have ready — so it's important to keep the
  surface stable before the model gets fancier.

The heavy import (`lime.lime_tabular`) is lazy and inside
`_build_explainer` so this module imports cleanly without it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from ml.sustainability.features.structured import FEATURE_NAMES, featurize_batch

if TYPE_CHECKING:
    from ml.sustainability.data.schema import CompanyProfile
    from ml.sustainability.models.multilabel import LinearLogisticMultiLabel


@dataclass(frozen=True)
class SustainabilityLIMEAttribution:
    """Per-row LIME attribution. `weights[i]` corresponds to
    `FEATURE_NAMES[i]` and is the coefficient of that feature in the
    local linear surrogate around the model's prediction on the
    environmental head (the same head SHAP uses today)."""

    intercept: float
    weights: np.ndarray


class SustainabilityLIMEExplainer:
    """Wraps a fitted `LinearLogisticMultiLabel` with LIME attribution.

    LIME needs a "background" sample of the feature space to fit its
    perturbation distribution. The caller passes the same background
    used for the SHAP adapter — typically a slice of the training
    pool — so the two explainers see the same reference distribution.

    All featurisation + standardisation runs through the model's own
    `_standardise()` so weights live in the standardised feature space
    (the same space the linear-SHAP closed form operates in).
    """

    def __init__(
        self,
        model: LinearLogisticMultiLabel,
        background: Sequence[CompanyProfile],
        *,
        pillar: str = "environmental",
        num_samples: int = 500,
        num_features: int | None = None,
    ) -> None:
        if pillar not in {"environmental", "social", "governance"}:
            raise ValueError(f"unknown pillar: {pillar!r}")
        self._model = model
        self._background_std = self._standardised(background)
        self._pillar_idx = {"environmental": 0, "social": 1, "governance": 2}[pillar]
        self._num_samples = max(50, int(num_samples))
        self._num_features = num_features if num_features is not None else len(FEATURE_NAMES)
        self._explainer: Any | None = None

    def explain(self, profile: CompanyProfile) -> SustainabilityLIMEAttribution:
        """Explain the model's prediction for one company on the chosen pillar.

        Returns a `SustainabilityLIMEAttribution` whose `weights` array
        is aligned with `FEATURE_NAMES`.
        """
        explainer = self._build_explainer()
        x_raw = featurize_batch([profile])[0]
        x_std = self._model._standardise(x_raw[np.newaxis, :])[0]
        exp = explainer.explain_instance(
            data_row=x_std,
            predict_fn=self._predict_fn,
            num_features=self._num_features,
            num_samples=self._num_samples,
        )
        label = next(iter(exp.as_map().keys()))
        weights = np.zeros(len(FEATURE_NAMES), dtype=np.float64)
        for idx, w in exp.as_map()[label]:
            if 0 <= int(idx) < len(FEATURE_NAMES):
                weights[int(idx)] = float(w)
        intercept = float(exp.intercept[label]) if hasattr(exp, "intercept") else 0.0
        return SustainabilityLIMEAttribution(intercept=intercept, weights=weights)

    @property
    def feature_names(self) -> tuple[str, ...]:
        return FEATURE_NAMES

    # ── internals ───────────────────────────────────────────────────
    def _standardised(self, profiles: Sequence[CompanyProfile]) -> np.ndarray:
        if not profiles:
            return np.zeros((1, len(FEATURE_NAMES)), dtype=np.float64)
        raw = featurize_batch(list(profiles))
        return self._model._standardise(raw)

    def _predict_fn(self, X_std: np.ndarray) -> np.ndarray:
        """LIME calls `predict_fn(perturbed_inputs)` with a 2-D batch
        and expects 1-D regression-style predictions. We feed the
        standardised perturbations straight into the chosen pillar's
        head, returning the sigmoid prob — same scalar the closed-form
        SHAP path attributes against."""
        w, b = self._model._heads[self._pillar_idx]
        logits = X_std @ w + b
        # numerically stable sigmoid
        return np.where(
            logits >= 0,
            1.0 / (1.0 + np.exp(-logits)),
            np.exp(logits) / (1.0 + np.exp(logits)),
        )

    def _build_explainer(self) -> Any:
        if self._explainer is None:
            try:
                from lime.lime_tabular import LimeTabularExplainer
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "SustainabilityLIMEExplainer requires `lime` (in ml/requirements.txt)."
                ) from exc
            self._explainer = LimeTabularExplainer(
                training_data=self._background_std,
                feature_names=list(FEATURE_NAMES),
                mode="regression",
                discretize_continuous=False,
                random_state=42,
            )
        return self._explainer


def top_k_lime_features(
    weights: dict[str, float], k: int = 3
) -> tuple[tuple[str, float], ...]:
    """Return the top-k features by absolute LIME weight magnitude.

    Same signature as `shap_adapter.top_k_shap_features` so the
    sustainability inference client can pivot between explainers
    without touching call sites."""
    items = sorted(weights.items(), key=lambda kv: -abs(kv[1]))
    return tuple(items[:k])
