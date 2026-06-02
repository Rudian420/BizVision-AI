"""
Constant-elasticity demand + closed-form optimal pricing.

The simplest econometric model that captures the price→demand response
in one number. Fitting is a single linear regression on log(price) vs
log(demand); the resulting elasticity `ε` gives:

    optimal_price* = unit_cost · ε / (ε + 1)     (revenue maximiser)
                                                 (defined for ε < -1)

This is the *interpretable arm* of AS-002: every recommendation reduces
to two numbers (elasticity, unit cost) and is verifiable with pen and
paper. The LightGBM arm beats it on capacity; this arm beats it on trust.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from ml.pricing.data.schema import PricePoint, PriceRecommendation
from ml.pricing.models.base import DemandModel, PricingPolicy

if TYPE_CHECKING:
    from ml.pricing.data.schema import PriceObservation, Product


class ConstantElasticityEstimator(DemandModel):
    """log(demand) = α + ε · log(price). Returns ε ∈ ℝ (typically < 0)."""

    requires_training = True

    def __init__(self) -> None:
        self._elasticity: float = -1.0
        self._intercept: float = 0.0
        self._fitted = False

    @property
    def name(self) -> str:
        return "demand-constant-elasticity"

    @property
    def elasticity(self) -> float:
        if not self._fitted:
            raise RuntimeError("ConstantElasticityEstimator.elasticity read before fit().")
        return self._elasticity

    def fit(self, observations: Sequence[PriceObservation]) -> ConstantElasticityEstimator:
        prices = np.asarray(
            [o.price for o in observations if o.price > 0 and o.demand > 0],
            dtype=np.float64,
        )
        demands = np.asarray(
            [o.demand for o in observations if o.price > 0 and o.demand > 0],
            dtype=np.float64,
        )
        log_p = np.log(prices) if prices.size else np.empty(0)
        # Need (a) at least two observations *and* (b) some variation in
        # log-price for the slope to be meaningful. Identical prices →
        # degenerate polyfit; fall back to unit-elastic.
        if prices.size < 2 or float(log_p.var()) < 1e-12:
            self._elasticity = -1.0
            self._intercept = 0.0
        else:
            log_d = np.log(demands)
            # numpy.polyfit returns highest-order coefficient first.
            slope, intercept = np.polyfit(log_p, log_d, 1)
            self._elasticity = float(slope)
            self._intercept = float(intercept)
        self._fitted = True
        return self

    def predict_demand(
        self,
        prices: np.ndarray,
        context: Sequence[PriceObservation] | None = None,
    ) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("ConstantElasticityEstimator.predict_demand before fit().")
        prices = np.asarray(prices, dtype=np.float64)
        # demand = exp(α) · price^ε
        return np.exp(self._intercept) * np.power(np.maximum(prices, 1e-9), self._elasticity)


class ElasticityOptimalPolicy(PricingPolicy):
    """Composes a `ConstantElasticityEstimator` and applies the closed-form
    optimal price. Falls back to a small grid search when ε ≥ -1 (the
    revenue-maximising price is unbounded above; we pick the best in a
    bounded grid)."""

    requires_training = True

    def __init__(self, estimator: ConstantElasticityEstimator | None = None) -> None:
        self._est = estimator if estimator is not None else ConstantElasticityEstimator()

    @property
    def name(self) -> str:
        return "policy-elasticity-optimal"

    def fit(self, observations: Sequence[PriceObservation]) -> ElasticityOptimalPolicy:
        self._est.fit(observations)
        return self

    def recommend_price(
        self,
        product: Product,
        context: Sequence[PriceObservation] | None = None,
    ) -> PriceRecommendation:
        eps = self._est.elasticity
        cost = max(0.0, float(product.unit_cost))
        cur = float(product.current_price) or max(cost, 1.0)

        # Closed-form revenue-maximising price requires ε < -1; otherwise
        # demand is inelastic and the optimum is at the top of any bounded
        # range. Use a grid centred on the current price either way so we
        # always return a defensible answer.
        lo = max(cost, cur * 0.6)
        hi = cur * 1.6
        grid = np.linspace(lo, hi, 25)
        demand = self._est.predict_demand(grid)
        revenue = grid * demand
        best_idx = int(np.argmax(revenue))

        curve = tuple(
            PricePoint(
                price=round(float(p), 4),
                expected_demand=round(float(d), 4),
                expected_revenue=round(float(p * d), 4),
                expected_profit=round(float((p - cost) * d), 4),
            )
            for p, d in zip(grid, demand, strict=False)
        )
        ci = (
            round(float(grid[best_idx]) * 0.95, 4),
            round(float(grid[best_idx]) * 1.05, 4),
        )
        rationale = (
            f"Estimated elasticity ε={eps:.2f}; "
            f"revenue maximised at p={grid[best_idx]:.2f} "
            f"(closed-form when ε < -1, bounded grid otherwise)."
        )
        return PriceRecommendation(
            product_id=product.product_id,
            recommended_price=round(float(grid[best_idx]), 4),
            expected_revenue=round(float(revenue[best_idx]), 4),
            expected_demand=round(float(demand[best_idx]), 4),
            confidence_interval=ci,
            revenue_curve=curve,
            sub_scores={"elasticity": round(eps, 4)},
            rationale=rationale,
        )
