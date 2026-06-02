"""Celery task modules. Importing registers tasks with the worker."""

from src.workers.tasks import ml  # (registers ml.* tasks)
