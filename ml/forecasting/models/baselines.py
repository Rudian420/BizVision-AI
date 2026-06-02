"""
Baseline forecasters.

  • `NaiveLast`       — predicts the last observed value, flat.
  • `NaiveSeasonal`   — predicts y_{t-s} where s is the seasonal period.

Both are unsupervised (`requires_training = False`) but expose `fit`
for ablation-harness uniformity. PI is built from the empirical
residual quantiles of the in-sample one-step-ahead errors so even
these baselines produce a valid PI for Winkler scoring (the textbook
posture from Hyndman & Athanasopoulos).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from ml.forecasting.data.schema import (
    ForecastInterval,
    ForecastResult,
    TimeSeriesDataset,
)
from ml.forecasting.models.base import ForecastModel


def _next_dates(last_ds: str, horizon: int) -> tuple[str, ...]:
    start = date.fromisoformat(last_ds)
    return tuple(
        (start + timedelta(days=i + 1)).isoformat() for i in range(horizon)
    )


def _residual_band(residuals: np.ndarray, pi_alpha: float) -> float:
    """Half-width of the empirical PI from in-sample residuals.

    Uses the residual quantile rather than a Gaussian assumption — robust
    to heavy tails. With no residuals (n < 2) falls back to ±5% of the
    last value, which the caller passes in via `level_fallback`.
    """
    if residuals.size < 2:
        return 0.0
    lo = np.quantile(residuals, pi_alpha / 2.0)
    hi = np.quantile(residuals, 1.0 - pi_alpha / 2.0)
    return float((hi - lo) / 2.0)


class NaiveLast(ForecastModel):
    """Flat forecast at the last observed level."""

    requires_training = False

    def __init__(self) -> None:
        self._residuals: np.ndarray = np.array([], dtype=np.float64)
        self._fitted: bool = False

    @property
    def name(self) -> str:
        return "NaiveLast"

    def fit(self, dataset: TimeSeriesDataset) -> NaiveLast:
        values = np.array(dataset.values, dtype=np.float64)
        # one-step naive residuals: y_t - y_{t-1}
        if values.size >= 2:
            self._residuals = values[1:] - values[:-1]
        self._fitted = True
        return self

    def predict(
        self, dataset: TimeSeriesDataset, horizon: int, pi_alpha: float = 0.05
    ) -> ForecastResult:
        if not self._fitted:
            self.fit(dataset)
        last = float(dataset.values[-1])
        band = _residual_band(self._residuals, pi_alpha) or abs(last) * 0.05
        ds_list = _next_dates(dataset.points[-1].ds, horizon)
        # PI widens with sqrt(h) — random-walk uncertainty growth.
        points = tuple(
            ForecastInterval(
                ds=d,
                yhat=last,
                yhat_lower=last - band * np.sqrt(i + 1),
                yhat_upper=last + band * np.sqrt(i + 1),
            )
            for i, d in enumerate(ds_list)
        )
        return ForecastResult(
            series_id=dataset.series_id,
            horizon_days=horizon,
            points=points,
            end_value=last,
            cumulative_value=float(last * horizon),
            model_name=self.name,
        )


class NaiveSeasonal(ForecastModel):
    """Predicts `y_{t-s}` — the value `s` steps ago."""

    requires_training = False

    def __init__(self, season_length: int = 7) -> None:
        if season_length <= 1:
            raise ValueError("season_length must be > 1")
        self.season_length = season_length
        self._residuals: np.ndarray = np.array([], dtype=np.float64)
        self._fitted: bool = False

    @property
    def name(self) -> str:
        return f"NaiveSeasonal(s={self.season_length})"

    def fit(self, dataset: TimeSeriesDataset) -> NaiveSeasonal:
        values = np.array(dataset.values, dtype=np.float64)
        s = self.season_length
        if values.size > s:
            self._residuals = values[s:] - values[:-s]
        self._fitted = True
        return self

    def predict(
        self, dataset: TimeSeriesDataset, horizon: int, pi_alpha: float = 0.05
    ) -> ForecastResult:
        if not self._fitted:
            self.fit(dataset)
        values = np.array(dataset.values, dtype=np.float64)
        s = self.season_length
        if values.size < s:
            raise ValueError(
                f"history of length {values.size} too short for season {s}"
            )
        # The last s values cycle.
        cycle = values[-s:]
        band = _residual_band(self._residuals, pi_alpha) or float(np.std(values) * 0.1)
        ds_list = _next_dates(dataset.points[-1].ds, horizon)
        yhats = np.array([cycle[i % s] for i in range(horizon)], dtype=np.float64)
        # PI widens with the number of cycles elapsed.
        scales = np.sqrt(1.0 + np.arange(horizon) // s)
        points = tuple(
            ForecastInterval(
                ds=ds_list[i],
                yhat=float(yhats[i]),
                yhat_lower=float(yhats[i] - band * scales[i]),
                yhat_upper=float(yhats[i] + band * scales[i]),
            )
            for i in range(horizon)
        )
        return ForecastResult(
            series_id=dataset.series_id,
            horizon_days=horizon,
            points=points,
            end_value=float(yhats[-1]),
            cumulative_value=float(yhats.sum()),
            model_name=self.name,
        )
