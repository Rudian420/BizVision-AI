"""Offline construction tests for the forecasting ORM model.

No DB connection — verifies the discriminator-keyed shape and the
headline-column nullability so a future refactor that breaks one column
is caught without spinning up the integration containers. Mirrors the
pattern used in `test_pricing_models.py` (TASK-009) and
`test_sustainability_models.py` (TASK-012)."""

from __future__ import annotations

import uuid

from src.models.forecasting import ForecastAnalysis, ForecastAnalysisType


def test_forecast_analysis_forecast_construction():
    row = ForecastAnalysis(
        user_id=uuid.uuid4(),
        analysis_type=ForecastAnalysisType.FORECAST,
        series_name="profit",
        request_payload={
            "series_name": "profit",
            "history": [{"ds": "2026-01-01", "y": 100.0}],
            "forecast_horizon_days": 90,
        },
        response_payload={
            "forecast_id": str(uuid.uuid4()),
            "series_name": "profit",
            "horizon_days": 90,
            "scenarios": {
                "base": {"end_value": 124.5},
                "bull": {"end_value": 143.2},
                "bear": {"end_value": 105.8},
            },
            "mape": 6.4,
        },
        horizon_days=90,
        base_end_value=124.5,
        bull_end_value=143.2,
        bear_end_value=105.8,
        mape=6.4,
        model_version="forecast-ensemble-mock-0.1",
        processing_time_ms=4.2,
        interpretation="90-day forecast for 'profit'.",
    )
    assert row.analysis_type is ForecastAnalysisType.FORECAST
    assert row.horizon_days == 90
    assert row.base_end_value == 124.5
    assert row.bull_end_value == 143.2
    assert row.bear_end_value == 105.8
    assert row.mape == 6.4
    assert row.request_payload["forecast_horizon_days"] == 90


def test_forecast_analysis_sensitivity_leaves_scenario_fields_null():
    """Sensitivity rows are tornado-only — no scenarios, no horizon."""
    row = ForecastAnalysis(
        user_id=uuid.uuid4(),
        analysis_type=ForecastAnalysisType.SENSITIVITY,
        series_name=None,
        request_payload={
            "history": [{"ds": "2026-01-01", "y": 100.0}],
            "drivers": {"price": 20.0, "headcount": 50.0},
            "perturbation_pct": 0.1,
        },
        response_payload={
            "forecast_id": str(uuid.uuid4()),
            "tornado": [
                {"driver": "headcount", "low_impact": -5.0, "high_impact": 5.0, "swing": 10.0}
            ],
            "most_sensitive_driver": "headcount",
        },
        model_version="forecast-ensemble-mock-0.1",
        processing_time_ms=1.2,
    )
    assert row.analysis_type is ForecastAnalysisType.SENSITIVITY
    assert row.horizon_days is None
    assert row.base_end_value is None
    assert row.bull_end_value is None
    assert row.bear_end_value is None
    assert row.mape is None
    assert row.series_name is None


def test_forecast_analysis_what_if_keeps_only_baseline():
    """What-if rows fill `base_end_value` from the baseline scenario but
    leave bull/bear NULL — only the adjusted leg is meaningful."""
    row = ForecastAnalysis(
        user_id=uuid.uuid4(),
        analysis_type=ForecastAnalysisType.WHAT_IF,
        series_name=None,
        request_payload={
            "history": [{"ds": "2026-01-01", "y": 100.0}],
            "adjustments": {"price_uplift_pct": 5.0},
            "forecast_horizon_days": 60,
        },
        response_payload={
            "forecast_id": str(uuid.uuid4()),
            "baseline_end_value": 120.0,
            "adjusted_end_value": 126.0,
            "delta_pct": 0.05,
        },
        horizon_days=60,
        base_end_value=120.0,
        bull_end_value=None,
        bear_end_value=None,
        model_version="forecast-ensemble-mock-0.1",
        processing_time_ms=2.5,
    )
    assert row.analysis_type is ForecastAnalysisType.WHAT_IF
    assert row.horizon_days == 60
    assert row.base_end_value == 120.0
    assert row.bull_end_value is None
    assert row.bear_end_value is None


def test_forecast_analysis_cross_module_keeps_three_scenarios():
    row = ForecastAnalysis(
        user_id=uuid.uuid4(),
        analysis_type=ForecastAnalysisType.CROSS_MODULE,
        series_name="profit_cross_module",
        request_payload={
            "history": [{"ds": "2026-01-01", "y": 100.0}],
            "forecast_horizon_days": 90,
            "include_pricing_signals": True,
            "include_recruitment_signals": True,
            "include_esg_signals": True,
        },
        response_payload={
            "forecast_id": str(uuid.uuid4()),
            "series_name": "profit_cross_module",
            "horizon_days": 90,
            "scenarios": {
                "base": {"end_value": 130.0},
                "bull": {"end_value": 149.5},
                "bear": {"end_value": 110.5},
            },
            "mape": 5.9,
        },
        horizon_days=90,
        base_end_value=130.0,
        bull_end_value=149.5,
        bear_end_value=110.5,
        mape=5.9,
        model_version="forecast-ensemble-mock-0.1",
        processing_time_ms=3.8,
    )
    assert row.analysis_type is ForecastAnalysisType.CROSS_MODULE
    assert row.series_name == "profit_cross_module"
    assert row.bull_end_value == 149.5
    assert row.mape == 5.9


def test_forecast_analysis_type_values_match_api_string():
    """The enum's string values are what `analysis_type` surfaces and
    the `/history?analysis_type=` filter accepts — keep them stable."""
    assert ForecastAnalysisType.FORECAST.value == "forecast"
    assert ForecastAnalysisType.SENSITIVITY.value == "sensitivity"
    assert ForecastAnalysisType.WHAT_IF.value == "what_if"
    assert ForecastAnalysisType.CROSS_MODULE.value == "cross_module"
