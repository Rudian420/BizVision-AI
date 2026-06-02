"""
BizVision AI — Profit Forecasting Schemas
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.v1.schemas.common import SHAPFeature

# ── Requests ───────────────────────────────────────────────────────


class TimeSeriesPoint(BaseModel):
    ds: date = Field(..., description="Date stamp")
    y: float = Field(..., description="Observed value (revenue/profit)")


class ForecastRequest(BaseModel):
    series_name: str = Field(default="profit")
    history: list[TimeSeriesPoint] = Field(..., min_length=3)
    forecast_horizon_days: int = Field(default=90, ge=7, le=365)
    include_scenarios: bool = True


class SensitivityAnalysisRequest(BaseModel):
    history: list[TimeSeriesPoint] = Field(..., min_length=3)
    drivers: dict[str, float] = Field(
        ..., description="Driver name -> baseline value (e.g. price, headcount)"
    )
    perturbation_pct: float = Field(default=0.1, gt=0, le=1.0)


class WhatIfRequest(BaseModel):
    history: list[TimeSeriesPoint] = Field(..., min_length=3)
    adjustments: dict[str, float] = Field(..., description="Driver name -> new value override")
    forecast_horizon_days: int = Field(default=90, ge=7, le=365)


class CrossModuleForecastRequest(BaseModel):
    history: list[TimeSeriesPoint] = Field(..., min_length=3)
    forecast_horizon_days: int = Field(default=90, ge=7, le=365)
    include_pricing_signals: bool = True
    include_recruitment_signals: bool = True
    include_esg_signals: bool = True


# ── Responses ──────────────────────────────────────────────────────


class ForecastPoint(BaseModel):
    ds: date
    yhat: float
    yhat_lower: float
    yhat_upper: float


class ScenarioForecast(BaseModel):
    scenario: str
    points: list[ForecastPoint] = Field(default_factory=list)
    end_value: float
    cumulative_value: float


class ForecastResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    forecast_id: UUID
    series_name: str
    generated_at: datetime
    horizon_days: int
    scenarios: dict[str, ScenarioForecast]
    primary_drivers: list[SHAPFeature] = Field(default_factory=list)
    mape: float = Field(..., description="Backtest mean absolute percentage error")
    model_version: str = "forecast-ensemble-mock-0.1"


class TornadoBar(BaseModel):
    driver: str
    low_impact: float
    high_impact: float
    swing: float


class SensitivityAnalysisResponse(BaseModel):
    forecast_id: UUID
    tornado: list[TornadoBar]
    most_sensitive_driver: str


class WhatIfResponse(BaseModel):
    forecast_id: UUID
    baseline_end_value: float
    adjusted_end_value: float
    delta_pct: float
    points: list[ForecastPoint] = Field(default_factory=list)


# ── Detail / record-view (TASK-033) ────────────────────────────────


class ForecastAnalysisDetailResponse(BaseModel):
    """Persisted-row reconstruction returned by
    `GET /forecasting/forecasts/{forecast_id}`. Backs the audit-feed
    deep-link from TASK-033 (`reference_type='forecast_analysis'`).

    Same posture as PricingAnalysisDetailResponse: discriminator-keyed
    polymorphic table → one schema serves every variant
    (forecast / sensitivity / what_if / cross_module). The
    `analysis_type` tells the UI which response_payload shape lives
    inside.
    """

    model_config = ConfigDict(protected_namespaces=())

    forecast_id: UUID
    analysis_type: str  # forecast / sensitivity / what_if / cross_module
    series_name: str | None = None
    created_at: datetime

    model_version: str
    processing_time_ms: float

    # Headline columns surfaced for cheap filtering.
    horizon_days: int | None = None
    base_end_value: float | None = None
    bull_end_value: float | None = None
    bear_end_value: float | None = None
    mape: float | None = None
    interpretation: str | None = None

    request_payload: dict
    response_payload: dict
