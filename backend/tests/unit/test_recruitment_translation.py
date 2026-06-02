"""Offline tests for the backend ↔ ml.recruitment translation layer.

These verify the API ↔ ML shape contract without instantiating any heavy
ML model (no SBERT, no XGBoost). The lazy `ml.recruitment` imports inside
the translation functions need the repo root on `sys.path` — that's
configured via the project's `pyproject.toml` testpaths convention.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path so `ml.recruitment` resolves when
# pytest is invoked from `backend/`.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Skip the whole module if `ml.recruitment` isn't importable in this env.
# (CI runs both backend tests and the ml package on the same image.)
pytest.importorskip("ml.recruitment.data.schema")

from src.api.v1.schemas.recruitment import (  # noqa: E402
    CandidateInput,
    JobDescriptionInput,
    RecruitmentAnalysisRequest,
)
from src.services.recruitment.ml_translation import (  # noqa: E402
    api_candidate_to_ml,
    api_job_to_ml,
    api_request_to_ml,
    ml_score_to_api_ranking,
)


def _make_request(*, anonymize: bool = True, n: int = 3) -> RecruitmentAnalysisRequest:
    return RecruitmentAnalysisRequest(
        job_description=JobDescriptionInput(
            title="Senior ML Engineer",
            description=(
                "Design and ship production ML systems with explainability "
                "and fairness in mind. Python + MLOps required."
            ),
            required_skills=["python", "ml", "mlops"],
            preferred_skills=["pytorch", "kubernetes"],
            min_years_experience=4,
        ),
        candidates=[
            CandidateInput(
                candidate_id=f"cand-{i:03d}",
                cv_text=f"Engineer #{i} with Python + ML.",
                name=f"Candidate {i}",
            )
            for i in range(n)
        ],
        anonymize_names=anonymize,
        protected_attributes=["gender"],
        top_k=2,
        ensemble_sbert_weight=0.6,
    )


def test_api_job_to_ml_preserves_skills_and_metadata():
    req = _make_request()
    ml_job = api_job_to_ml(req.job_description, job_id="my-job")
    assert ml_job.job_id == "my-job"
    assert ml_job.title == "Senior ML Engineer"
    assert ml_job.required_skills == ("python", "ml", "mlops")
    assert ml_job.preferred_skills == ("pytorch", "kubernetes")
    assert ml_job.min_years_experience == 4
    assert ml_job.remote_allowed is True


def test_api_candidate_to_ml_normalises_to_dataclass():
    req = _make_request()
    ml_c = api_candidate_to_ml(req.candidates[0])
    assert ml_c.candidate_id == "cand-000"
    assert ml_c.source == "api"
    assert "Engineer" in ml_c.cv_text


def test_api_request_to_ml_one_shot():
    req = _make_request(n=4)
    job, cands = api_request_to_ml(req)
    assert job.title == "Senior ML Engineer"
    assert len(cands) == 4
    assert [c.candidate_id for c in cands] == [
        "cand-000",
        "cand-001",
        "cand-002",
        "cand-003",
    ]


def test_ml_score_to_api_ranking_anonymised():
    """ScoreDetail → CandidateRankingResult, anonymisation honoured."""
    from ml.recruitment.models.base import ScoreDetail

    req = _make_request(anonymize=True, n=3)
    details = [
        ScoreDetail(
            candidate_id="cand-001",
            score=0.92,
            sub_scores={"semantic": 0.88, "structured": 0.81},
            features={"years_experience": 6.0, "education_rank": 2},
        ),
        ScoreDetail(
            candidate_id="cand-000",
            score=0.74,
            sub_scores={"semantic": 0.71, "structured": 0.66},
            features={"years_experience": 4.0, "education_rank": 1},
        ),
    ]
    candidate_in_by_id = {c.candidate_id: c for c in req.candidates}
    ranked = ml_score_to_api_ranking(
        details,
        candidate_in_by_id=candidate_in_by_id,
        anonymize_names=True,
        required_skills=("python", "ml", "mlops"),
        preferred_skills=("pytorch", "kubernetes"),
    )
    assert [r.rank for r in ranked] == [1, 2]
    assert [r.candidate_id for r in ranked] == ["cand-001", "cand-000"]
    assert all(r.display_name is None for r in ranked), "anonymisation broke"
    # Confidence proxy: 1 - |semantic - structured|
    assert ranked[0].confidence_level == pytest.approx(1.0 - abs(0.88 - 0.81), abs=1e-4)


def test_ml_score_to_api_ranking_with_display_names():
    from ml.recruitment.models.base import ScoreDetail

    req = _make_request(anonymize=False, n=2)
    details = [
        ScoreDetail(
            candidate_id="cand-000", score=0.6, sub_scores={"semantic": 0.6, "structured": 0.5}
        ),
        ScoreDetail(
            candidate_id="cand-001", score=0.5, sub_scores={"semantic": 0.5, "structured": 0.4}
        ),
    ]
    ranked = ml_score_to_api_ranking(
        details,
        candidate_in_by_id={c.candidate_id: c for c in req.candidates},
        anonymize_names=False,
        required_skills=("python",),
        preferred_skills=("kubernetes",),
    )
    assert ranked[0].display_name == "Candidate 0"
    assert ranked[1].display_name == "Candidate 1"


def test_education_rank_round_trip():
    """The education_rank → label inversion mirrors features.structured._EDU_RANK."""
    from ml.recruitment.models.base import ScoreDetail

    cases = [
        (0, "high_school"),
        (1, "bachelor"),
        (2, "master"),
        (3, "phd"),
        (-1, None),  # unknown
        (99, None),  # out of range
    ]
    for rank_val, expected in cases:
        details = [
            ScoreDetail(
                candidate_id="x",
                score=0.5,
                sub_scores={"semantic": 0.5, "structured": 0.5},
                features={"education_rank": rank_val},
            )
        ]
        out = ml_score_to_api_ranking(
            details,
            candidate_in_by_id={},
            anonymize_names=True,
            required_skills=(),
            preferred_skills=(),
        )
        assert out[0].education_level == expected, f"rank {rank_val} → {expected}"


# ── TASK-048 / FE-016 wave 3: LIME attribution plumbing ──────────────


def test_ml_score_to_api_ranking_emits_empty_lime_features_for_real_path():
    """The real-ML translator emits `top_lime_features=[]` until the
    `LIMERecruitmentExplainer` is threaded through the inference
    singleton (TASK-048 follow-up). The schema field must still be
    present so the frontend renders the empty-state copy rather than
    crashing on a missing attribute."""
    from ml.recruitment.models.base import ScoreDetail

    details = [
        ScoreDetail(
            candidate_id="c1",
            score=0.82,
            sub_scores={"semantic": 0.9, "structured": 0.74},
        ),
    ]
    out = ml_score_to_api_ranking(
        details,
        candidate_in_by_id={},
        anonymize_names=True,
        required_skills=(),
        preferred_skills=(),
    )
    assert out[0].top_lime_features == []
    assert isinstance(out[0].top_shap_features, list)


def test_mock_lime_attrs_returns_three_rules_with_distinct_ranks():
    """The mock-path helper `_mock_lime_attrs` in
    `recruitment_service` emits the wave-3 LIME-shaped attributions
    so the `<LimePanel>` has something defensible to render before
    the real `LIMERecruitmentExplainer` is wired into the singleton.
    Magnitudes differ from the SHAP mock block on purpose — LIME's
    local surrogate weights differ from SHAP's Shapley values, and
    surfacing that difference is the whole point of showing them
    side-by-side."""
    from src.services.recruitment.recruitment_service import _mock_lime_attrs

    attrs = _mock_lime_attrs(semantic=0.8, structured=0.6)
    assert len(attrs) == 3
    # Insertion order = rank ascending.
    assert [a.importance_rank for a in attrs] == [1, 2, 3]
    # LIME rule-style feature names (containing a threshold expression),
    # not the bare SHAP feature names.
    assert all(">" in a.feature_name for a in attrs)
    # All positive in the mock branch (non-negative semantic + structured);
    # negative contributions are reserved for the real LIME path when it lands.
    assert all(a.contribution_direction == "positive" for a in attrs)
