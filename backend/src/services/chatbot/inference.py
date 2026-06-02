"""
Chatbot ML Inference Client.

Wraps `ml.chatbot` for the backend — the chatbot analogue of
`SustainabilityInferenceClient` (TASK-018) and `PricingInferenceClient`
(ADR-024). Owns the lifecycle of the indexed RAG retriever + agent
executor:

    1. **Singleton cache** — one client per worker process; instantiated
       lazily on first call so an idle backend never imports
       `ml.chatbot` and its numpy chain.
    2. **MLflow Model Registry** — preferred source of a registered
       agent executor, loaded from the `chatbot-agent-executor`
       Production stage when present.
    3. **Synthetic-corpus bootstrap** — if no registered model exists,
       build a default executor (`HashEmbedder` → `NumpyVectorStore`
       indexed with `generate_synthetic_corpus()` → `KeywordRouterAgent`
       → `RagResponderAgent` → `AgentExecutor`). Logged loudly so
       operators can't miss the fallback.

The `ml.chatbot` import (with its numpy chain) happens **inside**
`_load_executor` — when `CHATBOT_USE_REAL_ML` is off, this module
imports cleanly. The translation layer (`ml_translation.py`) is
pure-Python and *never* touches a heavy import, so unit tests for
translation run in the backend's lean dev venv.

Endpoints handled:
  • `respond(content, ...)` →  `/chatbot/message` REST
                            +  WebSocket `stream_response`

`/executive-report` stays closed-form / static-catalog in wave 1 —
same posture as pricing's `/elasticity` and sustainability's
`/benchmarks/{industry}`. The chatbot service applies it inline
rather than routing through this client.

Unlike forecasting (per-request fit) and sustainability (per-process
fitted scorer), the chatbot client holds an **indexed RAG retriever**
across requests — the corpus is server-side state, not part of the
request payload. Each `respond` call dispatches a fresh query through
the same indexed corpus.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.core.logging import get_logger
from src.services.chatbot.ml_translation import (
    api_query_from_ws_payload,
)

if TYPE_CHECKING:
    from ml.chatbot.agents.base import BaseAgent
    from ml.chatbot.data.schema import AgentResponse as MLAgentResponse
    from ml.chatbot.data.schema import Query as MLQuery

logger = get_logger(__name__)


class ChatbotInferenceClient:
    """Thread-safe lazy holder for the chatbot agent executor.

    Construction is cheap — heavy imports + corpus indexing happen on
    the first call to `respond`. The `_lock` makes first-call init
    safe under FastAPI's threadpool concurrency.
    """

    def __init__(
        self,
        *,
        executor: BaseAgent | None = None,
    ) -> None:
        # Injection seam for tests; production leaves it None.
        self._executor: BaseAgent | None = executor
        self._lock = threading.Lock()
        self._source: str = "uninitialised"

    @property
    def source(self) -> str:
        """`mlflow:v3` / `synthetic-bootstrap` / `injected` / `uninitialised`."""
        return self._source

    # ── public API ──────────────────────────────────────────────────
    def respond(
        self,
        content: str,
        *,
        include_modules: tuple[str, ...] | list[str] | None = None,
        user_id: UUID | None = None,
        query_id: str | None = None,
    ) -> MLAgentResponse:
        """Run a query through the indexed executor.

        Accepts a raw `content` string so both the REST and WS paths
        can call this without first building a Pydantic request model
        — the WS handler doesn't carry one. The translation layer
        wraps the result into the API shape downstream.
        """
        executor = self._get_executor()
        query: MLQuery = api_query_from_ws_payload(
            content=content,
            include_modules=include_modules,
            user_id=user_id,
            query_id=query_id,
        )
        return executor.respond(query)

    def respond_to_query(self, query: MLQuery) -> MLAgentResponse:
        """Convenience overload — dispatches a pre-built `Query`."""
        return self._get_executor().respond(query)

    # ── internals ────────────────────────────────────────────────────
    def _get_executor(self) -> BaseAgent:
        if self._executor is not None:
            return self._executor
        with self._lock:
            if self._executor is None:
                self._executor, self._source = self._load_executor()
                logger.info("Chatbot executor initialised from {}", self._source)
        return self._executor

    def _load_executor(self) -> tuple[BaseAgent, str]:
        """Choose an executor source in priority order. The `ml.chatbot`
        imports live here so the backend stays importable without numpy."""
        try:
            # Ensure the ml.chatbot tree is importable before we try
            # anything — a missing numpy dep here is the operator's
            # signal to enable the ml-dev image.
            from ml.chatbot.data.loader import generate_synthetic_corpus  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "CHATBOT_USE_REAL_ML=True but `ml.chatbot` is not importable. "
                "Install ml/requirements.txt or run the backend inside the ml-dev container."
            ) from exc

        # ── 1. MLflow Production model, if present ────────────────
        registry_executor = _load_from_registry()
        if registry_executor is not None:
            executor, version = registry_executor
            return executor, f"mlflow:{version}"

        # ── 2. Synthetic-corpus bootstrap ─────────────────────────
        logger.warning(
            "No Production `chatbot-agent-executor` in MLflow — "
            "bootstrapping HashEmbedder + KeywordRouter + RagResponder "
            "on the synthetic 100-doc corpus. Replace via "
            "`python -m ml.chatbot.cli train`."
        )
        from ml.chatbot.agents.executor import AgentExecutor
        from ml.chatbot.agents.rag_responder import RagResponderAgent
        from ml.chatbot.agents.router import KeywordRouterAgent
        from ml.chatbot.data.loader import generate_synthetic_corpus
        from ml.chatbot.embeddings.hash_embedder import HashEmbedder
        from ml.chatbot.retrieval.rag import RagRetriever

        embedder = HashEmbedder(dimension=256)
        retriever = RagRetriever(embedder=embedder).index_corpus(
            generate_synthetic_corpus()
        )
        router = KeywordRouterAgent()
        responder = RagResponderAgent(retriever, top_k=3)
        executor = AgentExecutor(router=router, responder=responder)
        return executor, "synthetic-bootstrap"


# ── module-level helpers (importable by tests) ──────────────────────


def _load_from_registry() -> tuple[Any, str] | None:
    """Try MLflow Model Registry; swallow errors so a missing tracking
    server falls back to the synthetic bootstrap rather than crashing."""
    try:
        from ml.chatbot.registry.model_registry import latest_production

        version = latest_production()
        if version is None:
            return None
        import mlflow.pyfunc

        loaded = mlflow.pyfunc.load_model(version.source)
        return loaded, str(version.version)
    except Exception as exc:  # pragma: no cover - depends on live MLflow
        logger.info("MLflow Model Registry unavailable ({}); using bootstrap.", exc)
        return None


# ── Module-level singleton ──────────────────────────────────────────


_client_singleton: ChatbotInferenceClient | None = None
_singleton_lock = threading.Lock()


def get_inference_client() -> ChatbotInferenceClient:
    """Return the process-wide chatbot inference client."""
    global _client_singleton
    if _client_singleton is None:
        with _singleton_lock:
            if _client_singleton is None:
                _client_singleton = ChatbotInferenceClient()
    return _client_singleton


def reset_inference_client(client: ChatbotInferenceClient | None = None) -> None:
    """Replace the singleton — testing seam only. Pass `None` to clear."""
    global _client_singleton
    with _singleton_lock:
        _client_singleton = client
