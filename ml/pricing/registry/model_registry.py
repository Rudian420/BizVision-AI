"""
Pricing model registry — wraps the MLflow Registry API.

Convention:
    Registered model name → "smart-pricing-policy"
    Stages                → "None" → "Staging" → "Production"

Promotion gate (recommended): a new policy is promoted to Production only
if its mean revenue uplift on the AS-002 test pool is statistically
better than the current production model **and** its `value_at_risk_5pct`
is no worse. The benchmark harness exposes both numbers so the gate is a
two-line check at the registry call site.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mlflow.entities.model_registry import ModelVersion

REGISTERED_MODEL_NAME = "smart-pricing-policy"


def register_run(run_id: str, artifact_path: str = "model") -> ModelVersion:
    import mlflow

    model_uri = f"runs:/{run_id}/{artifact_path}"
    return mlflow.register_model(model_uri=model_uri, name=REGISTERED_MODEL_NAME)


def promote_to_production(
    version: int | str,
    *,
    description: str = "",
    archive_existing: bool = True,
) -> None:
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
    # Fast-path skip when MLflow is known to be unavailable (the
    # backend Docker stack has a chronic-restart MLflow container —
    # otherwise every inference cold-start eats ~5 min of urllib3
    # retries before falling through to bootstrap). Set
    # `BIZVISION_SKIP_MLFLOW=1` in compose env for that case.
    import os

    if os.environ.get("BIZVISION_SKIP_MLFLOW", "").lower() in {"1", "true", "yes"}:
        return None
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    versions = client.get_latest_versions(REGISTERED_MODEL_NAME, stages=["Production"])
    return versions[0] if versions else None
