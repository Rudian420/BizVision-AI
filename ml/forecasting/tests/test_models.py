"""
Offline unit tests for the forecasting model arms.

Each test is small enough to debug quickly but exercises the actual
recursion / closed-form math — not a smoke test. Synthetic fixtures
come from `data.loader.generate_synthetic_series` (deterministic seed).
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.forecasting.data.loader import generate_synthetic_series, split_train_test
from ml.forecasting.data.schema import (
    TimeSeriesDataset,
    TimeSeriesPoint,
)
from ml.forecasting.evaluation.metrics import mean_absolute_percentage_error
from ml.forecasting.models.baselines import NaiveLast, NaiveSeasonal
from ml.forecasting.models.exp_smoothing import HoltWintersForecaster
from ml.forecasting.models.theta import ThetaForecaster


def _ds_from_values(values: list[float], series_id: str = "test") -> TimeSeriesDataset:
    points = tuple(
        TimeSeriesPoint(ds=f"2024-01-{i + 1:02d}", y=v, series_id=series_id)
        for i, v in enumerate(values)
    )
    return TimeSeriesDataset(series_id=series_id, frequency="D", points=points)


# ── NaiveLast ──────────────────────────────────────────────────────


def test_naive_last_is_flat_at_last_value():
    ds = _ds_from_values([10.0, 20.0, 30.0, 40.0, 50.0])
    model = NaiveLast().fit(ds)
    result = model.predict(ds, horizon=3)
    assert all(p.yhat == 50.0 for p in result.points)
    assert result.end_value == 50.0


def test_naive_last_pi_widens_with_horizon():
    """Random-walk uncertainty scales with sqrt(h)."""
    ds = _ds_from_values([1.0, 3.0, 1.0, 3.0, 1.0, 3.0])
    model = NaiveLast().fit(ds)
    result = model.predict(ds, horizon=4)
    widths = [p.yhat_upper - p.yhat_lower for p in result.points]
    # widths should be strictly increasing
    assert all(widths[i] < widths[i + 1] for i in range(len(widths) - 1))


# ── NaiveSeasonal ──────────────────────────────────────────────────


def test_naive_seasonal_recovers_perfect_period():
    """y_t = sin(2π t/7) → naive-seasonal with s=7 → MAPE ≈ 0."""
    values = [10.0 + 5.0 * np.sin(2.0 * np.pi * i / 7.0) for i in range(28)]
    ds = _ds_from_values(values)
    model = NaiveSeasonal(season_length=7).fit(ds)
    result = model.predict(ds, horizon=7)
    y_pred = np.array([p.yhat for p in result.points])
    # forecast equals the most-recent cycle (last 7 values)
    y_expected = np.array(values[-7:])
    assert np.allclose(y_pred, y_expected)


def test_naive_seasonal_rejects_short_history():
    ds = _ds_from_values([1.0, 2.0, 3.0])
    model = NaiveSeasonal(season_length=7).fit(ds)
    with pytest.raises(ValueError, match="too short"):
        model.predict(ds, horizon=1)


def test_naive_seasonal_rejects_invalid_season():
    with pytest.raises(ValueError, match="season_length"):
        NaiveSeasonal(season_length=1)


# ── HoltWinters ────────────────────────────────────────────────────


def test_holt_winters_rejects_short_history():
    """HW needs at least 2 full seasons of history."""
    ds = _ds_from_values([1.0] * 13)  # 13 < 2·7 = 14
    model = HoltWintersForecaster(season_length=7)
    with pytest.raises(ValueError, match="too short"):
        model.fit(ds)


def test_holt_winters_beats_naive_last_on_seasonal_signal():
    """On a pure trend+seasonal series, HW should beat the flat naive baseline."""
    dataset = generate_synthetic_series(n_days=365, noise_std=10.0, seed=11)
    train_ds, test_ds = split_train_test(dataset, horizon=14)

    hw = HoltWintersForecaster(season_length=7).fit(train_ds)
    nl = NaiveLast().fit(train_ds)

    y_true = np.array(test_ds.values, dtype=np.float64)
    y_hw = np.array([p.yhat for p in hw.predict(train_ds, horizon=14).points])
    y_nl = np.array([p.yhat for p in nl.predict(train_ds, horizon=14).points])

    mape_hw = mean_absolute_percentage_error(y_true, y_hw)
    mape_nl = mean_absolute_percentage_error(y_true, y_nl)
    assert mape_hw < mape_nl


def test_holt_winters_pi_is_wider_at_larger_horizon():
    dataset = generate_synthetic_series(n_days=365, seed=7)
    hw = HoltWintersForecaster(season_length=7).fit(dataset)
    result = hw.predict(dataset, horizon=30)
    widths = [p.yhat_upper - p.yhat_lower for p in result.points]
    # Strict monotonicity comes from σ·√h scaling.
    assert widths[0] < widths[-1]


# ── Theta ──────────────────────────────────────────────────────────


def test_theta_recovers_linear_trend():
    """On a clean linear series, Theta should forecast the trend almost
    exactly — the LRL component IS the trend."""
    values = [10.0 + 0.5 * i for i in range(60)]
    ds = _ds_from_values(values)
    model = ThetaForecaster().fit(ds)
    result = model.predict(ds, horizon=10)
    expected = np.array([10.0 + 0.5 * (60 + i) for i in range(10)])
    y_pred = np.array([p.yhat for p in result.points])
    # within 0.1% — closed-form OLS + SES of a linear series
    assert np.allclose(y_pred, expected, rtol=1e-3)


def test_theta_requires_two_observations():
    ds = _ds_from_values([5.0])
    with pytest.raises(ValueError, match="at least 2"):
        ThetaForecaster().fit(ds)


def test_theta_sub_scores_record_fitted_alpha_and_slope():
    values = [10.0 + 0.5 * i for i in range(50)]
    ds = _ds_from_values(values)
    model = ThetaForecaster().fit(ds)
    result = model.predict(ds, horizon=3)
    assert "alpha" in result.sub_scores
    assert result.sub_scores["trend_slope"] == pytest.approx(0.5, rel=1e-3)
