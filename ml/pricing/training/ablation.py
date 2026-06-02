"""
AS-002 ablation runner.

Iterates over `{seed} × {n_observations}`, writes a tidy per-policy
results table plus per-run benchmark frames. Canonical command behind
the AS-002 chapter of the thesis (Section 11 in the outline)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from ml.pricing.training.config import PricingTrainingConfig
from ml.pricing.training.pipeline import PricingTrainingResult, train_pipeline


@dataclass
class AblationRunResult:
    runs: list[PricingTrainingResult] = field(default_factory=list)

    def summary_dataframe(self):
        """One row per (policy, seed, n_observations) with mean metrics."""
        import pandas as pd

        rows: list[dict] = []
        for run in self.runs:
            for policy_name, metrics in run.benchmark.metrics.items():
                rows.append(
                    {
                        "policy": policy_name,
                        "seed": run.config.seed,
                        "n_observations": run.config.n_synthetic_observations,
                        **metrics,
                    }
                )
        return pd.DataFrame(rows)

    def mean_with_ci(self, metric: str = "revenue_uplift_pct"):
        """Mean ± 95 % CI per policy across seeds (1.96 × SEM)."""
        df = self.summary_dataframe()
        grouped = df.groupby("policy")[metric]
        mean = grouped.mean()
        sem = grouped.std(ddof=1) / np.sqrt(grouped.count())
        return mean.to_frame(name="mean").assign(ci95=1.96 * sem.values)


def run_ablation(
    *,
    seeds: Sequence[int] = (42, 43, 44),
    n_observations_grid: Sequence[int] = (1_000, 3_000),
    base_config: PricingTrainingConfig | None = None,
) -> AblationRunResult:
    """Run the full AS-002 ablation matrix.

    Default: 3 seeds × 2 dataset sizes = 6 runs × 5 policies = 30 policy
    fits. With synthetic data + the LightGBM defaults this completes in
    ~15 minutes in the ml-dev container (PPO is the slow arm)."""
    out = AblationRunResult()
    for n in n_observations_grid:
        for seed in seeds:
            base_dict = (base_config or PricingTrainingConfig()).as_dict()
            cfg = PricingTrainingConfig(
                **{
                    **base_dict,
                    "seed": int(seed),
                    "n_synthetic_observations": int(n),
                    "run_name": f"ablation/n{n}/seed{seed}",
                }
            )
            out.runs.append(train_pipeline(cfg))
    return out
