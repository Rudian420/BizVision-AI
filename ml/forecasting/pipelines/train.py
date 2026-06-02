"""
Thin shim that defers to `ml.forecasting.training.pipeline.train`.

The original Phase-1 baseline lived here; TASK-015 (Session 14) moved
the real training pipeline into `ml/forecasting/training/` to mirror
`ml/pricing/training/`. This file is preserved as a callable shim so
the historical `python -m ml.forecasting.pipelines.train` invocation
(documented in `infrastructure/Makefile` and the original ml-dev
runbook) keeps working without code changes.

Prefer `ml.forecasting.training.pipeline.train` in new code.
"""

from __future__ import annotations

from ml.forecasting.training.config import TrainConfig
from ml.forecasting.training.pipeline import train as _train


def train(horizon: int = 90) -> dict:
    """Backward-compatible shim — same signature as the original Phase-1 stub."""
    return _train(TrainConfig(horizon=horizon))


if __name__ == "__main__":  # pragma: no cover
    print(train())
