"""
Recruitment data loader.

Two paths:
  • `load_synthetic()`  — uses the synthetic generator in `ml/data/synthetic`
                          for unit tests, ablation runs, and CI.
  • `load_jsonl()`      — ingests real-world JSONL with one Pair per line.

The loader exposes a `RecruitmentDataset` value type with deterministic
splits (`split()` is keyed on (candidate_id, seed) → no overlap between
train/val/test even when called multiple times).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ml.recruitment.data.schema import (
    CandidateRecord,
    JobDescription,
    Pair,
    ProtectedAttributes,
)


@dataclass
class RecruitmentDataset:
    """Container for a list of Pairs with deterministic train/val/test splits."""

    pairs: list[Pair]
    name: str = "unnamed"

    def __len__(self) -> int:
        return len(self.pairs)

    def __iter__(self) -> Iterator[Pair]:
        return iter(self.pairs)

    # ── deterministic splits ───────────────────────────────────────
    def split(
        self,
        train: float = 0.7,
        val: float = 0.15,
        seed: int = 42,
    ) -> tuple[RecruitmentDataset, RecruitmentDataset, RecruitmentDataset]:
        """Hash-based split — repeated calls produce identical partitions, and
        adding new candidates won't reshuffle existing ones. Test size = 1 - train - val."""
        if not 0 < train < 1 or not 0 <= val < 1 or train + val >= 1:
            raise ValueError("Invalid split proportions")

        def bucket(candidate_id: str) -> float:
            h = hashlib.sha256(f"{seed}:{candidate_id}".encode()).hexdigest()
            return int(h[:8], 16) / 0xFFFFFFFF

        tr, va, te = [], [], []
        for pair in self.pairs:
            b = bucket(pair.candidate.candidate_id)
            if b < train:
                tr.append(pair)
            elif b < train + val:
                va.append(pair)
            else:
                te.append(pair)
        return (
            RecruitmentDataset(tr, f"{self.name}/train"),
            RecruitmentDataset(va, f"{self.name}/val"),
            RecruitmentDataset(te, f"{self.name}/test"),
        )

    # ── projections ───────────────────────────────────────────────
    def jobs(self) -> list[JobDescription]:
        return list({p.job.job_id: p.job for p in self.pairs}.values())

    def candidates(self) -> list[CandidateRecord]:
        return list({p.candidate.candidate_id: p.candidate for p in self.pairs}.values())

    def labels(self) -> np.ndarray:
        return np.asarray([p.label for p in self.pairs], dtype=np.int32)


class RecruitmentDataLoader:
    """High-level loader. The synthetic path is the canonical fixture for
    development, CI, and ablation; the JSONL path is the production entry point
    once partner data is available."""

    def load_synthetic(self, n_candidates: int = 500, seed: int = 42) -> RecruitmentDataset:
        """Build a synthetic dataset by adapting the recruitment generator in
        `ml/data/synthetic/generators.py` into the Pair schema."""
        from ml.data.synthetic.generators import generate_recruitment

        df = generate_recruitment(n=n_candidates, seed=seed)

        # One synthetic job description that every candidate is scored against.
        # Real-world ingestion would have many JDs; this is sufficient for
        # baseline calibration and AS-001 (recruitment ablation).
        jd = JobDescription(
            job_id="synthetic-jd-001",
            title="Senior Machine Learning Engineer",
            description=(
                "We are hiring a Senior ML Engineer to design and ship "
                "production ML systems. The ideal candidate has experience "
                "with Python, distributed training, and MLOps."
            ),
            required_skills=("python", "machine learning", "mlops"),
            preferred_skills=("pytorch", "kubernetes", "leadership"),
            min_years_experience=4,
        )

        pairs: list[Pair] = []
        rng = np.random.default_rng(seed)
        skill_pool = ("python", "machine learning", "pytorch", "mlops", "kubernetes", "leadership")

        for i, row in df.iterrows():
            cid = f"cand-{int(i):05d}"
            n_skills = int(rng.integers(2, 5))
            skills = tuple(rng.choice(skill_pool, size=n_skills, replace=False).tolist())
            cand = CandidateRecord(
                candidate_id=cid,
                cv_text=_synthesise_cv_text(skills, float(row["years_experience"])),
                years_experience=float(row["years_experience"]),
                skills=skills,
                education_level=_education_from_int(int(row["education_level"])),
                protected=ProtectedAttributes(
                    gender="female" if int(row["gender"]) == 0 else "male",
                ),
                source="synthetic",
            )
            pairs.append(Pair(job=jd, candidate=cand, label=int(row["hired"])))

        return RecruitmentDataset(pairs, name="synthetic")

    def load_jsonl(self, path: str | Path) -> RecruitmentDataset:
        """Read a JSONL file where each line is one `{job, candidate, label}` record."""
        path = Path(path)
        pairs: list[Pair] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                record = json.loads(line)
                pairs.append(_pair_from_dict(record))
        return RecruitmentDataset(pairs, name=path.stem)


# ── private helpers ─────────────────────────────────────────────────


_EDU_BY_INT = ("high_school", "bachelor", "master", "phd")


def _education_from_int(level: int) -> str:
    return _EDU_BY_INT[max(0, min(level, len(_EDU_BY_INT) - 1))]


def _synthesise_cv_text(skills: Iterable[str], years: float) -> str:
    """Deterministic synthetic CV body — used by SBERTRanker so the semantic
    score has *some* signal even on synthetic data. Real ingestion supplies
    real `cv_text`."""
    skills_s = ", ".join(skills)
    return (
        f"Experienced engineer with {years:.1f} years in industry. "
        f"Core skills include {skills_s}. Built production systems, "
        f"delivered cross-functional projects, and led small teams."
    )


def _pair_from_dict(record: dict) -> Pair:
    jd_raw = record["job"]
    c_raw = record["candidate"]
    job = JobDescription(
        job_id=str(jd_raw["job_id"]),
        title=str(jd_raw.get("title", "")),
        description=str(jd_raw.get("description", "")),
        required_skills=tuple(jd_raw.get("required_skills") or ()),
        preferred_skills=tuple(jd_raw.get("preferred_skills") or ()),
        min_years_experience=jd_raw.get("min_years_experience"),
        max_years_experience=jd_raw.get("max_years_experience"),
        location=jd_raw.get("location"),
        remote_allowed=bool(jd_raw.get("remote_allowed", True)),
        department=jd_raw.get("department"),
    )
    protected = ProtectedAttributes(**(c_raw.get("protected") or {}))
    candidate = CandidateRecord(
        candidate_id=str(c_raw["candidate_id"]),
        cv_text=str(c_raw.get("cv_text", "")),
        name=c_raw.get("name"),
        years_experience=c_raw.get("years_experience"),
        skills=tuple(c_raw.get("skills") or ()),
        education_level=c_raw.get("education_level"),
        current_role=c_raw.get("current_role"),
        location=c_raw.get("location"),
        languages=tuple(c_raw.get("languages") or ()),
        protected=protected,
        source=str(c_raw.get("source", "api")),
    )
    return Pair(job=job, candidate=candidate, label=int(record.get("label", 0)))
