"""
Agent executor — composes a router + a responder into a final answer.

Wave 1 flow:
  1. router classifies the query → `module`
  2. responder retrieves + answers with `module_filter=module`
  3. executor merges the two `AgentResponse` traces

Wave 2 (LangGraph multi-agent) replaces the executor with a real graph
runner; the upstream agents stay the same.
"""

from __future__ import annotations

from ml.chatbot.agents.base import BaseAgent
from ml.chatbot.agents.rag_responder import RagResponderAgent
from ml.chatbot.agents.router import KeywordRouterAgent
from ml.chatbot.data.schema import AgentResponse, Query


class AgentExecutor(BaseAgent):
    """Router + responder pipeline."""

    def __init__(
        self,
        *,
        router: KeywordRouterAgent,
        responder: RagResponderAgent,
        apply_module_filter: bool = True,
    ) -> None:
        self._router = router
        self._responder = responder
        self._apply_module_filter = apply_module_filter

    @property
    def name(self) -> str:
        return f"Executor({self._router.name}+{self._responder.name})"

    def respond(self, query: Query) -> AgentResponse:
        module, confidence = self._router.classify(query.text)
        # Build a new Query with the router's verdict folded into
        # include_modules so the responder routes correctly.
        if self._apply_module_filter:
            routed_query = Query(
                query_id=query.query_id,
                text=query.text,
                include_modules=(module,),
                user_id=query.user_id,
            )
        else:
            routed_query = query

        response = self._responder.respond(routed_query)

        # Prepend the router's reasoning + tool call to the final trace
        # so the API can surface both steps.
        merged_trace = (
            f"Router classified query → '{module}' (confidence {confidence:.2f})",
            *response.reasoning_trace,
        )
        merged_tools = (
            *self._router.respond(query).tool_calls,
            *response.tool_calls,
        )

        return AgentResponse(
            query_id=response.query_id,
            content=response.content,
            reasoning_trace=merged_trace,
            sources=response.sources,
            tool_calls=merged_tools,
            tokens_used=response.tokens_used,
            agent_name=self.name,
        )
