"""
LIME companion artifacts for the recruitment model registry.

TASK-052 — closes the MLflow registry-path leg of FE-016 wave 3a.

Wave 3a (TASK-049) wired the real `LIMERecruitmentExplainer` through
`RecruitmentInferenceClient`, but only on the *synthetic-bootstrap*
path. The MLflow registry path was deliberately left empty because:

- `mlflow.pyfunc.load_model(...)` wraps the ensemble as an opaque
  callable. We cannot reach into it to recover the fitted XGBoost
  arm that LIME wants to perturb, nor the training-feature
  background it needs as a perturbation reference.
- LIME on a pyfunc-only registry payload would have to *recompute*
  the background by re-fetching the training data — expensive and
  fragile (data drift between train and serve).

The fix: when a real training run lands a model in the registry,
*also* log the XGBoost arm and the background matrix as *side*-
artifacts in a known subdirectory (`lime_companions/`). The
inference client's registry loader then downloads those side-
artifacts via `mlflow.artifacts.download_artifacts(...)` and
re-hydrates them next to the pyfunc.

Two-file format under `lime_companions/`:

    xgb_ranker.joblib   — the fitted `XGBoostRanker` (sklearn-style
                          pickle via joblib; small + standard).
    background.npy      — the `(n_pairs, n_features)` LIME
                          perturbation background (np.save format).

This module is the single source of truth for those two filenames —
both the training-side write path (`save_companions_to_dir`) and
the inference-side read path (`load_companions_from_dir`) live
here so a future filename change can't drift between them.

Heavy imports (`joblib`, `numpy`) are kept at module level — both
ship in `ml/requirements.txt` and `backend/requirements.txt`, and
the training + inference paths already pull them in directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ml.recruitment.models.structured import XGBoostRanker


# ── On-disk layout (the contract both sides honour) ──────────────────

COMPANIONS_DIR_NAME = "lime_companions"
XGB_FILENAME = "xgb_ranker.joblib"
BACKGROUND_FILENAME = "background.npy"


def save_companions_to_dir(
    out_dir: Path | str,
    *,
    xgb_ranker: XGBoostRanker,
    background: np.ndarray,
) -> Path:
    """Serialise `xgb_ranker` + `background` under
    `<out_dir>/lime_companions/`.

    Creates the subdirectory if it doesn't exist. Returns the
    absolute path to the companions directory so the caller can
    feed it to `mlflow.log_artifacts(local_dir=str(companions_dir),
    artifact_path=COMPANIONS_DIR_NAME)`.

    `background` is enforced to a 2-D float64 array — `np.save` is
    happy to round-trip any dtype, but pinning to float64 here
    keeps the contract narrow (the LIME explainer always operates
    on float64, and an unexpected dtype would silently broadcast).
    """
    import joblib  # local import — joblib's import time is non-trivial

    out_dir = Path(out_dir)
    companions_dir = out_dir / COMPANIONS_DIR_NAME
    companions_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(xgb_ranker, companions_dir / XGB_FILENAME)

    bg = np.asarray(background, dtype=np.float64)
    if bg.ndim != 2:
        raise ValueError(
            f"background must be 2-D; got shape {bg.shape}. "
            "Stack `build_feature_matrix(pair.job, [pair.candidate])[0]` "
            "over the training pairs before saving."
        )
    np.save(companions_dir / BACKGROUND_FILENAME, bg, allow_pickle=False)

    return companions_dir


def load_companions_from_dir(
    in_dir: Path | str,
) -> tuple["XGBoostRanker | None", np.ndarray | None]:
    """Deserialise the LIME companions from `<in_dir>/lime_companions/`.

    `in_dir` is typically the local path returned by
    `mlflow.artifacts.download_artifacts(...)` against the
    `recruitment-ranker` Production version. Returns `(None, None)`
    when the companions directory or either file is missing — the
    inference client falls through to empty LIME in that case,
    same defensive contract as the test-injection path (TASK-049).

    The XGBoost ranker round-trips as a self-contained joblib
    pickle. We do *not* re-fit anything here; the ranker's
    `_model` attribute (the actual XGBoost booster) is restored
    by joblib alongside its hyperparameters.
    """
    import joblib

    in_dir = Path(in_dir)
    companions_dir = in_dir / COMPANIONS_DIR_NAME
    xgb_path = companions_dir / XGB_FILENAME
    bg_path = companions_dir / BACKGROUND_FILENAME

    if not xgb_path.exists() or not bg_path.exists():
        return None, None

    try:
        xgb_ranker = joblib.load(xgb_path)
        background = np.load(bg_path, allow_pickle=False)
    except Exception:  # pragma: no cover - defensive
        return None, None

    if background.ndim != 2:
        return None, None

    return xgb_ranker, background
