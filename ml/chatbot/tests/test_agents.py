"""
Offline unit tests for the chatbot agents (router + responder + executor).
"""

from __future__ import annotations

import pytest

from ml.chatbot.agents.executor import AgentExecutor
from ml.chatbot.agents.rag_responder import RagResponderAgent
from ml.chatbot.agents.router import KeywordRouterAgent
from ml.chatbot.agents.tools import ToolRegistry
from ml.chatbot.data.loader import generate_synthetic_corpus
from ml.chatbot.data.schema import Query
from ml.chatbot.embeddings.hash_embedder import HashEmbedder
from ml.chatbot.retrieval.rag import RagRetriever


def _executor():
    retriever = RagRetriever(embedder=HashEmbedder(dimension=256)).index_corpus(
        generate_synthetic_corpus()
    )
    return AgentExecutor(
        router=KeywordRouterAgent(),
        responder=RagResponderAgent(retriever, top_k=3),
    )


# ── KeywordRouterAgent ─────────────────────────────────────────────


def test_router_classifies_pricing_query():
    router = KeywordRouterAgent()
    module, conf = router.classify("how do I optimize my SaaS pricing tier?")
    assert module == "pricing"
    assert conf > 0


def test_router_classifies_recruitment_query():
    router = KeywordRouterAgent()
    module, _ = router.classify("how long does it take to hire a senior engineer?")
    assert module == "recruitment"


def test_router_classifies_forecasting_query():
    router = KeywordRouterAgent()
    module, _ = router.classify("what is MAPE for our profit forecast?")
    assert module == "forecasting"


def test_router_classifies_sustainability_query():
    router = KeywordRouterAgent()
    module, _ = router.classify("How do I calculate Scope 3 emissions?")
    assert module == "sustainability"


def test_router_falls_back_to_default_on_unmatched():
    router = KeywordRouterAgent(default_module="general")
    module, _ = router.classify("xyzzy quux foobar")
    assert module == "general"


def test_router_respond_emits_classify_tool_call():
    router = KeywordRouterAgent()
    response = router.respond(Query(query_id="q", text="optimise our pricing"))
    assert response.tool_calls
    call = response.tool_calls[0]
    assert call.name == "router_classify"
    assert call.arguments["module"] == "pricing"


# ── RagResponderAgent ──────────────────────────────────────────────


def test_responder_requires_indexed_retriever():
    retriever = RagRetriever(embedder=HashEmbedder(dimension=64))
    with pytest.raises(ValueError, match="indexed"):
        RagResponderAgent(retriever, top_k=3)


def test_responder_emits_sources_and_trace():
    retriever = RagRetriever(embedder=HashEmbedder(dimension=256)).index_corpus(
        generate_synthetic_corpus()
    )
    responder = RagResponderAgent(retriever, top_k=3)
    response = responder.respond(
        Query(query_id="q", text="how long to hire a senior engineer")
    )
    assert len(response.sources) == 3
    assert all(c.rank == i for i, c in enumerate(response.sources))
    # Trace should mention the embedder name + chunk count
    trace_str = " ".join(response.reasoning_trace)
    assert "HashEmbedder" in trace_str
    assert "3 source" in trace_str
    # tokens_used must be positive
    assert response.tokens_used > 0


def test_responder_applies_module_filter_from_query():
    retriever = RagRetriever(embedder=HashEmbedder(dimension=256)).index_corpus(
        generate_synthetic_corpus()
    )
    responder = RagResponderAgent(retriever, top_k=3)
    response = responder.respond(
        Query(
            query_id="q",
            text="how to reduce emissions",
            include_modules=("sustainability",),
        )
    )
    assert all(c.document.module == "sustainability" for c in response.sources)


def test_responder_returns_no_sources_when_module_has_no_match():
    """When the module_filter rules out the entire corpus, the responder
    must surface the empty-state message without crashing."""
    retriever = RagRetriever(embedder=HashEmbedder(dimension=256)).index_corpus(
        generate_synthetic_corpus()
    )
    responder = RagResponderAgent(retriever, top_k=3, module_filter="nonexistent-module")
    response = responder.respond(Query(query_id="q", text="anything"))
    assert response.sources == ()
    assert "couldn't find" in response.content


# ── AgentExecutor (router + responder pipeline) ────────────────────


def test_executor_routes_recruitment_query_to_recruitment_module():
    executor = _executor()
    response = executor.respond(
        Query(query_id="q", text="how long does it take to hire a senior engineer?")
    )
    # All retrieved sources should be from the recruitment module
    # (because the router classifies "hire/engineer" as recruitment and
    # the responder applies the filter).
    assert response.sources
    assert all(c.document.module == "recruitment" for c in response.sources)


def test_executor_prepends_router_trace_step():
    executor = _executor()
    response = executor.respond(
        Query(query_id="q", text="what is price elasticity?")
    )
    # First reasoning step should be the router classification
    assert response.reasoning_trace[0].lower().startswith("router classified")
    assert "pricing" in response.reasoning_trace[0]


def test_executor_emits_both_router_and_rag_tool_calls():
    executor = _executor()
    response = executor.respond(
        Query(query_id="q", text="what is MAPE?")
    )
    names = [tc.name for tc in response.tool_calls]
    assert "router_classify" in names
    assert "rag_retrieve" in names


# ── ToolRegistry ────────────────────────────────────────────────────


def test_tool_registry_with_defaults_has_one_per_module():
    registry = ToolRegistry.with_defaults()
    names = set(registry.names())
    assert "fetch_latest_recruitment_session" in names
    assert "fetch_latest_pricing_recommendation" in names
    assert "fetch_latest_profit_forecast" in names
    assert "fetch_latest_esg_score" in names
    assert "fetch_cash_runway" in names


def test_tool_registry_dispatches_by_name():
    registry = ToolRegistry.with_defaults()
    tool = registry.get("fetch_latest_pricing_recommendation")
    result = tool.handler({})
    assert "stub" in result.lower()


def test_tool_registry_register_rejects_duplicate():
    registry = ToolRegistry.with_defaults()
    duplicate = registry.get("fetch_cash_runway")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(duplicate)


def test_tool_registry_for_module_filters():
    registry = ToolRegistry.with_defaults()
    pricing_tools = registry.for_module("pricing")
    assert len(pricing_tools) == 1
    assert pricing_tools[0].name == "fetch_latest_pricing_recommendation"
