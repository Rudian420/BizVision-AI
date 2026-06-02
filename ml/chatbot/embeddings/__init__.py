"""Chatbot embeddings — uniform interface + hash-based baseline + lazy SBERT."""

from ml.chatbot.embeddings.base import EmbeddingClient
from ml.chatbot.embeddings.hash_embedder import HashEmbedder

__all__ = ["EmbeddingClient", "HashEmbedder"]
