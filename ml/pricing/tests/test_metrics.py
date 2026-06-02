"""
Offline unit tests for the pricing metrics + Monte Carlo simulator +
constant-elasticity estimator. Pure numpy + pytest — runnable without
any of the heavy ML libs.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.pricing.data.schema import MonteCarloConfig, PriceObservation
from ml.pricing.evaluation.metrics import (
    mean_absolute_percentage_error,
    revenue_uplift,
    root_mean_squared_error,
    sharpe_ratio,
    value_at_risk,
    win_rate,
)
from ml.pricing.models.elasticity import ConstantElasticityEstimator
from ml.pricing.models.monte_carlo import MonteCarloSimulator

# ── MAPE / RMSE ──────────────────────────────────────────────────────


def test_mape_perfect_prediction_is_zero():
    y = np.array([10.0, 20.0, 30.0])
    assert mean_absolute_percentage_error(y, y) == 0.0


def test_mape_skips_zero_truth_entries():
    y_true = np.array([0.0, 10.0, 10.0])
    y_pred = np.array([5.0, 8.0, 12.0])
    # entry 0 (zero truth) is skipped → MAPE = mean(|0.2|, |0.2|) = 0.2
    assert mean_absolute_percentage_error(y_true, y_pred) == pytest.approx(0.2)


def test_mape_handworked():
    """|(100-90)/100| + |(50-40)/50| / 2 = (0.1 + 0.2) / 2 = 0.15"""
    y_true = np.array([100.0, 50.0])
    y_pred = np.array([90.0, 40.0])
    assert mean_absolute_percentage_error(y_true, y_pred) == pytest.approx(0.15)


def test_rmse_perfect_prediction_is_zero():
    y = np.array([1.0, 2.0, 3.0])
    assert root_mean_squared_error(y, y) == 0.0


def test_rmse_handworked():
    y_true = np.array([0.0, 0.0])
    y_pred = np.array([3.0, 4.0])
    # sqrt(mean(9, 16)) = sqrt(12.5) ≈ 3.5355
    assert root_mean_squared_error(y_true, y_pred) == pytest.approx(np.sqrt(12.5))


# ── Revenue uplift / win rate ────────────────────────────────────────


def test_revenue_uplift_handworked():
    base = np.array([100.0, 100.0])
    model = np.array([110.0, 120.0])
    # mean(model)=115, mean(base)=100 → 0.15
    assert revenue_uplift(base, model) == pytest.approx(0.15)


def test_revenue_uplift_zero_baseline_returns_zero():
    assert revenue_uplift(np.zeros(3), np.array([1.0, 2.0, 3.0])) == 0.0


def test_win_rate_ties_count_as_losses():
    base = np.array([10.0, 20.0, 30.0])
    model = np.array([15.0, 20.0, 25.0])  # win, tie (loss), loss → 1/3
    assert win_rate(base, model) == pytest.approx(1 / 3)


# ── Sharpe / VaR ─────────────────────────────────────────────────────


def test_sharpe_zero_std_returns_zero():
    assert sharpe_ratio(np.array([5.0, 5.0, 5.0, 5.0])) == 0.0


def test_sharpe_handworked():
    rev = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    # mean=3, std=sqrt(2.5) ≈ 1.5811 → Sharpe ≈ 1.897
    assert sharpe_ratio(rev) == pytest.approx(3.0 / np.std(rev, ddof=1), rel=1e-6)


def test_var_returns_zero_for_empty():
    assert value_at_risk(np.array([])) == 0.0


def test_var_nonnegative_for_normal_distribution():
    rng = np.random.default_rng(0)
    rev = rng.normal(100, 20, size=10_000)
    # 5% VaR should be positive (downside vs mean exists in any normal sample)
    assert value_at_risk(rev, alpha=0.05) > 0


# ── Constant-elasticity estimator ───────────────────────────────────


def test_elasticity_recovers_truth_on_synthetic_curve():
    """Synthesise demand = price^-1.5 — estimator should recover ε ≈ -1.5."""
    rng = np.random.default_rng(0)
    prices = np.exp(rng.uniform(np.log(5), np.log(50), size=200))
    demand = np.power(prices, -1.5)
    obs = [
        PriceObservation(product_id="p", price=float(p), demand=float(d))
        for p, d in zip(prices, demand, strict=False)
    ]
    est = ConstantElasticityEstimator().fit(obs)
    assert est.elasticity == pytest.approx(-1.5, rel=1e-2)


def test_elasticity_predict_demand_monotonic_decreasing():
    """An elasticity-fit curve must produce decreasing demand as price rises."""
    rng = np.random.default_rng(1)
    prices = np.exp(rng.uniform(1, 4, size=200))
    demand = np.power(prices, -2.0)
    est = ConstantElasticityEstimator().fit(
        [
            PriceObservation(product_id="p", price=float(p), demand=float(d))
            for p, d in zip(prices, demand, strict=False)
        ]
    )
    grid = np.linspace(5, 50, 25)
    pred = est.predict_demand(grid)
    assert np.all(np.diff(pred) < 0)


def test_elasticity_fit_handles_constant_observations():
    """All-identical prices → no slope; estimator defaults to ε = -1."""
    obs = [PriceObservation(product_id="p", price=10.0, demand=20.0) for _ in range(5)]
    est = ConstantElasticityEstimator().fit(obs)
    assert est.elasticity == -1.0


# ── Monte Carlo simulator ────────────────────────────────────────────


def test_monte_carlo_basic_shape():
    sim = MonteCarloSimulator()
    cfg = MonteCarloConfig(
        product_id="p",
        candidate_price=20.0,
        unit_cost=8.0,
        demand_mean=100.0,
        demand_std=10.0,
        num_trials=5_000,
        seed=42,
    )
    result = sim.simulate(cfg)
    assert result.num_trials == 5_000
    assert result.revenue_p5 <= result.revenue_p50 <= result.revenue_p95
    assert 0.0 <= result.probability_of_profit <= 1.0


def test_monte_carlo_deterministic_with_seed():
    sim = MonteCarloSimulator()
    cfg = MonteCarloConfig(
        product_id="p",
        candidate_price=20.0,
        unit_cost=5.0,
        demand_mean=100.0,
        demand_std=15.0,
        num_trials=2_000,
        seed=7,
    )
    r1 = sim.simulate(cfg)
    r2 = sim.simulate(cfg)
    assert r1.mean_revenue == r2.mean_revenue
    assert r1.revenue_p5 == r2.revenue_p5


def test_monte_carlo_high_margin_high_profit_probability():
    """Price >> cost → P(profit) should be ~1."""
    sim = MonteCarloSimulator()
    cfg = MonteCarloConfig(
        product_id="p",
        candidate_price=100.0,
        unit_cost=1.0,
        demand_mean=50.0,
        demand_std=5.0,
        num_trials=2_000,
        seed=1,
    )
    result = sim.simulate(cfg)
    assert result.probability_of_profit == pytest.approx(1.0, abs=0.01)
