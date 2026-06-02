"""
BizVision AI — ML Background Tasks (queue: ``ml``)

PHASE 1 SCAFFOLD: placeholder tasks that establish the routing contract
between the API layer and the heavy ML queue. Phase 3 replaces the
bodies with real training / batch-inference logic that logs to MLflow.
"""

from __future__ import annotations

from src.workers.celery_app import celery_app


@celery_app.task(name="src.workers.tasks.ml.warm_models")
def warm_models() -> dict:
    """Placeholder — Phase 3 will load models into the worker process."""
    return {"status": "ok", "warmed": ["recruitment", "pricing", "forecasting"]}


@celery_app.task(name="src.workers.tasks.ml.run_inference")
def run_inference(module: str, payload: dict) -> dict:
    """Placeholder batch-inference entry point."""
    return {"module": module, "status": "completed", "echo": payload}
