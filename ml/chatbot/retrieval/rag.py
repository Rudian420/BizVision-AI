"""
RAG retriever — bundles an `EmbeddingClient` + `VectorStore` into a
single seam the agents call.

Two-stage pipeline (Lewis et al. 2020 §2.1):
  1. embed the query → unit-norm vector
  2. cosine-search the store for top-k chunks

`build_context` concatenates the top-k chunk texts into a single
prompt-ready string with stable delimiters — the format the
`RagResponderAgent` and the LLM-backed copilot expect.
"""

from __future__ import annotations

from collections.abc import Iterable

from ml.chatbot.data.schema import Corpus, Document, Query, RetrievedChunk
from ml.chatbot.embeddings.base import EmbeddingClient
from ml.chatbot.retrieval.vector_store import NumpyVectorStore, VectorStore


class RagRetriever:
    """Embed-then-search retrieval pipeline."""

    def __init__(
        self,
        *,
        embedder: EmbeddingClient,
        store: VectorStore | None = None,
    ) -> None:
        self._embedder = embedder
        self._store: VectorStore = store or NumpyVectorStore()
        self._indexed = False

    @property
    def name(self) -> str:
        return f"Rag({self._embedder.name})"

    @property
    def embedder(self) -> EmbeddingClient:
        return self._embedder

    @property
    def store(self) -> VectorStore:
        return self._store

    @property
    def is_indexed(self) -> bool:
        return self._indexed

    # ── indexing ─────────────────────────────────────────────────────
    def index_corpus(self, corpus: Corpus) -> RagRetriever:
        """Embed and index every document in `corpus`. Returns self."""
        if not corpus.documents:
            self._indexed = True
            return self
        texts = [self._document_text(d) for d in corpus.documents]
        embeddings = self._embedder.embed_batch(texts)
        self._store.add(corpus.documents, embeddings)
        self._indexed = True
        return self

    # ── retrieval ────────────────────────────────────────────────────
    def retrieve(
        self,
        query: Query | str,
        *,
        top_k: int = 5,
        module_filter: str | None = None,
    ) -> tuple[RetrievedChunk, ...]:
        """Return the top-k chunks for a query.

        Accepts either a string or a structured `Query`. The structured
        form lets the caller request a `module_filter` via
        `query.include_modules` (first module wins; explicit
        `module_filter` arg overrides).
        """
        if isinstance(query, str):
            text = query
        else:
            text = query.text
            if module_filter is None and query.include_modules:
                module_filter = query.include_modules[0]
        if top_k <= 0:
            raise ValueError("top_k must be > 0")
        query_vec = self._embedder.embed(text)
        return self._store.search(query_vec, top_k=top_k, module_filter=module_filter)

    # ── context windowing ───────────────────────────────────────────
    def build_context(
        self,
        chunks: Iterable[RetrievedChunk],
        *,
        max_chars: int = 4000,
    ) -> str:
        """Concatenate chunk texts into a prompt-ready context block.

        Format:
            [#1 doc_id: title]
            content

            [#2 doc_id: title]
            content
            …

        Truncates at `max_chars` *between chunks* (never mid-chunk),
        so the LLM never sees a partial sentence — easier to evaluate
        faithfulness downstream.
        """
        parts: list[str] = []
        total = 0
        for chunk in chunks:
            block = (
                f"[#{chunk.rank + 1} {chunk.document.doc_id}: "
                f"{chunk.document.title}]\n{chunk.document.content}"
            )
            block_len = len(block) + 2  # +2 for the blank-line separator
            if total + block_len > max_chars and parts:
                break
            parts.append(block)
            total += block_len
        return "\n\n".join(parts)

    @staticmethod
    def _document_text(d: Document) -> str:
        """Index-time text composition. Title is duplicated to give it
        more weight under bag-of-words hashing (the standard trick from
        BM25 field weighting)."""
        return f"{d.title}. {d.title}. {d.content}"
