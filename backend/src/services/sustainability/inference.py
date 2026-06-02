"""
Sustainability ML Inference Client.

Wraps `ml.sustainability` for the backend — the sustainability analogue
of `PricingInferenceClient` (ADR-024) and `ForecastingInferenceClient`
(TASK-016). Owns the lifecycle of the fitted scorer + carbon model:

    1. **Singleton cache** — one client per worker process; instantiated
       lazily on first call so an idle backend never imports
       `ml.sustainability` and its numpy chain.
    2. **MLflow Model Registry** — preferred source of a fitted scorer,
       loaded from the `esg-multilabel-classifier` Production stage
       when present.
    3. **Synthetic bootstrap** — if no registered model exists, fit a
       `LinearLogisticMultiLabel` on the synthetic dataset so the
       real-ML branch is exercisable even before a training run has
       been registered. Loud-logged so operators can't miss it.

The `ml.sustainability` import (with its numpy chain) happens **inside**
`_load_scorer` — when `SUSTAINABILITY_USE_REAL_ML` is off, this module
imports cleanly even in environments without numpy. The translation
layer (`ml_translation.py`) is pure-Python and *never* touches a heavy
import, so unit tests for translation run in the backend's lean dev
venv.

Endpoints handled:
  • `calculate_score(request)`   →  `/sustainability/score`
  • `estimate_carbon(request)`   →  `/sustainability/carbon-estimate`

`/simulate`, `/recommendations`, and `/benchmarks/{industry}` stay
model-free in wave 1 — same posture as pricing's `/elasticity` and
forecasting's `/sensitivity`. The sustainability service applies them
inline rather than routing through this client.

Unlike forecasting — which fits a fresh model on every request because
the inline history is part of the payload — sustainability **holds a
fitted scorer across requests** (mirrors pricing's `PricingInferenceClient`).
A request supplies only its own company profile; the scorer is trained
on historical company data the API doesn't expose.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from src.api.v1.schemas.sustainability import (
    CarbonEstimateRequest,
    CarbonEstimateResponse,
    ESGScoreRequest,
    ESGScoreResponse,
)
from src.core.logging import get_logger
from src.services.sustainability.ml_translation import (
    api_company_profile_from_score,
    ml_carbon_to_api,
    ml_score_to_api,
)

if TYPE_CHECKING:
    from ml.sustainability.data.schema import CarbonEstimate as MLCarbonEstimate
    from ml.sustainability.models.base import ESGScorer
    from ml.sustainability.models.carbon import CarbonEstimatorModel

logger = get_logger(__name__)


class _ScorerLike(Protocol):
    """Structural shape the inference client expects — mirrors
    `ml.sustainability.models.base.ESGScorer.score`."""

    @property
    def name(self) -> str: ...

    def score(self, profile): ...


class SustainabilityInferenceClient:
    """Thread-safe lazy holder for the ESG scorer + carbon model.

    Construction is cheap — heavy imports + scorer fit happen on the
    first call. The `_lock` makes first-call init safe under FastAPI's
    threadpool concurrency.
    """

    def __init__(
        self,
        *,
        scorer: _ScorerLike | None = None,
        carbon_model: CarbonEstimatorModel | None = None,
    ) -> None:
        # Injection seam for tests; production leaves these None.
        self._scorer: _ScorerLike | None = scorer
        self._carbon_model: CarbonEstimatorModel | None = carbon_model
        self._lock = threading.Lock()
        self._source: str = "uninitialised"

    @property
    def source(self) -> str:
        """`mlflow:v3` / `synthetic-bootstrap` / `injected` / `uninitialised`."""
        return self._source

    # ── 1. /score ────────────────────────────────────────────────────
    def calculate_score(
        self,
        request: ESGScoreRequest,
        *,
        assessment_id: UUID | None = None,
    ) -> ESGScoreResponse:
        scorer = self._get_scorer()
        profile = api_company_profile_from_score(request)
        result = scorer.score(profile)
        return ml_score_to_api(
            result=result, request=request, assessment_id=assessment_id
        )

    # ── 2. /carbon-estimate ─────────────────────────────────────────
    def estimate_carbon(self, request: CarbonEstimateRequest) -> CarbonEstimateResponse:
        carbon = self._get_carbon_model()
        estimate: MLCarbonEstimate = carbon.predict(
            industry=request.industry,
            annual_revenue=float(request.annual_revenue),
            energy_kwh=request.energy_kwh,
            fleet_km=request.fleet_km,
        )
        pathways = carbon.reduction_pathways(estimate)
        return ml_carbon_to_api(estimate=estimate, request=request, pathways=pathways)

    # ── internals ────────────────────────────────────────────────────
    def _get_scorer(self) -> _ScorerLike:
        if self._scorer is not None:
            return self._scorer
        with self._lock:
            if self._scorer is None:
                self._scorer, self._source = self._load_scorer()
                logger.info("Sustainability scorer initialised from {}", self._source)
        return self._scorer

    def _get_carbon_model(self) -> CarbonEstimatorModel:
        if self._carbon_model is not None:
            return self._carbon_model
        with self._lock:
            if self._carbon_model is None:
                self._carbon_model = self._load_carbon_model()
        return self._carbon_model

    def _load_scorer(self) -> tuple[ESGScorer, str]:
        """Choose a scorer source in priority order. The `ml.sustainability`
        imports live here so the backend stays importable without numpy."""
        try:
            from ml.sustainability.data.loader import generate_synthetic_dataset
            from ml.sustainability.models.multilabel import LinearLogisticMultiLabel
        except ImportError as exc:
            raise RuntimeError(
                "SUSTAINABILITY_USE_REAL_ML=True but `ml.sustainability` is "
                "not importable. Install ml/requirements.txt or run the "
                "backend inside the ml-dev container."
            ) from exc

        # ── 1. MLflow Production model, if present ────────────────
        registry_model = _load_from_registry()
        if registry_model is not None:
            scorer, version = registry_model
            return scorer, f"mlflow:{version}"

        # ── 2. Synthetic bootstrap ────────────────────────────────
        logger.warning(
            "No Production `esg-multilabel-classifier` in MLflow — "
            "bootstrapping LinearLogisticMultiLabel on synthetic data. "
            "Replace via `python -m ml.sustainability.cli train`."
        )
        dataset = generate_synthetic_dataset(n_companies=600, seed=42)
        scorer = LinearLogisticMultiLabel(n_iterations=400).fit(dataset.observations)
        return scorer, "synthetic-bootstrap"

    def _load_carbon_model(self) -> CarbonEstimatorModel:
        """Carbon model has no parameters to fit; instantiate fresh."""
        try:
            from ml.sustainability.models.carbon import CarbonEstimatorModel
        except ImportError as exc:
            raise RuntimeError(
                "SUSTAINABILITY_USE_REAL_ML=True but `ml.sustainability` is "
                "not importable."
            ) from exc
        return CarbonEstimatorModel()


# ── module-level helpers (importable by tests) ──────────────────────


def _load_from_registry() -> tuple[Any, str] | None:
    """Try MLflow Model Registry; swallow errors so a missing tracking
    server falls back to the synthetic bootstrap rather than crashing."""
    try:
        from ml.sustainability.registry.model_registry import latest_production

        version = latest_production()
        if version is None:
            return None
        import mlflow.pyfunc

        loaded = mlflow.pyfunc.load_model(version.source)
        return loaded, str(version.version)
    except Exception as exc:  # pragma: no cover - depends on live MLflow
        logger.info("MLflow Model Registry unavailable ({}); using bootstrap.", exc)
        return None


# ── Module-level singleton ──────────────────────────────────────────


_client_singleton: SustainabilityInferenceClient | None = None
_singleton_lock = threading.Lock()


def get_inference_client() -> SustainabilityInferenceClient:
    """Return the process-wide sustainability inference client."""
    global _client_singleton
    if _client_singleton is None:
        with _singleton_lock:
            if _client_singleton is None:
                _client_singleton = SustainabilityInferenceClient()
    return _client_singleton


def reset_inference_client(client: SustainabilityInferenceClient | None = None) -> None:
    """Replace the singleton — testing seam only. Pass `None` to clear."""
    global _client_singleton
    with _singleton_lock:
        _client_singleton = client
