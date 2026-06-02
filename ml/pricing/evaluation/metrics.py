"""
Pricing metrics — pure numpy, no sklearn dependency.

Same philosophy as `ml.recruitment.evaluation.metrics`: every metric is
implemented from its mathematical definition so the test suite can
verify each against a hand-worked example. Thesis-grade reporting
demands that the metric *used* in EXP-PRC-001..002 / AS-002 is the
metric *documented* — no surprise behaviour from a future library bump.

Conventions:
  • `y_true`  — observed demand (or revenue) measurements (≥ 0).
  • `y_pred`  — model predictions, same shape as `y_true`.
  • `baseline_revenue` / `model_revenue` — revenue achieved per query
    by the baseline vs the candidate policy.
  • All percentage outputs are *fractions* (0.12 = 12% uplift), never
    pre-multiplied — keeps composability with other metrics clean.
"""

from __future__ import annotations

import numpy as np

# ── Forecasting error ──────────────────────────────────────────────


def mean_absolute_percentage_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """MAPE — mean absolute percentage error, expressed as a *fraction*.

    Zero-true entries are skipped (rather than producing inf) so the
    metric stays well-defined on sparse demand series; if every truth is
    zero we return 0.0."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    if y_true.size == 0:
        return 0.0
    mask = y_true != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])))


def root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """RMSE — root mean squared error in the units of `y_true`."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    if y_true.size == 0:
        return 0.0
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


# ── Policy revenue metrics ─────────────────────────────────────────


def revenue_uplift(baseline_revenue: np.ndarray, model_revenue: np.ndarray) -> float:
    """Fractional uplift over baseline.

    `uplift = (mean(model) - mean(baseline)) / mean(baseline)`.
    Returns 0 when the baseline mean is zero (avoids div/0 noise)."""
    base = float(np.mean(baseline_revenue)) if len(baseline_revenue) else 0.0
    if base == 0:
        return 0.0
    model = float(np.mean(model_revenue)) if len(model_revenue) else 0.0
    return (model - base) / base


def win_rate(baseline_revenue: np.ndarray, model_revenue: np.ndarray) -> float:
    """Fraction of queries where the model strictly beats the baseline.

    Ties count as losses (conservative). When both arrays are empty,
    returns 0.0."""
    baseline_revenue = np.asarray(baseline_revenue, dtype=np.float64)
    model_revenue = np.asarray(model_revenue, dtype=np.float64)
    n = min(baseline_revenue.size, model_revenue.size)
    if n == 0:
        return 0.0
    return float(np.mean(model_revenue[:n] > baseline_revenue[:n]))


# ── Risk-adjusted return ───────────────────────────────────────────


def sharpe_ratio(revenue: np.ndarray, *, risk_free: float = 0.0) -> float:
    """Per-query Sharpe ratio: (mean - risk_free) / std.

    Returns 0 when the std is degenerate (all entries equal). The
    risk-free rate is provided in the same units as `revenue` (default 0
    — pricing doesn't have a natural risk-free; downstream chapters can
    subtract a comparable-product baseline if desired)."""
    revenue = np.asarray(revenue, dtype=np.float64)
    if revenue.size < 2:
        return 0.0
    std = float(revenue.std(ddof=1))
    if std == 0:
        return 0.0
    return (float(revenue.mean()) - risk_free) / std


def value_at_risk(revenue: np.ndarray, *, alpha: float = 0.05) -> float:
    """Value-at-Risk at confidence `alpha` (default 5%).

    Returns the *positive* downside: `mean - quantile(alpha)`. A larger
    VaR means a wider downside tail."""
    revenue = np.asarray(revenue, dtype=np.float64)
    if revenue.size == 0:
        return 0.0
    q = float(np.quantile(revenue, alpha))
    return max(0.0, float(revenue.mean()) - q)
