"""
BizVision AI — Profit Forecasting API Router

Endpoints:
- POST /forecast — Generate multi-scenario profit forecast
- POST /sensitivity — Run sensitivity analysis
- POST /what-if — What-if scenario simulation
- GET  /explanation/{forecast_id} — SHAP explanation for forecast drivers
- POST /cross-module — Forecast incorporating signals from other modules
- GET  /history — Forecast history (paged, filterable by series_name + analysis_type)
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.forecasting import (
    CrossModuleForecastRequest,
    ForecastAnalysisDetailResponse,
    ForecastRequest,
    ForecastResponse,
    SensitivityAnalysisRequest,
    SensitivityAnalysisResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from src.core.database import get_db
from src.core.deps import get_current_user
from src.models.user import User
from src.services.forecasting.forecasting_service import ForecastingService
from src.services.shared_context.context_bus import SharedContextBus

router = APIRouter()


@router.post(
    "/forecast",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate multi-scenario profit forecast",
    description="""
    Core forecasting intelligence endpoint.

    Processes financial time series through a hybrid ensemble:
    1. **Prophet** — trend decomposition + seasonality + holidays
    2. **LSTM** — long-term sequence dependencies (PyTorch)
    3. **XGBoost** — lag features + engineered signals
    4. **Stacking** — meta-learner combines all three forecasts
    5. **Scenario Generation** — Base / Bull / Bear scenarios with prediction intervals
    6. **SHAP Attribution** — Identifies the primary drivers of the forecast

    Horizon: 30, 60, 90, or 180 days
    Confidence interval: 80% and 95% prediction intervals
    """,
)
async def generate_forecast(
    request: ForecastRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ForecastingService(db)
    result = await service.generate_forecast(request, user_id=current_user.id)

    # Publish to context bus — executive chatbot can reference this
    background_tasks.add_task(
        SharedContextBus.publish,
        event_type="forecasting.forecast_complete",
        payload={
            "forecast_id": str(result.forecast_id),
            "horizon_days": request.forecast_horizon_days,
            "base_scenario_end_value": result.scenarios["base"].end_value,
            "bull_scenario_end_value": result.scenarios["bull"].end_value,
            "bear_scenario_end_value": result.scenarios["bear"].end_value,
        },
        user_id=str(current_user.id),
    )

    return result


@router.post(
    "/sensitivity",
    response_model=SensitivityAnalysisResponse,
    summary="Run sensitivity analysis (tornado chart)",
    description="Analyzes how much each input variable affects the forecast. Returns tornado chart data showing top drivers and their impact ranges.",
)
async def run_sensitivity_analysis(
    request: SensitivityAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ForecastingService(db)
    return await service.sensitivity_analysis(request, user_id=current_user.id)


@router.post(
    "/what-if",
    response_model=WhatIfResponse,
    summary="What-if scenario simulation",
    description="Run a custom what-if scenario by adjusting any input parameter and see the projected impact on profit trajectory.",
)
async def what_if_simulation(
    request: WhatIfRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ForecastingService(db)
    return await service.what_if(request, user_id=current_user.id)


@router.post(
    "/cross-module",
    summary="Forecast with cross-module intelligence signals",
    description="""
    Enhanced forecasting that integrates signals from other BizVision AI modules:
    - Pricing signals: expected revenue impact from pricing changes
    - Recruitment signals: projected operational cost impact from hiring
    - ESG signals: regulatory compliance cost risk
    """,
)
async def cross_module_forecast(
    request: CrossModuleForecastRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ForecastingService(db)
    return await service.cross_module_forecast(request, user_id=current_user.id)


@router.get(
    "/explanation/{forecast_id}",
    summary="Get SHAP explanation for forecast",
    description="Returns SHAP feature importances showing which factors (seasonality, pricing, hiring costs, etc.) drove the forecast and by how much.",
)
async def get_forecast_explanation(
    forecast_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ForecastingService(db)
    return await service.get_explanation(forecast_id=forecast_id, user_id=current_user.id)


@router.get(
    "/forecasts/{forecast_id}",
    response_model=ForecastAnalysisDetailResponse,
    summary="Get a single forecast analysis with its full request + response payloads",
    description=(
        "Returns the persisted forecast row — discriminator + series_name "
        "+ headline columns + faithful request/response JSONB. Backs the "
        "audit-feed deep-link from TASK-033. 404 if the forecast does not "
        "belong to the calling user."
    ),
)
async def get_forecast_record(
    forecast_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ForecastingService(db)
    return await service.get_forecast_detail(
        forecast_id=forecast_id,
        user_id=current_user.id,
    )


@router.get(
    "/history",
    summary="List the caller's forecast history",
    description=(
        "Returns the caller's `forecast_analyses` rows, newest first, "
        "with optional filters by `series_name` and `analysis_type` "
        "(`forecast` | `sensitivity` | `what_if` | `cross_module`)."
    ),
)
async def list_forecast_history(
    series_name: str | None = Query(default=None),
    analysis_type: str | None = Query(default=None),
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ForecastingService(db)
    return await service.list_history(
        user_id=current_user.id,
        series_name=series_name,
        analysis_type=analysis_type,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )
