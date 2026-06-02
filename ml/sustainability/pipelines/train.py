"""
Thin shim that defers to `ml.sustainability.training.pipeline.train`.

The original Phase-1 baseline lived here; TASK-017 (Session 16) moved
the real training pipeline into `ml/sustainability/training/` to mirror
`ml/forecasting/training/` and `ml/pricing/training/`. This file is
preserved as a callable shim so the historical
`python -m ml.sustainability.pipelines.train` invocation (documented in
`infrastructure/Makefile` and the original ml-dev runbook) keeps
working without code changes.

Prefer `ml.sustainability.training.pipeline.train` in new code.
"""

from __future__ import annotations

from ml.sustainability.training.config import TrainConfig
from ml.sustainability.training.pipeline import train as _train


def train() -> dict:
    """Backward-compatible shim — same signature as the original Phase-1 stub."""
    return _train(TrainConfig())


if __name__ == "__main__":  # pragma: no cover
    print(train())
