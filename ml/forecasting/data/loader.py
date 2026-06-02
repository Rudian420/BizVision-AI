"""
Synthetic time-series loader.

Generates a deterministic profit / revenue series with:
  • linear trend
  • weekly + yearly seasonality (additive)
  • mild AR(1) noise

The same seed → the same series, so test-suite stability is preserved
across machines. Mirrors `ml.pricing.data.loader` in spirit: pure-numpy
generation, no heavy framework imports, fed into a frozen dataclass.

Used by:
  • Phase-3 training pipelines (`training.pipeline.train`)
  • Backend `ForecastingInferenceClient` synthetic-bootstrap fallback
    (TASK-016, future), same posture as `PricingInferenceClient`.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from ml.forecasting.data.schema import TimeSeriesDataset, TimeSeriesPoint


def generate_synthetic_series(
    n_days: int = 365 * 2,
    start: str = "2024-01-01",
    base_level: float = 10_000.0,
    daily_trend: float = 5.0,
    weekly_amp: float = 800.0,
    yearly_amp: float = 1500.0,
    noise_std: float = 250.0,
    ar1: float = 0.35,
    seed: int = 42,
    series_id: str = "synthetic-profit",
) -> TimeSeriesDataset:
    """Produce a `TimeSeriesDataset` of `n_days` synthetic daily values.

    The signal decomposition is:

        y_t = base + trend·t
              + weekly_amp · sin(2π t / 7)
              + yearly_amp · sin(2π t / 365.25)
              + ε_t,    ε_t = ar1·ε_{t-1} + N(0, noise_std)

    The signal-to-noise ratio is intentionally moderate (large enough
    that Theta and HoltWinters beat NaiveSeasonal, small enough that
    perfect MAPE is impossible). Use `noise_std=0` for a clean fixture
    when testing model recovery.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n_days, dtype=np.float64)

    trend = base_level + daily_trend * t
    weekly = weekly_amp * np.sin(2.0 * np.pi * t / 7.0)
    yearly = yearly_amp * np.sin(2.0 * np.pi * t / 365.25)

    noise = np.empty(n_days, dtype=np.float64)
    prev = 0.0
    for i in range(n_days):
        shock = rng.normal(0.0, noise_std)
        prev = ar1 * prev + shock
        noise[i] = prev

    y = trend + weekly + yearly + noise
    y = np.maximum(y, 0.0)  # profit clamped at zero — no negative series in fixtures

    start_d = date.fromisoformat(start)
    points = tuple(
        TimeSeriesPoint(
            ds=(start_d + timedelta(days=int(i))).isoformat(),
            y=float(y[i]),
            series_id=series_id,
        )
        for i in range(n_days)
    )
    return TimeSeriesDataset(series_id=series_id, frequency="D", points=points)


def split_train_test(
    dataset: TimeSeriesDataset, horizon: int
) -> tuple[TimeSeriesDataset, TimeSeriesDataset]:
    """Holdout the last `horizon` points as test. No overlap, no shuffle."""
    if horizon <= 0 or horizon >= len(dataset):
        raise ValueError(f"horizon {horizon} invalid for series of length {len(dataset)}")
    cut = len(dataset) - horizon
    train = TimeSeriesDataset(
        series_id=dataset.series_id,
        frequency=dataset.frequency,
        points=dataset.points[:cut],
    )
    test = TimeSeriesDataset(
        series_id=dataset.series_id,
        frequency=dataset.frequency,
        points=dataset.points[cut:],
    )
    return train, test
