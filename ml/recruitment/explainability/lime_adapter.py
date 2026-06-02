"""
LIME adapter — local model-agnostic explanations.

We pair LIME with SHAP rather than replacing one with the other (ADR-009):
LIME's local linear approximation produces human-readable rules
("years_experience > 5 AND required_skill_overlap > 0.6 → +0.31"),
while SHAP gives globally-consistent attributions. Both are surfaced in
the recruiter copilot output.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from ml.recruitment.features.structured import FEATURE_NAMES

if TYPE_CHECKING:
    from ml.recruitment.models.structured import XGBoostRanker


@dataclass(frozen=True)
class LIMERule:
    """A single LIME-discovered rule: ``feature condition → weight``."""

    condition: str
    weight: float


@dataclass(frozen=True)
class LIMEExplanation:
    candidate_id: str
    predicted_proba: float
    rules: tuple[LIMERule, ...]


class LIMERecruitmentExplainer:
    def __init__(
        self,
        ranker: XGBoostRanker,
        training_features: np.ndarray,
        feature_names: Sequence[str] = FEATURE_NAMES,
        class_names: Sequence[str] = ("not_hired", "hired"),
    ) -> None:
        self._ranker = ranker
        self._training = training_features
        self._feature_names = list(feature_names)
        self._class_names = list(class_names)
        self._explainer: Any | None = None

    def explain(
        self, x: np.ndarray, candidate_id: str = "", num_features: int = 5
    ) -> LIMEExplanation:
        explainer = self._build_explainer()
        proba_fn = self._ranker.model.predict_proba
        exp = explainer.explain_instance(
            data_row=x,
            predict_fn=proba_fn,
            num_features=num_features,
        )
        # LIME's `.as_list()` returns [(rule_text, weight), ...] for the positive class.
        rules = tuple(LIMERule(condition=str(r), weight=float(w)) for r, w in exp.as_list())
        proba = float(proba_fn(x.reshape(1, -1))[0, 1])
        return LIMEExplanation(candidate_id=candidate_id, predicted_proba=proba, rules=rules)

    def _build_explainer(self) -> Any:
        if self._explainer is None:
            try:
                from lime.lime_tabular import LimeTabularExplainer
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "LIMERecruitmentExplainer requires `lime` (in ml/requirements.txt)."
                ) from exc
            self._explainer = LimeTabularExplainer(
                training_data=self._training,
                feature_names=self._feature_names,
                class_names=self._class_names,
                mode="classification",
                discretize_continuous=True,
            )
        return self._explainer
