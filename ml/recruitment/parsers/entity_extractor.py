"""
Entity extraction from raw CV text.

We extract the *structured features* used by the boosting rankers
(years_experience, education_level, skills) using a hybrid of regular
expressions and a configurable skill lexicon. This is deliberately
lightweight and explainable — no NER model, no LLM round-trip — so the
parser is reproducible, fast (<1 ms / CV), and auditable.

A heavier transformer-based parser is on the Phase-4 roadmap and would
slot in behind the same `EntityExtractor` interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_SKILL_LEXICON: tuple[str, ...] = (
    # languages
    "python",
    "java",
    "javascript",
    "typescript",
    "go",
    "rust",
    "c++",
    "scala",
    # ml
    "machine learning",
    "deep learning",
    "nlp",
    "computer vision",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "xgboost",
    "lightgbm",
    "transformers",
    # infra
    "kubernetes",
    "docker",
    "aws",
    "gcp",
    "azure",
    "terraform",
    "mlops",
    "airflow",
    "spark",
    "kafka",
    # data
    "sql",
    "postgresql",
    "mongodb",
    "snowflake",
    "dbt",
    # soft
    "leadership",
    "communication",
    "project management",
)

EDUCATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("phd", re.compile(r"\b(ph\.?d|doctorate|doctoral)\b", re.IGNORECASE)),
    ("master", re.compile(r"\b(m\.?s|m\.?sc|master(?:'s)?)\b", re.IGNORECASE)),
    ("bachelor", re.compile(r"\b(b\.?s|b\.?sc|b\.?a|bachelor(?:'s)?)\b", re.IGNORECASE)),
    ("high_school", re.compile(r"\b(high school|gcse|a-levels?|diploma)\b", re.IGNORECASE)),
)

# Match "5 years", "5+ years", "5-7 years", "5 yrs" — case-insensitive.
YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractedEntities:
    years_experience: float | None
    education_level: str | None
    skills: tuple[str, ...] = field(default_factory=tuple)


class EntityExtractor:
    def __init__(self, skill_lexicon: tuple[str, ...] = DEFAULT_SKILL_LEXICON) -> None:
        # Pre-compile skill matchers once. Case-insensitive whole-word match.
        self._skill_lexicon = skill_lexicon
        self._skill_res = [
            (s, re.compile(rf"(?<![\w]){re.escape(s)}(?![\w])", re.IGNORECASE))
            for s in skill_lexicon
        ]

    def extract(self, text: str) -> ExtractedEntities:
        if not text:
            return ExtractedEntities(None, None, ())
        return ExtractedEntities(
            years_experience=self._years(text),
            education_level=self._education(text),
            skills=self._skills(text),
        )

    # ── internals ───────────────────────────────────────────────────
    @staticmethod
    def _years(text: str) -> float | None:
        m = YEARS_RE.search(text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _education(text: str) -> str | None:
        # Match highest-degree first.
        for level, pattern in EDUCATION_PATTERNS:
            if pattern.search(text):
                return level
        return None

    def _skills(self, text: str) -> tuple[str, ...]:
        hits: list[str] = []
        for skill, pat in self._skill_res:
            if pat.search(text):
                hits.append(skill)
        # Preserve lexicon order so the output is deterministic.
        return tuple(hits)
