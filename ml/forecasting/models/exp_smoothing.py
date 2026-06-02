"""
Holt-Winters triple exponential smoothing.

Additive trend + additive seasonality — the standard "ETS(A,A,A)" model
from Hyndman & Athanasopoulos chapter 8. Hand-implemented in pure numpy
so the package has no statsmodels / sktime dependency and remains
testable in the lean dev venv (same constraint as `ml.pricing`).

Smoothing coefficients (α, β, γ) are fit by grid search over a small
deterministic grid against in-sample one-step-ahead MSE — exhaustive but
N ≤ 11³ ≈ 1.3K evaluations on the synthetic fixture (well under 1s).

PI is built from one-step-ahead residual standard deviation, scaled by
the normal quantile and √h to model uncertainty growth — the same shape
as `statsmodels.tsa.holtwinters.ExponentialSmoothing.forecast` for h=1
and a defensible approximation thereafter.
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

# Standard-normal two-sided quantiles for common α — avoids scipy.stats.
_Z_TABLE: dict[float, float] = {
    0.01: 2.576,
    0.05: 1.960,
    0.10: 1.645,
    0.20: 1.282,
}


def _z_for(pi_alpha: float) -> float:
    """Closest tabulated z-quantile (defaults to 1.960 if unknown)."""
    return _Z_TABLE.get(round(pi_alpha, 2), 1.960)


def _next_dates(last_ds: str, horizon: int) -> tuple[str, ...]:
    start = date.fromisoformat(last_ds)
    return tuple(
        (start + timedelta(days=i + 1)).isoformat() for i in range(horizon)
    )


def _holt_winters_recursion(
    y: np.ndarray,
    season_length: int,
    alpha: float,
    beta: float,
    gamma: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Run the additive-trend-additive-seasonality recursion.

    Returns (level, trend, seasonal_idx, fitted) — each length n.

    Initial values follow the standard recipe:
      level_0  = mean(y[:s])
      trend_0  = (mean(y[s:2s]) - mean(y[:s])) / s
      season_0 = y[:s] - level_0
    """
    n = len(y)
    s = season_length
    level = np.zeros(n)
    trend = np.zeros(n)
    season = np.zeros(n + s)
    fitted = np.zeros(n)

    level[0] = float(np.mean(y[:s]))
    if n >= 2 * s:
        trend[0] = (float(np.mean(y[s : 2 * s])) - float(np.mean(y[:s]))) / s
    else:
        trend[0] = 0.0
    for i in range(s):
        season[i] = float(y[i]) - level[0]

    for t in range(n):
        # in-sample fitted value uses prior-step level/trend + this-cycle season
        fitted[t] = level[t - 1] + trend[t - 1] + season[t] if t > 0 else level[0] + season[0]
        if t == 0:
            continue
        prev_season = season[t]
        level[t] = alpha * (y[t] - prev_season) + (1.0 - alpha) * (
            level[t - 1] + trend[t - 1]
        )
        trend[t] = beta * (level[t] - level[t - 1]) + (1.0 - beta) * trend[t - 1]
        season[t + s] = gamma * (y[t] - level[t]) + (1.0 - gamma) * prev_season

    return level, trend, season, fitted


class HoltWintersForecaster(ForecastModel):
    """Holt-Winters additive method with grid-searched smoothing coefficients."""

    def __init__(
        self,
        season_length: int = 7,
        grid: tuple[float, ...] = (0.05, 0.15, 0.3, 0.5, 0.7, 0.9),
    ) -> None:
        if season_length <= 1:
            raise ValueError("season_length must be > 1")
        self.season_length = season_length
        self.grid = grid
        self._alpha: float = 0.3
        self._beta: float = 0.1
        self._gamma: float = 0.1
        self._level_end: float = 0.0
        self._trend_end: float = 0.0
        self._season_tail: np.ndarray = np.zeros(season_length)
        self._sigma: float = 0.0
        self._fitted: bool = False

    @property
    def name(self) -> str:
        return f"HoltWinters(s={self.season_length})"

    def fit(self, dataset: TimeSeriesDataset) -> HoltWintersForecaster:
        y = np.array(dataset.values, dtype=np.float64)
        s = self.season_length
        if y.size < 2 * s:
            raise ValueError(
                f"history of length {y.size} too short for HoltWinters(s={s})"
            )

        best = (float("inf"), self._alpha, self._beta, self._gamma)
        for a in self.grid:
            for b in self.grid:
                for g in self.grid:
                    _, _, _, fitted = _holt_winters_recursion(y, s, a, b, g)
                    # Score on observations past one full season — initial-condition warmup.
                    mse = float(np.mean((y[s:] - fitted[s:]) ** 2))
                    if mse < best[0]:
                        best = (mse, a, b, g)

        _, self._alpha, self._beta, self._gamma = best
        level, trend, season, fitted = _holt_winters_recursion(
            y, s, self._alpha, self._beta, self._gamma
        )
        self._level_end = float(level[-1])
        self._trend_end = float(trend[-1])
        # The next-cycle seasonal indices to use for the forecast tail.
        self._season_tail = season[len(y) : len(y) + s].copy()
        residuals = y[s:] - fitted[s:]
        self._sigma = float(np.std(residuals)) if residuals.size > 1 else 0.0
        self._fitted = True
        return self

    def predict(
        self, dataset: TimeSeriesDataset, horizon: int, pi_alpha: float = 0.05
    ) -> ForecastResult:
        if not self._fitted:
            self.fit(dataset)
        s = self.season_length
        z = _z_for(pi_alpha)
        ds_list = _next_dates(dataset.points[-1].ds, horizon)

        # Pre-compute the seasonal cycle the forecast extends through.
        season_cycle = self._season_tail
        yhats = np.empty(horizon, dtype=np.float64)
        for h in range(horizon):
            yhats[h] = self._level_end + (h + 1) * self._trend_end + season_cycle[h % s]

        # Uncertainty growth: σ · √h is the standard ETS(A,A,A) approximation.
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
            sub_scores={"alpha": self._alpha, "beta": self._beta, "gamma": self._gamma},
        )
