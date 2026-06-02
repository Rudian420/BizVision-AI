"""Synthetic data generators are deterministic and well-formed."""

from __future__ import annotations

from ml.data.synthetic.generators import (
    generate_forecasting,
    generate_pricing,
    generate_recruitment,
    generate_sustainability,
)


def test_recruitment_shape_and_determinism():
    a = generate_recruitment(n=500, seed=1)
    b = generate_recruitment(n=500, seed=1)
    assert len(a) == 500
    assert a.equals(b)  # deterministic for a fixed seed
    assert {"hired", "gender", "skill_match"}.issubset(a.columns)
    assert a["hired"].isin([0, 1]).all()


def test_pricing_demand_non_negative():
    df = generate_pricing(n=800, seed=2)
    assert (df["demand"] >= 0).all()


def test_forecasting_is_timeseries():
    df = generate_forecasting(days=200, seed=3)
    assert df["ds"].is_monotonic_increasing
    assert len(df) == 200


def test_sustainability_labels_binary():
    df = generate_sustainability(n=400, seed=4)
    for col in ("label_env_strong", "label_soc_strong", "label_gov_strong"):
        assert df[col].isin([0, 1]).all()
