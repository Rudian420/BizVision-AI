"""
Ensemble ranker — weighted convex combination of two ranking models.

EXP-REC-004 (target system): SBERT semantic cosine + XGBoost probability.

We deliberately *do not* stack via a meta-learner here. Reasons:

  1. **Interpretability.** A linear blend lets SHAP attributions on each
     leg be combined into a single attribution: `att_total = w_a·att_a +
     w_b·att_b`. A meta-learner would require explaining the meta-learner.
  2. **Calibration.** Both legs are pre-normalised to [0, 1] via min-max
     on the held-out validation pool; this keeps the weight `w` a true
     dial between "more semantic" and "more structured".
  3. **Cold-start.** A meta-learner needs O(few hundred) supervised
     observations to fit; SMEs may have ≤50 hires/year. The weighted
     blend works with no labels (default 0.6 / 0.4) and is fine-tunable
     when data arrives.

`find_optimal_weight` performs a 1-D grid search over `w` to maximise
NDCG@k on a validation split — used by the training pipeline once labels
are available.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from ml.recruitment.models.base import RankingModel, ScoreDetail

if TYPE_CHECKING:
    from ml.recruitment.data.schema import CandidateRecord, JobDescription, Pair


class EnsembleRanker(RankingModel):
    requires_training = True

    def __init__(
        self,
        left: RankingModel,
        right: RankingModel,
        *,
        weight: float = 0.6,
        left_label: str = "semantic",
        right_label: str = "structured",
    ) -> None:
        if not 0.0 <= weight <= 1.0:
            raise ValueError("ensemble weight must be in [0, 1]")
        self._left = left
        self._right = right
        self._w = float(weight)
        self._left_label = left_label
        self._right_label = right_label

    @property
    def name(self) -> str:
        return f"ensemble({self._left.name}@{self._w:.2f}+{self._right.name})"

    @property
    def weight(self) -> float:
        return self._w

    def set_weight(self, w: float) -> None:
        if not 0.0 <= w <= 1.0:
            raise ValueError("weight must be in [0, 1]")
        self._w = float(w)

    def fit(self, pairs: Sequence[Pair]) -> EnsembleRanker:
        # Train each leg independently — they share data but not gradients.
        if self._left.requires_training:
            self._left.fit(pairs)
        if self._right.requires_training:
            self._right.fit(pairs)
        return self

    def score(self, jd: JobDescription, candidates: Sequence[CandidateRecord]) -> np.ndarray:
        if len(candidates) == 0:
            return np.empty(0, dtype=np.float32)
        sl = _normalise(self._left.score(jd, candidates))
        sr = _normalise(self._right.score(jd, candidates))
        return (self._w * sl + (1.0 - self._w) * sr).astype(np.float32, copy=False)

    def score_with_detail(
        self, jd: JobDescription, candidates: Sequence[CandidateRecord]
    ) -> list[ScoreDetail]:
        sl = _normalise(self._left.score(jd, candidates))
        sr = _normalise(self._right.score(jd, candidates))
        composite = self._w * sl + (1.0 - self._w) * sr
        out: list[ScoreDetail] = []
        for i, c in enumerate(candidates):
            out.append(
                ScoreDetail(
                    candidate_id=c.candidate_id,
                    score=float(composite[i]),
                    sub_scores={
                        self._left_label: float(sl[i]),
                        self._right_label: float(sr[i]),
                    },
                )
            )
        return out


# ── helpers ───────────────────────────────────────────────────────────


def _normalise(arr: np.ndarray) -> np.ndarray:
    """Min-max to [0, 1]; degenerate batches (all identical) → 0.5."""
    if arr.size == 0:
        return arr
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-9:
        return np.full_like(arr, 0.5, dtype=np.float32)
    return ((arr - lo) / (hi - lo)).astype(np.float32, copy=False)


def find_optimal_weight(
    ensemble: EnsembleRanker,
    pairs: Sequence[Pair],
    *,
    grid: Sequence[float] = (0.3, 0.4, 0.5, 0.6, 0.7),
    k: int = 5,
) -> tuple[float, dict[float, float]]:
    """Grid-search the ensemble weight on a held-out set.

    Returns ``(best_weight, scores_by_weight)`` — caller is responsible for
    re-fitting the ensemble at the chosen weight (or simply calling
    ``ensemble.set_weight(best)``)."""
    from ml.recruitment.evaluation.metrics import ndcg_at_k

    # Group pairs by JD so NDCG is evaluated per-query then averaged.
    groups: dict[str, list] = {}
    for p in pairs:
        groups.setdefault(p.job.job_id, []).append(p)

    scores_by_weight: dict[float, float] = {}
    for w in grid:
        ensemble.set_weight(float(w))
        per_query: list[float] = []
        for _jd_id, items in groups.items():
            jd = items[0].job
            cands = [it.candidate for it in items]
            labels = np.asarray([it.label for it in items], dtype=np.int32)
            scores = ensemble.score(jd, cands)
            per_query.append(ndcg_at_k(labels, scores, k=k))
        scores_by_weight[float(w)] = float(np.mean(per_query)) if per_query else 0.0
    best = max(scores_by_weight, key=scores_by_weight.get)
    return best, scores_by_weight
