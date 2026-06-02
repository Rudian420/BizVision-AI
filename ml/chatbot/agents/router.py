"""
Keyword-based module router.

Classifies which BizVision module a query targets — feeds into the
retriever's `module_filter` so RAG only surfaces chunks from the
relevant module. Pure deterministic rules; no learned parameters; no
LLM call. Wave 2 may swap in a small text classifier behind the same
`BaseAgent` ABC.

The router is also a `BaseAgent` so the AS-005 ablation harness can
score router-only configurations against router+RAG variants on the
same golden queries.
"""

from __future__ import annotations

import re

from ml.chatbot.agents.base import BaseAgent
from ml.chatbot.data.schema import AgentResponse, Query, ToolCall

# Per-module keyword catalogs. Lower-case, whole-word matching (boundary
# regex) so "esg" doesn't match "message". Order doesn't matter — the
# scoring loop weights every match equally.
_MODULE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "recruitment": (
        "hire", "hiring", "recruit", "recruiter", "recruitment",
        "candidate", "interview", "interviewer", "resume", "talent",
        "onboarding", "headcount", "engineer", "compensation", "salary",
        "offer", "diversity", "dei", "panel", "sourcing", "funnel",
    ),
    "pricing": (
        "price", "pricing", "elasticity", "promotion", "discount",
        "tier", "tiered", "saas", "subscription", "bundle", "bundling",
        "rl", "reinforcement", "monte", "carlo", "competitor", "leader",
        "competitive", "loss-leader",
    ),
    "forecasting": (
        "forecast", "forecasting", "holt", "winters", "prophet",
        "lstm", "ensemble", "mape", "rmse", "scenario", "sensitivity",
        "tornado", "what-if", "horizon", "backtest", "interval", "prediction",
    ),
    "sustainability": (
        "esg", "scope", "scope-1", "scope-2", "scope-3", "emission",
        "emissions", "carbon", "renewable", "renewables", "fairness",
        "four-fifths", "disparate", "impact", "dei", "biodiversity",
        "water", "circular", "tcfd", "sasb", "gri", "ppa",
    ),
    "general": (
        "runway", "okr", "okrs", "budget", "budgeting", "board",
        "dashboard", "executive", "calibration", "narrative", "vendor",
        "capital", "allocation",
    ),
}


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9\-]+", text)}


class KeywordRouterAgent(BaseAgent):
    """Routes a query to a single BizVision module by keyword match.

    Scoring: count distinct keyword hits per module; ties broken by
    catalog order in `_MODULE_KEYWORDS` (recruitment > pricing > …).
    Unmatched queries default to `general`.
    """

    def __init__(
        self,
        *,
        keywords: dict[str, tuple[str, ...]] | None = None,
        default_module: str = "general",
    ) -> None:
        # Pre-compute lower-case sets for O(1) membership.
        catalog = keywords or _MODULE_KEYWORDS
        self._catalog: dict[str, frozenset[str]] = {
            mod: frozenset(k.lower() for k in kws) for mod, kws in catalog.items()
        }
        self._default = default_module

    @property
    def name(self) -> str:
        return "KeywordRouter"

    def classify(self, text: str) -> tuple[str, float]:
        """Return `(module, confidence)` for a raw text query.

        Confidence is `hits / max(1, n_tokens)` — bounded in [0, 1].
        """
        toks = _tokens(text)
        if not toks:
            return self._default, 0.0
        best_mod = self._default
        best_score = 0
        for mod, kws in self._catalog.items():
            score = sum(1 for t in toks if t in kws)
            if score > best_score:
                best_score = score
                best_mod = mod
        return best_mod, best_score / max(1, len(toks))

    def respond(self, query: Query) -> AgentResponse:
        """Build a structured response that *only* contains the routing
        decision — no retrieved chunks, no tool calls. The executor
        composes router + responder into a final response."""
        module, confidence = self.classify(query.text)
        return AgentResponse(
            query_id=query.query_id,
            content=f"Routed to module '{module}' (confidence {confidence:.2f}).",
            reasoning_trace=(
                f"Tokenized query into {len(_tokens(query.text))} terms",
                f"Matched {module} module with confidence {confidence:.2f}",
            ),
            tool_calls=(
                ToolCall(
                    name="router_classify",
                    arguments={"module": module, "confidence": f"{confidence:.4f}"},
                    status="completed",
                ),
            ),
            agent_name=self.name,
        )
