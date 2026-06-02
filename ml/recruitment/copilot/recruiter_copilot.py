"""
Recruiter Copilot.

The copilot is the conversational surface over the ranker — its job is to
turn the structured ranking + SHAP attributions + fairness audit into
recruiter-actionable English. It is *not* a chatbot wrapper: it owns the
prompt template, the structured-input contract, and the parsed
structured-output contract.

Why a dedicated module rather than just using the chatbot service: the
recruiter's questions ("draft interview questions for the top-3", "what
risks does this shortlist surface?") have a fixed, *typed* output shape
the recruitment UI can render directly. The chatbot service handles
free-form conversation; the copilot handles structured advisory.

Implementation:
    • `build_prompt()` is pure and deterministic — fully unit-testable.
    • `RecruiterCopilot.invoke()` calls the LLM provider via the chatbot
      service interface, then parses the JSON response.

LLM provider is left injectable so tests can pass a stub.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from ml.recruitment.explainability.narrative import NarrativeExplanation
from ml.recruitment.fairness.auditor import FairnessReport
from ml.recruitment.models.base import ScoreDetail

# ── input/output contracts ──────────────────────────────────────────


@dataclass(frozen=True)
class CopilotContext:
    """Everything the copilot needs to reason about a single shortlist."""

    job_title: str
    job_description: str
    required_skills: tuple[str, ...]
    shortlist: tuple[ScoreDetail, ...]
    narratives: tuple[NarrativeExplanation, ...]
    fairness: tuple[FairnessReport, ...] = ()


@dataclass(frozen=True)
class InterviewQuestion:
    candidate_id: str
    category: str  # "behavioural" | "technical" | "situational" | "skill-probe"
    question: str
    rationale: str


@dataclass(frozen=True)
class CopilotResponse:
    summary: str
    next_steps: tuple[str, ...]
    interview_questions: tuple[InterviewQuestion, ...]
    fairness_observations: tuple[str, ...] = field(default_factory=tuple)


# ── LLM provider protocol ───────────────────────────────────────────


class LLMProvider(Protocol):
    """Anything with `complete(system, user) -> str` (raw JSON expected)."""

    def complete(self, *, system: str, user: str) -> str: ...


# ── prompt construction ─────────────────────────────────────────────


SYSTEM_PROMPT = """\
You are a senior recruiting partner advising a hiring manager. You analyse
a ranked shortlist of candidates and produce **concise, actionable, fair**
advisory output. You ALWAYS:

  - Refer to candidates by their candidate_id only (never by name).
  - Quote the SHAP-derived rationale faithfully; do not invent facts.
  - Surface fairness concerns when the audit flags them.
  - Return strict JSON matching the schema in the user message.
"""


def build_prompt(ctx: CopilotContext) -> tuple[str, str]:
    """Pure function — returns ``(system_prompt, user_prompt)`` ready to send.

    Deterministic given the same `ctx`, so unit-testable independent of LLM."""

    shortlist_lines = []
    for sd, narr in zip(ctx.shortlist, ctx.narratives, strict=False):
        shortlist_lines.append(
            f"  - candidate_id={sd.candidate_id} "
            f"score={sd.score:.3f} "
            f"semantic={sd.sub_scores.get('semantic', float('nan')):.3f} "
            f"structured={sd.sub_scores.get('structured', float('nan')):.3f}\n"
            f"    rationale: {narr.one_liner}\n"
            f"    drivers: {'; '.join(narr.bullets)}"
        )

    fairness_lines = []
    for f in ctx.fairness:
        fairness_lines.append(
            f"  - attribute={f.protected_attribute} "
            f"DPD={f.demographic_parity_difference:.3f} "
            f"DI={f.disparate_impact:.2f} risk={f.overall_risk}"
        )

    user = f"""\
Job: {ctx.job_title}
Required skills: {", ".join(ctx.required_skills) or "(unspecified)"}

Shortlist ({len(ctx.shortlist)} candidates):
{chr(10).join(shortlist_lines) if shortlist_lines else "  (empty)"}

Fairness audit:
{chr(10).join(fairness_lines) if fairness_lines else "  (none)"}

Return strict JSON with this schema (no commentary outside the JSON):
{{
  "summary": "<<=2 sentences capturing the shortlist's overall strength>>",
  "next_steps": ["<step1>", "<step2>", ...],
  "interview_questions": [
    {{"candidate_id": "<id>", "category": "behavioural|technical|situational|skill-probe",
      "question": "<question>", "rationale": "<why this question for this candidate>"}}
  ],
  "fairness_observations": ["<short concrete observation>", ...]
}}
"""
    return SYSTEM_PROMPT, user


# ── orchestrator ────────────────────────────────────────────────────


class RecruiterCopilot:
    """Round-trip: build prompt → invoke LLM → parse JSON."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def invoke(self, ctx: CopilotContext) -> CopilotResponse:
        system, user = build_prompt(ctx)
        raw = self._llm.complete(system=system, user=user)
        data = _parse_json_strict(raw)
        return CopilotResponse(
            summary=str(data.get("summary", "")),
            next_steps=tuple(data.get("next_steps", []) or []),
            interview_questions=tuple(
                InterviewQuestion(
                    candidate_id=str(q.get("candidate_id", "")),
                    category=str(q.get("category", "")),
                    question=str(q.get("question", "")),
                    rationale=str(q.get("rationale", "")),
                )
                for q in (data.get("interview_questions") or [])
            ),
            fairness_observations=tuple(data.get("fairness_observations", []) or []),
        )


def _parse_json_strict(raw: str) -> dict:
    """Trim Markdown ``` fences if the model wrapped its JSON, then parse."""
    s = raw.strip()
    if s.startswith("```"):
        # Strip ```json … ``` envelope
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s
        if s.startswith("json"):
            s = s[4:]
    return json.loads(s)
