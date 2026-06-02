"""
API ↔ `ml.recruitment` schema translation.

The backend speaks **Pydantic schemas** (`src.api.v1.schemas.recruitment`)
and the ML package speaks **frozen dataclasses** (`ml.recruitment.data.schema`).
This module is the only place that knows about both — keep it that way so
changes to either side localise here.

Pure Python, zero heavy imports. Unit-testable without the ML toolchain
installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.api.v1.schemas.common import RiskLevel as APIRiskLevel
from src.api.v1.schemas.recruitment import (
    BiasType,
    CandidateRankingResult,
    FairnessAuditSummary,
    FairnessMetric,
    RecruitmentAnalysisRequest,
    SHAPFeatureAttribution,
)
from src.api.v1.schemas.recruitment import (
    RiskLevel as RecRiskLevel,
)

if TYPE_CHECKING:
    # Import for type-checker only — keeps this module importable in the
    # backend's lean runtime image where ml/ may not be on sys.path.
    from ml.recruitment.data.schema import (
        CandidateRecord as MLCandidate,
    )
    from ml.recruitment.data.schema import (
        JobDescription as MLJob,
    )
    from ml.recruitment.fairness.auditor import FairnessReport
    from ml.recruitment.models.base import ScoreDetail


# ── API → ml.recruitment ────────────────────────────────────────────


def api_job_to_ml(job_in, job_id: str = "api-job-001") -> MLJob:
    """Build an `ml.recruitment.JobDescription` from a Pydantic JD input.

    `job_in` is the `JobDescriptionInput` schema; we deliberately accept it
    structurally (any object exposing the same field names) so unit tests
    can pass plain dataclasses too.
    """
    from ml.recruitment.data.schema import JobDescription as MLJobImpl

    return MLJobImpl(
        job_id=job_id,
        title=job_in.title,
        description=job_in.description,
        required_skills=tuple(job_in.required_skills or ()),
        preferred_skills=tuple(job_in.preferred_skills or ()),
        min_years_experience=getattr(job_in, "min_years_experience", None),
        max_years_experience=getattr(job_in, "max_years_experience", None),
        location=getattr(job_in, "location", None),
        remote_allowed=bool(getattr(job_in, "remote_allowed", True)),
        department=getattr(job_in, "department", None),
    )


def api_candidate_to_ml(cand_in) -> MLCandidate:
    """Build an `ml.recruitment.CandidateRecord` from a Pydantic candidate input.

    The API delivers `cv_text` (raw) and `cv_file_id` (resolved upstream).
    The ML layer wants a single normalised `CandidateRecord`. Structured
    feature extraction (skills / years / education) happens inside
    `ml.recruitment` when the real ensemble runs — we pass through what
    the API supplied and let the encoder handle the rest.
    """
    from ml.recruitment.data.schema import (
        CandidateRecord as MLCandImpl,
    )
    from ml.recruitment.data.schema import (
        ProtectedAttributes as MLProtImpl,
    )

    return MLCandImpl(
        candidate_id=cand_in.candidate_id,
        cv_text=cand_in.cv_text or "",
        name=getattr(cand_in, "name", None),
        protected=MLProtImpl(),
        source="api",
    )


def api_request_to_ml(
    request: RecruitmentAnalysisRequest,
) -> tuple[MLJob, list[MLCandidate]]:
    """One-shot translation: full `analyze` request → (jd, candidates)."""
    job = api_job_to_ml(request.job_description, job_id=f"req-{id(request):x}")
    candidates = [api_candidate_to_ml(c) for c in request.candidates]
    return job, candidates


# ── ml.recruitment → API ────────────────────────────────────────────


def _shap_attrs_from_detail(detail: ScoreDetail) -> list[SHAPFeatureAttribution]:
    """Turn a `ScoreDetail.features` map into ranked SHAP attributions.

    The ensemble's `sub_scores` map ("semantic", "structured") becomes the
    top two attributions; any additional `features` are tacked on with
    declining rank. This keeps the API contract stable while letting the
    underlying model produce richer attributions over time.
    """
    items: list[tuple[str, float]] = []
    for key in ("semantic", "structured"):
        if key in detail.sub_scores:
            items.append((f"{key}_score", detail.sub_scores[key]))
    items.extend(detail.features.items())

    attrs: list[SHAPFeatureAttribution] = []
    for rank, (name, value) in enumerate(items, start=1):
        attrs.append(
            SHAPFeatureAttribution(
                feature_name=name,
                shap_value=round(float(value), 4),
                feature_value=round(float(value), 4),
                contribution_direction="positive" if value >= 0 else "negative",
                importance_rank=rank,
            )
        )
    return attrs


def ml_score_to_api_ranking(
    details: list[ScoreDetail],
    *,
    candidate_in_by_id: dict[str, object],
    anonymize_names: bool,
    required_skills: tuple[str, ...],
    preferred_skills: tuple[str, ...],
    lime_by_candidate: dict[str, list[SHAPFeatureAttribution]] | None = None,
) -> list[CandidateRankingResult]:
    """Convert a list of `ScoreDetail` into API ranking results.

    Caller provides the original API candidate inputs (by id) so we can
    echo the display name when anonymisation is off. `details` is assumed
    pre-sorted by composite score descending — we just assign ranks.

    TASK-049 / FE-016 wave 3a: `lime_by_candidate` is an optional
    `{candidate_id: [SHAPFeatureAttribution, ...]}` map produced by the
    inference client's `LIMERecruitmentExplainer`. Falls through to an
    empty list per candidate when None or when a particular id is
    missing — same shape as the wave-3 empty default."""
    lime_by_candidate = lime_by_candidate or {}
    results: list[CandidateRankingResult] = []
    for rank, detail in enumerate(details, start=1):
        cand_in = candidate_in_by_id.get(detail.candidate_id)
        display_name = (
            getattr(cand_in, "name", None) if cand_in is not None and not anonymize_names else None
        )
        semantic = float(detail.sub_scores.get("semantic", 0.0))
        structured = float(detail.sub_scores.get("structured", 0.0))
        results.append(
            CandidateRankingResult(
                rank=rank,
                candidate_id=detail.candidate_id,
                display_name=display_name,
                composite_score=round(float(detail.score), 4),
                semantic_score=round(semantic, 4),
                structured_score=round(structured, 4),
                # Confidence proxy: how close the two legs agree (1 = identical).
                confidence_level=round(1.0 - abs(semantic - structured), 4),
                years_experience=detail.features.get("years_experience"),
                matched_skills=list(required_skills[:3]),
                missing_skills=list(preferred_skills[:1]),
                education_level=_education_from_rank(detail.features.get("education_rank")),
                top_shap_features=_shap_attrs_from_detail(detail),
                top_lime_features=lime_by_candidate.get(detail.candidate_id, []),
                ai_rationale=(
                    "Composite score blends SBERT semantic similarity with the "
                    "structured-feature boosting model (ADR-023)."
                ),
            )
        )
    return results


def _education_from_rank(rank: float | int | None) -> str | None:
    """Inverse of `ml.recruitment.features.structured._EDU_RANK`."""
    if rank is None:
        return None
    table = ("high_school", "bachelor", "master", "phd")
    idx = int(rank)
    if not 0 <= idx < len(table):
        return None
    return table[idx]


# ── Fairness report (ml) → API summary ──────────────────────────────


_ML_RISK_TO_API = {
    "low": RecRiskLevel.LOW,
    "medium": RecRiskLevel.MEDIUM,
    "high": RecRiskLevel.HIGH,
    "critical": RecRiskLevel.CRITICAL,
}


def ml_fairness_to_api(
    reports: dict[str, FairnessReport],
    total_candidates: int,
) -> FairnessAuditSummary:
    """Aggregate one `intersectional_audit` output into the API summary."""
    from datetime import datetime, timezone

    api_metrics: list[FairnessMetric] = []
    overall = RecRiskLevel.LOW
    risk_order = [
        RecRiskLevel.LOW,
        RecRiskLevel.MEDIUM,
        RecRiskLevel.HIGH,
        RecRiskLevel.CRITICAL,
    ]
    for attr, rep in reports.items():
        api_metrics.append(
            FairnessMetric(
                attribute=attr,
                metric_name=BiasType.DEMOGRAPHIC_PARITY.value,
                value=round(rep.demographic_parity_difference, 4),
                threshold=0.1,
                passed=rep.disparate_impact >= 0.8,
                interpretation=rep.interpretation,
            )
        )
        rep_risk = _ML_RISK_TO_API.get(rep.overall_risk, RecRiskLevel.LOW)
        if risk_order.index(rep_risk) > risk_order.index(overall):
            overall = rep_risk

    return FairnessAuditSummary(
        overall_risk_level=overall,
        total_candidates_audited=total_candidates,
        fairness_metrics=api_metrics,
        recommendations=[
            "SHAP-attributed bias decomposition available via "
            "`ml.recruitment.explainability.shap_adapter` (RC-002).",
        ],
        audit_timestamp=datetime.now(timezone.utc),
    )


# Avoid an unused-import warning while keeping `APIRiskLevel` in the
# explicit imports — same module is consumed elsewhere by name.
_ = APIRiskLevel
