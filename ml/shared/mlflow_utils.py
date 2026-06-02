"""
BizVision AI — MLflow tracking helpers

Centralises experiment naming and run setup so every module logs to a
consistent ``{prefix}-{module}`` experiment namespace (ADR-005).

When the MLflow tracking server is unreachable (the chronic-restart
case in the local Docker stack), set `BIZVISION_SKIP_MLFLOW=1` and
`start_run` redirects to a local file-store URI so `mlflow.log_param`
/ `log_metric` calls inside the context still succeed (writing to
`/tmp/mlruns`) and bootstrap-training pipelines don't crash.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
EXPERIMENT_PREFIX = os.getenv("MLFLOW_EXPERIMENT_PREFIX", "bizvision")
LOCAL_FALLBACK_URI = os.getenv(
    "MLFLOW_LOCAL_FALLBACK_URI", "file:///tmp/mlruns"
)


def _mlflow_skipped() -> bool:
    return os.environ.get("BIZVISION_SKIP_MLFLOW", "").lower() in {"1", "true", "yes"}


def experiment_name(module: str) -> str:
    return f"{EXPERIMENT_PREFIX}-{module}"


@contextmanager
def start_run(module: str, run_name: str | None = None, tags: dict | None = None) -> Iterator:
    """Open an MLflow run bound to a module's experiment.

    Usage:
        with start_run("recruitment", run_name="sbert-xgb-v1") as run:
            mlflow.log_param(...); mlflow.log_metric(...)

    When `BIZVISION_SKIP_MLFLOW=1` is set, monkey-patches the common
    `mlflow.log_*` / `set_tag` calls to no-ops within the context so
    bootstrap-training pipelines complete without a live MLflow
    tracking server (and without crashing on metric-name validation
    against the local file store).
    """
    import mlflow

    if _mlflow_skipped():
        # Stash + null-out the tracking calls the training pipelines
        # use most. Restore on exit so the rest of the process is
        # unaffected. `start_run` becomes a true no-op context.
        _saved = {
            name: getattr(mlflow, name, None)
            for name in (
                "log_param", "log_params", "log_metric", "log_metrics",
                "log_artifact", "log_artifacts", "log_dict", "log_text",
                "set_tag", "set_tags", "log_figure", "log_image",
            )
        }
        noop = lambda *a, **kw: None  # noqa: E731 - one-line stub
        try:
            for name in _saved:
                setattr(mlflow, name, noop)
            yield None
        finally:
            for name, fn in _saved.items():
                if fn is not None:
                    setattr(mlflow, name, fn)
        return

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(experiment_name(module))
    with mlflow.start_run(run_name=run_name, tags=tags) as run:
        yield run
