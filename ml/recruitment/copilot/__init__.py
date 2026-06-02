"""Recruiter copilot — the conversational LLM layer over the ranker."""

from ml.recruitment.copilot.recruiter_copilot import (
    CopilotContext,
    CopilotResponse,
    RecruiterCopilot,
    build_prompt,
)

__all__ = ["CopilotContext", "CopilotResponse", "RecruiterCopilot", "build_prompt"]
