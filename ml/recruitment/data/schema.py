"""
Recruitment data schemas.

Pure dataclasses — no heavy imports — so they can be used across the parser,
ranker, evaluator, and fairness auditor without dragging in numpy / pandas /
torch. The split between *raw* input (free-text CV) and *structured* features
(years, education, …) is intentional: parsers fill the structured slots, and
each ranking model decides which slots it consumes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class JobDescription:
    """A job description against which candidates are ranked."""

    job_id: str
    title: str
    description: str
    required_skills: tuple[str, ...] = ()
    preferred_skills: tuple[str, ...] = ()
    min_years_experience: int | None = None
    max_years_experience: int | None = None
    location: str | None = None
    remote_allowed: bool = True
    department: str | None = None

    @property
    def all_skills(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.required_skills, *self.preferred_skills)))


@dataclass(frozen=True)
class ProtectedAttributes:
    """Self-reported (or imputed) demographics. Optional — present only when
    fairness auditing is enabled and the candidate has provided values.

    All attributes are optional so that fairness auditing degrades gracefully
    when only a subset of demographics is available."""

    gender: str | None = None
    age_group: str | None = None  # e.g. "18-25", "26-35", ...
    ethnicity: str | None = None
    disability_status: str | None = None
    veteran_status: str | None = None


@dataclass(frozen=True)
class CandidateRecord:
    """A single candidate normalised for ranking.

    `cv_text` is the raw resume; the other fields are structured features
    extracted by the parser. Models may use any subset:
      - SBERT ranker → reads `cv_text` only
      - XGBoost ranker → reads structured features only
      - Ensemble → reads both
    """

    candidate_id: str
    cv_text: str

    # Structured features (filled by ResumeParser).
    name: str | None = None
    years_experience: float | None = None
    skills: tuple[str, ...] = ()
    education_level: str | None = None  # "high_school" | "bachelor" | "master" | "phd"
    current_role: str | None = None
    location: str | None = None
    languages: tuple[str, ...] = ()

    # Audit-only — never used as a feature.
    protected: ProtectedAttributes = field(default_factory=ProtectedAttributes)

    # Provenance.
    source: str = "synthetic"  # "synthetic" | "pdf" | "docx" | "text" | "api"


@dataclass(frozen=True)
class Pair:
    """A single training/eval observation: (job, candidate, label).

    `label` is the ground-truth relevance. For binary supervised training
    `label ∈ {0, 1}` (hired vs not); for graded relevance (NDCG) `label ∈ {0, 1, 2, 3}`.
    """

    job: JobDescription
    candidate: CandidateRecord
    label: int


# ── Helpers ─────────────────────────────────────────────────────────


def coerce_skills(raw: Mapping[str, object] | None, key: str) -> tuple[str, ...]:
    """Defensive parser for skill lists coming from JSON / CSV — collapses
    None, lists, comma-separated strings into a clean string tuple."""
    if not raw or key not in raw:
        return ()
    val = raw[key]
    if val is None:
        return ()
    if isinstance(val, str):
        return tuple(s.strip() for s in val.split(",") if s.strip())
    if isinstance(val, (list, tuple)):
        return tuple(str(s).strip() for s in val if str(s).strip())
    return ()
