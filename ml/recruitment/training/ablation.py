"""
AS-001 ablation runner.

Iterates over `{seed} × {n_candidates}` and writes a tidy results table
plus per-run benchmark frames. Designed to be the canonical command behind
the ablation chapter of the thesis (Section 11 in the outline).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from ml.recruitment.training.config import TrainingConfig
from ml.recruitment.training.pipeline import TrainingResult, train_pipeline


@dataclass
class AblationRunResult:
    runs: list[TrainingResult] = field(default_factory=list)

    def summary_dataframe(self):
        """One row per (model, seed, n_candidates) with mean metrics.

        Returns a pandas DataFrame so callers can plot directly."""
        import pandas as pd

        rows: list[dict] = []
        for run in self.runs:
            for model_name, metrics in run.benchmark.metrics.items():
                rows.append(
                    {
                        "model": model_name,
                        "seed": run.config.seed,
                        "n_candidates": run.config.n_synthetic_candidates,
                        **metrics,
                    }
                )
        return pd.DataFrame(rows)

    def mean_with_ci(self, metric: str = "ndcg@5"):
        """Return a DataFrame of mean ± 95% CI per model across seeds.

        CI estimated via 1.96 × SEM (large-n normal approximation; for
        thesis-grade work prefer bootstrap)."""
        df = self.summary_dataframe()
        grouped = df.groupby("model")[metric]
        mean = grouped.mean()
        sem = grouped.std(ddof=1) / np.sqrt(grouped.count())
        return mean.to_frame(name="mean").assign(ci95=1.96 * sem.values)


def run_ablation(
    *,
    seeds: Sequence[int] = (42, 43, 44),
    n_candidates_grid: Sequence[int] = (500, 2000),
    base_config: TrainingConfig | None = None,
) -> AblationRunResult:
    """Run the full AS-001 ablation matrix.

    Default: 3 seeds × 2 dataset sizes = 6 runs. Each run trains all 5
    arms + the ensemble → 6 models per run × 6 = 36 model fits. With
    synthetic data and the XGBoost defaults this completes in ~10 minutes
    in the ml-dev container.
    """
    out = AblationRunResult()
    for n in n_candidates_grid:
        for seed in seeds:
            cfg = base_config or TrainingConfig()
            # Build a new immutable cfg with this seed/size.
            cfg = TrainingConfig(
                **{
                    **cfg.as_dict(),
                    "seed": int(seed),
                    "n_synthetic_candidates": int(n),
                    "run_name": f"ablation/n{n}/seed{seed}",
                }
            )
            out.runs.append(train_pipeline(cfg))
    return out
