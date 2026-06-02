"""
Sustainability model registry — wraps the MLflow Registry API.

Convention:
    Registered model name → "esg-multilabel-classifier"
    Stages                → "None" → "Staging" → "Production"

Promotion gate (recommended): a new classifier is promoted to
Production only if its macro-F1 on the AS-004 test pool is higher than
the current production model **and** its per-pillar four-fifths-rule
status is no worse (i.e., no new fairness violations introduced). The
benchmark + audit harnesses expose both numbers so the gate is a
two-line check at the registry call site.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mlflow.entities.model_registry import ModelVersion

REGISTERED_MODEL_NAME = "esg-multilabel-classifier"


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
    # See pricing/registry — skip MLflow lookup when unavailable.
    import os

    if os.environ.get("BIZVISION_SKIP_MLFLOW", "").lower() in {"1", "true", "yes"}:
        return None
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    versions = client.get_latest_versions(REGISTERED_MODEL_NAME, stages=["Production"])
    return versions[0] if versions else None
