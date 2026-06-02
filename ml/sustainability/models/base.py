"""
Uniform `ESGScorer` interface.

One ABC — matching recruitment's single `RankingModel` and forecasting's
single `ForecastModel` posture. ESG scoring has one role: given a
`CompanyProfile`, produce an `ESGScoreResult` (per-pillar scores + risk
level + per-label probabilities + top driving features). The ablation
harness in `evaluation.benchmark` treats every arm the same; the AS-004
campaign (TASK-017) will score them on identical splits.

`requires_training` lets unsupervised baselines (industry-mean, majority
label) skip the fit call without harness type checks. Carbon estimation
lives in its own module (`carbon.py`) because it's a regression task,
not a scoring task — same posture as pricing's two-ABC split
(`DemandModel` ≠ `PricingPolicy`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ml.sustainability.data.schema import (
        CompanyProfile,
        ESGObservation,
        ESGScoreResult,
    )


class ESGScorer(ABC):
    """Predicts per-pillar ESG scores + per-label probabilities."""

    requires_training: bool = True

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fit(self, observations: Sequence[ESGObservation]) -> ESGScorer:
        """Train on a list of historical observations. May be a no-op."""

    @abstractmethod
    def score(self, profile: CompanyProfile) -> ESGScoreResult:
        """Produce the structured score for a single company."""

    def score_proba(self, profile: CompanyProfile) -> np.ndarray:
        """Return per-label probabilities as a length-3 vector (E, S, G).

        Default implementation reads the `label_probabilities` dict from
        `score(profile)`; arms with a fast batched path can override.
        """
        result = self.score(profile)
        return np.array(
            [
                result.label_probabilities.get("env_strong", 0.5),
                result.label_probabilities.get("soc_strong", 0.5),
                result.label_probabilities.get("gov_strong", 0.5),
            ],
            dtype=np.float64,
        )
