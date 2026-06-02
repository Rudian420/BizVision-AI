"""
Tabular feature engineering for the XGBoost / LightGBM rankers.

Features are intentionally simple and *explainable* — every column is one
of: a normalised numeric attribute (years, edu rank), a fraction (skill
overlap), or a boolean flag (location match, min-years met). This makes
SHAP attributions readable in plain English by the narrative engine.

`FEATURE_NAMES` is the canonical order: pass it through to SHAP /
ml-experiments so attribution outputs line up with the matrix columns.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from ml.recruitment.data.schema import CandidateRecord, JobDescription

# Education ordinal — used as a structured feature, NOT as a class label.
# Higher = more education. Unknown → -1 so the boosting model can branch on
# missingness rather than imputing.
_EDU_RANK: dict[str, int] = {
    "high_school": 0,
    "bachelor": 1,
    "master": 2,
    "phd": 3,
}

FEATURE_NAMES: tuple[str, ...] = (
    "years_experience",
    "education_rank",
    "required_skill_overlap",  # |required ∩ candidate| / |required|
    "preferred_skill_overlap",  # |preferred ∩ candidate| / |preferred|
    "total_skill_count",
    "min_years_met",  # 1 if years >= min_years_experience else 0
    "location_match",  # 1 if candidate.location matches job.location or remote_allowed
    "has_education",  # 1 if education_level extracted else 0
)


def _education_rank(level: str | None) -> int:
    if level is None:
        return -1
    return _EDU_RANK.get(level, -1)


def _overlap(required: tuple[str, ...], candidate_skills: tuple[str, ...]) -> float:
    if not required:
        return 0.0
    req = {s.lower() for s in required}
    cs = {s.lower() for s in candidate_skills}
    return len(req & cs) / len(req)


def _location_match(jd: JobDescription, cand: CandidateRecord) -> int:
    if jd.remote_allowed:
        return 1
    if jd.location and cand.location and jd.location.lower() == cand.location.lower():
        return 1
    return 0


def _min_years_met(jd: JobDescription, cand: CandidateRecord) -> int:
    if jd.min_years_experience is None:
        return 1  # no requirement → trivially met
    if cand.years_experience is None:
        return 0
    return int(cand.years_experience >= jd.min_years_experience)


def candidate_features(jd: JobDescription, cand: CandidateRecord) -> np.ndarray:
    """Vectorise a (job, candidate) pair into the FEATURE_NAMES ordering."""
    years = cand.years_experience if cand.years_experience is not None else -1.0
    return np.array(
        [
            years,
            _education_rank(cand.education_level),
            _overlap(jd.required_skills, cand.skills),
            _overlap(jd.preferred_skills, cand.skills),
            float(len(cand.skills)),
            _min_years_met(jd, cand),
            _location_match(jd, cand),
            int(cand.education_level is not None),
        ],
        dtype=np.float32,
    )


def build_feature_matrix(
    jd: JobDescription,
    candidates: Iterable[CandidateRecord],
) -> np.ndarray:
    """Stack per-candidate feature vectors into a (n_candidates × n_features) matrix."""
    rows = [candidate_features(jd, c) for c in candidates]
    if not rows:
        return np.empty((0, len(FEATURE_NAMES)), dtype=np.float32)
    return np.vstack(rows)
