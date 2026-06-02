"""
BizVision AI — Celery Application

Background task queue for non-blocking ML inference, batch jobs, and
scheduled maintenance. The worker and beat scheduler are launched from
docker-compose (`celery -A src.workers.celery_app ...`).

Queues:
    - ``ml``       : heavy model inference / training jobs
    - ``default``  : lightweight async tasks (emails, cache warm, cleanup)
"""

from __future__ import annotations

from celery import Celery

from src.core.config import settings

celery_app = Celery(
    "bizvision",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["src.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 30,  # hard limit: 30 min
    task_soft_time_limit=60 * 25,  # soft limit: 25 min
    worker_prefetch_multiplier=1,  # fair dispatch for long ML tasks
    task_default_queue="default",
    task_routes={
        "src.workers.tasks.ml.*": {"queue": "ml"},
    },
    result_expires=60 * 60 * 24,  # results live 24h
)


@celery_app.task(name="bizvision.health.ping")
def ping() -> str:
    """Trivial liveness task used by Flower / smoke tests."""
    return "pong"
