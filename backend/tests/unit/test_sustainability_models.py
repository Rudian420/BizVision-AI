"""Offline construction tests for the sustainability ORM model.

No DB connection — verifies the discriminator-keyed shape and the
headline-column nullability so a future refactor that breaks one column
is caught without spinning up the integration containers. Mirrors the
pattern used in `test_pricing_models.py` (TASK-009)."""

from __future__ import annotations

import uuid

from src.models.sustainability import (
    SustainabilityAssessment,
    SustainabilityAssessmentType,
)


def test_sustainability_assessment_score_construction():
    row = SustainabilityAssessment(
        user_id=uuid.uuid4(),
        assessment_type=SustainabilityAssessmentType.SCORE,
        company_name="Acme Corp",
        industry="manufacturing",
        request_payload={
            "company_name": "Acme Corp",
            "industry": "manufacturing",
            "annual_revenue": 5_000_000.0,
            "employee_count": 42,
            "environmental_indicators": {"energy_efficiency": 0.7},
        },
        response_payload={
            "composite_score": 64.5,
            "risk_level": "medium",
            "sub_scores": {
                "environmental": 70.0,
                "social": 60.0,
                "governance": 63.5,
            },
        },
        composite_score=64.5,
        risk_level="medium",
        model_version="esg-mock-0.1",
        processing_time_ms=3.1,
        interpretation="Composite 64.5/100 → medium risk.",
    )
    assert row.assessment_type is SustainabilityAssessmentType.SCORE
    assert row.composite_score == 64.5
    assert row.risk_level == "medium"
    assert row.total_tco2e is None
    assert row.request_payload["annual_revenue"] == 5_000_000.0


def test_sustainability_assessment_simulation_construction():
    """Simulation rows carry a projected composite_score + risk_level
    but reference the parent score via `request_payload['assessment_id']`."""
    parent_id = uuid.uuid4()
    row = SustainabilityAssessment(
        user_id=uuid.uuid4(),
        assessment_type=SustainabilityAssessmentType.SIMULATION,
        company_name="Acme Corp",
        industry="manufacturing",
        request_payload={
            "assessment_id": str(parent_id),
            "investments": {"solar_install": 50_000.0},
            "horizon_months": 24,
        },
        response_payload={
            "assessment_id": str(parent_id),
            "baseline_score": 64.5,
            "projected_score": 69.5,
            "score_uplift": 5.0,
            "payback_months": 18,
            "projected_carbon_reduction_tco2e": 100.0,
        },
        composite_score=69.5,
        risk_level="medium",
        model_version="esg-mock-0.1",
        processing_time_ms=1.8,
    )
    assert row.assessment_type is SustainabilityAssessmentType.SIMULATION
    assert row.composite_score == 69.5
    assert row.request_payload["assessment_id"] == str(parent_id)
    assert row.total_tco2e is None


def test_sustainability_assessment_recommendations_construction():
    """Recommendations rows leave all headline columns NULL — they're a
    catalog read, not a fresh score."""
    parent_id = uuid.uuid4()
    row = SustainabilityAssessment(
        user_id=uuid.uuid4(),
        assessment_type=SustainabilityAssessmentType.RECOMMENDATIONS,
        company_name="Acme Corp",
        industry="manufacturing",
        request_payload={
            "assessment_id": str(parent_id),
            "max_recommendations": 5,
        },
        response_payload={
            "assessment_id": str(parent_id),
            "recommendations": [
                {
                    "title": "Switch to renewable energy contract",
                    "pillar": "E",
                    "estimated_score_impact": 6.5,
                    "implementation_effort": "medium",
                    "rationale": "Cuts Scope 2 emissions.",
                }
            ],
        },
        model_version="esg-mock-0.1",
        processing_time_ms=0.9,
    )
    assert row.composite_score is None
    assert row.risk_level is None
    assert row.total_tco2e is None
    assert len(row.response_payload["recommendations"]) == 1


def test_sustainability_assessment_carbon_estimate_construction():
    row = SustainabilityAssessment(
        user_id=uuid.uuid4(),
        assessment_type=SustainabilityAssessmentType.CARBON_ESTIMATE,
        company_name=None,
        industry="logistics",
        request_payload={
            "industry": "logistics",
            "annual_revenue": 2_000_000.0,
            "employee_count": 15,
            "energy_kwh": 100_000.0,
            "fleet_km": 250_000.0,
        },
        response_payload={
            "scope_1_tco2e": 42.5,
            "scope_2_tco2e": 40.0,
            "scope_3_tco2e": 600.0,
            "total_tco2e": 682.5,
            "intensity_per_revenue": 341.25,
        },
        total_tco2e=682.5,
        model_version="esg-mock-0.1",
        processing_time_ms=2.2,
        interpretation="Total 682.5 tCO2e.",
    )
    assert row.assessment_type is SustainabilityAssessmentType.CARBON_ESTIMATE
    assert row.total_tco2e == 682.5
    assert row.composite_score is None
    assert row.risk_level is None
    assert row.company_name is None


def test_sustainability_assessment_type_values_match_api_string():
    """The enum's string values are what `assessment_type` surfaces — keep them stable."""
    assert SustainabilityAssessmentType.SCORE.value == "score"
    assert SustainabilityAssessmentType.SIMULATION.value == "simulation"
    assert SustainabilityAssessmentType.RECOMMENDATIONS.value == "recommendations"
    assert SustainabilityAssessmentType.CARBON_ESTIMATE.value == "carbon_estimate"
