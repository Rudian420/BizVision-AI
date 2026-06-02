"""
Offline unit tests for the chatbot embeddings.

Verifies the `HashEmbedder` contract: deterministic, unit-norm,
similar-text-yields-similar-embeddings.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.chatbot.embeddings.hash_embedder import HashEmbedder


def test_embedding_is_unit_norm():
    embedder = HashEmbedder(dimension=128)
    vec = embedder.embed("How long does it take to hire a senior engineer?")
    assert np.linalg.norm(vec) == pytest.approx(1.0)


def test_embedding_is_deterministic_across_calls():
    embedder = HashEmbedder(dimension=128)
    v1 = embedder.embed("price elasticity of demand")
    v2 = embedder.embed("price elasticity of demand")
    assert np.allclose(v1, v2)


def test_embedding_dim_matches_constructor():
    embedder = HashEmbedder(dimension=512)
    assert embedder.dimension == 512
    assert embedder.embed("anything").shape == (512,)


def test_embedding_zero_for_empty_text():
    embedder = HashEmbedder(dimension=64)
    assert np.allclose(embedder.embed(""), np.zeros(64))


def test_embedding_zero_for_stopwords_only():
    """Pure stopwords → all tokens filtered → zero vector."""
    embedder = HashEmbedder(dimension=64)
    assert np.allclose(embedder.embed("the and or but"), np.zeros(64))


def test_similar_text_has_higher_cosine_than_dissimilar():
    """Cosine similarity between paraphrases should beat unrelated text."""
    embedder = HashEmbedder(dimension=256)
    base = embedder.embed("how long does it take to hire a senior software engineer")
    paraphrase = embedder.embed("how long does it take to hire a senior engineer")
    unrelated = embedder.embed("scope 3 carbon emissions supply chain")
    assert float(base @ paraphrase) > float(base @ unrelated)


def test_embed_batch_stacks_rows():
    embedder = HashEmbedder(dimension=64)
    batch = embedder.embed_batch(["one query", "another query"])
    assert batch.shape == (2, 64)


def test_embed_batch_empty_returns_zero_shaped_matrix():
    embedder = HashEmbedder(dimension=64)
    batch = embedder.embed_batch([])
    assert batch.shape == (0, 64)


def test_embedder_rejects_invalid_dimension():
    with pytest.raises(ValueError):
        HashEmbedder(dimension=0)
