"""
Chatbot model registry — wraps the MLflow Registry API.

Convention:
    Registered model name → "chatbot-agent-executor"
    Stages                → "None" → "Staging" → "Production"

Promotion gate (recommended): a new executor is promoted to
Production only if its MRR on the AS-005 golden set is higher than
the current production model **and** its routing accuracy is no
worse. The benchmark harness exposes both numbers so the gate is a
two-line check at the registry call site.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mlflow.entities.model_registry import ModelVersion

REGISTERED_MODEL_NAME = "chatbot-agent-executor"


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
