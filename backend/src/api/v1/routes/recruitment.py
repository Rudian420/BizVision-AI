"""
BizVision AI — Recruitment Intelligence API Router

Endpoints:
- POST /analyze — Analyze job description + candidate CVs, return ranked results
- POST /rank — Rank an existing candidate pool against a JD
- GET  /explanation/{job_id} — Get SHAP explanation for a ranking decision
- GET  /fairness/{job_id} — Get fairness audit report for a ranking
- POST /generate-questions — Generate interview questions for a candidate
- GET  /sessions — List all recruitment analysis sessions
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.recruitment import (
    ExplanationResponse,
    FairnessAuditResponse,
    InterviewQuestionsResponse,
    RecruitmentAnalysisRequest,
    RecruitmentAnalysisResponse,
    RecruitmentSessionDetailResponse,
    UploadCVsResponse,
)
from src.core.database import get_db
from src.core.deps import get_current_user
from src.models.user import User
from src.services.recruitment.recruitment_service import RecruitmentService
from src.services.shared_context.context_bus import SharedContextBus

router = APIRouter()


@router.post(
    "/analyze",
    response_model=RecruitmentAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze job description against candidate pool",
    description="""
    The core recruitment intelligence endpoint.

    Processes a job description and up to 50 candidate CVs through:
    1. **NLP Parsing** — extracts structured entities from free-text CVs
    2. **SBERT Embedding** — semantic similarity via 768-dim sentence embeddings
    3. **XGBoost Ranking** — structured feature ensemble with boosted trees
    4. **Ensemble Fusion** — weighted combination of semantic + structured scores
    5. **SHAP Explanation** — feature attribution for each ranking decision
    6. **Fairness Audit** — demographic parity analysis across protected attributes

    Returns ranked candidates with scores, explanations, and fairness metrics.
    """,
)
async def analyze_recruitment(
    request: RecruitmentAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecruitmentService(db)
    result = await service.analyze(request, user_id=current_user.id)

    # Publish cross-module signal asynchronously (doesn't block response)
    background_tasks.add_task(
        SharedContextBus.publish,
        event_type="recruitment.analysis_complete",
        payload={
            "session_id": str(result.session_id),
            "total_candidates": len(result.ranked_candidates),
            "top_candidate_score": result.ranked_candidates[0].composite_score
            if result.ranked_candidates
            else 0,
            "fairness_flag": result.fairness_audit.overall_risk_level,
        },
        user_id=str(current_user.id),
    )

    return result


@router.post(
    "/upload-cvs",
    response_model=UploadCVsResponse,
    summary="Upload CV files for analysis",
    description=(
        "Upload PDF / DOCX / TXT CVs for batch parsing (max 50). Each file is "
        "read through `ml.recruitment.parsers.ResumeParser`: pypdf for PDF, "
        "python-docx for DOCX, plain UTF-8 for TXT, with skills / years / "
        "education extracted via `EntityExtractor`. Returns the extracted "
        "`cv_text` + parsed fields per file so the caller can pipe them "
        "directly into `/analyze` without manual paste. A file that fails to "
        "parse comes back with an `error` field set — the batch still "
        "returns the rest."
    ),
)
async def upload_cvs(
    files: list[UploadFile] = File(..., description="PDF or DOCX CV files (max 50)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadCVsResponse:
    if len(files) > 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 50 CVs per analysis session",
        )

    service = RecruitmentService(db)
    return await service.process_cv_uploads(files, user_id=current_user.id)


@router.get(
    "/explanation/{session_id}",
    response_model=ExplanationResponse,
    summary="Get SHAP explanation for ranking decision",
    description="Returns SHAP waterfall values, feature importances, and LLM-generated narrative for a specific ranking.",
)
async def get_explanation(
    session_id: UUID,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecruitmentService(db)
    return await service.get_shap_explanation(
        session_id=session_id,
        candidate_id=candidate_id,
        user_id=current_user.id,
    )


@router.get(
    "/fairness/{session_id}",
    response_model=FairnessAuditResponse,
    summary="Get comprehensive fairness audit report",
    description="Returns demographic parity, equalized odds, individual fairness metrics, and bias mitigation recommendations.",
)
async def get_fairness_audit(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecruitmentService(db)
    return await service.get_fairness_audit(
        session_id=session_id,
        user_id=current_user.id,
    )


@router.post(
    "/generate-questions",
    response_model=InterviewQuestionsResponse,
    summary="Generate AI-powered interview questions",
    description="Generates role-specific, behavioural, and technical interview questions tailored to the candidate's profile and the job requirements.",
)
async def generate_interview_questions(
    session_id: UUID,
    candidate_id: str,
    question_types: Annotated[list[str] | None, Query()] = None,
    num_questions: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecruitmentService(db)
    return await service.generate_interview_questions(
        session_id=session_id,
        candidate_id=candidate_id,
        question_types=question_types or ["behavioural", "technical", "situational"],
        num_questions=num_questions,
        user_id=current_user.id,
    )


@router.get(
    "/sessions",
    summary="List recruitment analysis sessions",
)
async def list_sessions(
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecruitmentService(db)
    return await service.list_sessions(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        since=since,
        until=until,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=RecruitmentSessionDetailResponse,
    summary="Get a single recruitment session with its ranked candidates",
    description=(
        "Returns the persisted session row + every candidate score in "
        "rank order, with the original SHAP attributions. Backs the "
        "frontend's session-detail deep-link from the ML Decision Feed "
        "(TASK-032). 404 if the session does not belong to the calling "
        "user."
    ),
)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecruitmentService(db)
    return await service.get_session_detail(
        session_id=session_id,
        user_id=current_user.id,
    )
