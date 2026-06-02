"""
Pricing Copilot.

Conversational surface over the pricing policy + SHAP narrative + Monte
Carlo result. Mirrors `ml.recruitment.copilot.recruiter_copilot`:

  • `build_prompt(ctx)` is *pure and deterministic* — fully unit-testable
    independent of any LLM.
  • `PricingCopilot.invoke(ctx)` calls an injectable provider and parses
    the JSON response into a typed `PricingCopilotResponse`.

The output is *structured* — the merchant UI binds directly to the JSON
fields, no free-form text extraction. The LLM is responsible only for
the *advisory layer*: prioritised next actions and risk callouts; it
never *generates* prices. Prices come from the policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from ml.pricing.data.schema import PriceRecommendation
from ml.pricing.explainability.narrative import PricingNarrative
from ml.pricing.models.monte_carlo import MonteCarloResult


@dataclass(frozen=True)
class PricingCopilotContext:
    """Everything the copilot needs to reason about a single recommendation."""

    product_id: str
    product_category: str | None
    current_price: float
    unit_cost: float
    recommendation: PriceRecommendation
    narrative: PricingNarrative
    monte_carlo: MonteCarloResult | None = None


@dataclass(frozen=True)
class PricingCopilotResponse:
    summary: str
    next_steps: tuple[str, ...]
    risks: tuple[str, ...]
    monitoring_metrics: tuple[str, ...]
    rollout_plan: tuple[str, ...] = field(default_factory=tuple)


class LLMProvider(Protocol):
    def complete(self, *, system: str, user: str) -> str: ...


SYSTEM_PROMPT = """\
You are a senior pricing analyst advising a small-business owner. You
read a SHAP-attributed pricing recommendation and Monte-Carlo revenue
distribution, then produce **concise, actionable, risk-aware** advisory
output. You ALWAYS:

  - Reference the product by `product_id` only.
  - Quote the SHAP-derived rationale faithfully; never invent factors.
  - Surface downside risk when Value-at-Risk is significant.
  - NEVER recommend a price different from the one in the input.
  - Return strict JSON matching the schema in the user message.
"""


def build_prompt(ctx: PricingCopilotContext) -> tuple[str, str]:
    """Pure function — returns ``(system_prompt, user_prompt)``."""
    rec = ctx.recommendation
    bullets = "\n      ".join(f"- {b}" for b in ctx.narrative.bullets) or "(none)"
    mc_line = (
        f"  Monte Carlo: mean={ctx.monte_carlo.mean_revenue:,.0f}, "
        f"P5={ctx.monte_carlo.revenue_p5:,.0f}, P95={ctx.monte_carlo.revenue_p95:,.0f}, "
        f"VaR(5%)={ctx.monte_carlo.value_at_risk_5pct:,.0f}, "
        f"P(profit)={ctx.monte_carlo.probability_of_profit:.0%}"
        if ctx.monte_carlo is not None
        else "  Monte Carlo: (not run)"
    )

    user = f"""\
Product: {ctx.product_id} (category: {ctx.product_category or "unknown"})
Current price: {ctx.current_price:.2f} · Unit cost: {ctx.unit_cost:.2f}

Recommendation:
  Recommended price: {rec.recommended_price:.2f}
  Expected revenue : {rec.expected_revenue:,.2f}
  Expected demand  : {rec.expected_demand:,.2f}
  CI               : ({rec.confidence_interval[0]:.2f}, {rec.confidence_interval[1]:.2f})
  Policy rationale : {rec.rationale}

SHAP narrative:
  Headline: {ctx.narrative.headline}
  Drivers:
      {bullets}

{mc_line}

Return strict JSON with this schema (no commentary outside the JSON):
{{
  "summary": "<<=2 sentence summary>>",
  "next_steps": ["<step1>", "<step2>", ...],
  "risks": ["<short concrete risk>", ...],
  "monitoring_metrics": ["<metric to track post-rollout>", ...],
  "rollout_plan": ["<phase1>", "<phase2>", ...]
}}
"""
    return SYSTEM_PROMPT, user


class PricingCopilot:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def invoke(self, ctx: PricingCopilotContext) -> PricingCopilotResponse:
        system, user = build_prompt(ctx)
        raw = self._llm.complete(system=system, user=user)
        data = _parse_json_strict(raw)
        return PricingCopilotResponse(
            summary=str(data.get("summary", "")),
            next_steps=tuple(data.get("next_steps", []) or []),
            risks=tuple(data.get("risks", []) or []),
            monitoring_metrics=tuple(data.get("monitoring_metrics", []) or []),
            rollout_plan=tuple(data.get("rollout_plan", []) or []),
        )


def _parse_json_strict(raw: str) -> dict:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s
        if s.startswith("json"):
            s = s[4:]
    return json.loads(s)
