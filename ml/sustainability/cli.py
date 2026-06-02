"""
Sustainability CLI — `train` / `ablate` / `benchmark` / `audit` subcommands.

Mirrors `ml.forecasting.cli` and `ml.pricing.cli`:

    python -m ml.sustainability.cli train
    python -m ml.sustainability.cli ablate
    python -m ml.sustainability.cli benchmark --arm LinearLogisticMultiLabel
    python -m ml.sustainability.cli audit
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from ml.sustainability.data.loader import generate_synthetic_dataset, split_train_test
from ml.sustainability.evaluation.benchmark import benchmark_arm
from ml.sustainability.fairness.auditor import audit_industry_fairness
from ml.sustainability.models.baselines import (
    IndustryBaselineScorer,
    MajorityLabelScorer,
)
from ml.sustainability.models.multilabel import LinearLogisticMultiLabel
from ml.sustainability.training.ablation import run as ablation_run
from ml.sustainability.training.config import TrainConfig
from ml.sustainability.training.pipeline import train as train_run


def _arm(name: str):
    if name == "MajorityLabel":
        return MajorityLabelScorer()
    if name == "IndustryBaseline":
        return IndustryBaselineScorer()
    if name == "LinearLogisticMultiLabel":
        return LinearLogisticMultiLabel()
    raise SystemExit(f"unknown arm: {name!r}")


def _cmd_train(args: argparse.Namespace) -> int:
    cfg = TrainConfig(n_companies=args.n_companies, seed=args.seed)
    print(json.dumps(train_run(cfg), default=str, indent=2))
    return 0


def _cmd_ablate(args: argparse.Namespace) -> int:
    cfg = TrainConfig(
        n_companies=args.n_companies, n_folds=args.n_folds, seed=args.seed
    )
    seeds = tuple(int(s) for s in args.seeds.split(","))
    results = ablation_run(cfg, seeds=seeds)
    summary = {arm: [asdict(r) for r in runs] for arm, runs in results.items()}
    print(json.dumps(summary, default=str, indent=2))
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    dataset = generate_synthetic_dataset(n_companies=args.n_companies, seed=args.seed)
    model = _arm(args.arm)
    result = benchmark_arm(
        dataset=dataset,
        model=model,
        n_folds=args.n_folds,
        test_fraction=args.test_fraction,
        base_seed=args.seed,
        threshold=args.threshold,
    )
    print(json.dumps(asdict(result), default=str, indent=2))
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    dataset = generate_synthetic_dataset(n_companies=args.n_companies, seed=args.seed)
    train_ds, test_ds = split_train_test(dataset, test_fraction=args.test_fraction, seed=args.seed)
    model = _arm(args.arm)
    model.fit(train_ds.observations)
    audit = audit_industry_fairness(
        model,
        [obs.profile for obs in test_ds.observations],
        threshold=args.threshold,
    )
    payload = {
        "threshold": audit.threshold,
        "any_violation": audit.any_violation,
        "per_pillar": [
            {
                "pillar": m.pillar,
                "disparate_impact": m.disparate_impact,
                "demographic_parity_difference": m.demographic_parity_difference,
                "four_fifths_violated": m.four_fifths_violated,
                "reference_group": m.reference_group,
                "per_group_rate": m.per_group_rate,
                "per_group_n": m.per_group_n,
            }
            for m in audit.per_pillar
        ],
    }
    print(json.dumps(payload, default=str, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ml.sustainability")
    sub = parser.add_subparsers(dest="cmd", required=True)

    train_p = sub.add_parser("train", help="Train the recommended single arm")
    train_p.add_argument("--n-companies", type=int, default=600)
    train_p.add_argument("--seed", type=int, default=42)
    train_p.set_defaults(func=_cmd_train)

    ablate_p = sub.add_parser("ablate", help="Run the AS-004 ablation campaign")
    ablate_p.add_argument("--n-companies", type=int, default=600)
    ablate_p.add_argument("--n-folds", type=int, default=3)
    ablate_p.add_argument("--seed", type=int, default=42)
    ablate_p.add_argument("--seeds", default="42,1337,31337")
    ablate_p.set_defaults(func=_cmd_ablate)

    bench_p = sub.add_parser("benchmark", help="Benchmark a single arm")
    bench_p.add_argument(
        "--arm",
        choices=[
            "MajorityLabel",
            "IndustryBaseline",
            "LinearLogisticMultiLabel",
        ],
        required=True,
    )
    bench_p.add_argument("--n-companies", type=int, default=600)
    bench_p.add_argument("--n-folds", type=int, default=3)
    bench_p.add_argument("--test-fraction", type=float, default=0.2)
    bench_p.add_argument("--threshold", type=float, default=0.5)
    bench_p.add_argument("--seed", type=int, default=42)
    bench_p.set_defaults(func=_cmd_benchmark)

    audit_p = sub.add_parser("audit", help="Run the industry fairness audit")
    audit_p.add_argument(
        "--arm",
        choices=[
            "MajorityLabel",
            "IndustryBaseline",
            "LinearLogisticMultiLabel",
        ],
        default="LinearLogisticMultiLabel",
    )
    audit_p.add_argument("--n-companies", type=int, default=600)
    audit_p.add_argument("--test-fraction", type=float, default=0.2)
    audit_p.add_argument("--threshold", type=float, default=0.5)
    audit_p.add_argument("--seed", type=int, default=42)
    audit_p.set_defaults(func=_cmd_audit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
