"""Offline construction tests for the pricing ORM model.

These don't touch a database — they verify the dataclass-like shape and
the discriminator behaviour so a future refactor that breaks one column
is caught without spinning up the integration containers."""

from __future__ import annotations

import uuid

from src.models.pricing import PricingAnalysis, PricingAnalysisType


def test_pricing_analysis_optimize_construction():
    row = PricingAnalysis(
        user_id=uuid.uuid4(),
        analysis_type=PricingAnalysisType.OPTIMIZE,
        product_id="sku-001",
        request_payload={
            "product_id": "sku-001",
            "current_price": 19.99,
            "unit_cost": 7.5,
            "objective": "revenue",
        },
        response_payload={
            "recommended_price": 23.50,
            "expected_revenue_uplift": 0.124,
        },
        recommended_price=23.50,
        expected_revenue_uplift=0.124,
        model_version="pricing-mock-0.1",
        processing_time_ms=4.2,
        num_trials_or_points=26,
    )
    assert row.analysis_type is PricingAnalysisType.OPTIMIZE
    assert row.recommended_price == 23.50
    assert row.expected_revenue_uplift == 0.124
    assert row.request_payload["current_price"] == 19.99


def test_pricing_analysis_monte_carlo_no_recommended_price():
    """Non-optimise types leave the headline columns NULL."""
    row = PricingAnalysis(
        user_id=uuid.uuid4(),
        analysis_type=PricingAnalysisType.MONTE_CARLO,
        product_id="sku-001",
        request_payload={"candidate_price": 21.0, "num_trials": 10_000},
        response_payload={
            "mean_revenue": 18_900,
            "revenue_p5": 16_200,
            "revenue_p95": 21_600,
        },
        model_version="pricing-mock-0.1",
        processing_time_ms=12.7,
        num_trials_or_points=10_000,
    )
    assert row.recommended_price is None
    assert row.expected_revenue_uplift is None
    assert row.num_trials_or_points == 10_000


def test_pricing_analysis_type_values_match_api_string():
    """The enum's string values are what the API surfaces — keep them stable."""
    assert PricingAnalysisType.OPTIMIZE.value == "optimize"
    assert PricingAnalysisType.MONTE_CARLO.value == "monte_carlo"
    assert PricingAnalysisType.ELASTICITY.value == "elasticity"
    assert PricingAnalysisType.SCENARIO_COMPARISON.value == "scenario_comparison"


def test_pricing_analysis_scenario_comparison_keeps_recommended():
    """Scenario comparison fills `recommended_price` from the winning scenario."""
    row = PricingAnalysis(
        user_id=uuid.uuid4(),
        analysis_type=PricingAnalysisType.SCENARIO_COMPARISON,
        product_id="sku-042",
        request_payload={"current_price": 50.0, "unit_cost": 20.0},
        response_payload={
            "scenarios": {"optimal": {"price": 54.0}},
            "recommended_scenario": "optimal",
        },
        recommended_price=54.0,
        model_version="pricing-mock-0.1",
        processing_time_ms=2.1,
        num_trials_or_points=3,
    )
    assert row.recommended_price == 54.0
    assert row.expected_revenue_uplift is None
