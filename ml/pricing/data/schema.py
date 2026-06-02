"""
Pricing data schemas.

Pure dataclasses — no heavy imports. Mirrors `ml.recruitment.data.schema`
so the cross-module pattern stays recognisable: every package's `data`
sub-module holds frozen dataclasses, the loader produces a `*Dataset`
container, and downstream code consumes these without dragging in pandas
/ numpy at import time.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Product:
    """A single product / SKU under pricing consideration."""

    product_id: str
    category: str | None = None
    unit_cost: float = 0.0
    current_price: float = 0.0
    competitor_prices: tuple[float, ...] = ()
    location: str | None = None
    seasonal_factor: float = 1.0  # 1.0 = neutral; >1.0 = peak; <1.0 = trough


@dataclass(frozen=True)
class PriceObservation:
    """One historical (price, demand) data point for a product.

    `season` is an integer category (0=Q1, 1=Q2, ...) used as a structured
    feature by the boosting demand model — see `features.structured`.
    """

    product_id: str
    price: float
    demand: float
    season: int = 0
    competitor_price: float | None = None
    promotion: bool = False
    timestamp: str | None = None  # ISO-8601 string, optional


@dataclass(frozen=True)
class PricingScenario:
    """A what-if scenario: a `Product` plus a candidate price."""

    product: Product
    candidate_price: float
    label: str = "scenario"  # 'conservative' | 'optimal' | 'aggressive' | ...


@dataclass(frozen=True)
class MonteCarloConfig:
    """Parameters for the revenue Monte Carlo simulator."""

    product_id: str
    candidate_price: float
    unit_cost: float = 0.0
    demand_mean: float = 100.0
    demand_std: float = 10.0
    num_trials: int = 10_000
    seed: int | None = None


@dataclass(frozen=True)
class PricePoint:
    """One point on the revenue curve (mirrors the API schema)."""

    price: float
    expected_demand: float
    expected_revenue: float
    expected_profit: float


@dataclass(frozen=True)
class PriceRecommendation:
    """Structured output of a `PricingPolicy.recommend_price` call.

    `sub_scores` carries the SHAP attribution top-K (game-theoretic
    Shapley values from the LightGBM TreeExplainer), per TASK-042.
    `lime_attributions` carries a second, complementary view: local
    linear coefficients from a LIME tabular explainer (TASK-044 /
    FE-016). Both are pure-Python dicts of `feature_name → float` so
    downstream translators stay decoupled from the explainer
    implementations.
    """

    product_id: str
    recommended_price: float
    expected_revenue: float
    expected_demand: float
    confidence_interval: tuple[float, float]
    revenue_curve: tuple[PricePoint, ...] = ()
    sub_scores: dict[str, float] = field(default_factory=dict)
    lime_attributions: dict[str, float] = field(default_factory=dict)
    rationale: str = ""
