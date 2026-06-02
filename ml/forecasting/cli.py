"""
Forecasting CLI — `train` / `ablate` / `benchmark` subcommands.

Mirrors `ml.pricing.cli`:

    python -m ml.forecasting.cli train
    python -m ml.forecasting.cli ablate
    python -m ml.forecasting.cli benchmark --arm HoltWinters
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

import numpy as np

from ml.forecasting.data.loader import generate_synthetic_series
from ml.forecasting.evaluation.benchmark import rolling_origin_backtest
from ml.forecasting.models.baselines import NaiveLast, NaiveSeasonal
from ml.forecasting.models.exp_smoothing import HoltWintersForecaster
from ml.forecasting.models.theta import ThetaForecaster
from ml.forecasting.training.ablation import run as ablation_run
from ml.forecasting.training.config import TrainConfig
from ml.forecasting.training.pipeline import train as train_run


def _arm(name: str, season_length: int):
    if name == "NaiveLast":
        return NaiveLast()
    if name == "NaiveSeasonal":
        return NaiveSeasonal(season_length=season_length)
    if name == "HoltWinters":
        return HoltWintersForecaster(season_length=season_length)
    if name == "Theta":
        return ThetaForecaster()
    raise SystemExit(f"unknown arm: {name!r}")


def _cmd_train(args: argparse.Namespace) -> int:
    cfg = TrainConfig(
        n_days=args.n_days, horizon=args.horizon, seed=args.seed
    )
    print(json.dumps(train_run(cfg), default=str, indent=2))
    return 0


def _cmd_ablate(args: argparse.Namespace) -> int:
    cfg = TrainConfig(
        n_days=args.n_days, horizon=args.horizon, n_folds=args.n_folds, seed=args.seed
    )
    seeds = tuple(int(s) for s in args.seeds.split(","))
    results = ablation_run(cfg, seeds=seeds)
    summary = {
        arm: [asdict(r) for r in runs] for arm, runs in results.items()
    }
    print(json.dumps(summary, default=str, indent=2))
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    dataset = generate_synthetic_series(n_days=args.n_days, seed=args.seed)
    model = _arm(args.arm, season_length=args.season_length)
    result = rolling_origin_backtest(
        dataset=dataset,
        model=model,
        horizon=args.horizon,
        n_folds=args.n_folds,
        season_length=args.season_length,
        pi_alpha=args.pi_alpha,
    )
    print(json.dumps(asdict(result), default=str, indent=2))
    # silence numpy import-only warning in some envs
    _ = np
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ml.forecasting")
    sub = parser.add_subparsers(dest="cmd", required=True)

    train_p = sub.add_parser("train", help="Train the recommended single arm")
    train_p.add_argument("--n-days", type=int, default=365 * 2)
    train_p.add_argument("--horizon", type=int, default=90)
    train_p.add_argument("--seed", type=int, default=42)
    train_p.set_defaults(func=_cmd_train)

    ablate_p = sub.add_parser("ablate", help="Run the AS-003 ablation campaign")
    ablate_p.add_argument("--n-days", type=int, default=365 * 2)
    ablate_p.add_argument("--horizon", type=int, default=90)
    ablate_p.add_argument("--n-folds", type=int, default=5)
    ablate_p.add_argument("--seed", type=int, default=42)
    ablate_p.add_argument("--seeds", default="42,1337,31337")
    ablate_p.set_defaults(func=_cmd_ablate)

    bench_p = sub.add_parser("benchmark", help="Benchmark a single arm")
    bench_p.add_argument(
        "--arm",
        choices=["NaiveLast", "NaiveSeasonal", "HoltWinters", "Theta"],
        required=True,
    )
    bench_p.add_argument("--n-days", type=int, default=365 * 2)
    bench_p.add_argument("--horizon", type=int, default=90)
    bench_p.add_argument("--n-folds", type=int, default=5)
    bench_p.add_argument("--season-length", type=int, default=7)
    bench_p.add_argument("--pi-alpha", type=float, default=0.05)
    bench_p.add_argument("--seed", type=int, default=42)
    bench_p.set_defaults(func=_cmd_benchmark)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
