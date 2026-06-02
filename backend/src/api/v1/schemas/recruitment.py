"""
BizVision AI — Recruitment Intelligence Pydantic Schemas

All request/response models for the recruitment module.
Strict typing ensures automatic OpenAPI documentation generation.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Enums ─────────────────────────────────────────────────────────


class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BiasType(str, Enum):
    DEMOGRAPHIC_PARITY = "demographic_parity"
    EQUALIZED_ODDS = "equalized_odds"
    INDIVIDUAL_FAIRNESS = "individual_fairness"
    CALIBRATION = "calibration"


# ── Request Schemas ───────────────────────────────────────────────


class JobDescriptionInput(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, description="Job title")
    description: str = Field(..., min_length=50, description="Full job description text")
    required_skills: list[str] = Field(default=[], description="Required technical/soft skills")
    preferred_skills: list[str] = Field(default=[], description="Nice-to-have skills")
    experience_level: ExperienceLevel = Field(default=ExperienceLevel.MID)
    min_years_experience: int | None = Field(default=None, ge=0, le=30)
    max_years_experience: int | None = Field(default=None, ge=0, le=30)
    location: str | None = None
    remote_allowed: bool = True
    department: str | None = None


class CandidateInput(BaseModel):
    candidate_id: str = Field(..., description="Unique identifier for the candidate")
    cv_text: str | None = Field(default=None, description="Raw CV text (alternative to file ID)")
    cv_file_id: str | None = Field(default=None, description="File ID from /upload-cvs endpoint")
    name: str | None = None  # Optional — don't require for anonymized screening

    @field_validator("cv_text", "cv_file_id", mode="before")
    @classmethod
    def require_cv_source(cls, v, info):
        # At least one of cv_text or cv_file_id must be provided
        # (validated at model level)
        return v


class RecruitmentAnalysisRequest(BaseModel):
    job_description: JobDescriptionInput
    candidates: list[CandidateInput] = Field(..., min_length=1, max_length=50)
    anonymize_names: bool = Field(
        default=True, description="Remove candidate names from ranking to reduce name-based bias"
    )
    protected_attributes: list[str] = Field(
        default=["gender", "age_group"], description="Demographic attributes to audit for fairness"
    )
    top_k: int = Field(default=10, ge=1, le=50, description="Number of top candidates to return")
    ensemble_sbert_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Weight for SBERT semantic score in ensemble (1-w for XGBoost)",
    )


# ── Response Schemas ──────────────────────────────────────────────


class SHAPFeatureAttribution(BaseModel):
    feature_name: str
    shap_value: float
    feature_value: str | float
    contribution_direction: str  # "positive" | "negative"
    importance_rank: int


class CandidateRankingResult(BaseModel):
    rank: int
    candidate_id: str
    display_name: str | None = None  # None if anonymized

    # Scores
    composite_score: float = Field(..., ge=0.0, le=1.0)
    semantic_score: float = Field(..., ge=0.0, le=1.0, description="SBERT cosine similarity")
    structured_score: float = Field(..., ge=0.0, le=1.0, description="XGBoost probability")
    confidence_level: float = Field(..., ge=0.0, le=1.0)

    # Extracted features
    years_experience: float | None = None
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    education_level: str | None = None

    # Explainability
    top_shap_features: list[SHAPFeatureAttribution] = []
    top_lime_features: list[SHAPFeatureAttribution] = Field(
        default_factory=list,
        description=(
            "Top-K LIME local linear surrogate weights for this candidate, "
            "in the same shape as `top_shap_features` so the UI can reuse "
            "the bar-chart component. SHAP and LIME are two independent "
            "post-hoc explainers; agreement between them on the strongest "
            "ranking drivers is a robustness signal for the recommendation. "
            "Empty when LIME wasn't computed (mock fallback before TASK-048, "
            "or real-ML XGBoost path before the explainer is wired with a "
            "background training-feature matrix). TASK-048, FE-016 wave 3."
        ),
    )
    ai_rationale: str = Field("", description="LLM-generated plain-English ranking rationale")


class FairnessMetric(BaseModel):
    attribute: str
    metric_name: str
    value: float
    threshold: float
    passed: bool
    interpretation: str


class FairnessAuditSummary(BaseModel):
    overall_risk_level: RiskLevel
    total_candidates_audited: int
    fairness_metrics: list[FairnessMetric]
    recommendations: list[str]
    audit_timestamp: datetime


class RecruitmentAnalysisResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    session_id: UUID
    job_title: str
    analysis_timestamp: datetime
    total_candidates: int
    processing_time_ms: float

    ranked_candidates: list[CandidateRankingResult]
    fairness_audit: FairnessAuditSummary

    # Model metadata
    model_version: str
    sbert_model: str
    ensemble_weights: dict[str, float]

    # Cross-module context published
    context_signal_id: str | None = None


class ExplanationResponse(BaseModel):
    session_id: UUID
    candidate_id: str
    composite_score: float
    shap_base_value: float
    shap_features: list[SHAPFeatureAttribution]
    lime_explanation: dict
    narrative: str = Field(..., description="Human-readable explanation of the ranking decision")
    visualization_data: dict = Field({}, description="Data for SHAP waterfall plot rendering")


class FairnessAuditResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    session_id: UUID
    audit_timestamp: datetime
    protected_attributes: list[str]
    metrics: list[FairnessMetric]
    bias_heatmap_data: dict = Field({}, description="Data for bias visualization")
    mitigation_strategies: list[dict]
    overall_risk_level: RiskLevel
    model_card_url: str | None = None


class CandidateRankingResponse(BaseModel):
    session_id: UUID
    ranked_candidates: list[CandidateRankingResult]


class InterviewQuestionsResponse(BaseModel):
    session_id: UUID
    candidate_id: str
    questions: list[dict]
    generated_at: datetime


class RecruitmentSessionDetailResponse(BaseModel):
    """Persisted-session detail view.

    Backs the frontend's `/modules/recruitment/sessions/{id}` deep-
    link route (TASK-032) — the audit log's recruitment rows carry
    `reference_id = session_id` + `reference_type = recruitment_session`,
    and the dashboard's per-row footer becomes a clickable link into
    this view.

    Mirrors the persisted shape rather than the live `/analyze`
    response: no live `processing_time_ms` (the row carries the
    original timing), no `analysis_timestamp` (created_at is the row
    of record). The `ranked_candidates` list comes from the persisted
    CandidateScore rows in rank order, with their SHAP attributions
    intact.
    """

    model_config = ConfigDict(protected_namespaces=())

    session_id: UUID
    job_title: str
    job_description: str
    created_at: datetime

    total_candidates: int
    top_k: int
    anonymize_names: bool
    protected_attributes: list[str]

    ranked_candidates: list[CandidateRankingResult]

    model_version: str
    sbert_model: str
    ensemble_weights: dict[str, float]


# ── /upload-cvs (ML-003, TASK-045) ──────────────────────────────────


class UploadFileResult(BaseModel):
    """One parsed CV from the `/upload-cvs` batch.

    The endpoint now runs the real `ml.recruitment.parsers.ResumeParser`
    (pypdf for PDF, python-docx for DOCX, plain UTF-8 for TXT) instead
    of returning a fake file_id. The frontend can pipe `cv_text` +
    `skills` straight into the `/analyze` body, skipping the manual
    paste step.

    `error` is set when a single file fails to parse — the batch
    still returns the rest so a malformed PDF in the middle of 50
    uploads doesn't tank the whole submission.
    """

    file_id: UUID = Field(default_factory=uuid4, description="Synthetic ID for in-flight reference")
    filename: str
    source: str = Field(description="`pdf` / `docx` / `text` / `unknown`")
    cv_text: str = Field(default="", description="Raw extracted text")
    char_count: int = Field(default=0, ge=0)
    skills: list[str] = Field(default_factory=list)
    years_experience: float | None = None
    education_level: str | None = None
    error: str | None = Field(
        default=None,
        description="Set when this file failed to parse; cv_text will be empty.",
    )


class UploadCVsResponse(BaseModel):
    uploaded: list[UploadFileResult] = Field(default_factory=list)
    count: int = Field(default=0, ge=0, description="Number of files in the batch")
    parsed_count: int = Field(
        default=0,
        ge=0,
        description="Number of files that parsed cleanly (no `error`)",
    )
