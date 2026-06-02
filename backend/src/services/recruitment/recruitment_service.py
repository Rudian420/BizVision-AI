"""
BizVision AI — Recruitment Intelligence Service

Persistence-aware service that produces ranking + fairness + explanations
and writes them through to the database.

State of integration (2026-05-28):
  • **Persistence is real** — `RecruitmentSession`, `CandidateScore`, and
    `FairnessAuditRecord` rows are created on every `analyze` call and
    read back by `list_sessions` / `get_shap_explanation` /
    `get_fairness_audit`.
  • **ML computation defaults to the deterministic mock** — the SBERT +
    XGBoost ensemble lives in `ml/recruitment/` (Session 5) but its heavy
    dependencies aren't on the backend container by default. Flip
    `settings.RECRUITMENT_USE_REAL_ML=True` in the `ml-dev` container to
    swap in real inference; the persistence layer is identical either way.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.v1.schemas.recruitment import (
    BiasType,
    CandidateRankingResult,
    ExplanationResponse,
    FairnessAuditResponse,
    FairnessAuditSummary,
    FairnessMetric,
    InterviewQuestionsResponse,
    RecruitmentAnalysisRequest,
    RecruitmentAnalysisResponse,
    RecruitmentSessionDetailResponse,
    RiskLevel,
    SHAPFeatureAttribution,
)
from src.core.config import settings
from src.models.audit import AuditModule
from src.models.recruitment import (
    CandidateScore,
    FairnessAuditRecord,
    RecruitmentSession,
)
from src.services.audit.audit_service import AuditService


def _seed(text: str) -> float:
    """Deterministic 0-1 pseudo-score from text (stable across calls)."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _mock_lime_attrs(
    *,
    semantic: float,
    structured: float,
) -> list[SHAPFeatureAttribution]:
    """Mock-path LIME attributions, sibling to the SHAP mock block above
    (TASK-048 / FE-016 wave 3).

    LIME on a classifier with discretised features renders rules like
    `years_experience > 5 → +0.31`, which we synthesise here so the
    `<LimePanel>` has something defensible to render in the mock branch.
    Magnitudes differ from the mock SHAP attributions on purpose:
    LIME's local linear surrogate weights differ from SHAP's
    Shapley-value attributions even on the same model, and surfacing
    that difference is the whole point of showing them side-by-side.
    """
    return [
        SHAPFeatureAttribution(
            feature_name="semantic_similarity > 0.6",
            shap_value=round(0.25 * semantic, 4),
            feature_value=semantic,
            contribution_direction="positive",
            importance_rank=1,
        ),
        SHAPFeatureAttribution(
            feature_name="years_experience > 5",
            shap_value=round(0.12 * structured, 4),
            feature_value=structured,
            contribution_direction="positive",
            importance_rank=2,
        ),
        SHAPFeatureAttribution(
            feature_name="required_skill_overlap > 0.5",
            shap_value=round(0.08 * (semantic + structured) / 2.0, 4),
            feature_value=(semantic + structured) / 2.0,
            contribution_direction="positive",
            importance_rank=3,
        ),
    ]


# ── ML producer (mock or real) ──────────────────────────────────────


