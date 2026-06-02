"""
Offline tests for the industry fairness audit.

Pure numpy + pytest. The audit machinery is small but load-bearing for
the thesis chapter on fair ESG scoring — we verify the disparate-impact
formula, the four-fifths rule threshold, and the per-pillar
aggregation against hand-worked examples.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from ml.sustainability.data.loader import generate_synthetic_dataset
from ml.sustainability.data.schema import CompanyProfile, ESGScoreResult, PillarScore
from ml.sustainability.fairness.auditor import (
    audit_industry_fairness,
    disparate_impact,
    four_fifths_rule_violation,
)
from ml.sustainability.models.base import ESGScorer


class _IndustryConditionalStub(ESGScorer):
    """Stub scorer with hard-coded per-industry probabilities.

    Lets us prove the audit machinery flags a known-biased model.
    """

    requires_training = False

    def __init__(self, per_industry_proba: dict[str, tuple[float, float, float]]):
        self._per_industry = per_industry_proba

    @property
    def name(self) -> str:
        return "industry-conditional-stub"

    def fit(self, observations):
        return self

    def score(self, profile: CompanyProfile) -> ESGScoreResult:
        probs = self._per_industry.get(profile.industry, (0.5, 0.5, 0.5))
        return ESGScoreResult(
            company_name=profile.company_name,
            industry=profile.industry,
            pillar_scores=PillarScore(50.0, 50.0, 50.0),
            risk_level="medium",
            industry_percentile=50.0,
            label_probabilities={
                "env_strong": probs[0],
                "soc_strong": probs[1],
                "gov_strong": probs[2],
            },
            model_name=self.name,
        )

    def score_proba(self, profile: CompanyProfile) -> np.ndarray:
        return np.array(self._per_industry.get(profile.industry, (0.5, 0.5, 0.5)))


def _profiles_for_industries(industries: Sequence[str], n_per: int = 10) -> list[CompanyProfile]:
    out = []
    for ind in industries:
        for i in range(n_per):
            out.append(
                CompanyProfile(
                    company_name=f"{ind}-{i}",
                    industry=ind,
                    annual_revenue=1_000_000.0,
                    employee_count=10,
                )
            )
    return out


# ── disparate_impact / four-fifths ─────────────────────────────────


def test_disparate_impact_perfect_parity_is_one():
    assert disparate_impact(0.5, 0.5) == 1.0


def test_disparate_impact_handworked():
    """50% min / 80% max → DI = 0.625."""
    assert disparate_impact(0.5, 0.8) == pytest.approx(0.625)


def test_disparate_impact_zero_max_returns_one():
    """Both rates ~0 → no disparity possible by convention."""
    assert disparate_impact(0.0, 0.0) == 1.0


def test_four_fifths_rule_at_threshold():
    assert four_fifths_rule_violation(0.79) is True
    assert four_fifths_rule_violation(0.80) is False
    assert four_fifths_rule_violation(1.0) is False


# ── audit_industry_fairness ────────────────────────────────────────


def test_audit_flags_biased_environmental_classifier():
    """If env_prob varies wildly across industries, the env pillar
    should fail the four-fifths rule."""
    biased = _IndustryConditionalStub(
        per_industry_proba={
            "manufacturing": (0.10, 0.5, 0.5),  # very low env-strong rate
            "technology": (0.90, 0.5, 0.5),  # very high env-strong rate
            "retail": (0.50, 0.5, 0.5),
        }
    )
    profiles = _profiles_for_industries(["manufacturing", "technology", "retail"])
    audit = biased.fit([]).score_proba  # sanity — just ensure score_proba works
    assert audit(profiles[0])[0] == pytest.approx(0.10)

    result = audit_industry_fairness(biased, profiles, threshold=0.5)
    env = next(m for m in result.per_pillar if m.pillar == "environmental")
    assert env.four_fifths_violated is True
    # The other pillars (soc, gov) have uniform probabilities → no violation.
    others = [m for m in result.per_pillar if m.pillar != "environmental"]
    assert not any(m.four_fifths_violated for m in others)
    assert result.any_violation is True


def test_audit_clean_classifier_does_not_flag_violation():
    fair = _IndustryConditionalStub(
        per_industry_proba={
            "manufacturing": (0.55, 0.55, 0.55),
            "technology": (0.60, 0.60, 0.60),
            "retail": (0.58, 0.58, 0.58),
        }
    )
    profiles = _profiles_for_industries(["manufacturing", "technology", "retail"])
    result = audit_industry_fairness(fair, profiles, threshold=0.5)
    # All three pillars should pass the four-fifths rule.
    assert all(not m.four_fifths_violated for m in result.per_pillar)
    assert result.any_violation is False


def test_audit_records_per_group_sample_sizes():
    """`per_group_n` should reflect the actual count per industry."""
    stub = _IndustryConditionalStub({"technology": (0.5, 0.5, 0.5)})
    profiles = _profiles_for_industries(["technology"], n_per=12)
    result = audit_industry_fairness(stub, profiles, threshold=0.5)
    for m in result.per_pillar:
        assert m.per_group_n["technology"] == 12


def test_audit_on_real_industry_baseline_does_not_crash():
    """End-to-end smoke — the real IndustryBaselineScorer feeds into
    the audit without exception."""
    from ml.sustainability.models.baselines import IndustryBaselineScorer

    ds = generate_synthetic_dataset(n_companies=200, seed=11)
    model = IndustryBaselineScorer().fit(ds.observations)
    audit = audit_industry_fairness(
        model, [obs.profile for obs in ds.observations[:50]], threshold=0.5
    )
    # Three pillars audited; per-group rates populated for the sampled industries.
    assert len(audit.per_pillar) == 3
