"""
LightGBM demand model + grid-search pricing policy.

EXP-PRC-001. The LightGBM regressor sees the engineered tabular features
(`features.structured.FEATURE_NAMES`) and predicts demand at arbitrary
price points. `LightGBMGridPolicy` wraps it: at recommendation time it
constructs a price grid bounded by `(0.6 · current, 1.6 · current)`,
predicts demand at each, multiplies to get revenue, and returns the
argmax. This is the *capacity* arm of AS-002 — captures non-linear
price/competitor/season interactions that constant elasticity misses.

`lightgbm` is imported lazily inside `fit` so the module imports cleanly
in environments without it (CI lint, backend container).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from ml.pricing.data.schema import PriceObservation, PricePoint, PriceRecommendation
from ml.pricing.features.structured import FEATURE_NAMES, build_feature_matrix
from ml.pricing.models.base import DemandModel, PricingPolicy

if TYPE_CHECKING:
    from ml.pricing.data.schema import Product

# Sensible defaults; the ablation runner overrides via `__init__(**params)`.
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 400,
    "max_depth": -1,
    "num_leaves": 31,
    "learning_rate": 0.05,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "min_child_samples": 20,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "objective": "regression",
    "metric": "rmse",
    "verbosity": -1,
}


class LightGBMDemandModel(DemandModel):
    requires_training = True

    def __init__(self, **params: Any) -> None:
        self._params = {**DEFAULT_PARAMS, **params}
        self._model: Any | None = None

    @property
    def name(self) -> str:
        return "demand-lightgbm"

    @property
    def model(self) -> Any:
        """Expose the fitted booster for the SHAP adapter."""
        if self._model is None:
            raise RuntimeError("LightGBMDemandModel.model read before fit().")
        return self._model

    @property
    def feature_names(self) -> tuple[str, ...]:
        return FEATURE_NAMES

    def fit(self, observations: Sequence[PriceObservation]) -> LightGBMDemandModel:
        from lightgbm import LGBMRegressor

        x = build_feature_matrix(observations)
        y = np.asarray([o.demand for o in observations], dtype=np.float64)
        self._model = LGBMRegressor(**self._params)
        self._model.fit(x, y)
        return self

    def predict_demand(
        self,
        prices: np.ndarray,
        context: Sequence[PriceObservation] | None = None,
    ) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("LightGBMDemandModel.predict_demand before fit().")
        prices = np.asarray(prices, dtype=np.float64)

        if context is None:
            # Synthesise neutral context for each price point.
            context = [PriceObservation(product_id="", price=float(p), demand=0.0) for p in prices]
        else:
            # Override the price field in each context row with the query price.
            context = [
                PriceObservation(
                    product_id=c.product_id,
                    price=float(p),
                    demand=0.0,
                    season=c.season,
                    competitor_price=c.competitor_price,
                    promotion=c.promotion,
                )
                for p, c in zip(prices, context, strict=False)
            ]
        x = build_feature_matrix(context)
        return np.asarray(self._model.predict(x), dtype=np.float64)


class LightGBMGridPolicy(PricingPolicy):
    """Wraps a `LightGBMDemandModel`; grid-search recommends the
    revenue-maximising price within `(0.6·current, 1.6·current)`."""

    requires_training = True

    def __init__(
        self,
        demand_model: LightGBMDemandModel | None = None,
        *,
        grid_size: int = 25,
    ) -> None:
        self._demand = demand_model if demand_model is not None else LightGBMDemandModel()
        self._grid_size = max(2, int(grid_size))

    @property
    def name(self) -> str:
        return "policy-lightgbm-grid"

    def fit(self, observations: Sequence[PriceObservation]) -> LightGBMGridPolicy:
        self._demand.fit(observations)
        return self

    def recommend_price(
        self,
        product: Product,
        context: Sequence[PriceObservation] | None = None,
    ) -> PriceRecommendation:
        cost = max(0.0, float(product.unit_cost))
        cur = float(product.current_price) or max(cost, 1.0)
        lo = max(cost, cur * 0.6)
        hi = cur * 1.6

        grid = np.linspace(lo, hi, self._grid_size)
        # Build a context row at the current product's competitor price /
        # default season for each grid point so the demand model sees a
        # consistent non-price context.
        comp_price = float(product.competitor_prices[0]) if product.competitor_prices else None
        ctx = [
            PriceObservation(
                product_id=product.product_id,
                price=float(p),
                demand=0.0,
                season=0,
                competitor_price=comp_price,
                promotion=False,
            )
            for p in grid
        ]
        demand = self._demand.predict_demand(grid, context=ctx)
        demand = np.maximum(demand, 0.0)
        revenue = grid * demand
        best = int(np.argmax(revenue))

        curve = tuple(
            PricePoint(
                price=round(float(p), 4),
                expected_demand=round(float(d), 4),
                expected_revenue=round(float(p * d), 4),
                expected_profit=round(float((p - cost) * d), 4),
            )
            for p, d in zip(grid, demand, strict=False)
        )

        # SHAP attribution for the best price point.
        # Why: the API translator (`ml_recommendation_to_api`) projects
        # `sub_scores` directly into `top_shap_features` for the UI's
        # "why this price?" panel. Computing SHAP here keeps the
        # attribution tied to the same fitted booster that produced the
        # recommendation. Swallow on failure so the recommendation still
        # ships even if the SHAP backend (lightgbm/shap version drift)
        # rejects the input.
        sub_scores = _shap_sub_scores_for_best(self._demand, ctx, best, top_k=6)

        # LIME attribution — same input, different explainer (TASK-044 /
        # FE-016). Lets the UI render SHAP and LIME side-by-side so the
        # thesis claim of "robust explanation = two independent
        # explainers agree on the top drivers" is demonstrable.
        lime_attributions = _lime_sub_scores_for_best(
            self._demand, ctx, best, top_k=6
        )

        return PriceRecommendation(
            product_id=product.product_id,
            recommended_price=round(float(grid[best]), 4),
            expected_revenue=round(float(revenue[best]), 4),
            expected_demand=round(float(demand[best]), 4),
            confidence_interval=(
                round(float(grid[best]) * 0.95, 4),
                round(float(grid[best]) * 1.05, 4),
            ),
            revenue_curve=curve,
            sub_scores=sub_scores,
            lime_attributions=lime_attributions,
            rationale=(
                f"LightGBM demand model + {len(grid)}-point grid; "
                f"revenue maximised at p={grid[best]:.2f}."
            ),
        )


def _shap_sub_scores_for_best(
    demand_model: LightGBMDemandModel,
    ctx: Sequence[PriceObservation],
    best: int,
    *,
    top_k: int,
) -> dict[str, float]:
    """Compute SHAP attributions for `ctx[best]`, return the top-`k`
    `(feature_name → shap_value)` ranked by |shap| descending.

    Returns `{}` on any failure so the recommendation still ships
    (the API `top_shap_features` list will just be empty, which the
    frontend handles gracefully — same UX as the mock path's previous
    behaviour). Logs the failure quietly via the logger module so
    operators can spot a misconfigured SHAP backend without seeing it
    bubble up as a 500."""
    try:
        from ml.pricing.explainability.shap_adapter import PricingSHAPExplainer

        x_best = build_feature_matrix([ctx[best]])[0]
        attribution = PricingSHAPExplainer(demand_model).explain(x_best)
        order = np.argsort(-np.abs(attribution.shap_values))[:top_k]
        return {
            FEATURE_NAMES[int(i)]: round(float(attribution.shap_values[int(i)]), 6)
            for i in order
        }
    except Exception:  # pragma: no cover - defensive
        import logging

        logging.getLogger(__name__).info(
            "PricingSHAPExplainer.explain failed; returning empty sub_scores",
            exc_info=True,
        )
        return {}


def _lime_sub_scores_for_best(
    demand_model: LightGBMDemandModel,
    ctx: Sequence[PriceObservation],
    best: int,
    *,
    top_k: int,
) -> dict[str, float]:
    """Compute LIME attributions for `ctx[best]`, return the top-`k`
    `(feature_name → weight)` ranked by |weight| descending.

    LIME needs a small "training-like" sample to fit its perturbation
    distribution — we reuse the full `ctx` matrix (the grid of price
    points at the current product's competitor / season context),
    which is exactly the local neighbourhood the explainer should
    perturb around. Returns `{}` on any failure (mirrors the SHAP
    helper's contract — the UI handles an empty `top_lime_features`
    list as the empty-state)."""
    try:
        from ml.pricing.explainability.lime_adapter import PricingLIMEExplainer

        ctx_matrix = build_feature_matrix(ctx)
        x_best = ctx_matrix[best]
        explainer = PricingLIMEExplainer(demand_model, background=ctx_matrix)
        attribution = explainer.explain(x_best)
        order = np.argsort(-np.abs(attribution.weights))[:top_k]
        return {
            FEATURE_NAMES[int(i)]: round(float(attribution.weights[int(i)]), 6)
            for i in order
        }
    except Exception:  # pragma: no cover - defensive
        import logging

        logging.getLogger(__name__).info(
            "PricingLIMEExplainer.explain failed; returning empty lime_attributions",
            exc_info=True,
        )
        return {}
