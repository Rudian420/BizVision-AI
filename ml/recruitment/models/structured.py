"""
Structured ranker — XGBoost / LightGBM on tabular features.

EXP-REC-003. The structured features (`features/structured.py`) capture
years-of-experience, education level, skill overlap, location match —
strong signal for "hireable / not" classification but blind to free-text
semantics. The composite system fixes that by ensembling this model with
the SBERT cosine signal (`EnsembleRanker`).

XGBoost is preferred because:
  • `TreeExplainer` (SHAP) gives exact attributions in O(n_features × n_trees) —
    fast enough to explain every prediction in production.
  • Native missingness handling — no imputation pipeline for missing
    parser fields.
  • CUDA `device` parameter accepts the same `tree_method` config we'd use
    on CPU — single config path.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from ml.recruitment.features.structured import FEATURE_NAMES, build_feature_matrix
from ml.recruitment.models.base import RankingModel, ScoreDetail

if TYPE_CHECKING:
    from ml.recruitment.data.schema import CandidateRecord, JobDescription, Pair

# Sensible defaults; ablation runs override via `__init__(**params)`.
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 400,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "min_child_weight": 3,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "eval_metric": "auc",
    "objective": "binary:logistic",
    "tree_method": "hist",
}


class XGBoostRanker(RankingModel):
    requires_training = True

    def __init__(self, **params: Any) -> None:
        self._params = {**DEFAULT_PARAMS, **params}
        self._model: Any | None = None

    @property
    def name(self) -> str:
        return "structured-xgboost"

    @property
    def model(self) -> Any:
        """Expose the fitted booster for SHAP / LIME adapters."""
        if self._model is None:
            raise RuntimeError("XGBoostRanker not fit yet.")
        return self._model

    @property
    def feature_names(self) -> tuple[str, ...]:
        return FEATURE_NAMES

    def fit(self, pairs: Sequence[Pair]) -> XGBoostRanker:
        from xgboost import XGBClassifier

        x = np.vstack([build_feature_matrix(p.job, [p.candidate])[0] for p in pairs])
        y = np.asarray([p.label for p in pairs], dtype=np.int32)
        self._model = XGBClassifier(**self._params)
        self._model.fit(x, y, verbose=False)
        return self

    def score(self, jd: JobDescription, candidates: Sequence[CandidateRecord]) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("XGBoostRanker.score called before fit().")
        if len(candidates) == 0:
            return np.empty(0, dtype=np.float32)
        x = build_feature_matrix(jd, candidates)
        proba = self._model.predict_proba(x)[:, 1]
        return proba.astype(np.float32, copy=False)

    def score_with_detail(
        self, jd: JobDescription, candidates: Sequence[CandidateRecord]
    ) -> list[ScoreDetail]:
        scores = self.score(jd, candidates)
        x = build_feature_matrix(jd, candidates)
        out: list[ScoreDetail] = []
        for c, s, row in zip(candidates, scores, x, strict=False):
            features = {name: float(v) for name, v in zip(FEATURE_NAMES, row, strict=False)}
            out.append(ScoreDetail(candidate_id=c.candidate_id, score=float(s), features=features))
        return out
