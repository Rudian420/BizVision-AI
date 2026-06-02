"""
Recruitment model registry — wraps the MLflow Registry API.

Convention:
    Registered model name → "recruitment-ranker"
    Stages                → "None" (default after register) → "Staging" → "Production"

Promotion is gated by the benchmark harness: a new model is promoted to
Production only if its NDCG@5 is statistically better than the current
production model AND its DPD ≤ DPD_current.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mlflow.entities.model_registry import ModelVersion

REGISTERED_MODEL_NAME = "recruitment-ranker"


def register_run(
    run_id: str,
    artifact_path: str = "model",
    *,
    xgb_ranker: Any | None = None,
    background: Any | None = None,
) -> ModelVersion:
    """Register an MLflow run's model artifact under `recruitment-ranker`.

    Returns the new ModelVersion (caller can read `.version` and promote it).

    TASK-052: optionally logs the LIME companions (XGBoost arm +
    perturbation background) as side-artifacts under
    `lime_companions/`. When both are supplied, the inference
    client's registry loader can re-hydrate them next to the
    pyfunc, lighting up LIME on the MLflow registry path. When
    they're missing, the loader silently falls through to empty
    LIME — same UX as the wave-3 mock-vs-real split.
    """
    import mlflow

    if xgb_ranker is not None and background is not None:
        import tempfile

        from ml.recruitment.registry.lime_companions import (
            COMPANIONS_DIR_NAME,
            save_companions_to_dir,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            save_companions_to_dir(
                tmpdir, xgb_ranker=xgb_ranker, background=background
            )
            mlflow.log_artifacts(
                local_dir=str(tmpdir + "/" + COMPANIONS_DIR_NAME),
                artifact_path=COMPANIONS_DIR_NAME,
            )

    model_uri = f"runs:/{run_id}/{artifact_path}"
    return mlflow.register_model(model_uri=model_uri, name=REGISTERED_MODEL_NAME)


def promote_to_production(
    version: int | str,
    *,
    description: str = "",
    archive_existing: bool = True,
) -> None:
    """Transition `version` of the registered model to Production.

    Existing Production models are archived (the standard MLflow pattern)
    unless `archive_existing=False`.
    """
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    client.transition_model_version_stage(
        name=REGISTERED_MODEL_NAME,
        version=str(version),
        stage="Production",
        archive_existing_versions=archive_existing,
    )
    if description:
        client.update_model_version(
            name=REGISTERED_MODEL_NAME, version=str(version), description=description
        )


def latest_production() -> Any:
    """Return the latest Production-staged ModelVersion (or None).

    Fast-path skip via `BIZVISION_SKIP_MLFLOW=1` when the MLflow
    container is unreachable — otherwise urllib3 retries cost ~5 min
    per inference cold-start before falling through to bootstrap.
    """
    import os

    if os.environ.get("BIZVISION_SKIP_MLFLOW", "").lower() in {"1", "true", "yes"}:
        return None
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    versions = client.get_latest_versions(REGISTERED_MODEL_NAME, stages=["Production"])
    return versions[0] if versions else None
