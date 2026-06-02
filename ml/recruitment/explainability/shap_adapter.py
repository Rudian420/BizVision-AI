"""
SHAP adapter for the structured leg of the recruitment ensemble.

Why "adapter" not "engine": the shared engine in `ml.shared.explainability`
is module-agnostic. Here we specialise it for the structured XGBoost
ranker by (a) providing the canonical feature names from
`features/structured.py`, (b) integrating attributions back into the
ensemble's composite score, and (c) producing the SHAP-attributed bias
decomposition described in RC-002 — the novel contribution of the
recruitment thesis chapter.

The SHAP-attributed bias decomposition works as follows:
    1. Run SHAP on the structured ranker.
    2. Stratify the test set by the protected attribute (e.g. gender).
    3. Compute the mean SHAP value per feature per group.
    4. The *difference* in mean SHAP per feature between the favoured
       and unfavoured group attributes the demographic-parity gap to
       individual features.

This identifies *which features in the model drive demographic
unfairness* — actionable signal that group-level metrics (DPD, EOD)
cannot supply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from ml.recruitment.features.structured import FEATURE_NAMES

if TYPE_CHECKING:
    from ml.recruitment.models.structured import XGBoostRanker


@dataclass(frozen=True)
class SHAPAttribution:
    """Per-candidate SHAP attribution.

    `shap_values` is aligned with `FEATURE_NAMES`; positive = pushed the
    score toward "hire", negative = pushed toward "no hire".
    """

    candidate_id: str
    base_value: float
    shap_values: np.ndarray  # shape (n_features,)


@dataclass
class BiasDecomposition:
    """Novel contribution (RC-002): per-feature attribution of the
    demographic-parity gap. `gap[i]` is the difference
    (mean SHAP, favoured group) − (mean SHAP, unfavoured group)
    for feature `i`."""

    protected_attribute: str
    feature_names: tuple[str, ...]
    gap: np.ndarray
    favoured_group: str
    unfavoured_group: str
    per_group_mean_shap: dict[str, np.ndarray] = field(default_factory=dict)


class SHAPRecruitmentExplainer:
    """Wraps the structured ranker with SHAP explanations."""

    def __init__(self, ranker: XGBoostRanker) -> None:
        self._ranker = ranker
        self._explainer: Any | None = None

    # ── single-prediction explanation ───────────────────────────────
    def explain(self, x: np.ndarray, candidate_id: str = "") -> SHAPAttribution:
        """Explain a single candidate feature vector (length = len(FEATURE_NAMES))."""
        explainer = self._build_explainer()
        # TreeExplainer for binary classifier → list[ndarray] of length 2 with
        # values for class 0 / 1 (older shap versions). Newer returns ndarray
        # of shape (n, n_features) on the positive-class output directly.
        raw = explainer.shap_values(x.reshape(1, -1))
        shap_values = raw[1][0] if isinstance(raw, list) else raw[0]
        base_value = float(
            explainer.expected_value[1]
            if isinstance(explainer.expected_value, (list, np.ndarray))
            else explainer.expected_value
        )
        return SHAPAttribution(
            candidate_id=candidate_id,
            base_value=base_value,
            shap_values=np.asarray(shap_values, dtype=np.float64),
        )

    # ── batch explanation ────────────────────────────────────────────
    def explain_batch(self, x: np.ndarray) -> np.ndarray:
        """Return a (n_samples × n_features) SHAP matrix."""
        explainer = self._build_explainer()
        raw = explainer.shap_values(x)
        return np.asarray(raw[1] if isinstance(raw, list) else raw, dtype=np.float64)

    # ── NOVEL: SHAP-attributed bias decomposition (RC-002) ──────────
    def bias_decomposition(
        self,
        x: np.ndarray,
        protected_values: np.ndarray,
        attribute_name: str,
    ) -> BiasDecomposition:
        """Decompose group-level prediction-rate gap into per-feature attributions.

        `protected_values` is a 1-D string array aligned with `x` rows.
        Categories with the highest and lowest mean SHAP sum are taken as
        the favoured / unfavoured groups (so the method works with any
        cardinality, not just binary attributes)."""
        shap_matrix = self.explain_batch(x)
        groups = np.unique(protected_values)

        per_group_mean: dict[str, np.ndarray] = {
            g: shap_matrix[protected_values == g].mean(axis=0) for g in groups
        }
        per_group_score = {g: float(v.sum()) for g, v in per_group_mean.items()}

        favoured = max(per_group_score, key=per_group_score.get)
        unfavoured = min(per_group_score, key=per_group_score.get)
        gap = per_group_mean[favoured] - per_group_mean[unfavoured]

        return BiasDecomposition(
            protected_attribute=attribute_name,
            feature_names=FEATURE_NAMES,
            gap=gap,
            favoured_group=favoured,
            unfavoured_group=unfavoured,
            per_group_mean_shap=per_group_mean,
        )

    # ── internals ────────────────────────────────────────────────────
    def _build_explainer(self) -> Any:
        if self._explainer is None:
            try:
                import shap
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "SHAPRecruitmentExplainer requires `shap`. "
                    "Install via `pip install shap` (already in ml/requirements.txt)."
                ) from exc
            # TreeExplainer is exact + fast for XGBoost/LightGBM.
            self._explainer = shap.TreeExplainer(self._ranker.model)
        return self._explainer
