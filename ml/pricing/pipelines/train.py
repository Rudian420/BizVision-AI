"""
Legacy entry point retained because the project Makefile invokes
`python -m ml.pricing.pipelines.train`. The real implementation lives in
`ml.pricing.training.pipeline` (see ADR-025 for the package layout).
This module is a thin shim — kept stable so the canonical command keeps
working — that forwards to the new pipeline.

If you are adding new training code, edit
`ml.pricing.training.pipeline`, *not* this file.
"""

from __future__ import annotations

from ml.pricing.training.config import PricingTrainingConfig
from ml.pricing.training.pipeline import PricingTrainingResult, train_pipeline

__all__ = ["PricingTrainingConfig", "PricingTrainingResult", "train_pipeline"]


def main() -> None:  # pragma: no cover
    """`python -m ml.pricing.pipelines.train` — runs the canonical pipeline."""
    train_pipeline()


if __name__ == "__main__":  # pragma: no cover
    main()
