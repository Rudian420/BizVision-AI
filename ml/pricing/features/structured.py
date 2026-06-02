"""
Tabular feature engineering for the LightGBM demand model.

Same philosophy as `ml.recruitment.features.structured`: every column is
a numeric / fraction / boolean that has a recruiter-readable name, so
SHAP attributions on top of the boosting model produce a narrative the
copilot can render directly.

`FEATURE_NAMES` is the canonical column order — pass it through to SHAP
so attribution outputs line up with the matrix.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from ml.pricing.data.schema import PriceObservation

FEATURE_NAMES: tuple[str, ...] = (
    "price",
    "price_log",  # log(1 + price) — captures multiplicative scale
    "competitor_price_gap",  # (price - competitor_price) / competitor_price
    "competitor_price_log",
    "season_sin",  # sin(2π · season / 4) — cyclical encoding
    "season_cos",  # cos(2π · season / 4)
    "promotion_flag",
    "has_competitor",
)


def _log1p(x: float) -> float:
    return float(np.log1p(max(0.0, x)))


def observation_features(obs: PriceObservation) -> np.ndarray:
    """Vectorise a single observation into the FEATURE_NAMES ordering.

    Missing competitor prices are imputed as 0 with `has_competitor=0` so
    the boosting model can branch on missingness rather than seeing a
    zero-gap signal."""
    price = float(obs.price)
    competitor = float(obs.competitor_price) if obs.competitor_price is not None else 0.0
    has_comp = 1 if obs.competitor_price is not None else 0
    if has_comp and competitor > 0:
        gap = (price - competitor) / competitor
    else:
        gap = 0.0

    season_rad = 2 * np.pi * (obs.season % 4) / 4
    return np.array(
        [
            price,
            _log1p(price),
            float(gap),
            _log1p(competitor),
            float(np.sin(season_rad)),
            float(np.cos(season_rad)),
            1.0 if obs.promotion else 0.0,
            float(has_comp),
        ],
        dtype=np.float32,
    )


def build_feature_matrix(observations: Iterable[PriceObservation]) -> np.ndarray:
    """Stack per-observation feature vectors into a (n × n_features) matrix."""
    rows = [observation_features(o) for o in observations]
    if not rows:
        return np.empty((0, len(FEATURE_NAMES)), dtype=np.float32)
    return np.vstack(rows)
