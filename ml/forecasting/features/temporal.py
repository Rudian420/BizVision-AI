"""
Temporal feature engineering.

Pure-numpy lag / rolling / calendar features for the tabular forecasting
models (XGBoost / LightGBM regressors). Lives in `features/` so the
forecasting models import the exact same builder regardless of whether
they're called from the training pipeline or the inference client —
identical features in / identical features out.

This is *not* used by Theta / HoltWinters which work on the raw level
series; they sit in `models/` and call the schema directly.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from ml.forecasting.data.schema import TimeSeriesDataset


def lag_features(
    values: np.ndarray, lags: tuple[int, ...] = (1, 7, 14, 28)
) -> np.ndarray:
    """Return a 2-D matrix of shape (n_obs, len(lags)).

    Position `(i, k)` holds `values[i - lags[k]]` if available, else
    `values[0]` (a constant pad — keeps the matrix dense and avoids
    inflating the early-period error from NaN-imputation choices).
    """
    n = len(values)
    out = np.empty((n, len(lags)), dtype=np.float64)
    for k, lag in enumerate(lags):
        col = np.empty(n, dtype=np.float64)
        col[:lag] = values[0]
        col[lag:] = values[:-lag]
        out[:, k] = col
    return out


def rolling_features(
    values: np.ndarray,
    windows: tuple[int, ...] = (7, 14, 28),
) -> np.ndarray:
    """Causal rolling mean + std per window. 2-D matrix shape (n, 2·W).

    Causal — position i uses values[:i], never the future. Pre-fill
    period (i < window) uses the mean/std of values[:i+1] so the
    column is dense from the start.
    """
    n = len(values)
    out = np.empty((n, 2 * len(windows)), dtype=np.float64)
    for k, w in enumerate(windows):
        means = np.empty(n, dtype=np.float64)
        stds = np.empty(n, dtype=np.float64)
        for i in range(n):
            lo = max(0, i - w + 1)
            window = values[lo : i + 1]
            means[i] = float(np.mean(window))
            stds[i] = float(np.std(window)) if len(window) > 1 else 0.0
        out[:, 2 * k] = means
        out[:, 2 * k + 1] = stds
    return out


def calendar_features(dates: tuple[str, ...]) -> np.ndarray:
    """Cyclical day-of-week + day-of-year encoding (sin/cos), shape (n, 4).

    Sin/cos preserves the wrap-around so day-365 is adjacent to day-0,
    which a raw integer feature would not — see the standard reference
    in Hyndman & Athanasopoulos.
    """
    n = len(dates)
    out = np.empty((n, 4), dtype=np.float64)
    for i, ds in enumerate(dates):
        d = date.fromisoformat(ds)
        dow = d.weekday()  # 0..6
        doy = d.timetuple().tm_yday  # 1..366
        out[i, 0] = np.sin(2.0 * np.pi * dow / 7.0)
        out[i, 1] = np.cos(2.0 * np.pi * dow / 7.0)
        out[i, 2] = np.sin(2.0 * np.pi * doy / 365.25)
        out[i, 3] = np.cos(2.0 * np.pi * doy / 365.25)
    return out


def build_feature_matrix(dataset: TimeSeriesDataset) -> tuple[np.ndarray, np.ndarray]:
    """End-to-end feature builder: returns (X, y).

    X is the concatenation of lag + rolling + calendar features
    (column order is stable for SHAP attribution downstream).
    """
    values = np.array(dataset.values, dtype=np.float64)
    dates = tuple(p.ds for p in dataset.points)
    X = np.concatenate(
        [lag_features(values), rolling_features(values), calendar_features(dates)],
        axis=1,
    )
    return X, values


# Stable column-order labels — re-used by the SHAP narrative generator.
FEATURE_NAMES: tuple[str, ...] = (
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "roll7_mean",
    "roll7_std",
    "roll14_mean",
    "roll14_std",
    "roll28_mean",
    "roll28_std",
    "dow_sin",
    "dow_cos",
    "doy_sin",
    "doy_cos",
)
