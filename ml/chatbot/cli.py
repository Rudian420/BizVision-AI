"""
Chatbot CLI — `train` / `ablate` / `benchmark` / `chat` subcommands.

Mirrors `ml.sustainability.cli` and the other module CLIs:

    python -m ml.chatbot.cli train
    python -m ml.chatbot.cli ablate
    python -m ml.chatbot.cli benchmark --arm RouterPlusRag
    python -m ml.chatbot.cli chat --text "How long to hire an engineer?"
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from ml.chatbot.agents.executor import AgentExecutor
from ml.chatbot.agents.rag_responder import RagResponderAgent
from ml.chatbot.agents.router import KeywordRouterAgent
from ml.chatbot.data.loader import generate_golden_queries, generate_synthetic_corpus
from ml.chatbot.data.schema import Query
from ml.chatbot.embeddings.hash_embedder import HashEmbedder
from ml.chatbot.evaluation.benchmark import (
    benchmark_executor,
    benchmark_retriever,
)
from ml.chatbot.retrieval.rag import RagRetriever
from ml.chatbot.training.ablation import run as ablation_run
from ml.chatbot.training.config import TrainConfig
from ml.chatbot.training.pipeline import train as train_run


def _build_retriever(dim: int):
    embedder = HashEmbedder(dimension=dim)
    return RagRetriever(embedder=embedder).index_corpus(generate_synthetic_corpus())


def _cmd_train(args: argparse.Namespace) -> int:
    cfg = TrainConfig(embedding_dim=args.dim, seed=args.seed)
    print(json.dumps(train_run(cfg), default=str, indent=2))
    return 0


def _cmd_ablate(args: argparse.Namespace) -> int:
    cfg = TrainConfig(embedding_dim=args.dim, seed=args.seed)
    seeds = tuple(int(s) for s in args.seeds.split(","))
    results = ablation_run(cfg, seeds=seeds)
    summary = {arm: [asdict(r) for r in runs] for arm, runs in results.items()}
    print(json.dumps(summary, default=str, indent=2))
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    retriever = _build_retriever(args.dim)
    golden = generate_golden_queries()
    if args.arm == "RagOnly":
        result = benchmark_retriever(retriever, golden)
    else:  # "RouterPlusRag"
        router = KeywordRouterAgent()
        responder = RagResponderAgent(retriever, top_k=args.top_k)
        executor = AgentExecutor(router=router, responder=responder)
        result = benchmark_executor(executor, golden)
    print(json.dumps(asdict(result), default=str, indent=2))
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    retriever = _build_retriever(args.dim)
    router = KeywordRouterAgent()
    responder = RagResponderAgent(retriever, top_k=args.top_k)
    executor = AgentExecutor(router=router, responder=responder)
    query = Query(query_id="cli", text=args.text)
    response = executor.respond(query)
    print(json.dumps(
        {
            "content": response.content,
            "reasoning_trace": list(response.reasoning_trace),
            "sources": [
                {
                    "doc_id": c.document.doc_id,
                    "title": c.document.title,
                    "module": c.document.module,
                    "rank": c.rank,
                    "score": round(c.score, 4),
                }
                for c in response.sources
            ],
            "tool_calls": [
                {"name": tc.name, "arguments": dict(tc.arguments), "status": tc.status}
                for tc in response.tool_calls
            ],
            "tokens_used": response.tokens_used,
            "agent_name": response.agent_name,
        },
        indent=2,
    ))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ml.chatbot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    train_p = sub.add_parser("train", help="Train the recommended executor")
    train_p.add_argument("--dim", type=int, default=256)
    train_p.add_argument("--seed", type=int, default=42)
    train_p.set_defaults(func=_cmd_train)

    ablate_p = sub.add_parser("ablate", help="Run the AS-005 ablation campaign")
    ablate_p.add_argument("--dim", type=int, default=256)
    ablate_p.add_argument("--seed", type=int, default=42)
    ablate_p.add_argument("--seeds", default="42,1337,31337")
    ablate_p.set_defaults(func=_cmd_ablate)

    bench_p = sub.add_parser("benchmark", help="Benchmark a single arm")
    bench_p.add_argument(
        "--arm", choices=["RagOnly", "RouterPlusRag"], required=True
    )
    bench_p.add_argument("--dim", type=int, default=256)
    bench_p.add_argument("--top-k", type=int, default=5)
    bench_p.set_defaults(func=_cmd_benchmark)

    chat_p = sub.add_parser("chat", help="Run one query through the executor")
    chat_p.add_argument("--text", required=True)
    chat_p.add_argument("--dim", type=int, default=256)
    chat_p.add_argument("--top-k", type=int, default=5)
    chat_p.set_defaults(func=_cmd_chat)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
