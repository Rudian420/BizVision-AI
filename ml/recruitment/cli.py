"""
Recruitment Intelligence CLI.

    python -m ml.recruitment.cli train [--seed 42] [--n 2000]
    python -m ml.recruitment.cli ablate
    python -m ml.recruitment.cli benchmark
    python -m ml.recruitment.cli explain --candidate <idx>
"""

from __future__ import annotations

import argparse
import sys

from ml.recruitment.training.ablation import run_ablation
from ml.recruitment.training.config import TrainingConfig
from ml.recruitment.training.pipeline import train_pipeline


def _cmd_train(args: argparse.Namespace) -> int:
    cfg = TrainingConfig(seed=args.seed, n_synthetic_candidates=args.n)
    result = train_pipeline(cfg)
    print("\n=== Recruitment training summary ===")
    print(f"  best ensemble weight: {result.best_weight:.2f}")
    print("\n  Benchmark (mean across queries):")
    for model_name, metrics in result.benchmark.metrics.items():
        ndcg5 = metrics.get("ndcg@5", float("nan"))
        auc = metrics.get("auc", float("nan"))
        mrr = metrics.get("mrr", float("nan"))
        print(f"    {model_name:50s}  NDCG@5={ndcg5:.3f}  AUC={auc:.3f}  MRR={mrr:.3f}")
    print("\n  Fairness:")
    for attr, rep in result.fairness_reports.items():
        print(
            f"    {attr:30s}  DPD={rep.demographic_parity_difference:.3f}  "
            f"DI={rep.disparate_impact:.2f}  risk={rep.overall_risk}"
        )
    return 0


def _cmd_ablate(args: argparse.Namespace) -> int:
    result = run_ablation(seeds=tuple(args.seeds), n_candidates_grid=tuple(args.n_grid))
    summary = result.mean_with_ci("ndcg@5")
    print("\n=== AS-001 Ablation (mean NDCG@5 ± 95% CI across seeds) ===")
    print(summary)
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    # Benchmark is a single training run without weight search — the
    # `train` command already prints the benchmark frame.
    cfg = TrainingConfig(seed=args.seed, n_synthetic_candidates=args.n)
    result = train_pipeline(cfg)
    df = result.benchmark.to_dataframe()
    print(df.to_string())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ml.recruitment")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_train = sub.add_parser("train", help="run a single training pipeline")
    p_train.add_argument("--seed", type=int, default=42)
    p_train.add_argument("--n", type=int, default=2000, help="synthetic candidate count")
    p_train.set_defaults(func=_cmd_train)

    p_ablate = sub.add_parser("ablate", help="run the AS-001 ablation matrix")
    p_ablate.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    p_ablate.add_argument("--n-grid", type=int, nargs="+", default=[500, 2000])
    p_ablate.set_defaults(func=_cmd_ablate)

    p_bench = sub.add_parser("benchmark", help="print the benchmark dataframe")
    p_bench.add_argument("--seed", type=int, default=42)
    p_bench.add_argument("--n", type=int, default=2000)
    p_bench.set_defaults(func=_cmd_benchmark)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
