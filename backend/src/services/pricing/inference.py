"""
Pricing ML Inference Client.

Wraps `ml.pricing` for the backend — the pricing analogue of
`RecruitmentInferenceClient` (ADR-024). Owns the lifecycle of the
fitted policy + simulator + elasticity estimator:

    1. **Singleton cache** — one client per worker process; instantiated
       lazily on first call so an idle backend never imports lightgbm
       / torch / gymnasium.
    2. **MLflow Model Registry** — preferred source of a fitted policy,
       loaded from the `smart-pricing-policy` Production stage when
       present.
    3. **Synthetic bootstrap** — if no registered model exists, fit a
       LightGBM-grid policy on the synthetic dataset so the backend
       isn't dead on a fresh deploy. Logged loudly; replaced as soon as
       a real training run lands.

The `ml.pricing` import (with its lightgbm / sb3 / shap chain) happens
**inside** `_load_policy` — when `PRICING_USE_REAL_ML` is off, this
module imports cleanly even in environments without those deps. The
translation layer (`ml_translation.py`) is pure-Python and *never*
touches a heavy import, so unit tests for translation run in the
backend's lean dev venv.

Endpoints handled:
  • `recommend_price(request)`   →  `/pricing/optimize`
  • `simulate(request)`          →  `/pricing/simulate`
  • `estimate_elasticity(request)` →  `/pricing/elasticity`
  • `compare_scenarios(request)`  →  `/pricing/scenarios`

The latter two are stateless (don't need a fitted policy) so they work
in `PRICING_USE_REAL_ML=true` mode even before MLflow has a Production
model.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from src.api.v1.schemas.pricing import (
    ElasticityAnalysisRequest,
    ElasticityAnalysisResponse,
    MonteCarloSimulationRequest,
    MonteCarloSimulationResponse,
    PriceOptimizationRequest,
    PriceOptimizationResponse,
    ScenarioComparisonRequest,
    ScenarioComparisonResponse,
)
from src.core.logging import get_logger
from src.services.pricing.ml_translation import (
    api_monte_carlo_config,
    api_observations_from_elasticity,
    api_product_from_optimize,
    api_product_from_scenarios,
    ml_elasticity_to_api,
    ml_monte_carlo_to_api,
    ml_recommendation_to_api,
    ml_scenarios_to_api,
)

if TYPE_CHECKING:
    from ml.pricing.models.base import PricingPolicy

logger = get_logger(__name__)


class _PolicyLike(Protocol):
    """Structural shape the inference client expects from a policy —
    mirrors `ml.pricing.models.base.PricingPolicy.recommend_price`."""

    def recommend_price(self, product, context=None): ...


class PricingInferenceClient:
    """Thread-safe lazy holder for the pricing policy.

    Construction is cheap — heavy imports + policy fit happen on the
    first call to `recommend_price`. The `_lock` makes first-call init
    safe under FastAPI's threadpool concurrency.
    """

    def __init__(self, *, policy: _PolicyLike | None = None) -> None:
        # Injection seam for tests; production leaves it None.
        self._policy: _PolicyLike | None = policy
        self._lock = threading.Lock()
        self._source: str = "uninitialised"

    # ── public API: 4 methods, one per endpoint ────────────────────
    def recommend_price(
        self,
        request: PriceOptimizationRequest,
        *,
        analysis_id: UUID | None = None,
    ) -> PriceOptimizationResponse:
        policy = self._get_policy()
        product = api_product_from_optimize(request)
        recommendation = policy.recommend_price(product)
        return ml_recommendation_to_api(
            recommendation=recommendation,
            request=request,
            analysis_id=analysis_id,
        )

    def simulate(
        self,
        request: MonteCarloSimulationRequest,
        *,
        analysis_id: UUID | None = None,
    ) -> MonteCarloSimulationResponse:
        # Stateless — no policy needed.
        from ml.pricing.models.monte_carlo import MonteCarloSimulator

        config = api_monte_carlo_config(request)
        result = MonteCarloSimulator().simulate(config)
        return ml_monte_carlo_to_api(result=result, request=request, analysis_id=analysis_id)

    def estimate_elasticity(
        self,
        request: ElasticityAnalysisRequest,
        *,
        analysis_id: UUID | None = None,
    ) -> ElasticityAnalysisResponse:
        # Stateless — fresh estimator per call (the API supplies its own
        # `(price_points, observed_demand)` pairs).
        from ml.pricing.models.elasticity import ConstantElasticityEstimator

        observations = api_observations_from_elasticity(request)
        est = ConstantElasticityEstimator().fit(observations)
        return ml_elasticity_to_api(
            elasticity=est.elasticity, request=request, analysis_id=analysis_id
        )

    def compare_scenarios(
        self,
        request: ScenarioComparisonRequest,
        *,
        analysis_id: UUID | None = None,
    ) -> ScenarioComparisonResponse:
        policy = self._get_policy()
        product = api_product_from_scenarios(request)
        scenarios = _build_scenarios(product, policy)
        return ml_scenarios_to_api(scenarios=scenarios, request=request, analysis_id=analysis_id)

    @property
    def source(self) -> str:
        """`mlflow:v3` / `synthetic-bootstrap` / `injected` / `uninitialised`."""
        return self._source

    # ── internals ───────────────────────────────────────────────────
    def _get_policy(self) -> _PolicyLike:
        if self._policy is not None:
            return self._policy
        with self._lock:
            if self._policy is None:
                self._policy, self._source = self._load_policy()
                logger.info("Pricing policy initialised from {}", self._source)
        return self._policy

    def _load_policy(self) -> tuple[PricingPolicy, str]:
        """Choose a policy source in priority order. The `ml.pricing`
        imports live here so the backend stays importable without the ML
        deps."""
        try:
            from ml.pricing.training.config import PricingTrainingConfig
            from ml.pricing.training.pipeline import train_pipeline
        except ImportError as exc:
            raise RuntimeError(
                "PRICING_USE_REAL_ML=True but `ml.pricing` is not importable. "
                "Install ml/requirements.txt or run the backend inside the "
                "ml-dev container."
            ) from exc

        # ── 1. MLflow Production model, if present ────────────────
        registry_model = _load_from_registry()
        if registry_model is not None:
            policy, version = registry_model
            return policy, f"mlflow:{version}"

        # ── 2. Synthetic bootstrap ────────────────────────────────
        # Train a LightGBM-grid policy on the synthetic dataset so the
        # real-ML branch is exercisable even before a training run has
        # been registered. Loud-logged so operators can't miss it.
        logger.warning(
            "No Production `smart-pricing-policy` in MLflow — "
            "bootstrapping LightGBM-grid on synthetic data. Replace via "
            "`python -m ml.pricing.cli train`."
        )
        cfg = PricingTrainingConfig(n_synthetic_observations=1_500, seed=42)
        policy = _build_bootstrap_policy(cfg)
        # train_pipeline is reused so MLflow tagging stays consistent;
        # the bootstrap policy we return is fitted directly so the
        # first inference doesn't pay the cost twice.
        try:
            _ = train_pipeline(cfg)  # logs to MLflow; we ignore the result
        except Exception as exc:  # pragma: no cover - defensive
            logger.info("Bootstrap MLflow log failed ({}); continuing.", exc)
        return policy, "synthetic-bootstrap"


# ── module-level helpers (importable by tests) ──────────────────────


def _build_scenarios(product, policy: _PolicyLike) -> dict:
    """Apply three multipliers to the current price and convert each into
    an `ml.pricing.PriceRecommendation` via the policy."""
    from ml.pricing.data.schema import Product as MLProductImpl

    def _scoped(multiplier: float):
        scoped_product = MLProductImpl(
            product_id=product.product_id,
            unit_cost=float(product.unit_cost),
            current_price=float(product.current_price) * multiplier,
            competitor_prices=product.competitor_prices,
        )
        return policy.recommend_price(scoped_product)

    return {
        "conservative": _scoped(0.95),
        "optimal": _scoped(1.08),
        "aggressive": _scoped(1.20),
    }


def _load_from_registry() -> tuple[PricingPolicy, str] | None:
    """Try MLflow Model Registry; swallow errors so a missing tracking
    server falls back to the synthetic bootstrap rather than crashing."""
    try:
        from ml.pricing.registry.model_registry import latest_production

        version = latest_production()
        if version is None:
            return None
        import mlflow.pyfunc

        loaded = mlflow.pyfunc.load_model(version.source)
        return loaded, str(version.version)
    except Exception as exc:  # pragma: no cover - depends on live MLflow
        logger.info("MLflow Model Registry unavailable ({}); using bootstrap.", exc)
        return None


def _build_bootstrap_policy(cfg) -> PricingPolicy:
    """Fit a LightGBM-grid policy on the synthetic dataset; return the
    fitted instance directly for first-call use."""
    from ml.pricing.data.loader import PricingDataLoader
    from ml.pricing.models.demand import LightGBMGridPolicy

    loader = PricingDataLoader()
    dataset = loader.load_synthetic(n_observations=cfg.n_synthetic_observations, seed=cfg.seed)
    policy = LightGBMGridPolicy()
    policy.fit(dataset.observations)
    return policy


# ── Module-level singleton ──────────────────────────────────────────
# Created once per process. Construction is cheap (no heavy imports);
# `recommend_price` / `compare_scenarios` trigger the first load.


_client_singleton: PricingInferenceClient | None = None
_singleton_lock = threading.Lock()


def get_inference_client() -> PricingInferenceClient:
    """Return the process-wide pricing inference client."""
    global _client_singleton
    if _client_singleton is None:
        with _singleton_lock:
            if _client_singleton is None:
                _client_singleton = PricingInferenceClient()
    return _client_singleton


def reset_inference_client(client: PricingInferenceClient | None = None) -> None:
    """Replace the singleton — testing seam only. Pass `None` to clear."""
    global _client_singleton
    with _singleton_lock:
        _client_singleton = client
