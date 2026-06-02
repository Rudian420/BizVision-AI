"""
Theta forecasting method (Assimakopoulos & Nikolopoulos, 2000).

The classical θ=2 decomposition:
    forecast = 0.5 · (LRL extrapolation) + 0.5 · (SES of the θ=2 line)

where LRL is the ordinary-least-squares trend through the history.
Equivalent to SES with a drift; consistently competitive with much
more elaborate models on the M3 / M4 competitions, which is why it's
in the ablation arm list (`AS-003`).

Pure numpy — closed-form LRL slope/intercept plus a single-coefficient
SES fit (α grid-searched on in-sample MSE). PI uses the residual-σ
band scaled by `z · √h`, same posture as HoltWinters.
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
from ml.forecasting.models.exp_smoothing import _z_for


def _next_dates(last_ds: str, horizon: int) -> tuple[str, ...]:
    start = date.fromisoformat(last_ds)
    return tuple(
        (start + timedelta(days=i + 1)).isoformat() for i in range(horizon)
    )


def _linear_trend(y: np.ndarray) -> tuple[float, float]:
    """OLS y = a + b·t. Returns (a, b)."""
    n = len(y)
    if n < 2:
        return float(y[0]) if n else 0.0, 0.0
    t = np.arange(n, dtype=np.float64)
    t_mean = float(np.mean(t))
    y_mean = float(np.mean(y))
    denom = float(np.sum((t - t_mean) ** 2)) or 1.0
    slope = float(np.sum((t - t_mean) * (y - y_mean)) / denom)
    intercept = y_mean - slope * t_mean
    return intercept, slope


def _ses_fit_predict(
    y: np.ndarray, alpha: float
) -> tuple[np.ndarray, float, float]:
    """Simple exponential smoothing. Returns (fitted, level_end, σ_resid)."""
    n = len(y)
    fitted = np.empty(n, dtype=np.float64)
    level = float(y[0])
    fitted[0] = level
    for t in range(1, n):
        fitted[t] = level
        level = alpha * float(y[t]) + (1.0 - alpha) * level
    residuals = y - fitted
    sigma = float(np.std(residuals)) if residuals.size > 1 else 0.0
    return fitted, level, sigma


class ThetaForecaster(ForecastModel):
    """Classical θ=2 method with α grid-searched on in-sample MSE."""

    def __init__(
        self,
        alpha_grid: tuple[float, ...] = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9),
    ) -> None:
        self.alpha_grid = alpha_grid
        self._intercept: float = 0.0
        self._slope: float = 0.0
        self._alpha: float = 0.3
        self._ses_level_end: float = 0.0
        self._sigma: float = 0.0
        self._n: int = 0
        self._fitted: bool = False

    @property
    def name(self) -> str:
        return "Theta"

    def fit(self, dataset: TimeSeriesDataset) -> ThetaForecaster:
        y = np.array(dataset.values, dtype=np.float64)
        n = len(y)
        if n < 2:
            raise ValueError("Theta requires at least 2 observations")

        # θ=2 line: doubles the curvature of the original. With LRL trend
        # already extracted, the θ=2 sequence is 2y - linear_trend.
        self._intercept, self._slope = _linear_trend(y)
        t = np.arange(n, dtype=np.float64)
        lrl = self._intercept + self._slope * t
        theta2 = 2.0 * y - lrl

        best_mse = float("inf")
        for a in self.alpha_grid:
            fitted, _, _ = _ses_fit_predict(theta2, a)
            mse = float(np.mean((theta2 - fitted) ** 2))
            if mse < best_mse:
                best_mse = mse
                self._alpha = a

        _, self._ses_level_end, _ = _ses_fit_predict(theta2, self._alpha)

        # Final fit-residual σ on the *combined* forecast at h=1..n
        # (re-running here avoids double-counting the in-sample SES residuals).
        combined_fitted = np.empty(n, dtype=np.float64)
        fitted_theta, _, _ = _ses_fit_predict(theta2, self._alpha)
        combined_fitted[:] = 0.5 * lrl + 0.5 * fitted_theta
        residuals = y - combined_fitted
        self._sigma = float(np.std(residuals)) if residuals.size > 1 else 0.0
        self._n = n
        self._fitted = True
        return self

    def predict(
        self, dataset: TimeSeriesDataset, horizon: int, pi_alpha: float = 0.05
    ) -> ForecastResult:
        if not self._fitted:
            self.fit(dataset)
        ds_list = _next_dates(dataset.points[-1].ds, horizon)
        z = _z_for(pi_alpha)

        # The LRL extrapolation past the training tail.
        future_t = np.arange(self._n, self._n + horizon, dtype=np.float64)
        lrl_future = self._intercept + self._slope * future_t
        # SES of θ=2 is flat at level_end past the tail.
        theta2_future = np.full(horizon, self._ses_level_end, dtype=np.float64)
        yhats = 0.5 * lrl_future + 0.5 * theta2_future

        scales = np.sqrt(np.arange(1, horizon + 1))
        bands = z * self._sigma * scales

        points = tuple(
            ForecastInterval(
                ds=ds_list[i],
                yhat=float(yhats[i]),
                yhat_lower=float(yhats[i] - bands[i]),
                yhat_upper=float(yhats[i] + bands[i]),
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
            sub_scores={
                "alpha": self._alpha,
                "trend_slope": self._slope,
                "trend_intercept": self._intercept,
            },
        )