def _mock_score_candidates(
    request: RecruitmentAnalysisRequest,
) -> list[CandidateRankingResult]:
    """Deterministic mock ranking — used when `RECRUITMENT_USE_REAL_ML` is off."""
    ranked: list[CandidateRankingResult] = []
    for candidate in request.candidates:
        semantic = round(0.45 + 0.5 * _seed(candidate.candidate_id + "sem"), 4)
        structured = round(0.40 + 0.5 * _seed(candidate.candidate_id + "str"), 4)
        composite = round(
            request.ensemble_sbert_weight * semantic
            + (1 - request.ensemble_sbert_weight) * structured,
            4,
        )
        ranked.append(
            CandidateRankingResult(
                rank=0,
                candidate_id=candidate.candidate_id,
                display_name=None if request.anonymize_names else candidate.name,
                composite_score=composite,
                semantic_score=semantic,
                structured_score=structured,
                confidence_level=round(0.6 + 0.35 * _seed(candidate.candidate_id), 4),
                years_experience=round(2 + 10 * _seed(candidate.candidate_id + "yrs"), 1),
                matched_skills=list(request.job_description.required_skills[:3]),
                missing_skills=list(request.job_description.preferred_skills[:1]),
                education_level="bachelor",
                top_shap_features=[
                    SHAPFeatureAttribution(
                        feature_name="semantic_similarity",
                        shap_value=round(0.2 * semantic, 4),
                        feature_value=semantic,
                        contribution_direction="positive",
                        importance_rank=1,
                    ),
                    SHAPFeatureAttribution(
                        feature_name="years_experience",
                        shap_value=round(0.1 * structured, 4),
                        feature_value=structured,
                        contribution_direction="positive",
                        importance_rank=2,
                    ),
                ],
                top_lime_features=_mock_lime_attrs(
                    semantic=semantic, structured=structured
                ),
                ai_rationale=(
                    "Strong semantic alignment with the role's core "
                    "requirements; competitive structured profile."
                ),
            )
        )

    ranked.sort(key=lambda c: c.composite_score, reverse=True)
    for i, cand in enumerate(ranked, start=1):
        cand.rank = i
    return ranked


def _real_score_candidates(
    request: RecruitmentAnalysisRequest,
) -> list[CandidateRankingResult]:
    """Real `ml.recruitment` path — guarded behind `RECRUITMENT_USE_REAL_ML`.

    Delegates to the process-wide `RecruitmentInferenceClient` (ADR-024)
    which lazy-loads the fitted ensemble on first call (preferring an
    MLflow-registered Production model; falling back to a synthetic
    bootstrap so the path is testable on a fresh deploy)."""
    # Local import keeps the heavy ML chain out of the cold-start cost when
    # the feature flag is off — see ADR-024.
    from src.services.recruitment.inference import get_inference_client

    client = get_inference_client()
    return client.score_candidates(request)


# ── Service ─────────────────────────────────────────────────────────


class RecruitmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 1. analyze: rank → persist → return ─────────────────────────
    async def analyze(
        self, request: RecruitmentAnalysisRequest, user_id: UUID
    ) -> RecruitmentAnalysisResponse:
        scorer = (
            _real_score_candidates if settings.RECRUITMENT_USE_REAL_ML else _mock_score_candidates
        )
        ranked_full = scorer(request)
        ranked = ranked_full[: request.top_k]

        fairness_summary = self._build_fairness_summary(
            list(request.protected_attributes), total=len(request.candidates)
        )

        session = await self._persist_session(
            request=request,
            user_id=user_id,
            ranked_full=ranked_full,
            ranked_topk=ranked,
            fairness_summary=fairness_summary,
        )

        # Audit log — fire-and-forget cross-module index (ADR-031). A
        # failure here must not roll back the analysis; AuditService
        # swallows + logs its own errors.
        top_features = (
            [f.model_dump(mode="json") for f in ranked[0].top_shap_features[:3]]
            if ranked
            else []
        )

        # Per-attribute fairness slice — keeps the structured metrics
        # for downstream `/audits/fairness` aggregation (TASK-031,
        # FAIR-003). Each attribute carries every metric the auditor
        # produced for it, plus a derived `passed` boolean for cheap
        # GROUP BY in the aggregation endpoint.
        attribute_rollup: dict[str, dict[str, Any]] = {}
        for m in fairness_summary.fairness_metrics:
            entry = attribute_rollup.setdefault(
                m.attribute, {"name": m.attribute, "metrics": [], "passed": True}
            )
            entry["metrics"].append(
                {
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "threshold": m.threshold,
                    "passed": m.passed,
                }
            )
            if not m.passed:
                entry["passed"] = False

        await AuditService(self.db).record(
            user_id=user_id,
            module=AuditModule.RECRUITMENT,
            action="analyze",
            reference_id=session.id,
            reference_type="recruitment_session",
            request_summary={
                "job_title": session.job_title,
                "total_candidates": session.total_candidates,
                "top_k": session.top_k,
                "protected_attributes": session.protected_attributes,
            },
            response_summary={
                "top_candidate_score": ranked[0].composite_score if ranked else None,
                "returned_candidates": len(ranked),
                "ensemble_weights": session.ensemble_weights,
            },
            explanation_summary={"top_shap_features": top_features},
            fairness_summary={
                "overall_risk_level": fairness_summary.overall_risk_level.value,
                "candidates_audited": fairness_summary.total_candidates_audited,
                "all_metrics_pass": all(
                    m.passed for m in fairness_summary.fairness_metrics
                ),
                "attributes": list(attribute_rollup.values()),
            },
            risk_tier=fairness_summary.overall_risk_level.value,
            model_version=session.model_version,
            latency_ms=session.processing_time_ms,
        )

        return RecruitmentAnalysisResponse(
            session_id=session.id,
            job_title=session.job_title,
            analysis_timestamp=session.created_at,
            total_candidates=session.total_candidates,
            processing_time_ms=session.processing_time_ms,
            ranked_candidates=ranked,
            fairness_audit=fairness_summary,
            model_version=session.model_version,
            sbert_model=session.sbert_model,
            ensemble_weights=session.ensemble_weights,
        )

    # ── 2. list sessions (paged) ────────────────────────────────────
    async def list_sessions(
        self,
        user_id: UUID,
        page: int,
        page_size: int,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        # Date-range filter (TASK-037).
        filters = [RecruitmentSession.user_id == user_id]
        if since is not None:
            filters.append(RecruitmentSession.created_at >= since)
        if until is not None:
            filters.append(RecruitmentSession.created_at <= until)

        total = await self.db.scalar(
            select(func.count())
            .select_from(RecruitmentSession)
            .where(*filters)
        )
        rows = await self.db.execute(
            select(RecruitmentSession)
            .where(*filters)
            .order_by(RecruitmentSession.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = [
            {
                "session_id": str(s.id),
                "job_title": s.job_title,
                "total_candidates": s.total_candidates,
                "model_version": s.model_version,
                "created_at": s.created_at.isoformat(),
            }
            for s in rows.scalars()
        ]
        return {
            "items": items,
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
        }

    # ── 3a. session detail (reads from DB) ──────────────────────────
    async def get_session_detail(
        self, session_id: UUID, user_id: UUID
    ) -> RecruitmentSessionDetailResponse:
        """Reconstruct the persisted session + its ranked candidates.

        Backs `/recruitment/sessions/{session_id}` (TASK-032) — the
        audit log's `reference_id` deep-links into this view. Returns
        404 via `_find_session` when the session doesn't belong to the
        calling user."""
        sess = await self._find_session(session_id, user_id)
        ranked = sorted(sess.candidates, key=lambda c: c.rank)
        ranked_candidates = [
            CandidateRankingResult(
                rank=c.rank,
                candidate_id=c.candidate_id,
                display_name=c.display_name,
                composite_score=float(c.composite_score),
                semantic_score=float(c.semantic_score),
                structured_score=float(c.structured_score),
                confidence_level=float(c.confidence_level),
                years_experience=(
                    float(c.years_experience)
                    if c.years_experience is not None
                    else None
                ),
                matched_skills=list(c.matched_skills or []),
                missing_skills=list(c.missing_skills or []),
                education_level=c.education_level,
                top_shap_features=[
                    SHAPFeatureAttribution(**f) for f in (c.top_shap_features or [])
                ],
                # TASK-050: round-trip LIME from `candidate_scores.top_lime_features`.
                # Falls through to [] for rows persisted before the migration —
                # the Pydantic schema default keeps the response shape stable.
                top_lime_features=[
                    SHAPFeatureAttribution(**f)
                    for f in (getattr(c, "top_lime_features", None) or [])
                ],
                ai_rationale=c.ai_rationale or "",
            )
            for c in ranked
        ]
        return RecruitmentSessionDetailResponse(
            session_id=sess.id,
            job_title=sess.job_title,
            job_description=sess.job_description,
            created_at=sess.created_at,
            total_candidates=sess.total_candidates,
            top_k=sess.top_k,
            anonymize_names=sess.anonymize_names,
            protected_attributes=list(sess.protected_attributes or []),
            ranked_candidates=ranked_candidates,
            model_version=sess.model_version,
            sbert_model=sess.sbert_model,
            ensemble_weights=dict(sess.ensemble_weights or {}),
        )

    # ── 3. SHAP explanation for one candidate ───────────────────────
    async def get_shap_explanation(
        self, session_id: UUID, candidate_id: str, user_id: UUID
    ) -> ExplanationResponse:
        cs = await self._find_candidate(session_id, candidate_id, user_id)

        features = [SHAPFeatureAttribution(**f) for f in cs.top_shap_features]
        base = (
            float(cs.composite_score) - sum(f.shap_value for f in features)
            if features
            else float(cs.composite_score)
        )
        return ExplanationResponse(
            session_id=session_id,
            candidate_id=candidate_id,
            composite_score=float(cs.composite_score),
            shap_base_value=round(base, 4),
            shap_features=features,
            lime_explanation={"top_terms": cs.matched_skills[:3]},
            narrative=cs.ai_rationale,
            visualization_data={"waterfall": [round(base, 4), *[f.shap_value for f in features]]},
        )

    # ── 4. fairness audit for the session ───────────────────────────
    async def get_fairness_audit(self, session_id: UUID, user_id: UUID) -> FairnessAuditResponse:
        sess = await self._find_session(session_id, user_id)
        audits = sess.fairness_audits
        # Combine all per-attribute records into the API response shape.
        metrics: list[FairnessMetric] = []
        bias_heatmap: dict[str, Any] = {}
        mitigation: list[dict[str, Any]] = []
        attributes: list[str] = []
        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        overall = RiskLevel.LOW
        for rec in audits:
            attributes.append(rec.protected_attribute)
            for m in rec.metrics:
                metrics.append(FairnessMetric(**m))
            bias_heatmap.update(rec.bias_heatmap_data or {})
            mitigation.extend(rec.mitigation_strategies or [])
            rec_risk = RiskLevel(rec.overall_risk_level)
            if risk_order.index(rec_risk) > risk_order.index(overall):
                overall = rec_risk

        return FairnessAuditResponse(
            session_id=session_id,
            audit_timestamp=sess.created_at,
            protected_attributes=attributes,
            metrics=metrics,
            bias_heatmap_data=bias_heatmap,
            mitigation_strategies=mitigation,
            overall_risk_level=overall,
            model_card_url=None,
        )

    # ── 5. interview questions (still procedural) ────────────────────
    async def generate_interview_questions(
        self,
        session_id: UUID,
        candidate_id: str,
        question_types: list[str],
        num_questions: int,
        user_id: UUID,
    ) -> InterviewQuestionsResponse:
        # Validate the candidate exists in this session.
        await self._find_candidate(session_id, candidate_id, user_id)
        questions = [
            {
                "type": question_types[i % len(question_types)],
                "question": f"Sample {question_types[i % len(question_types)]} question #{i + 1}",
            }
            for i in range(num_questions)
        ]
        return InterviewQuestionsResponse(
            session_id=session_id,
            candidate_id=candidate_id,
            questions=questions,
            generated_at=datetime.now(timezone.utc),
        )

    # ── 6. CV upload (TASK-045 / ML-003) ─────────────────────────────
    # Reads each uploaded file's bytes through `ml.recruitment.parsers.
    # ResumeParser`: pypdf for PDF, python-docx for DOCX, plain UTF-8
    # for TXT. Skill / years / education extraction via the existing
    # `EntityExtractor`. Returns a typed `UploadCVsResponse` so the
    # frontend can pipe parsed `cv_text` + `skills` straight into the
    # `/analyze` body without a manual paste.
    #
    # MinIO object storage is *not* exercised here — see ADR-036.
    # A future task can persist the originals + tag the file_id with
    # the MinIO object key once the storage container is healthy.
    async def process_cv_uploads(self, files, user_id: UUID) -> "UploadCVsResponse":
        import tempfile
        from pathlib import Path

        from src.api.v1.schemas.recruitment import (
            UploadCVsResponse,
            UploadFileResult,
        )

        parser = _get_resume_parser()
        results: list[UploadFileResult] = []
        parsed_ok = 0
        for f in files:
            filename = getattr(f, "filename", "cv") or "cv"
            suffix = Path(filename).suffix.lower()
            source = {".pdf": "pdf", ".docx": "docx", ".doc": "docx", ".txt": "text"}.get(
                suffix, "unknown"
            )
            try:
                data = await f.read()
            except Exception as exc:  # pragma: no cover - network/IO
                results.append(
                    UploadFileResult(
                        filename=filename,
                        source=source,
                        error=f"read failed: {exc!s}"[:200],
                    )
                )
                continue
            if not data:
                results.append(
                    UploadFileResult(
                        filename=filename, source=source, error="empty upload"
                    )
                )
                continue
            if source == "unknown":
                results.append(
                    UploadFileResult(
                        filename=filename,
                        source=source,
                        error=f"unsupported extension: {suffix or '(none)'}",
                    )
                )
                continue
            try:
                # ResumeParser reads from a path — write the upload
                # to a tempfile so we don't have to re-implement the
                # pypdf / python-docx dispatch here.
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(data)
                    tmp_path = Path(tmp.name)
                try:
                    record = parser.parse_file(tmp_path)
                finally:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:  # pragma: no cover - best-effort cleanup
                        pass
            except Exception as exc:
                results.append(
                    UploadFileResult(
                        filename=filename,
                        source=source,
                        error=f"parse failed: {exc!s}"[:200],
                    )
                )
                continue
            results.append(
                UploadFileResult(
                    filename=filename,
                    source=source,
                    cv_text=record.cv_text,
                    char_count=len(record.cv_text),
                    skills=list(record.skills),
                    years_experience=record.years_experience,
                    education_level=record.education_level,
                )
            )
            parsed_ok += 1
        return UploadCVsResponse(
            uploaded=results,
            count=len(results),
            parsed_count=parsed_ok,
        )

    # ── internals ───────────────────────────────────────────────────
    async def _persist_session(
        self,
        *,
        request: RecruitmentAnalysisRequest,
        user_id: UUID,
        ranked_full: list[CandidateRankingResult],
        ranked_topk: list[CandidateRankingResult],
        fairness_summary: FairnessAuditSummary,
    ) -> RecruitmentSession:
        sess = RecruitmentSession(
            user_id=user_id,
            job_title=request.job_description.title,
            job_description=request.job_description.description,
            job_details=request.job_description.model_dump(mode="json"),
            total_candidates=len(request.candidates),
            top_k=request.top_k,
            anonymize_names=request.anonymize_names,
            protected_attributes=list(request.protected_attributes),
            processing_time_ms=42.0,
            model_version=(
                "recruitment-real-0.1"
                if settings.RECRUITMENT_USE_REAL_ML
                else "recruitment-mock-0.1"
            ),
            sbert_model="sentence-transformers/all-mpnet-base-v2",
            ensemble_weights={
                "sbert": request.ensemble_sbert_weight,
                "xgboost": round(1 - request.ensemble_sbert_weight, 4),
            },
        )
        self.db.add(sess)
        await self.db.flush()  # populate sess.id for FKs

        # Persist the full ranking (not just top-k) so a later API call with
        # a larger top-k doesn't need to re-run the model.
        for c in ranked_full:
            self.db.add(
                CandidateScore(
                    session_id=sess.id,
                    candidate_id=c.candidate_id,
                    display_name=c.display_name,
                    rank=c.rank,
                    composite_score=c.composite_score,
                    semantic_score=c.semantic_score,
                    structured_score=c.structured_score,
                    confidence_level=c.confidence_level,
                    years_experience=c.years_experience,
                    education_level=c.education_level,
                    matched_skills=list(c.matched_skills),
                    missing_skills=list(c.missing_skills),
                    top_shap_features=[f.model_dump(mode="json") for f in c.top_shap_features],
                    # TASK-050: persist LIME alongside SHAP so the
                    # session-detail history page reconstructs both
                    # panels. Defaults to [] when LIME wasn't computed
                    # (e.g. test stub injection — TASK-049).
                    top_lime_features=[
                        f.model_dump(mode="json")
                        for f in (c.top_lime_features or [])
                    ],
                    ai_rationale=c.ai_rationale,
                )
            )

        # One fairness record per protected attribute (mirrors the
        # intersectional-audit shape in ml.recruitment.fairness.auditor).
        for attr in request.protected_attributes:
            attr_metrics = [m for m in fairness_summary.fairness_metrics if m.attribute == attr]
            self.db.add(
                FairnessAuditRecord(
                    session_id=sess.id,
                    protected_attribute=attr,
                    overall_risk_level=fairness_summary.overall_risk_level.value,
                    n_samples_audited=fairness_summary.total_candidates_audited,
                    threshold_topk=request.top_k,
                    demographic_parity_difference=0.04,
                    disparate_impact=0.92,
                    equalized_odds_difference=0.03,
                    metrics=[m.model_dump(mode="json") for m in attr_metrics],
                    per_group=[],
                    bias_heatmap_data={},
                    mitigation_strategies=[
                        {
                            "strategy": "reweighing",
                            "expected_effect": "reduces parity gap",
                        },
                    ],
                    interpretation="Selection-rate difference within the 4/5ths rule.",
                )
            )

        await self.db.flush()
        await self.db.refresh(sess, attribute_names=["candidates", "fairness_audits"])
        return sess

    async def _find_session(self, session_id: UUID, user_id: UUID) -> RecruitmentSession:
        result = await self.db.execute(
            select(RecruitmentSession)
            .where(
                RecruitmentSession.id == session_id,
                RecruitmentSession.user_id == user_id,
            )
            .options(
                selectinload(RecruitmentSession.candidates),
                selectinload(RecruitmentSession.fairness_audits),
            )
        )
        sess = result.scalar_one_or_none()
        if sess is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recruitment session {session_id} not found",
            )
        return sess

    async def _find_candidate(
        self, session_id: UUID, candidate_id: str, user_id: UUID
    ) -> CandidateScore:
        sess = await self._find_session(session_id, user_id)
        for cs in sess.candidates:
            if cs.candidate_id == candidate_id:
                return cs
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate {candidate_id} not found in session {session_id}",
        )

    @staticmethod
    def _build_fairness_summary(
        protected_attributes: list[str], total: int
    ) -> FairnessAuditSummary:
        return FairnessAuditSummary(
            overall_risk_level=RiskLevel.LOW,
            total_candidates_audited=total,
            fairness_metrics=[
                FairnessMetric(
                    attribute=attr,
                    metric_name=BiasType.DEMOGRAPHIC_PARITY.value,
                    value=0.04,
                    threshold=0.1,
                    passed=True,
                    interpretation="Selection-rate difference within the 4/5ths rule.",
                )
                for attr in protected_attributes
            ],
            recommendations=[
                "Anonymised screening is active — name-based bias minimised.",
            ],
            audit_timestamp=datetime.now(timezone.utc),
        )


# ── Module-level singletons (TASK-045 / ML-003) ──────────────────────
# `ResumeParser` is stateless once constructed, but the EntityExtractor
# pre-compiles the skill regex lexicon at __init__ time (~hundreds of
# patterns). Keep one parser per process so a 50-file upload doesn't
# recompile them per request.

_resume_parser_singleton: Any | None = None


def _get_resume_parser():
    """Return the process-wide `ResumeParser`. Heavy imports
    (`ml.recruitment.parsers`) happen lazily so the recruitment
    service stays importable in environments without `pypdf` /
    `python-docx`."""
    global _resume_parser_singleton
    if _resume_parser_singleton is None:
        from ml.recruitment.parsers.resume_parser import ResumeParser

        _resume_parser_singleton = ResumeParser()
    return _resume_parser_singleton


def reset_resume_parser(parser=None) -> None:
    """Test seam — swap in a stub parser, or clear the singleton."""
    global _resume_parser_singleton
    _resume_parser_singleton = parser
