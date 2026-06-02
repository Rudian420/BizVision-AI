"""
ESG benchmark harness — train/test holdout with multi-fold seeding.

Returns an `ArmResult` per scorer aggregated across folds. The harness
treats every arm uniformly — it only calls the `ESGScorer` ABC, never
any concrete class — which is why the uniform-interface decision
(ADR-022 in recruitment, applied here for sustainability) matters.

Same structural posture as `ml.forecasting.evaluation.benchmark` but
with classification rather than time-series metrics.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml.sustainability.data.loader import split_train_test
from ml.sustainability.data.schema import ESGDataset
from ml.sustainability.evaluation.metrics import (
    accuracy,
    brier_score,
    expected_calibration_error,
    hamming_loss,
    macro_f1,
)
from ml.sustainability.features.structured import labels_to_matrix
from ml.sustainability.models.base import ESGScorer


@dataclass(frozen=True)
class ArmResult:
    """Aggregated cross-fold metrics for a single ESG scoring arm."""

    name: str
    n_folds: int
    macro_f1: float
    accuracy: float
    hamming_loss: float
    brier_score: float
    expected_calibration_error: float


def _predict_arrays(model: ESGScorer, dataset: ESGDataset) -> tuple[np.ndarray, np.ndarray]:
    """Return (Y_true, Y_proba) for the given test dataset."""
    Y_true = labels_to_matrix(list(dataset.observations))
    proba_rows = []
    for obs in dataset.observations:
        proba_rows.append(model.score_proba(obs.profile))
    Y_proba = np.stack(proba_rows, axis=0)
    return Y_true, Y_proba


def benchmark_arm(
    dataset: ESGDataset,
    model: ESGScorer,
    *,
    n_folds: int = 3,
    test_fraction: float = 0.2,
    base_seed: int = 42,
    threshold: float = 0.5,
) -> ArmResult:
    """Multi-seed holdout: fit on each train split, score the held-out test.

    Independent random splits per fold (NOT k-fold CV — we use the
    cheaper variant to keep AS-004 runs fast). The full k-fold variant
    is a one-line change if a future thesis chapter wants it.
    """
    if n_folds < 1:
        raise ValueError("n_folds must be ≥ 1")
    macro_f1s, accs, hammings, briers, eces = [], [], [], [], []
    for k in range(n_folds):
        train, test = split_train_test(
            dataset, test_fraction=test_fraction, seed=base_seed + k
        )

        # Refit a fresh instance each fold so learned state never leaks.
        fresh = type(model).__new__(type(model))
        try:
            fresh.__init__()  # type: ignore[misc]
        except TypeError:
            # __init__ takes required args — preserve the original arms' hyperparams.
            fresh.__dict__.update(model.__dict__)
        # Copy user-tunable hyperparams from the template (non-underscored attrs).
        for attr, value in model.__dict__.items():
            if not attr.startswith("_"):
                setattr(fresh, attr, value)
        fresh.fit(train.observations)

        Y_true, Y_proba = _predict_arrays(fresh, test)
        Y_pred = (Y_proba >= threshold).astype(np.int64)
        macro_f1s.append(macro_f1(Y_true, Y_pred))
        accs.append(accuracy(Y_true, Y_pred))
        hammings.append(hamming_loss(Y_true, Y_pred))
        briers.append(brier_score(Y_true, Y_proba))
        eces.append(expected_calibration_error(Y_true, Y_proba))

    return ArmResult(
        name=model.name,
        n_folds=n_folds,
        macro_f1=float(np.mean(macro_f1s)),
        accuracy=float(np.mean(accs)),
        hamming_loss=float(np.mean(hammings)),
        brier_score=float(np.mean(briers)),
        expected_calibration_error=float(np.mean(eces)),
    )
