"""
Chatbot training pipeline.

Mirrors the other modules' `training.pipeline.train`. Steps:

  1. seed → build the corpus + golden set
  2. index the corpus with the `HashEmbedder`
  3. run the executor on every golden query
  4. log retrieval metrics + routing accuracy to MLflow

The wave-1 "training" is mostly about *evaluating* on the golden set
— there are no learned parameters in `HashEmbedder` or
`KeywordRouterAgent`. Wave 2 (SBERT + learned router) will turn this
into a real training pipeline behind the same entry point.

`python -m ml.chatbot.training.pipeline` runs it once with defaults.
"""

from __future__ import annotations

from dataclasses import asdict

from ml.chatbot.agents.executor import AgentExecutor
from ml.chatbot.agents.rag_responder import RagResponderAgent
from ml.chatbot.agents.router import KeywordRouterAgent
from ml.chatbot.data.loader import generate_golden_queries, generate_synthetic_corpus
from ml.chatbot.embeddings.hash_embedder import HashEmbedder
from ml.chatbot.evaluation.benchmark import benchmark_executor
from ml.chatbot.reproducibility import capture_env_snapshot, seed_everything
from ml.chatbot.retrieval.rag import RagRetriever
from ml.chatbot.training.config import TrainConfig


def train(config: TrainConfig | None = None) -> dict:
    """Train (evaluate) the recommended executor and return its metrics."""
    cfg = config or TrainConfig()
    seed_everything(cfg.seed)

    corpus = generate_synthetic_corpus()
    golden = generate_golden_queries()

    embedder = HashEmbedder(dimension=cfg.embedding_dim)
    retriever = RagRetriever(embedder=embedder).index_corpus(corpus)
    router = KeywordRouterAgent()
    responder = RagResponderAgent(retriever, top_k=cfg.top_k)
    executor = AgentExecutor(router=router, responder=responder)

    result = benchmark_executor(executor, golden)
    metrics: dict[str, float] = {
        "recall_at_3": result.recall_at_3,
        "recall_at_5": result.recall_at_5,
        "precision_at_3": result.precision_at_3,
        "mrr": result.mrr,
        "ndcg_at_5": result.ndcg_at_5,
        "routing_accuracy": result.routing_accuracy,
    }

    # MLflow logging — optional; skipped if mlflow isn't installed.
    try:  # pragma: no cover - optional dep
        import mlflow

        mlflow.set_experiment(cfg.mlflow_experiment)
        with mlflow.start_run(run_name=f"{executor.name}-baseline"):
            mlflow.log_params(asdict(cfg))
            mlflow.log_params(capture_env_snapshot())
            mlflow.log_metrics(metrics)
    except ImportError:
        pass

    return {
        "executor": executor.name,
        "metrics": metrics,
        "config": asdict(cfg),
    }


if __name__ == "__main__":  # pragma: no cover
    out = train()
    print(out)
