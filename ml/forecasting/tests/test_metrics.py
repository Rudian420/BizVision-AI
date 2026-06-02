"""
Offline unit tests for forecasting metrics.

Pure numpy + pytest — runnable without prophet / statsmodels / sktime.
Every metric is verified against a hand-worked example from its
mathematical definition; surprise behaviour from a future library bump
would break the suite immediately.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.forecasting.evaluation.metrics import (
    coverage,
    mean_absolute_percentage_error,
    mean_absolute_scaled_error,
    root_mean_squared_error,
    symmetric_mape,
    winkler_score,
)

# ── MAPE ────────────────────────────────────────────────────────────


def test_mape_perfect_prediction_is_zero():
    y = np.array([10.0, 20.0, 30.0])
    assert mean_absolute_percentage_error(y, y) == 0.0


def test_mape_skips_zero_truth_entries():
    y_true = np.array([0.0, 10.0, 10.0])
    y_pred = np.array([5.0, 8.0, 12.0])
    # zero-truth entry skipped → mean(|0.2|, |0.2|) = 0.2
    assert mean_absolute_percentage_error(y_true, y_pred) == pytest.approx(0.2)


def test_mape_handworked():
    y_true = np.array([100.0, 50.0])
    y_pred = np.array([90.0, 40.0])
    # (|10/100| + |10/50|) / 2 = (0.1 + 0.2) / 2 = 0.15
    assert mean_absolute_percentage_error(y_true, y_pred) == pytest.approx(0.15)


def test_mape_empty_is_zero():
    assert mean_absolute_percentage_error(np.array([]), np.array([])) == 0.0


# ── sMAPE ───────────────────────────────────────────────────────────


def test_smape_is_bounded_in_zero_to_two():
    """sMAPE stays in [0, 2] regardless of scale — the bounded property
    that MAPE lacks. Pathological cases (predict 0 when truth is 1, or
    predict 1 when truth is 0) both saturate at exactly 2."""
    assert symmetric_mape(np.array([1.0]), np.array([0.0])) == pytest.approx(2.0)
    assert symmetric_mape(np.array([0.0]), np.array([1.0])) == pytest.approx(2.0)
    # And a normal mid-range error stays well below 2.
    val = symmetric_mape(np.array([100.0]), np.array([110.0]))
    assert 0.0 <= val <= 2.0
    assert val < 0.2


def test_smape_handworked():
    y_true = np.array([100.0, 50.0])
    y_pred = np.array([90.0, 60.0])
    # 2·10/(100+90) + 2·10/(50+60) = 20/190 + 20/110, divided by 2
    expected = 0.5 * (20.0 / 190.0 + 20.0 / 110.0)
    assert symmetric_mape(y_true, y_pred) == pytest.approx(expected)


def test_smape_perfect_is_zero():
    y = np.array([10.0, 20.0, 30.0])
    assert symmetric_mape(y, y) == 0.0


def test_smape_zero_denominator_returns_zero():
    """If both truth and prediction are 0, sMAPE is 0 (not nan)."""
    assert symmetric_mape(np.zeros(3), np.zeros(3)) == 0.0


# ── RMSE ────────────────────────────────────────────────────────────


def test_rmse_perfect_is_zero():
    y = np.array([1.0, 2.0, 3.0])
    assert root_mean_squared_error(y, y) == 0.0


def test_rmse_handworked():
    y_true = np.array([0.0, 0.0, 0.0])
    y_pred = np.array([3.0, 4.0, 0.0])
    # sqrt((9 + 16 + 0)/3) = sqrt(25/3)
    assert root_mean_squared_error(y_true, y_pred) == pytest.approx(np.sqrt(25.0 / 3.0))


# ── MASE ────────────────────────────────────────────────────────────


def test_mase_perfect_is_zero():
    y_true = np.array([10.0, 20.0])
    y_train = np.array([1.0, 2.0, 3.0, 4.0])
    assert mean_absolute_scaled_error(y_true, y_true, y_train) == 0.0


def test_mase_handworked():
    """Numerator = |2-1| = 1; denominator = mean(|2-1|,|3-2|,|4-3|) = 1.
    MASE = 1 / 1 = 1."""
    y_true = np.array([2.0])
    y_pred = np.array([1.0])
    y_train = np.array([1.0, 2.0, 3.0, 4.0])
    assert mean_absolute_scaled_error(y_true, y_pred, y_train) == pytest.approx(1.0)


def test_mase_returns_inf_for_constant_training_series():
    """If the training series is constant, the naive denominator is 0
    → MASE is undefined; we return inf rather than nan."""
    y_true = np.array([1.0, 2.0])
    y_pred = np.array([0.0, 1.0])
    y_train = np.array([5.0, 5.0, 5.0])
    assert mean_absolute_scaled_error(y_true, y_pred, y_train) == float("inf")


def test_mase_seasonal_naive_denominator():
    """`season_length=7` → denominator uses |y_t - y_{t-7}|."""
    y_train = np.arange(14, dtype=np.float64)
    # y[7:] - y[:-7] is uniformly 7 → denom = 7
    y_true = np.array([14.0, 15.0])
    y_pred = np.array([14.0, 15.0])
    # MASE for perfect prediction is 0
    assert mean_absolute_scaled_error(y_true, y_pred, y_train, season_length=7) == 0.0


# ── Winkler / coverage ─────────────────────────────────────────────


def test_winkler_inside_interval_is_just_width():
    y_true = np.array([10.0])
    y_lower = np.array([8.0])
    y_upper = np.array([12.0])
    # All inside → score = width = 4
    assert winkler_score(y_true, y_lower, y_upper, pi_alpha=0.05) == pytest.approx(4.0)


def test_winkler_penalises_below_lower():
    """y=5, [8,12], α=0.1 → width=4 + (2/0.1)·(8-5) = 4 + 60 = 64."""
    y_true = np.array([5.0])
    y_lower = np.array([8.0])
    y_upper = np.array([12.0])
    assert winkler_score(y_true, y_lower, y_upper, pi_alpha=0.1) == pytest.approx(64.0)


def test_winkler_penalises_above_upper():
    """y=15, [8,12], α=0.1 → width=4 + (2/0.1)·(15-12) = 4 + 60 = 64."""
    y_true = np.array([15.0])
    y_lower = np.array([8.0])
    y_upper = np.array([12.0])
    assert winkler_score(y_true, y_lower, y_upper, pi_alpha=0.1) == pytest.approx(64.0)


def test_coverage_perfectly_inside_is_one():
    y_true = np.array([5.0, 6.0, 7.0])
    y_lower = np.array([0.0, 0.0, 0.0])
    y_upper = np.array([10.0, 10.0, 10.0])
    assert coverage(y_true, y_lower, y_upper) == 1.0


def test_coverage_half_inside_is_half():
    y_true = np.array([5.0, 100.0])  # second one is outside
    y_lower = np.array([0.0, 0.0])
    y_upper = np.array([10.0, 10.0])
    assert coverage(y_true, y_lower, y_upper) == 0.5
