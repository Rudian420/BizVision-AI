"""
Sustainability training pipeline.

Mirrors `ml.forecasting.training.pipeline.train`. Steps:

  1. seed → load synthetic → train/test split
  2. fit LinearLogisticMultiLabel (the recommended production arm) on train
  3. score it on test with the same metric basket the benchmark uses
  4. run the industry fairness audit on the held-out test pool
  5. log everything to MLflow

This is the *single-arm* training entry — the full AS-004 ablation
campaign lives in `training.ablation.run` and scores every arm on the
same folds. Both share the same metric definitions.

`python -m ml.sustainability.training.pipeline` runs it once with defaults.
"""

from __future__ import annotations

from dataclasses import asdict

from ml.sustainability.data.loader import generate_synthetic_dataset, split_train_test
from ml.sustainability.evaluation.benchmark import _predict_arrays
from ml.sustainability.evaluation.metrics import (
    accuracy,
    brier_score,
    expected_calibration_error,
    hamming_loss,
    macro_f1,
)
from ml.sustainability.fairness.auditor import audit_industry_fairness
from ml.sustainability.models.multilabel import LinearLogisticMultiLabel
from ml.sustainability.reproducibility import capture_env_snapshot, seed_everything
from ml.sustainability.training.config import TrainConfig


def train(config: TrainConfig | None = None) -> dict:
    """Train the recommended single-arm scorer and return its metrics."""
    cfg = config or TrainConfig()
    seed_everything(cfg.seed)

    dataset = generate_synthetic_dataset(n_companies=cfg.n_companies, seed=cfg.seed)
    train_ds, test_ds = split_train_test(
        dataset, test_fraction=cfg.test_fraction, seed=cfg.seed
    )

    model = LinearLogisticMultiLabel().fit(train_ds.observations)

    Y_true, Y_proba = _predict_arrays(model, test_ds)
    Y_pred = (Y_proba >= cfg.threshold).astype(int)
    metrics: dict[str, float] = {
        "macro_f1": macro_f1(Y_true, Y_pred),
        "accuracy": accuracy(Y_true, Y_pred),
        "hamming_loss": hamming_loss(Y_true, Y_pred),
        "brier_score": brier_score(Y_true, Y_proba),
        "expected_calibration_error": expected_calibration_error(Y_true, Y_proba),
    }

    audit = audit_industry_fairness(
        model,
        [obs.profile for obs in test_ds.observations],
        threshold=cfg.threshold,
    )
    metrics["fairness_any_violation"] = float(audit.any_violation)
    metrics["fairness_n_pillars_violated"] = float(
        sum(1 for m in audit.per_pillar if m.four_fifths_violated)
    )

    # MLflow logging — optional; skipped if mlflow isn't installed.
    try:  # pragma: no cover - optional dep
        import mlflow

        mlflow.set_experiment(cfg.mlflow_experiment)
        with mlflow.start_run(run_name=f"{model.name}-baseline"):
            mlflow.log_params(asdict(cfg))
            mlflow.log_params(capture_env_snapshot())
            mlflow.log_metrics(metrics)
    except ImportError:
        pass

    return {
        "model": model.name,
        "metrics": metrics,
        "config": asdict(cfg),
    }


if __name__ == "__main__":  # pragma: no cover
    out = train()
    print(out)
