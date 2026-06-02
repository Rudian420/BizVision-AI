"""Offline construction tests for the recruitment ORM models.

These don't touch a database — they verify the dataclass-like shape and
default behaviour so a future refactor that breaks one column is caught
without the integration containers.
"""

from __future__ import annotations

import uuid

from src.models.recruitment import (
    CandidateScore,
    FairnessAuditRecord,
    RecruitmentSession,
)


def test_recruitment_session_basic_construction():
    sess = RecruitmentSession(
        user_id=uuid.uuid4(),
        job_title="Senior ML Engineer",
        job_description="Build production ML systems.",
        job_details={"required_skills": ["python", "ml"]},
        total_candidates=12,
        top_k=5,
        protected_attributes=["gender"],
        processing_time_ms=41.2,
        model_version="recruitment-mock-0.1",
        sbert_model="sentence-transformers/all-mpnet-base-v2",
        ensemble_weights={"sbert": 0.6, "xgboost": 0.4},
    )
    assert sess.total_candidates == 12
    assert sess.ensemble_weights["sbert"] == 0.6
    assert sess.protected_attributes == ["gender"]


def test_candidate_score_with_shap_payload():
    cs = CandidateScore(
        session_id=uuid.uuid4(),
        candidate_id="cand-001",
        rank=1,
        composite_score=0.84,
        semantic_score=0.81,
        structured_score=0.71,
        confidence_level=0.90,
        years_experience=6.5,
        education_level="master",
        matched_skills=["python", "mlops"],
        missing_skills=["kubernetes"],
        top_shap_features=[
            {
                "feature_name": "semantic_similarity",
                "shap_value": 0.18,
                "feature_value": 0.81,
                "contribution_direction": "positive",
                "importance_rank": 1,
            }
        ],
        ai_rationale="Strong alignment with the role.",
    )
    assert cs.rank == 1
    assert cs.top_shap_features[0]["feature_name"] == "semantic_similarity"


def test_fairness_audit_record_intersectional_attribute_name():
    rec = FairnessAuditRecord(
        session_id=uuid.uuid4(),
        protected_attribute="gender×age_group",
        overall_risk_level="low",
        n_samples_audited=50,
        threshold_topk=5,
        demographic_parity_difference=0.06,
        disparate_impact=0.9,
        metrics=[],
        per_group=[],
        bias_heatmap_data={},
        mitigation_strategies=[{"strategy": "reweighing"}],
    )
    assert "×" in rec.protected_attribute
    assert rec.overall_risk_level == "low"
