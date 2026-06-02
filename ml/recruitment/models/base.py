"""
Unified ranking-model interface.

Every recruitment ranker — baseline, semantic, boosting, ensemble —
implements the same five-method contract:

    fit(pairs)         -> Self
    score(jd, cands)   -> ndarray[float, n_candidates]
    score_with_detail  -> list[ScoreDetail]   (optional richer output)
    name               -> short identifier
    requires_training  -> bool                (False for unsupervised baselines)

This uniform interface is the foundation for the benchmark harness, the
ablation matrix, the ensemble weighted-combiner, and the recruiter copilot
which all consume *any* `RankingModel` without case analysis.

Scores are *not* required to be probabilities — only that higher = more
relevant. Calibration is the caller's responsibility (see `evaluation`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ml.recruitment.data.schema import CandidateRecord, JobDescription, Pair


@dataclass(frozen=True)
class ScoreDetail:
    """Per-candidate score plus optional sub-scores / metadata.

    Used by the ensemble and the explainability adapter to attribute the
    composite score back to its semantic + structured components.
    """

    candidate_id: str
    score: float
    sub_scores: dict[str, float] = field(default_factory=dict)
    features: dict[str, float] = field(default_factory=dict)


class RankingModel(ABC):
    """Abstract recruitment ranker."""

    requires_training: bool = True

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fit(self, pairs: Sequence[Pair]) -> RankingModel:
        """Train on a list of (job, candidate, label) observations.

        Unsupervised baselines (RandomRanker, TFIDFRanker, SBERTRanker,
        BM25Ranker) still receive `fit` so the call site is uniform — they
        use the call to gather the text corpus for vocab fitting, but ignore
        the labels."""

    @abstractmethod
    def score(
        self,
        jd: JobDescription,
        candidates: Sequence[CandidateRecord],
    ) -> np.ndarray:
        """Return a 1-D array of relevance scores, one per candidate."""

    # Optional — default implementation derives a ScoreDetail per candidate
    # from `score`. Ensembles / structured rankers override to add sub-scores.
    def score_with_detail(
        self,
        jd: JobDescription,
        candidates: Sequence[CandidateRecord],
    ) -> list[ScoreDetail]:
        scores = self.score(jd, candidates)
        return [
            ScoreDetail(candidate_id=c.candidate_id, score=float(s))
            for c, s in zip(candidates, scores, strict=False)
        ]
