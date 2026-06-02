"""
pgvector-backed candidate index — the production semantic-search path.

For each candidate we persist the SBERT embedding into a `candidate_vector`
table (created by Alembic migration) and run cosine-distance queries
through pgvector's HNSW index. This module is the *thin* SQL wrapper;
embedding management belongs to `embeddings.sbert`, and the calling code
(backend recruitment service) owns the SQLAlchemy session.

ADR-003 ratifies pgvector over a dedicated vector DB at SME scale.

Schema (target — Phase-3 Alembic migration):

    CREATE TABLE candidate_vector (
        candidate_id  UUID PRIMARY KEY,
        embedding     vector(768) NOT NULL,
        encoder_name  TEXT NOT NULL,
        updated_at    TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX candidate_vector_hnsw
        ON candidate_vector USING hnsw (embedding vector_cosine_ops);

The SQL strings here are the canonical statements consumed by the
backend's SQLAlchemy session — keeping them in this module guarantees
the index helper and the service can never drift.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

UPSERT_SQL = """
INSERT INTO candidate_vector (candidate_id, embedding, encoder_name)
VALUES (:candidate_id, :embedding, :encoder_name)
ON CONFLICT (candidate_id) DO UPDATE
   SET embedding    = EXCLUDED.embedding,
       encoder_name = EXCLUDED.encoder_name,
       updated_at   = NOW();
""".strip()

# pgvector's `<=>` is cosine *distance*; convert with (1 - distance) for cosine sim.
KNN_SQL = """
SELECT candidate_id,
       1 - (embedding <=> CAST(:query AS vector)) AS similarity
  FROM candidate_vector
 WHERE encoder_name = :encoder_name
 ORDER BY embedding <=> CAST(:query AS vector)
 LIMIT :k;
""".strip()


@dataclass(frozen=True)
class IndexedCandidate:
    candidate_id: str
    similarity: float


class CandidateVectorIndex:
    """SQL-driven facade — caller injects a session-like object exposing
    ``.execute(sql, params).fetchall()``. Keeps this module DB-driver agnostic."""

    def __init__(self, session: object, encoder_name: str) -> None:
        self._session = session
        self._encoder_name = encoder_name

    # ── writes ──────────────────────────────────────────────────────
    def upsert(self, candidate_id: str, embedding: np.ndarray) -> None:
        emb = np.asarray(embedding, dtype=np.float32).tolist()
        self._session.execute(  # type: ignore[attr-defined]
            UPSERT_SQL,
            {"candidate_id": candidate_id, "embedding": emb, "encoder_name": self._encoder_name},
        )

    # ── reads ───────────────────────────────────────────────────────
    def knn(self, query_embedding: np.ndarray, k: int = 50) -> list[IndexedCandidate]:
        emb = np.asarray(query_embedding, dtype=np.float32).tolist()
        rows = self._session.execute(  # type: ignore[attr-defined]
            KNN_SQL, {"query": emb, "encoder_name": self._encoder_name, "k": k}
        ).fetchall()
        return [IndexedCandidate(candidate_id=str(r[0]), similarity=float(r[1])) for r in rows]
