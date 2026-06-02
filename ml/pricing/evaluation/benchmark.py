"""
Benchmark harness — fit each policy on `train`, evaluate on `test`'s
held-out products, report revenue uplift / MAPE / Sharpe.

Test design: every product in `test` is scored against every policy.
The *baseline revenue* for each product is the policy `ConstantPricePolicy`
recommendation × the demand predicted by the held-out
`ConstantElasticityEstimator` fit on the test pool. This makes the
benchmark comparable across runs — the demand model used to *score*
recommendations is independent of any policy that *makes* them.

ADR-022's uniform-interface principle: the harness is generic over any
`PricingPolicy`, same as recruitment's harness over any `RankingModel`.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ml.pricing.data.schema import PriceObservation, Product
from ml.pricing.evaluation.metrics import (
    revenue_uplift,
    sharpe_ratio,
    value_at_risk,
    win_rate,
)
from ml.pricing.models.base import PricingPolicy
from ml.pricing.models.elasticity import ConstantElasticityEstimator


@dataclass
class BenchmarkResult:
    metrics: dict[str, dict[str, float]]
    raw: dict[str, dict[str, np.ndarray]]
    runtime: dict[str, dict[str, float]]

    def to_dataframe(self):
        import pandas as pd

        return pd.DataFrame(self.metrics).T


def run_benchmark(
    policies: Sequence[PricingPolicy],
    *,
    train: Sequence[PriceObservation],
    test_products: Sequence[Product],
    test_observations: Sequence[PriceObservation],
) -> BenchmarkResult:
    """Run AS-002's comparison.

    `train`              — observations every policy fits on.
    `test_products`      — products to score (each policy recommends one
                            price per product).
    `test_observations`  — held-out observations the evaluation demand
                            model is fit on (independent of policy choice).
    """
    eval_demand = ConstantElasticityEstimator().fit(test_observations)

    metrics: dict[str, dict[str, float]] = {}
    raw: dict[str, dict[str, np.ndarray]] = {}
    runtime: dict[str, dict[str, float]] = {}

    # Baseline arm: always score "current price" → demand from eval model.
    baseline_prices = np.asarray([float(p.current_price) for p in test_products], dtype=np.float64)
    baseline_demand = eval_demand.predict_demand(baseline_prices)
    baseline_revenue = baseline_prices * baseline_demand

    for policy in policies:
        t0 = time.perf_counter()
        if policy.requires_training:
            policy.fit(train)
        t_fit = time.perf_counter() - t0

        # Recommendation per product → score by eval demand model.
        t0 = time.perf_counter()
        prices = np.zeros(len(test_products), dtype=np.float64)
        for i, prod in enumerate(test_products):
            rec = policy.recommend_price(prod)
            prices[i] = float(rec.recommended_price)
        demand = eval_demand.predict_demand(prices)
        revenue = prices * demand
        t_infer = time.perf_counter() - t0

        metrics[policy.name] = {
            "revenue_uplift_pct": revenue_uplift(baseline_revenue, revenue),
            "mean_revenue": float(revenue.mean()) if revenue.size else 0.0,
            "win_rate_vs_baseline": win_rate(baseline_revenue, revenue),
            "sharpe": sharpe_ratio(revenue),
            "var_5pct": value_at_risk(revenue, alpha=0.05),
        }
        raw[policy.name] = {
            "prices": prices,
            "demand": demand,
            "revenue": revenue,
        }
        runtime[policy.name] = {"fit_s": t_fit, "infer_s": t_infer}

    # Add the baseline as a row in the result so the dataframe is
    # self-contained.
    metrics["__baseline_constant__"] = {
        "revenue_uplift_pct": 0.0,
        "mean_revenue": float(baseline_revenue.mean()) if baseline_revenue.size else 0.0,
        "win_rate_vs_baseline": 0.0,
        "sharpe": sharpe_ratio(baseline_revenue),
        "var_5pct": value_at_risk(baseline_revenue, alpha=0.05),
    }
    raw["__baseline_constant__"] = {
        "prices": baseline_prices,
        "demand": baseline_demand,
        "revenue": baseline_revenue,
    }
    runtime["__baseline_constant__"] = {"fit_s": 0.0, "infer_s": 0.0}

    return BenchmarkResult(metrics=metrics, raw=raw, runtime=runtime)
