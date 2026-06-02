"""
Baseline ESG scorers.

  • `IndustryBaselineScorer` — predicts the per-pillar mean of the
    training rows in the *same industry*. Captures the obvious
    industry-conditional signal without learning any per-company
    structure.
  • `MajorityLabelScorer`    — predicts the majority class for each
    pillar globally. The honest "must beat random" floor.

Both are unsupervised (`requires_training = False`) but expose `fit`
for ablation-harness uniformity.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ml.sustainability.data.schema import (
    CompanyProfile,
    ESGObservation,
    ESGScoreResult,
    PillarScore,
)
from ml.sustainability.models.base import ESGScorer


def _risk_level(composite: float) -> str:
    if composite >= 75:
        return "low"
    if composite >= 55:
        return "medium"
    if composite >= 35:
        return "high"
    return "critical"


class IndustryBaselineScorer(ESGScorer):
    """Predicts per-industry mean pillar score + per-industry label rate."""

    requires_training = False

    def __init__(self) -> None:
        self._industry_means: dict[str, np.ndarray] = {}
        self._industry_labels: dict[str, np.ndarray] = {}
        self._global_mean: np.ndarray = np.array([0.5, 0.5, 0.5])
        self._global_label_rate: np.ndarray = np.array([0.5, 0.5, 0.5])

    @property
    def name(self) -> str:
        return "IndustryBaseline"

    def fit(self, observations: Sequence[ESGObservation]) -> IndustryBaselineScorer:
        by_ind: dict[str, list[tuple[float, float, float]]] = {}
        labels_by_ind: dict[str, list[tuple[int, int, int]]] = {}
        for obs in observations:
            ind = obs.profile.industry
            e = _mean(obs.profile.environmental_indicators)
            s = _mean(obs.profile.social_indicators)
            g = _mean(obs.profile.governance_indicators)
            by_ind.setdefault(ind, []).append((e, s, g))
            labels_by_ind.setdefault(ind, []).append(
                (int(obs.label.env_strong), int(obs.label.soc_strong), int(obs.label.gov_strong))
            )

        for ind, rows in by_ind.items():
            self._industry_means[ind] = np.array(rows, dtype=np.float64).mean(axis=0)
        for ind, rows in labels_by_ind.items():
            self._industry_labels[ind] = np.array(rows, dtype=np.float64).mean(axis=0)

        if by_ind:
            all_rows = np.concatenate(
                [np.array(rows, dtype=np.float64) for rows in by_ind.values()],
                axis=0,
            )
            self._global_mean = all_rows.mean(axis=0)
            all_labels = np.concatenate(
                [np.array(rows, dtype=np.float64) for rows in labels_by_ind.values()],
                axis=0,
            )
            self._global_label_rate = all_labels.mean(axis=0)
        return self

    def score(self, profile: CompanyProfile) -> ESGScoreResult:
        means = self._industry_means.get(profile.industry, self._global_mean)
        labels = self._industry_labels.get(profile.industry, self._global_label_rate)
        pillars = PillarScore(
            environmental=float(np.clip(means[0] * 100.0, 0.0, 100.0)),
            social=float(np.clip(means[1] * 100.0, 0.0, 100.0)),
            governance=float(np.clip(means[2] * 100.0, 0.0, 100.0)),
        )
        return ESGScoreResult(
            company_name=profile.company_name,
            industry=profile.industry,
            pillar_scores=pillars,
            risk_level=_risk_level(pillars.composite),
            industry_percentile=round(min(99.0, pillars.composite + 5.0), 1),
            label_probabilities={
                "env_strong": float(labels[0]),
                "soc_strong": float(labels[1]),
                "gov_strong": float(labels[2]),
            },
            top_features=(
                ("industry_mean_E", float(means[0])),
                ("industry_mean_S", float(means[1])),
                ("industry_mean_G", float(means[2])),
            ),
            model_name=self.name,
            rationale=(
                f"Predicts {profile.industry}'s per-pillar means: "
                f"E={means[0]:.2f}, S={means[1]:.2f}, G={means[2]:.2f}."
            ),
        )


class MajorityLabelScorer(ESGScorer):
    """Predicts the globally most-common label for each pillar.

    The "must beat random" floor: if a multi-label classifier doesn't
    beat majority-label F1 on at least one pillar, it's not learning
    anything useful.
    """

    requires_training = False

    def __init__(self) -> None:
        self._majority: np.ndarray = np.array([0, 0, 0], dtype=np.int64)
        self._global_pillar_mean: np.ndarray = np.array([0.5, 0.5, 0.5])

    @property
    def name(self) -> str:
        return "MajorityLabel"

    def fit(self, observations: Sequence[ESGObservation]) -> MajorityLabelScorer:
        if not observations:
            return self
        labels = np.array(
            [
                (
                    int(obs.label.env_strong),
                    int(obs.label.soc_strong),
                    int(obs.label.gov_strong),
                )
                for obs in observations
            ],
            dtype=np.float64,
        )
        rates = labels.mean(axis=0)
        self._majority = (rates >= 0.5).astype(np.int64)
        pillar_rows = np.array(
            [
                (
                    _mean(obs.profile.environmental_indicators),
                    _mean(obs.profile.social_indicators),
                    _mean(obs.profile.governance_indicators),
                )
                for obs in observations
            ],
            dtype=np.float64,
        )
        self._global_pillar_mean = pillar_rows.mean(axis=0)
        return self

    def score(self, profile: CompanyProfile) -> ESGScoreResult:
        pillars = PillarScore(
            environmental=float(self._global_pillar_mean[0] * 100.0),
            social=float(self._global_pillar_mean[1] * 100.0),
            governance=float(self._global_pillar_mean[2] * 100.0),
        )
        return ESGScoreResult(
            company_name=profile.company_name,
            industry=profile.industry,
            pillar_scores=pillars,
            risk_level=_risk_level(pillars.composite),
            industry_percentile=round(min(99.0, pillars.composite + 5.0), 1),
            label_probabilities={
                "env_strong": float(self._majority[0]),
                "soc_strong": float(self._majority[1]),
                "gov_strong": float(self._majority[2]),
            },
            top_features=(),
            model_name=self.name,
            rationale="Predicts the globally most-common label per pillar.",
        )


def _mean(d: dict[str, float]) -> float:
    if not d:
        return 0.5
    return float(np.mean(list(d.values())))
