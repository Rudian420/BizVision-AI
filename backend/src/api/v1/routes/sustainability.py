"""
BizVision AI — Green Business Sustainability Scorer API Router

Endpoints:
- POST /score — Calculate comprehensive ESG sustainability score
- POST /simulate — Simulate ESG improvement scenarios
- GET  /benchmarks — Industry ESG benchmarks comparison
- GET  /explanation/{assessment_id} — SHAP explanation for ESG score
- POST /recommendations — Get AI-powered improvement recommendations
- GET  /carbon-estimate — Carbon footprint estimation
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.sustainability import (
    CarbonEstimateRequest,
    CarbonEstimateResponse,
    ESGScoreRequest,
    ESGScoreResponse,
    ESGSimulationRequest,
    ESGSimulationResponse,
    RecommendationsRequest,
    RecommendationsResponse,
    SustainabilityAssessmentDetailResponse,
)
from src.core.database import get_db
from src.core.deps import get_current_user
from src.models.user import User
from src.services.shared_context.context_bus import SharedContextBus
from src.services.sustainability.sustainability_service import SustainabilityService

router = APIRouter()


@router.post(
    "/score",
    response_model=ESGScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate comprehensive ESG sustainability score",
    description="""
    Core ESG intelligence endpoint.

    Processes business data through multi-label ESG classification:

    **Environmental (E)**
    - Carbon emissions estimation
    - Energy efficiency scoring
    - Waste management practices
    - Supply chain sustainability

    **Social (S)**
    - Employee wellbeing metrics
    - DEI (Diversity, Equity, Inclusion) indicators
    - Community impact assessment
    - Labor practice compliance

    **Governance (G)**
    - Transparency and reporting quality
    - Board structure analysis
    - Anti-corruption measures
    - Stakeholder engagement

    Returns: 0-100 composite ESG score + sub-scores + SHAP attributions + industry percentile ranking.
    """,
)
async def calculate_esg_score(
    request: ESGScoreRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SustainabilityService(db)
    result = await service.calculate_score(request, user_id=current_user.id)

    # Cross-module: ESG risk affects profit forecasting
    background_tasks.add_task(
        SharedContextBus.publish,
        event_type="sustainability.score_complete",
        payload={
            "assessment_id": str(result.assessment_id),
            "composite_score": result.composite_score,
            "risk_level": result.risk_level,
            "industry_percentile": result.industry_percentile,
            "regulatory_risk_flag": result.regulatory_risk_flag,
        },
        user_id=str(current_user.id),
    )

    return result


@router.post(
    "/simulate",
    response_model=ESGSimulationResponse,
    summary="Simulate ESG improvement scenarios",
    description="Model the impact of specific sustainability investments on the ESG score, carbon footprint, and regulatory compliance risk over time.",
)
async def simulate_esg_improvements(
    request: ESGSimulationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SustainabilityService(db)
    return await service.simulate_improvements(request, user_id=current_user.id)


@router.post(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="Get AI-powered ESG improvement recommendations",
    description="Returns prioritized, actionable sustainability recommendations based on the current ESG score, industry benchmarks, and regulatory requirements. Each recommendation includes estimated score impact and implementation effort.",
)
async def get_recommendations(
    request: RecommendationsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SustainabilityService(db)
    return await service.get_recommendations(request, user_id=current_user.id)


@router.get(
    "/benchmarks/{industry}",
    summary="Get industry ESG benchmarks",
    description="Returns ESG score distributions, median values, and top-quartile thresholds for the specified industry sector.",
)
async def get_industry_benchmarks(
    industry: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SustainabilityService(db)
    return await service.get_benchmarks(industry=industry)


@router.post(
    "/carbon-estimate",
    response_model=CarbonEstimateResponse,
    summary="Estimate carbon footprint",
    description="Estimates Scope 1, 2, and 3 carbon emissions from business operations. Returns tCO2e breakdown by category with reduction pathway recommendations.",
)
async def estimate_carbon(
    request: CarbonEstimateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SustainabilityService(db)
    return await service.estimate_carbon(request, user_id=current_user.id)


@router.get(
    "/explanation/{assessment_id}",
    summary="Get SHAP explanation for ESG score",
    description="Returns feature attributions showing which business practices drove the ESG score up or down, with narrative explanation and improvement priorities.",
)
async def get_esg_explanation(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SustainabilityService(db)
    return await service.get_explanation(assessment_id=assessment_id, user_id=current_user.id)


@router.get(
    "/assessments",
    summary="List the caller's sustainability assessments (paged)",
    description=(
        "Returns the caller's `sustainability_assessments` rows, newest "
        "first, with optional filters by `assessment_type` "
        "(`score` | `simulation` | `recommendations` | `carbon_estimate`) "
        "and `industry`. Mirrors pricing's `/history` + forecasting's "
        "`/history` posture so the frontend history pages share the same "
        "shape across modules."
    ),
)
async def list_assessments(
    assessment_type: str | None = None,
    industry: str | None = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SustainabilityService(db)
    return await service.list_assessments(
        user_id=current_user.id,
        assessment_type=assessment_type,
        industry=industry,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=SustainabilityAssessmentDetailResponse,
    summary="Get a single sustainability assessment with its full request + response payloads",
    description=(
        "Returns the persisted assessment row — discriminator + "
        "company/industry + headline columns + faithful request/response "
        "JSONB. Backs the audit-feed deep-link from TASK-033. 404 if "
        "the assessment does not belong to the calling user."
    ),
)
async def get_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SustainabilityService(db)
    return await service.get_assessment_detail(
        assessment_id=assessment_id,
        user_id=current_user.id,
    )
