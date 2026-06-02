"""Round-trip tests for the LIME companion serialisation
(TASK-052 / FE-016 wave 3a — MLflow registry leg).

We test the on-disk contract directly so the suite stays runnable
without a live MLflow server or a real `XGBoostRanker`. Joblib
round-trips any standard Python object, so a small dataclass is
enough to exercise the save → load → assert-equality path.

The real `XGBoostRanker` round-trip is exercised by the
recruitment training pipeline's MLflow integration once the
container is healthy (TASK-051).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from ml.recruitment.registry.lime_companions import (
    BACKGROUND_FILENAME,
    COMPANIONS_DIR_NAME,
    XGB_FILENAME,
    load_companions_from_dir,
    save_companions_to_dir,
)


@dataclass
class _StubRanker:
    """Joblib-picklable stub mirroring the surface
    `LIMERecruitmentExplainer.__init__` expects from `XGBoostRanker`
    — but we don't invoke any of it here, only the pickle round-trip."""

    name: str = "stub-xgb"
    params: dict = None


def test_save_and_load_roundtrip(tmp_path):
    """The companions written by `save_companions_to_dir` deserialise
    back to equivalent objects via `load_companions_from_dir`. This
    is the bedrock contract — the inference client's MLflow registry
    path leans on it being honest."""
    ranker = _StubRanker(name="round-tripper", params={"n_estimators": 100})
    background = np.array(
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
        dtype=np.float64,
    )

    companions_dir = save_companions_to_dir(
        tmp_path, xgb_ranker=ranker, background=background
    )

    # On-disk layout matches the documented contract.
    assert companions_dir == tmp_path / COMPANIONS_DIR_NAME
    assert (companions_dir / XGB_FILENAME).exists()
    assert (companions_dir / BACKGROUND_FILENAME).exists()

    loaded_ranker, loaded_bg = load_companions_from_dir(tmp_path)
    assert loaded_ranker is not None
    assert loaded_bg is not None
    assert loaded_ranker.name == "round-tripper"
    assert loaded_ranker.params == {"n_estimators": 100}
    np.testing.assert_array_equal(loaded_bg, background)


def test_load_returns_none_for_missing_directory(tmp_path):
    """When the `lime_companions/` subdir doesn't exist (e.g. a run
    registered before TASK-052), the loader returns `(None, None)`
    rather than raising — the inference client interprets that as
    "no LIME on this path"."""
    out = load_companions_from_dir(tmp_path)
    assert out == (None, None)


def test_load_returns_none_for_partial_companions(tmp_path):
    """Half-written companions (e.g. an interrupted training run that
    saved the XGBoost arm but not the background) must NOT
    deserialise into a working pair — the loader returns
    `(None, None)`, keeping LIME empty rather than running the
    explainer against a stale or unknown background."""
    companions_dir = tmp_path / COMPANIONS_DIR_NAME
    companions_dir.mkdir()
    # Only XGB; background is missing.
    import joblib

    joblib.dump(_StubRanker(), companions_dir / XGB_FILENAME)
    out = load_companions_from_dir(tmp_path)
    assert out == (None, None)


def test_save_rejects_non_2d_background(tmp_path):
    """Pinning the background to 2-D keeps the contract narrow —
    a 1-D or 3-D matrix would silently broadcast inside LIME's
    perturbation step, which is a debugging hellscape. Reject at
    save time instead."""
    ranker = _StubRanker()
    one_d = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    with pytest.raises(ValueError, match="background must be 2-D"):
        save_companions_to_dir(tmp_path, xgb_ranker=ranker, background=one_d)


def test_save_normalises_background_to_float64(tmp_path):
    """`np.save` happily round-trips any dtype, but LIME always
    operates on float64. The saver coerces — verify the loaded
    matrix is float64 even when the caller passed int32."""
    ranker = _StubRanker()
    int_bg = np.array([[1, 2], [3, 4], [5, 6]], dtype=np.int32)
    save_companions_to_dir(tmp_path, xgb_ranker=ranker, background=int_bg)
    _, loaded_bg = load_companions_from_dir(tmp_path)
    assert loaded_bg is not None
    assert loaded_bg.dtype == np.float64
    np.testing.assert_array_equal(loaded_bg, int_bg.astype(np.float64))
