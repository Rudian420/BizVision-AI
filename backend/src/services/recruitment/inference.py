"""
Recruitment ML Inference Client.

Wraps `ml.recruitment` for the backend (ADR-024). Owns the lifecycle of
the fitted ranker:

    1. **Singleton cache** — one ensemble per process; instantiated lazily
       on first call so an idle backend never imports torch.
    2. **MLflow Model Registry** — preferred source of a fitted ranker;
       loaded from the `recruitment-ranker` Production stage when present.
    3. **Synthetic bootstrap** — if no registered model exists, fit on
       the synthetic dataset so the backend isn't dead on a fresh deploy.
       Logged loudly; replaced as soon as a real training run lands.

The `ml.recruitment` import (with its torch / xgboost / sentence-transformers
chain) happens **inside** `_load_ranker` — when `RECRUITMENT_USE_REAL_ML`
is off, this module imports cleanly even in environments without the ML
deps. The translation layer (`ml_translation.py`) is pure-Python and
*never* touches a heavy import, so unit tests for translation run in the
backend's lean dev venv.

This integration is intentionally **synchronous in-process** for now;
ADR-024 documents the Celery offload that will arrive when SBERT inference
latency on a real workload pushes us over the 500 ms response budget.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Protocol

from src.core.logging import get_logger
from src.services.recruitment.ml_translation import (
    api_request_to_ml,
    ml_score_to_api_ranking,
)

if TYPE_CHECKING:
    import numpy as np

    from ml.recruitment.models.base import RankingModel
    from ml.recruitment.models.structured import XGBoostRanker
    from src.api.v1.schemas.recruitment import (
        CandidateRankingResult,
        RecruitmentAnalysisRequest,
        SHAPFeatureAttribution,
    )

logger = get_logger(__name__)


class _RankerLike(Protocol):
    """Structural shape the inference client expects from a ranker.

    Mirrors `ml.recruitment.models.base.RankingModel.score_with_detail` so
    a unit test can pass a hand-rolled stub without importing the heavy ML
    chain just to satisfy a type."""

    def score_with_detail(self, jd, candidates): ...


class RecruitmentInferenceClient:
    """Thread-safe lazy holder for a fitted ranker.

    Construction is cheap — heavy imports + model loading happen on the
    first `score_candidates` call. The `_lock` makes the first-call init
    safe under FastAPI's threadpool concurrency.
    """

    def __init__(self, *, ranker: _RankerLike | None = None) -> None:
        # `ranker` injection is for unit tests; production leaves it None
        # and lets `_get_ranker` choose between MLflow and synthetic bootstrap.
        self._ranker: _RankerLike | None = ranker
        self._lock = threading.Lock()
        self._source: str = "uninitialised"
        # TASK-049 / FE-016 wave 3a — LIME explainability over the
        # structured XGBoost arm. The boost ranker + training-feature
        # background are captured during the synthetic-bootstrap or
        # MLflow load so the LIME adapter has something to perturb
        # around. The explainer itself is lazily built on first
        # `_get_lime_explainer()` call (same singleton posture as the
        # ranker itself). Stays None when LIME isn't wireable (e.g. a
        # test stub that injects only `_ranker`).
        self._xgb_ranker: XGBoostRanker | None = None
        self._lime_background: np.ndarray | None = None
        self._lime_explainer: Any | None = None

    # ── public API ────────────────────────────────────────────────
    def score_candidates(self, request: RecruitmentAnalysisRequest) -> list[CandidateRankingResult]:
        """Score every candidate in `request`; returns API-ranking results
        sorted by composite score descending. Does **not** apply `top_k`
        — the caller (`recruitment_service.analyze`) persists the full
        ranking and slices for the response."""
        ranker = self._get_ranker()

        job, candidates = api_request_to_ml(request)
        details = ranker.score_with_detail(job, candidates)
        # Defensive sort — the ranker interface doesn't promise an ordering.
        details_sorted = sorted(details, key=lambda d: d.score, reverse=True)

        # Per-candidate LIME features over the XGBoost arm — wave 3a.
        # Computed eagerly here rather than lazily in the translator
        # because the explainer needs the actual feature matrix
        # `build_feature_matrix(job, candidates)`, which the translator
        # has no access to (it speaks Pydantic, not `ml.recruitment`).
        # Failures fall through to an empty `lime_by_candidate` dict
        # so a misconfigured LIME backend doesn't take the ranking
        # response down — `top_lime_features` will just be empty for
        # every candidate, same UX as wave-3's mock-vs-real split.
        lime_by_candidate = self._lime_features_for_candidates(job, candidates)

        candidate_in_by_id = {c.candidate_id: c for c in request.candidates}
        return ml_score_to_api_ranking(
            details_sorted,
            candidate_in_by_id=candidate_in_by_id,
            anonymize_names=request.anonymize_names,
            required_skills=tuple(request.job_description.required_skills or ()),
            preferred_skills=tuple(request.job_description.preferred_skills or ()),
            lime_by_candidate=lime_by_candidate,
        )

    def _lime_features_for_candidates(
        self, job: Any, candidates: list[Any]
    ) -> dict[str, list[SHAPFeatureAttribution]]:
        """Return `{candidate_id: [SHAPFeatureAttribution, ...]}` from the
        LIME explainer over the structured XGBoost arm.

        Returns an empty dict on any failure (LIME not available, no
        XGBoost ranker captured, explainer init failure, per-call
        failure). The translator handles a missing candidate_id by
        emitting `top_lime_features=[]` — same defensive UX as
        wave-3's mock-vs-real split."""
        explainer = self._get_lime_explainer()
        if explainer is None:
            return {}
        try:
            from ml.recruitment.features.structured import build_feature_matrix
        except Exception:  # pragma: no cover - depends on ml.recruitment availability
            return {}
        try:
            X = build_feature_matrix(job, candidates)
        except Exception:  # pragma: no cover - defensive
            logger.info("LIME feature-matrix build failed; skipping LIME attribution.")
            return {}

        from src.api.v1.schemas.recruitment import SHAPFeatureAttribution as _Attr

        out: dict[str, list[SHAPFeatureAttribution]] = {}
        for cand, row in zip(candidates, X, strict=False):
            try:
                explanation = explainer.explain(row, candidate_id=cand.candidate_id)
            except Exception:  # pragma: no cover - per-call defensive
                continue
            attrs: list[SHAPFeatureAttribution] = []
            for rank, rule in enumerate(explanation.rules, start=1):
                weight = float(rule.weight)
                attrs.append(
                    _Attr(
                        feature_name=str(rule.condition),
                        shap_value=round(weight, 4),
                        feature_value=round(weight, 4),
                        contribution_direction="positive" if weight >= 0 else "negative",
                        importance_rank=rank,
                    )
                )
            out[cand.candidate_id] = attrs
        return out

    def _get_lime_explainer(self) -> Any | None:
        """Lazily build the LIME explainer the first time it's needed.

        Returns None when either the XGBoost arm or the training-
        feature background isn't available (e.g. test stub injected a
        ranker directly). The lock guards the same first-call init
        race that protects `_get_ranker`."""
        if self._lime_explainer is not None:
            return self._lime_explainer
        if self._xgb_ranker is None or self._lime_background is None:
            return None
        with self._lock:
            if self._lime_explainer is not None:
                return self._lime_explainer
            try:
                from ml.recruitment.explainability.lime_adapter import (
                    LIMERecruitmentExplainer,
                )
            except Exception:  # pragma: no cover - defensive
                return None
            try:
                self._lime_explainer = LIMERecruitmentExplainer(
                    ranker=self._xgb_ranker,
                    training_features=self._lime_background,
                )
                logger.info(
                    "Recruitment LIME explainer initialised over XGBoost arm "
                    "with {} background rows.",
                    len(self._lime_background),
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.info("LIME explainer init failed ({}); LIME will be empty.", exc)
                return None
        return self._lime_explainer

    @property
    def source(self) -> str:
        """Human-readable provenance: `mlflow:v3` / `synthetic-bootstrap` / `injected`."""
        return self._source

    # ── internals ─────────────────────────────────────────────────
    def _get_ranker(self) -> _RankerLike:
        if self._ranker is not None:
            return self._ranker
        with self._lock:
            if self._ranker is None:
                ranker, source, xgb, background = self._load_ranker()
                self._ranker = ranker
                self._source = source
                # Wave 3a: these may be None when MLflow returns a
                # pyfunc whose internals we can't introspect — LIME
                # silently degrades to empty in that case.
                self._xgb_ranker = xgb
                self._lime_background = background
                logger.info("Recruitment ranker initialised from {}", self._source)
        return self._ranker

    def _load_ranker(
        self,
    ) -> tuple[RankingModel, str, XGBoostRanker | None, np.ndarray | None]:
        """Choose a ranker source in priority order. Imports of
        `ml.recruitment` live here so the backend stays importable without
        the ML deps.

        Returns a 4-tuple `(ranker, source, xgb_ranker, training_features)`.
        The last two are populated only on the synthetic-bootstrap path
        where we built the ensemble ourselves and know the inner XGBoost
        arm + training matrix; the MLflow pyfunc path leaves them as
        `None` (LIME silently degrades to empty)."""
        try:
            from ml.recruitment.training.config import TrainingConfig
            from ml.recruitment.training.pipeline import train_pipeline
        except ImportError as exc:
            raise RuntimeError(
                "RECRUITMENT_USE_REAL_ML=True but `ml.recruitment` is not "
                "importable. Install ml/requirements.txt or run the backend "
                "inside the ml-dev container."
            ) from exc

        # ── 1. MLflow Production model, if present ────────────────
        registry_model = _load_from_registry()
        if registry_model is not None:
            ranker, version, registry_xgb, registry_bg = registry_model
            # TASK-052: when the training run logged LIME companions
            # under `lime_companions/`, the registry loader returns
            # the rehydrated XGBoost arm + background here. The pyfunc
            # is still the production ranker; the companions only
            # power LIME side-attribution. Both fall through as None
            # if the run pre-dates TASK-052, in which case LIME on the
            # registry path stays empty (same UX as the wave-3-empty
            # contract).
            return ranker, f"mlflow:{version}", registry_xgb, registry_bg

        # ── 2. Synthetic bootstrap — train on the synthetic dataset ──
        # This is *not* production behaviour. It exists so the backend's
        # real-ML path is exercised even before a training run has been
        # registered. The result is loud-logged so operators can't miss it.
        logger.warning(
            "No Production `recruitment-ranker` in MLflow — bootstrapping "
            "on synthetic data. Replace via `python -m ml.recruitment.cli train`."
        )
        cfg = TrainingConfig(n_synthetic_candidates=500, seed=42)
        result = train_pipeline(cfg)
        # The pipeline always trains an ensemble; pull it out by name.
        ensemble_name = next(
            (name for name in result.benchmark.metrics if name.startswith("ensemble(")),
            None,
        )
        # Reconstruct the fitted ensemble for inference + capture the
        # XGBoost arm + training feature matrix for LIME (TASK-049).
        ranker, xgb, training_features = _reconstruct_ensemble_from_result(result)
        if ranker is None:
            raise RuntimeError(
                f"Synthetic bootstrap produced no usable ranker "
                f"(benchmark={list(result.benchmark.metrics)} ensemble={ensemble_name})."
            )
        return ranker, "synthetic-bootstrap", xgb, training_features


# ── module-level helpers (importable by tests) ──────────────────────


def _load_from_registry() -> (
    tuple[RankingModel, str, XGBoostRanker | None, np.ndarray | None] | None
):
    """Try MLflow Model Registry; swallow errors so a missing tracking
    server falls back to the synthetic bootstrap rather than crashing.

    TASK-052: returns a 4-tuple `(ranker, version, xgb_ranker,
    background)`. The trailing two are populated when the registry
    artifact carries the `lime_companions/` subdirectory (logged
    alongside the pyfunc by the training pipeline's
    `register_run(..., xgb_ranker=..., background=...)` call).
    Falls back to `(ranker, version, None, None)` when the run
    pre-dates TASK-052 or the companions can't be downloaded —
    LIME stays empty on that path, same UX as the wave-3 empty
    contract.
    """
    try:
        from ml.recruitment.registry.model_registry import latest_production

        version = latest_production()
        if version is None:
            return None
        import mlflow.pyfunc

        loaded = mlflow.pyfunc.load_model(version.source)
        xgb_ranker, background = _try_load_lime_companions(version)
        return loaded, str(version.version), xgb_ranker, background
    except Exception as exc:  # pragma: no cover - depends on live MLflow
        logger.info("MLflow Model Registry unavailable ({}); using bootstrap.", exc)
        return None


def _try_load_lime_companions(
    version,
) -> tuple[XGBoostRanker | None, np.ndarray | None]:
    """Download + deserialise the `lime_companions/` subdirectory for the
    given registered model version. Returns `(None, None)` for runs
    that pre-date TASK-052 or whose companion artifacts can't be
    downloaded — the inference client interprets that as "no LIME on
    this path", same fallback as the test-injection branch.

    `version.source` is `runs:/<run_id>/<artifact_path>`; the
    companions live as a *sibling* under the run's artifact root
    (`runs:/<run_id>/lime_companions/`), so we strip the trailing
    `<artifact_path>` segment to land on the run root."""
    try:
        from ml.recruitment.registry.lime_companions import (
            COMPANIONS_DIR_NAME,
            load_companions_from_dir,
        )
        import mlflow.artifacts

        # `version.source` shape: `runs:/<run_id>/<artifact_path>` —
        # we want `runs:/<run_id>/lime_companions/`, i.e. the same
        # run root with the companions subdir.
        source = str(version.source)
        if source.startswith("runs:/"):
            # split off the trailing `/<artifact_path>` if present
            parts = source.split("/")
            # parts == ['runs:', '', '<run_id>', '<artifact_path>'?]
            if len(parts) >= 3:
                run_root = "/".join(parts[:3])
                companion_uri = f"{run_root}/{COMPANIONS_DIR_NAME}"
            else:
                return None, None
        else:
            return None, None

        local_dir = mlflow.artifacts.download_artifacts(artifact_uri=companion_uri)
        # `load_companions_from_dir` expects the *parent* of
        # `lime_companions/` (it appends the dir name itself), so step
        # back one level.
        from pathlib import Path

        parent = Path(local_dir).parent
        return load_companions_from_dir(parent)
    except Exception as exc:  # pragma: no cover - depends on live MLflow
        logger.info(
            "LIME companions unavailable for MLflow version ({}); LIME stays empty on registry path.",
            exc,
        )
        return None, None


def _reconstruct_ensemble_from_result(
    result,
) -> tuple[RankingModel | None, XGBoostRanker | None, np.ndarray | None]:
    """`train_pipeline` returns the metrics + config but doesn't expose its
    fitted ensemble directly. We rebuild a fresh ensemble + refit on the
    same synthetic data using the chosen weight from `result.best_weight`.

    Wasteful — but the synthetic bootstrap path is explicitly temporary
    (the warning above tells operators to replace it). Once the MLflow
    registry hop is wired, this branch is unreachable in production.

    TASK-049 / FE-016 wave 3a: returns a 3-tuple
    `(ensemble, xgb_ranker, training_features)`. `training_features` is
    the same `(n_pairs, n_features)` matrix the XGBoost fit consumed —
    LIME uses it as the perturbation background. Both extras fall
    through as `None` if the ml.recruitment chain isn't importable.
    """
    try:
        import numpy as np

        from ml.recruitment.data.loader import RecruitmentDataLoader
        from ml.recruitment.features.structured import build_feature_matrix
        from ml.recruitment.models.ensemble import EnsembleRanker
        from ml.recruitment.models.semantic import SBERTRanker
        from ml.recruitment.models.structured import XGBoostRanker
    except ImportError:
        return None, None, None

    loader = RecruitmentDataLoader()
    dataset = loader.load_synthetic(
        n_candidates=result.config.n_synthetic_candidates,
        seed=result.config.seed,
    )
    train, _val, _test = dataset.split(
        train=result.config.train_pct,
        val=result.config.val_pct,
        seed=result.config.seed,
    )
    sbert = SBERTRanker()
    xgb = XGBoostRanker(**result.config.xgb_params)
    sbert.fit(train.pairs)
    xgb.fit(train.pairs)
    ensemble = EnsembleRanker(sbert, xgb, weight=float(result.best_weight))
    ensemble.fit(train.pairs)

    # Build the LIME background matrix from the training pairs the
    # XGBoost arm just consumed. `build_feature_matrix(jd, [cand])`
    # returns a `(1, n_features)` row per pair; stacking gives the
    # `(n_train, n_features)` background LIME needs.
    background_rows: list[np.ndarray] = []
    for pair in train.pairs:
        try:
            background_rows.append(
                build_feature_matrix(pair.job, [pair.candidate])[0]
            )
        except Exception:  # pragma: no cover - per-row defensive
            continue
    training_features = (
        np.vstack(background_rows) if background_rows else None
    )
    return ensemble, xgb, training_features


# Module-level singleton — created once per process. Construction is
# cheap (no heavy imports); `score_candidates` triggers the first load.
_client_singleton: RecruitmentInferenceClient | None = None
_singleton_lock = threading.Lock()


def get_inference_client() -> RecruitmentInferenceClient:
    """Return the process-wide inference client."""
    global _client_singleton
    if _client_singleton is None:
        with _singleton_lock:
            if _client_singleton is None:
                _client_singleton = RecruitmentInferenceClient()
    return _client_singleton


def reset_inference_client(client: RecruitmentInferenceClient | None = None) -> None:
    """Replace the singleton — testing seam only. Pass `None` to clear."""
    global _client_singleton
    with _singleton_lock:
        _client_singleton = client
