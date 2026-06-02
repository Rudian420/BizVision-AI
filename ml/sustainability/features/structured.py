"""
Structured-feature builder for ESG scoring.

Converts a `CompanyProfile` into a dense numeric vector that the
multi-label classifier consumes. The vector layout is **stable** —
SHAP attribution downstream relies on `FEATURE_NAMES` ordering, same
posture as `ml.forecasting.features.temporal.FEATURE_NAMES` and
`ml.pricing.features.structured`.

Feature breakdown (12 dims):
  0..3   pillar means + composite mean (E, S, G, mean(E,S,G))
  4..8   industry one-hot (5 industries — see `data.loader.INDUSTRIES`)
  9..11  scale features (log-revenue, log-headcount, revenue per head)

We deliberately keep the dimensionality low so the linear-logistic
classifier in `models/multilabel.py` stays interpretable — RC-002's
SHAP-attributed bias decomposition pattern carries over cleanly when
the package gets wired into the backend (TASK-018 future).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ml.sustainability.data.loader import INDUSTRIES
from ml.sustainability.data.schema import CompanyProfile, ESGObservation

# Stable column-order labels — re-used by the SHAP narrative generator.
FEATURE_NAMES: tuple[str, ...] = (
    "env_mean",
    "soc_mean",
    "gov_mean",
    "composite_mean",
    *(f"industry_{i}" for i in INDUSTRIES),
    "log_revenue",
    "log_headcount",
    "revenue_per_head",
)


def _pillar_mean(indicators: dict[str, float]) -> float:
    if not indicators:
        return 0.5
    return float(np.mean(list(indicators.values())))


def featurize(profile: CompanyProfile) -> np.ndarray:
    """Return a 1-D feature vector for one company. Length = `len(FEATURE_NAMES)`."""
    env = _pillar_mean(profile.environmental_indicators)
    soc = _pillar_mean(profile.social_indicators)
    gov = _pillar_mean(profile.governance_indicators)
    composite = (env + soc + gov) / 3.0

    onehot = np.zeros(len(INDUSTRIES), dtype=np.float64)
    if profile.industry in INDUSTRIES:
        onehot[INDUSTRIES.index(profile.industry)] = 1.0

    revenue = max(profile.annual_revenue, 1.0)
    headcount = max(profile.employee_count, 1)
    scale = np.array(
        [
            np.log1p(revenue),
            np.log1p(headcount),
            revenue / headcount,
        ],
        dtype=np.float64,
    )

    return np.concatenate([np.array([env, soc, gov, composite]), onehot, scale])


def featurize_batch(profiles: Sequence[CompanyProfile]) -> np.ndarray:
    """Stack `featurize` over a sequence of profiles → (n, len(FEATURE_NAMES))."""
    if not profiles:
        return np.zeros((0, len(FEATURE_NAMES)), dtype=np.float64)
    rows = [featurize(p) for p in profiles]
    return np.stack(rows, axis=0)


def labels_to_matrix(observations: Sequence[ESGObservation]) -> np.ndarray:
    """Return an (n, 3) binary matrix in column order (E, S, G)."""
    n = len(observations)
    out = np.zeros((n, 3), dtype=np.int64)
    for i, obs in enumerate(observations):
        out[i, 0] = int(obs.label.env_strong)
        out[i, 1] = int(obs.label.soc_strong)
        out[i, 2] = int(obs.label.gov_strong)
    return out


PILLAR_NAMES: tuple[str, ...] = ("environmental", "social", "governance")
LABEL_KEYS: tuple[str, ...] = ("env_strong", "soc_strong", "gov_strong")
