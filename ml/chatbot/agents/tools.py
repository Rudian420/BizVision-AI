"""
Typed tool registry — one stub tool per BizVision module.

In wave 1 every tool is a deterministic stub returning a fixed string;
the registry exists so the wave-2 LangGraph agent can register real
backend-facing tools (e.g. fetch latest pricing recommendation, latest
ESG score) behind the same interface. The router agent's `tool_calls`
list references these names regardless of which wave is active.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tool:
    """One callable backend tool.

    Wave 1 tools return a fixed string. Wave 2 swaps in a real
    callable that hits the backend module API (e.g.
    `/pricing/optimize`) via a shared httpx client.
    """

    name: str
    description: str
    handler: Callable[[dict[str, str]], str]
    module: str = "general"


def _stub_handler(name: str) -> Callable[[dict[str, str]], str]:
    def handler(_args: dict[str, str]) -> str:
        return f"[stub] {name} returned a placeholder result."

    return handler


_DEFAULT_TOOLS: tuple[Tool, ...] = (
    Tool(
        name="fetch_latest_recruitment_session",
        description="Look up the caller's most recent recruitment session.",
        handler=_stub_handler("fetch_latest_recruitment_session"),
        module="recruitment",
    ),
    Tool(
        name="fetch_latest_pricing_recommendation",
        description="Look up the caller's most recent /pricing/optimize result.",
        handler=_stub_handler("fetch_latest_pricing_recommendation"),
        module="pricing",
    ),
    Tool(
        name="fetch_latest_profit_forecast",
        description="Look up the caller's most recent /forecasting/forecast result.",
        handler=_stub_handler("fetch_latest_profit_forecast"),
        module="forecasting",
    ),
    Tool(
        name="fetch_latest_esg_score",
        description="Look up the caller's most recent /sustainability/score result.",
        handler=_stub_handler("fetch_latest_esg_score"),
        module="sustainability",
    ),
    Tool(
        name="fetch_cash_runway",
        description="Approximate the caller's current cash runway.",
        handler=_stub_handler("fetch_cash_runway"),
        module="general",
    ),
)


@dataclass
class ToolRegistry:
    """Holds named tools and dispatches by name.

    Mutable on purpose — wave 2 mutates this at startup to register
    real backend-facing tools.
    """

    tools: dict[str, Tool] = field(default_factory=dict)

    @classmethod
    def with_defaults(cls) -> ToolRegistry:
        registry = cls()
        for tool in _DEFAULT_TOOLS:
            registry.register(tool)
        return registry

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"tool {tool.name!r} is already registered")
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self.tools:
            raise KeyError(f"unknown tool: {name!r}")
        return self.tools[name]

    def for_module(self, module: str) -> tuple[Tool, ...]:
        return tuple(t for t in self.tools.values() if t.module == module)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.tools.keys()))
