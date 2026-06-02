"""
BizVision AI — Smart Pricing Advisor API Router

Endpoints:
- POST /optimize — Get AI-optimized price recommendation
- POST /simulate — Run Monte Carlo price simulation
- POST /elasticity — Calculate price elasticity curve
- GET  /explanation/{analysis_id} — SHAP explanation for price decision
- POST /scenarios — Compare multiple pricing scenarios
- GET  /history — Price optimization history
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.pricing import (
    ElasticityAnalysisRequest,
    ElasticityAnalysisResponse,
    MonteCarloSimulationRequest,
    MonteCarloSimulationResponse,
    PriceOptimizationRequest,
    PriceOptimizationResponse,
    PricingAnalysisDetailResponse,
    ScenarioComparisonRequest,
    ScenarioComparisonResponse,
)
from src.core.database import get_db
from src.core.deps import get_current_user
from src.models.user import User
from src.services.pricing.pricing_service import PricingService
from src.services.shared_context.context_bus import SharedContextBus

router = APIRouter()


@router.post(
    "/optimize",
    response_model=PriceOptimizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI-optimized price recommendation",
    description="""
    Core pricing intelligence endpoint.

    Processes product/service data through:
    1. **Demand Forecasting** — LightGBM model predicts demand at each price point
    2. **Elasticity Estimation** — Calculates price sensitivity curve
    3. **Revenue Surface** — Computes revenue = price × demand across full range
    4. **RL Refinement** — PPO agent recommends strategic price based on business context
    5. **SHAP Attribution** — Explains which factors drove the recommendation
    6. **Scenario Generation** — Conservative / Optimal / Aggressive price variants

    Returns recommended price with confidence interval, scenario analysis, and SHAP explanation.
    """,
)
async def optimize_price(
    request: PriceOptimizationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PricingService(db)
    result = await service.optimize(request, user_id=current_user.id)

    # Cross-module signal: pricing decisions affect forecasting
    background_tasks.add_task(
        SharedContextBus.publish,
        event_type="pricing.optimization_complete",
        payload={
            "analysis_id": str(result.analysis_id),
            "product_id": request.product_id,
            "recommended_price": result.recommended_price,
            "expected_revenue_uplift": result.expected_revenue_uplift,
            "price_confidence_interval": result.confidence_interval,
        },
        user_id=str(current_user.id),
    )

    return result


@router.post(
    "/simulate",
    response_model=MonteCarloSimulationResponse,
    summary="Run Monte Carlo price simulation",
    description="Runs N Monte Carlo trials to estimate revenue distribution and price risk at various price points. Returns percentiles, VaR, and probability distributions.",
)
async def run_monte_carlo(
    request: MonteCarloSimulationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PricingService(db)
    return await service.run_monte_carlo(request, user_id=current_user.id)


@router.post(
    "/elasticity",
    response_model=ElasticityAnalysisResponse,
    summary="Calculate price elasticity curve",
    description="Estimates price elasticity of demand across the full price range. Identifies elastic/inelastic regions and optimal pricing zone.",
)
async def calculate_elasticity(
    request: ElasticityAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PricingService(db)
    return await service.calculate_elasticity(request, user_id=current_user.id)


@router.post(
    "/scenarios",
    response_model=ScenarioComparisonResponse,
    summary="Compare multiple pricing scenarios",
    description="Compare conservative, optimal, and aggressive pricing strategies side-by-side with revenue projections, risk metrics, and recommendation rationale.",
)
async def compare_scenarios(
    request: ScenarioComparisonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PricingService(db)
    return await service.compare_scenarios(request, user_id=current_user.id)


@router.get(
    "/explanation/{analysis_id}",
    summary="Get SHAP explanation for pricing recommendation",
    description="Returns SHAP feature attributions, LIME local explanation, and LLM-generated pricing rationale for a specific analysis.",
)
async def get_pricing_explanation(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PricingService(db)
    return await service.get_explanation(analysis_id=analysis_id, user_id=current_user.id)


@router.get(
    "/analyses/{analysis_id}",
    response_model=PricingAnalysisDetailResponse,
    summary="Get a single pricing analysis with its full request + response payloads",
    description=(
        "Returns the persisted analysis row — discriminator + product_id "
        "+ headline columns + faithful request/response JSONB. Backs the "
        "audit-feed deep-link from TASK-033. 404 if the analysis does not "
        "belong to the calling user."
    ),
)
async def get_pricing_analysis(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PricingService(db)
    return await service.get_analysis_detail(
        analysis_id=analysis_id,
        user_id=current_user.id,
    )


@router.get(
    "/history",
    summary="List price optimization history",
)
async def list_pricing_history(
    product_id: str | None = None,
    analysis_type: str | None = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PricingService(db)
    return await service.list_history(
        user_id=current_user.id,
        product_id=product_id,
        analysis_type=analysis_type,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )
