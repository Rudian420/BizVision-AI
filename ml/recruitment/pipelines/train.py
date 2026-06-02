"""
Legacy entry point retained because the project Makefile (and any external
schedulers) invoke `python -m ml.recruitment.pipelines.train`.

The implementation lives in `ml.recruitment.training.pipeline` (see ADR-020
for the package layout). This module is a thin shim — kept stable so the
canonical command keeps working — that forwards to the new pipeline.

If you are adding new training code, edit `ml.recruitment.training.pipeline`,
*not* this file.
"""

from __future__ import annotations

from ml.recruitment.training.config import TrainingConfig
from ml.recruitment.training.pipeline import TrainingResult, train_pipeline

__all__ = ["TrainingConfig", "TrainingResult", "train_pipeline"]


def main() -> None:  # pragma: no cover
    """`python -m ml.recruitment.pipelines.train` — runs the canonical training pipeline."""
    train_pipeline()


if __name__ == "__main__":  # pragma: no cover
    main()
