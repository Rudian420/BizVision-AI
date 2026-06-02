"""
Offline unit tests for chatbot retrieval (vector store + RAG retriever).
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.chatbot.data.schema import Corpus, Document, Query
from ml.chatbot.embeddings.hash_embedder import HashEmbedder
from ml.chatbot.retrieval.rag import RagRetriever
from ml.chatbot.retrieval.vector_store import NumpyVectorStore


def _toy_corpus() -> Corpus:
    return Corpus(
        documents=(
            Document(doc_id="r-1", title="Hiring", content="recruit engineer hire", module="recruitment"),
            Document(doc_id="p-1", title="Pricing", content="price elasticity demand", module="pricing"),
            Document(doc_id="f-1", title="Forecasting", content="forecast time series", module="forecasting"),
        )
    )


# ── NumpyVectorStore ───────────────────────────────────────────────


def test_vector_store_search_returns_ordered_top_k():
    store = NumpyVectorStore()
    docs = (
        Document(doc_id="a", title="a", content="a"),
        Document(doc_id="b", title="b", content="b"),
        Document(doc_id="c", title="c", content="c"),
    )
    # Pre-computed embeddings, manually unit-normed.
    e = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.8, 0.6, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    store.add(docs, e)
    # Query = [1, 0, 0] — `a` should be first, `b` second, `c` last.
    out = store.search(np.array([1.0, 0.0, 0.0]), top_k=3)
    assert [c.document.doc_id for c in out] == ["a", "b", "c"]
    assert out[0].rank == 0
    assert out[1].rank == 1


def test_vector_store_module_filter_excludes_other_modules():
    embedder = HashEmbedder(dimension=64)
    corpus = _toy_corpus()
    retriever = RagRetriever(embedder=embedder).index_corpus(corpus)
    chunks = retriever.retrieve("recruit engineer", top_k=3, module_filter="recruitment")
    assert all(c.document.module == "recruitment" for c in chunks)


def test_vector_store_rejects_dim_mismatch_on_add():
    store = NumpyVectorStore()
    store.add(
        (Document(doc_id="a", title="t", content="c"),),
        np.array([[1.0, 0.0]]),
    )
    with pytest.raises(ValueError, match="dim mismatch"):
        store.add(
            (Document(doc_id="b", title="t", content="c"),),
            np.array([[1.0, 0.0, 0.0]]),
        )


def test_vector_store_rejects_count_mismatch():
    store = NumpyVectorStore()
    with pytest.raises(ValueError, match="count mismatch"):
        store.add(
            (Document(doc_id="a", title="t", content="c"),),
            np.array([[1.0, 0.0], [0.0, 1.0]]),  # 2 embeddings for 1 doc
        )


def test_vector_store_search_top_k_must_be_positive():
    store = NumpyVectorStore()
    store.add(
        (Document(doc_id="a", title="t", content="c"),),
        np.array([[1.0]]),
    )
    with pytest.raises(ValueError, match="top_k"):
        store.search(np.array([1.0]), top_k=0)


def test_vector_store_empty_search_returns_empty_tuple():
    store = NumpyVectorStore()
    assert store.search(np.array([1.0, 0.0]), top_k=5) == ()


# ── RagRetriever ───────────────────────────────────────────────────


def test_retriever_index_corpus_makes_it_searchable():
    embedder = HashEmbedder(dimension=128)
    corpus = _toy_corpus()
    retriever = RagRetriever(embedder=embedder)
    assert not retriever.is_indexed
    retriever.index_corpus(corpus)
    assert retriever.is_indexed
    out = retriever.retrieve("hire engineer recruit", top_k=2)
    assert len(out) == 2
    # The recruitment document should rank first.
    assert out[0].document.doc_id == "r-1"


def test_retriever_accepts_string_or_query():
    embedder = HashEmbedder(dimension=128)
    retriever = RagRetriever(embedder=embedder).index_corpus(_toy_corpus())
    out_str = retriever.retrieve("price elasticity", top_k=3)
    out_query = retriever.retrieve(
        Query(query_id="q", text="price elasticity"), top_k=3
    )
    assert [c.document.doc_id for c in out_str] == [c.document.doc_id for c in out_query]


def test_retriever_query_with_include_modules_filters():
    embedder = HashEmbedder(dimension=128)
    retriever = RagRetriever(embedder=embedder).index_corpus(_toy_corpus())
    out = retriever.retrieve(
        Query(query_id="q", text="anything", include_modules=("recruitment",)),
        top_k=3,
    )
    assert all(c.document.module == "recruitment" for c in out)


def test_retriever_build_context_truncates_at_max_chars():
    embedder = HashEmbedder(dimension=64)
    retriever = RagRetriever(embedder=embedder).index_corpus(_toy_corpus())
    chunks = retriever.retrieve("anything", top_k=3)
    short_context = retriever.build_context(chunks, max_chars=80)
    # At max 80 chars we can fit at most one block (rough envelope check).
    assert len(short_context) <= 200


def test_retriever_empty_corpus_returns_empty():
    embedder = HashEmbedder(dimension=64)
    retriever = RagRetriever(embedder=embedder).index_corpus(
        Corpus(documents=())
    )
    assert retriever.retrieve("anything", top_k=3) == ()
