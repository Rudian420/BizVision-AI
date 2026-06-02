"""
AS-005 ablation runner.

Scores every named arm on the same corpus + golden set + seeds,
returns a result per arm. Matches AS-001..004 — single source of
truth for *the* chatbot ablation experiment that fills
`ml-experiments.md` EXP-BOT-001..003.

Wave-1 arm catalog (kept stable for thesis reproducibility):
    RagOnly         — retriever without module routing (raw retrieval)
    RouterPlusRag   — keyword router → module-filtered retriever
                      (the recommended Phase-3 wave-1 executor)
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from ml.chatbot.agents.executor import AgentExecutor
from ml.chatbot.agents.rag_responder import RagResponderAgent
from ml.chatbot.agents.router import KeywordRouterAgent
from ml.chatbot.data.loader import generate_golden_queries, generate_synthetic_corpus
from ml.chatbot.embeddings.hash_embedder import HashEmbedder
from ml.chatbot.evaluation.benchmark import (
    benchmark_executor,
    benchmark_retriever,
)
from ml.chatbot.reproducibility import seed_everything
from ml.chatbot.retrieval.rag import RagRetriever
from ml.chatbot.training.config import TrainConfig


def run(
    config: TrainConfig | None = None,
    seeds: tuple[int, ...] = (42, 1337, 31337),
) -> dict[str, list]:
    """Run every arm × every seed. Returns name → list of results."""
    cfg = config or TrainConfig()
    results: dict[str, list] = {arm: [] for arm in cfg.arms}

    for seed in seeds:
        seed_everything(seed)
        corpus = generate_synthetic_corpus()
        golden = generate_golden_queries()
        embedder = HashEmbedder(dimension=cfg.embedding_dim)
        retriever = RagRetriever(embedder=embedder).index_corpus(corpus)

        for arm in cfg.arms:
            if arm == "RagOnly":
                arm_result = benchmark_retriever(retriever, golden)
            elif arm == "RouterPlusRag":
                router = KeywordRouterAgent()
                responder = RagResponderAgent(retriever, top_k=cfg.top_k)
                executor = AgentExecutor(router=router, responder=responder)
                arm_result = benchmark_executor(executor, golden)
            else:
                raise ValueError(f"unknown chatbot arm: {arm!r}")
            results[arm].append(arm_result)

    try:  # pragma: no cover - optional dep
        import mlflow

        mlflow.set_experiment(cfg.mlflow_experiment)
        for arm, runs in results.items():
            with mlflow.start_run(run_name=f"ablation-{arm}"):
                mlflow.log_params({**asdict(cfg), "arm": arm, "n_seeds": len(seeds)})
                mlflow.log_metrics(
                    {
                        "recall_at_3_mean": float(np.mean([r.recall_at_3 for r in runs])),
                        "recall_at_5_mean": float(np.mean([r.recall_at_5 for r in runs])),
                        "precision_at_3_mean": float(
                            np.mean([r.precision_at_3 for r in runs])
                        ),
                        "mrr_mean": float(np.mean([r.mrr for r in runs])),
                        "ndcg_at_5_mean": float(np.mean([r.ndcg_at_5 for r in runs])),
                    }
                )
    except ImportError:
        pass

    return results
