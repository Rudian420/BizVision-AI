"""
Forecasting metrics — pure numpy, no sklearn dependency.

Same philosophy as `ml.recruitment.evaluation.metrics` and
`ml.pricing.evaluation.metrics`: every metric implemented from its
mathematical definition so the test suite can verify each against a
hand-worked example. Thesis-grade reporting demands that the metric
*used* in EXP-FOR-001..003 / AS-003 is the metric *documented* — no
surprise behaviour from a future library bump.

Conventions:
  • `y_true`  — observed test-window values (≥ 0).
  • `y_pred`  — model point forecasts, same shape as `y_true`.
  • `y_lower` / `y_upper` — PI bounds, same shape.
  • `y_train` — full training-window observations (for seasonal MASE).
  • All percentage outputs are *fractions* (0.12 = 12% error).
"""

from __future__ import annotations

import numpy as np

# ── Point error ────────────────────────────────────────────────────


def mean_absolute_percentage_error(
    y_true: np.ndarray, y_pred: np.ndarray
) -> float:
    """MAPE — mean absolute percentage error, expressed as a *fraction*.

    Zero-true entries are skipped (rather than producing inf) so the
    metric stays well-defined on sparse series."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    if y_true.size == 0:
        return 0.0
    mask = y_true != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])))


def symmetric_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """sMAPE — bounded in [0, 2]. The M-competitions definition.

    `2 · |y_t - ŷ_t| / (|y_t| + |ŷ_t|)`, averaged.

    "Symmetric" refers to its *bounded* behaviour — the metric stays in
    [0, 2] regardless of the absolute scale, unlike MAPE which is
    unbounded as `y_t → 0`. It is **not** exactly symmetric under
    sign-flipped errors at non-zero truth (the denominator changes
    with `ŷ_t`), but the asymmetry is much milder than MAPE's. Returns
    0 when `y_t = ŷ_t = 0`.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    if y_true.size == 0:
        return 0.0
    denom = np.abs(y_true) + np.abs(y_pred)
    mask = denom > 0
    if not mask.any():
        return 0.0
    return float(
        np.mean(2.0 * np.abs(y_true[mask] - y_pred[mask]) / denom[mask])
    )


def root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """RMSE in the units of `y_true`."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    if y_true.size == 0:
        return 0.0
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mean_absolute_scaled_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray,
    season_length: int = 1,
) -> float:
    """MASE — Hyndman & Koehler 2006.

    Numerator: mean absolute error on the test window.
    Denominator: mean absolute one-step (or one-season) naive error on
    the training window. MASE < 1 ⇒ candidate beats the in-sample
    naive baseline.

    Returns `inf` if the training-window denominator is zero (constant
    series), `0` if both sides have zero length.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    y_train = np.asarray(y_train, dtype=np.float64)
    if y_true.size == 0:
        return 0.0
    if y_train.size <= season_length:
        return float("inf")
    naive_diffs = np.abs(y_train[season_length:] - y_train[:-season_length])
    denom = float(np.mean(naive_diffs))
    if denom <= 0.0:
        return float("inf")
    numer = float(np.mean(np.abs(y_true - y_pred)))
    return numer / denom


# ── Prediction-interval scoring ────────────────────────────────────


def winkler_score(
    y_true: np.ndarray,
    y_lower: np.ndarray,
    y_upper: np.ndarray,
    pi_alpha: float = 0.05,
) -> float:
    """Winkler / interval score (Gneiting & Raftery 2007).

    `width + (2/α) · (lower - y) · 1[y < lower]
            + (2/α) · (y - upper) · 1[y > upper]`,
    averaged. Proper scoring rule for PIs — lower is better. The α
    here is the *significance* (0.05 ⇒ 95% PI), matching every other
    `pi_alpha` argument in the package.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_lower = np.asarray(y_lower, dtype=np.float64)
    y_upper = np.asarray(y_upper, dtype=np.float64)
    if y_true.size == 0:
        return 0.0
    width = y_upper - y_lower
    below = np.maximum(0.0, y_lower - y_true)
    above = np.maximum(0.0, y_true - y_upper)
    penalty = (2.0 / pi_alpha) * (below + above)
    return float(np.mean(width + penalty))


def coverage(
    y_true: np.ndarray, y_lower: np.ndarray, y_upper: np.ndarray
) -> float:
    """Empirical PI coverage — fraction of `y_true` inside [lower, upper]."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_lower = np.asarray(y_lower, dtype=np.float64)
    y_upper = np.asarray(y_upper, dtype=np.float64)
    if y_true.size == 0:
        return 0.0
    inside = (y_true >= y_lower) & (y_true <= y_upper)
    return float(np.mean(inside))
