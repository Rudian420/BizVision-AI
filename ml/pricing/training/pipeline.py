"""
End-to-end pricing training pipeline.

Mirrors `ml.recruitment.training.pipeline`:

    data → policies (5 arms) → benchmark → MLflow logging

Returns a `PricingTrainingResult` suitable for the CLI and the AS-002
ablation runner.
"""

from __future__ import annotations

from dataclasses import dataclass

from ml.pricing.data.loader import PricingDataLoader
from ml.pricing.evaluation.benchmark import BenchmarkResult, run_benchmark
from ml.pricing.models.baselines import CompetitorMatchPolicy, ConstantPricePolicy
from ml.pricing.models.demand import LightGBMGridPolicy
from ml.pricing.models.elasticity import ElasticityOptimalPolicy
from ml.pricing.models.rl_agent import PPOPricingPolicy
from ml.pricing.reproducibility.env import capture_environment
from ml.pricing.reproducibility.seed import set_global_seed
from ml.pricing.training.config import PricingTrainingConfig
from ml.shared.mlflow_utils import start_run


@dataclass
class PricingTrainingResult:
    config: PricingTrainingConfig
    benchmark: BenchmarkResult
    env: dict[str, str]


def train_pipeline(config: PricingTrainingConfig | None = None) -> PricingTrainingResult:
    cfg = config or PricingTrainingConfig()
    set_global_seed(cfg.seed)
    env = capture_environment()

    # ── data ─────────────────────────────────────────────────────
    loader = PricingDataLoader()
    dataset = loader.load_synthetic(n_observations=cfg.n_synthetic_observations, seed=cfg.seed)
    train, _val, test = dataset.split(train=cfg.train_pct, val=cfg.val_pct, seed=cfg.seed)
    test_products = list(test.products.values())
    test_observations = test.observations

    # ── policies (5 arms of AS-002) ─────────────────────────────
    policies = [
        ConstantPricePolicy(),
        CompetitorMatchPolicy(),
        ElasticityOptimalPolicy(),
        LightGBMGridPolicy(),
        PPOPricingPolicy(total_timesteps=cfg.ppo_total_timesteps, seed=cfg.seed),
    ]

    # ── benchmark ────────────────────────────────────────────────
    bench = run_benchmark(
        policies,
        train=train.observations,
        test_products=test_products,
        test_observations=test_observations,
    )

    # ── MLflow ───────────────────────────────────────────────────
    with start_run("pricing", run_name=cfg.run_name, tags=env) as _:
        _log_to_mlflow(cfg=cfg, bench=bench, env=env)

    return PricingTrainingResult(config=cfg, benchmark=bench, env=env)


def _log_to_mlflow(
    *,
    cfg: PricingTrainingConfig,
    bench: BenchmarkResult,
    env: dict[str, str],
) -> None:
    import mlflow

    mlflow.log_params({"config": str(cfg.as_dict())})
    mlflow.log_params({f"env.{k}": v for k, v in env.items()})
    for policy_name, metrics in bench.metrics.items():
        clean = (
            policy_name.replace("::", "__").replace("/", "_").replace("(", "_").replace(")", "_")
        )
        for metric_name, value in metrics.items():
            mlflow.log_metric(f"{clean}.{metric_name}", float(value))
