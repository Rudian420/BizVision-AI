"""
AS-005 benchmark harness — scores a retriever or executor on the
golden query set.

Two modes:
  • `benchmark_retriever(rag)` — measures retrieval quality directly
    (Recall@k, Precision@k, MRR, NDCG@k). The router is not exercised.
  • `benchmark_executor(executor)` — measures *end-to-end* quality:
    the router's classification + the responder's retrieval, plus
    routing accuracy against the golden set's `expected_module`.

The harness treats every retriever / executor the same — it only
calls the relevant ABCs (`RagRetriever` / `BaseAgent`), so the
AS-005 ablation can swap arms uniformly. Same posture as the other
benchmark harnesses (AS-002 / AS-003 / AS-004).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ml.chatbot.agents.executor import AgentExecutor
from ml.chatbot.data.schema import GoldenExample
from ml.chatbot.evaluation.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    routing_accuracy,
)
from ml.chatbot.retrieval.rag import RagRetriever


@dataclass(frozen=True)
class RetrievalResult:
    """Aggregated cross-query retrieval metrics."""

    name: str
    n_queries: int
    recall_at_3: float
    recall_at_5: float
    precision_at_3: float
    mrr: float
    ndcg_at_5: float


@dataclass(frozen=True)
class ExecutorResult:
    """Retrieval metrics + routing accuracy for an end-to-end executor."""

    name: str
    n_queries: int
    recall_at_3: float
    recall_at_5: float
    precision_at_3: float
    mrr: float
    ndcg_at_5: float
    routing_accuracy: float


def _retrieve_doc_ids(rag: RagRetriever, query, top_k: int) -> list[str]:
    chunks = rag.retrieve(query, top_k=top_k)
    return [c.document.doc_id for c in chunks]


def benchmark_retriever(
    retriever: RagRetriever, golden: Sequence[GoldenExample]
) -> RetrievalResult:
    """Score a retriever on the golden query set."""
    if not retriever.is_indexed:
        raise ValueError("retriever must be indexed before benchmarking")

    retrieved_lists: list[list[str]] = []
    relevant_lists: list[tuple[str, ...]] = []
    rec3, rec5, prec3, ndcg5 = [], [], [], []
    for example in golden:
        # Query without module filter — measures raw retrieval quality.
        chunks = retriever.retrieve(example.query.text, top_k=5)
        ids = [c.document.doc_id for c in chunks]
        retrieved_lists.append(ids)
        relevant_lists.append(example.relevant_doc_ids)
        rec3.append(recall_at_k(ids, example.relevant_doc_ids, k=3))
        rec5.append(recall_at_k(ids, example.relevant_doc_ids, k=5))
        prec3.append(precision_at_k(ids, example.relevant_doc_ids, k=3))
        ndcg5.append(ndcg_at_k(ids, example.relevant_doc_ids, k=5))

    return RetrievalResult(
        name=retriever.name,
        n_queries=len(golden),
        recall_at_3=float(np.mean(rec3)) if rec3 else 0.0,
        recall_at_5=float(np.mean(rec5)) if rec5 else 0.0,
        precision_at_3=float(np.mean(prec3)) if prec3 else 0.0,
        mrr=mean_reciprocal_rank(retrieved_lists, relevant_lists),
        ndcg_at_5=float(np.mean(ndcg5)) if ndcg5 else 0.0,
    )


def benchmark_executor(
    executor: AgentExecutor, golden: Sequence[GoldenExample]
) -> ExecutorResult:
    """Score an end-to-end executor (router + retriever + responder)."""
    retrieved_lists: list[list[str]] = []
    relevant_lists: list[tuple[str, ...]] = []
    predicted_modules: list[str] = []
    expected_modules: list[str] = []
    rec3, rec5, prec3, ndcg5 = [], [], [], []
    for example in golden:
        response = executor.respond(example.query)
        ids = [c.document.doc_id for c in response.sources]
        retrieved_lists.append(ids)
        relevant_lists.append(example.relevant_doc_ids)
        expected_modules.append(example.expected_module)
        # Pull the predicted module out of the router's tool_call args.
        router_call = next(
            (tc for tc in response.tool_calls if tc.name == "router_classify"),
            None,
        )
        predicted_modules.append(
            router_call.arguments.get("module", "general")
            if router_call is not None
            else "general"
        )
        rec3.append(recall_at_k(ids, example.relevant_doc_ids, k=3))
        rec5.append(recall_at_k(ids, example.relevant_doc_ids, k=5))
        prec3.append(precision_at_k(ids, example.relevant_doc_ids, k=3))
        ndcg5.append(ndcg_at_k(ids, example.relevant_doc_ids, k=5))

    return ExecutorResult(
        name=executor.name,
        n_queries=len(golden),
        recall_at_3=float(np.mean(rec3)) if rec3 else 0.0,
        recall_at_5=float(np.mean(rec5)) if rec5 else 0.0,
        precision_at_3=float(np.mean(prec3)) if prec3 else 0.0,
        mrr=mean_reciprocal_rank(retrieved_lists, relevant_lists),
        ndcg_at_5=float(np.mean(ndcg5)) if ndcg5 else 0.0,
        routing_accuracy=routing_accuracy(predicted_modules, expected_modules),
    )
