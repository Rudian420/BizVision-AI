"""
Baseline pricing policies — the floors AS-002 must beat.

ConstantPricePolicy and CompetitorMatchPolicy are *unsupervised* (they
ignore training data) but still implement `fit` so the benchmark
harness's call site is uniform across arms — same convention as
`ml.recruitment.models.baselines.RandomRanker`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ml.pricing.data.schema import PriceRecommendation
from ml.pricing.models.base import PricingPolicy

if TYPE_CHECKING:
    from ml.pricing.data.schema import PriceObservation, Product


class ConstantPricePolicy(PricingPolicy):
    """Always recommend the product's current price. The sanity floor any
    other policy must out-perform on revenue uplift."""

    requires_training = False

    @property
    def name(self) -> str:
        return "baseline-constant-price"

    def fit(self, observations: Sequence[PriceObservation]) -> ConstantPricePolicy:
        return self

    def recommend_price(
        self,
        product: Product,
        context: Sequence[PriceObservation] | None = None,
    ) -> PriceRecommendation:
        return PriceRecommendation(
            product_id=product.product_id,
            recommended_price=float(product.current_price),
            expected_revenue=0.0,
            expected_demand=0.0,
            confidence_interval=(
                float(product.current_price),
                float(product.current_price),
            ),
            rationale="Status quo — current price retained.",
        )


class CompetitorMatchPolicy(PricingPolicy):
    """Match the lowest competitor price (a classic lexical-retrieval-style
    baseline for pricing — reactive, no demand model involved)."""

    requires_training = False

    @property
    def name(self) -> str:
        return "baseline-competitor-match"

    def fit(self, observations: Sequence[PriceObservation]) -> CompetitorMatchPolicy:
        return self

    def recommend_price(
        self,
        product: Product,
        context: Sequence[PriceObservation] | None = None,
    ) -> PriceRecommendation:
        if not product.competitor_prices:
            # No signal → fall back to current price.
            price = float(product.current_price)
            rationale = "No competitor signal — falling back to current price."
        else:
            price = float(min(product.competitor_prices))
            rationale = (
                f"Matching lowest of {len(product.competitor_prices)} "
                f"competitor price(s): {price:.2f}."
            )
        return PriceRecommendation(
            product_id=product.product_id,
            recommended_price=price,
            expected_revenue=0.0,
            expected_demand=0.0,
            confidence_interval=(price, price),
            rationale=rationale,
        )
