"""
Smart Pricing Advisor CLI.

    python -m ml.pricing.cli train     [--seed 42] [--n 3000]
    python -m ml.pricing.cli ablate    [--seeds 42 43 44] [--n-grid 1000 3000]
    python -m ml.pricing.cli benchmark
"""

from __future__ import annotations

import argparse
import sys

from ml.pricing.training.ablation import run_ablation
from ml.pricing.training.config import PricingTrainingConfig
from ml.pricing.training.pipeline import train_pipeline


def _cmd_train(args: argparse.Namespace) -> int:
    cfg = PricingTrainingConfig(seed=args.seed, n_synthetic_observations=args.n)
    result = train_pipeline(cfg)
    print("\n=== Smart Pricing training summary ===")
    print(f"  seed={cfg.seed}  n_observations={cfg.n_synthetic_observations}")
    print("\n  Benchmark (mean across products):")
    for policy_name, metrics in result.benchmark.metrics.items():
        uplift = metrics.get("revenue_uplift_pct", 0.0)
        sharpe = metrics.get("sharpe", 0.0)
        var5 = metrics.get("var_5pct", 0.0)
        print(
            f"    {policy_name:35s}  uplift={uplift*100:+6.2f}%  "
            f"sharpe={sharpe:+5.2f}  VaR5%={var5:8.2f}"
        )
    return 0


def _cmd_ablate(args: argparse.Namespace) -> int:
    result = run_ablation(seeds=tuple(args.seeds), n_observations_grid=tuple(args.n_grid))
    summary = result.mean_with_ci("revenue_uplift_pct")
    print("\n=== AS-002 Ablation (mean uplift % ± 95% CI across seeds) ===")
    print(summary)
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    cfg = PricingTrainingConfig(seed=args.seed, n_synthetic_observations=args.n)
    result = train_pipeline(cfg)
    df = result.benchmark.to_dataframe()
    print(df.to_string())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ml.pricing")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_train = sub.add_parser("train", help="run a single training pipeline")
    p_train.add_argument("--seed", type=int, default=42)
    p_train.add_argument("--n", type=int, default=3000)
    p_train.set_defaults(func=_cmd_train)

    p_ablate = sub.add_parser("ablate", help="run the AS-002 ablation matrix")
    p_ablate.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    p_ablate.add_argument("--n-grid", type=int, nargs="+", default=[1000, 3000])
    p_ablate.set_defaults(func=_cmd_ablate)

    p_bench = sub.add_parser("benchmark", help="print the benchmark dataframe")
    p_bench.add_argument("--seed", type=int, default=42)
    p_bench.add_argument("--n", type=int, default=3000)
    p_bench.set_defaults(func=_cmd_benchmark)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
