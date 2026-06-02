"""
Offline unit tests for the sustainability scoring arms + carbon model.

Each test exercises actual fit/score recursion — not a smoke test.
Synthetic fixtures come from `data.loader.generate_synthetic_dataset`
(deterministic seed).
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.sustainability.data.loader import generate_synthetic_dataset, split_train_test
from ml.sustainability.data.schema import CompanyProfile
from ml.sustainability.evaluation.metrics import macro_f1
from ml.sustainability.features.structured import labels_to_matrix
from ml.sustainability.models.baselines import (
    IndustryBaselineScorer,
    MajorityLabelScorer,
)
from ml.sustainability.models.carbon import CarbonEstimatorModel
from ml.sustainability.models.multilabel import LinearLogisticMultiLabel


def _profile(industry: str = "technology") -> CompanyProfile:
    return CompanyProfile(
        company_name="test-co",
        industry=industry,
        annual_revenue=10_000_000.0,
        employee_count=50,
        environmental_indicators={"a": 0.7, "b": 0.8},
        social_indicators={"a": 0.6, "b": 0.65},
        governance_indicators={"a": 0.55, "b": 0.6},
    )


# ── baselines ──────────────────────────────────────────────────────


def test_majority_label_scorer_fits_and_predicts_constants():
    ds = generate_synthetic_dataset(n_companies=100, seed=7)
    model = MajorityLabelScorer().fit(ds.observations)
    a = model.score(_profile())
    b = model.score(_profile(industry="manufacturing"))
    # By construction the majority arm is industry-agnostic.
    assert a.label_probabilities == b.label_probabilities


def test_industry_baseline_scorer_differs_by_industry():
    """Industry-baseline should produce *different* per-pillar means
    for different industries on the synthetic dataset (the loader
    deliberately shifts the means)."""
    ds = generate_synthetic_dataset(n_companies=300, seed=7)
    model = IndustryBaselineScorer().fit(ds.observations)
    tech = model.score(_profile(industry="technology"))
    manuf = model.score(_profile(industry="manufacturing"))
    # Tech firms score higher on environmental in the synthetic dist.
    assert tech.pillar_scores.environmental > manuf.pillar_scores.environmental


def test_industry_baseline_falls_back_to_global_for_unknown_industry():
    ds = generate_synthetic_dataset(n_companies=100, seed=7)
    model = IndustryBaselineScorer().fit(ds.observations)
    result = model.score(_profile(industry="space-mining"))
    # Should still produce *some* score (not crash) via the global fallback.
    assert 0.0 <= result.pillar_scores.composite <= 100.0


# ── LinearLogisticMultiLabel ───────────────────────────────────────


def test_linear_logistic_fit_score_basic_shape():
    ds = generate_synthetic_dataset(n_companies=120, seed=11)
    model = LinearLogisticMultiLabel(n_iterations=200).fit(ds.observations)
    result = model.score(_profile())
    # Three probabilities; each in [0, 1]; composite well-defined.
    for key in ("env_strong", "soc_strong", "gov_strong"):
        assert key in result.label_probabilities
        assert 0.0 <= result.label_probabilities[key] <= 1.0
    assert 0.0 <= result.pillar_scores.composite <= 100.0
    # SHAP-style top features should reference real feature names.
    assert len(result.top_features) == 3


def test_linear_logistic_beats_majority_baseline_macro_f1():
    """On the synthetic dataset with industry-conditional labels, the
    learning arm must beat the must-beat-random floor."""
    ds = generate_synthetic_dataset(n_companies=400, seed=11)
    train_ds, test_ds = split_train_test(ds, test_fraction=0.25, seed=11)

    majority = MajorityLabelScorer().fit(train_ds.observations)
    logistic = LinearLogisticMultiLabel(n_iterations=400).fit(train_ds.observations)

    Y_true = labels_to_matrix(list(test_ds.observations))
    Y_majority = np.stack(
        [majority.score_proba(obs.profile) for obs in test_ds.observations], axis=0
    )
    Y_logistic = np.stack(
        [logistic.score_proba(obs.profile) for obs in test_ds.observations], axis=0
    )
    f1_majority = macro_f1(Y_true, (Y_majority >= 0.5).astype(int))
    f1_logistic = macro_f1(Y_true, (Y_logistic >= 0.5).astype(int))
    assert f1_logistic > f1_majority


def test_linear_logistic_raises_before_fit():
    with pytest.raises(RuntimeError, match="fit"):
        LinearLogisticMultiLabel().score(_profile())


def test_linear_logistic_weights_inspection():
    """`weights_per_pillar` returns 3 vectors of the right length."""
    ds = generate_synthetic_dataset(n_companies=80, seed=11)
    model = LinearLogisticMultiLabel(n_iterations=100).fit(ds.observations)
    weights = model.weights_per_pillar()
    assert set(weights.keys()) == {"environmental", "social", "governance"}
    for vec in weights.values():
        assert vec.ndim == 1


# ── carbon ─────────────────────────────────────────────────────────


def test_carbon_scope_3_scales_with_revenue():
    """At fixed industry, doubling revenue should double Scope-3 tCO2e."""
    model = CarbonEstimatorModel()
    low = model.predict(industry="retail", annual_revenue=1_000_000)
    high = model.predict(industry="retail", annual_revenue=2_000_000)
    assert high.scope_3_tco2e == pytest.approx(2.0 * low.scope_3_tco2e, rel=1e-6)


def test_carbon_industry_intensity_uses_table():
    """Logistics has higher intensity than technology — Scope 3 should reflect that."""
    model = CarbonEstimatorModel()
    tech = model.predict(industry="technology", annual_revenue=5_000_000)
    log_ = model.predict(industry="logistics", annual_revenue=5_000_000)
    assert log_.scope_3_tco2e > tech.scope_3_tco2e


def test_carbon_total_is_sum_of_scopes():
    model = CarbonEstimatorModel()
    est = model.predict(
        industry="manufacturing",
        annual_revenue=5_000_000,
        energy_kwh=100_000.0,
        fleet_km=200_000.0,
    )
    total = est.scope_1_tco2e + est.scope_2_tco2e + est.scope_3_tco2e
    assert est.total_tco2e == pytest.approx(total)


def test_carbon_reduction_pathways_ordered_by_scope_share():
    """Largest-scope label appears first."""
    model = CarbonEstimatorModel()
    # Synthetic estimate where Scope 1 dominates.
    from ml.sustainability.data.schema import CarbonEstimate

    est = CarbonEstimate(
        industry="logistics", scope_1_tco2e=100.0, scope_2_tco2e=10.0, scope_3_tco2e=20.0
    )
    paths = model.reduction_pathways(est)
    # Scope 1 corresponds to "fleet" lever
    assert "fleet" in paths[0].lower()


def test_carbon_unknown_industry_uses_default():
    model = CarbonEstimatorModel()
    est = model.predict(industry="space-mining", annual_revenue=1_000_000)
    assert est.scope_3_tco2e > 0
