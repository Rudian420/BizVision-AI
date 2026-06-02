"""Chatbot training config — frozen dataclass, JSON-round-trippable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainConfig:
    """Knobs for `pipeline.train` and `ablation.run`.

    Identical posture to `ml.sustainability.training.config.TrainConfig`:
    a frozen dataclass that the CLI deserialises from CLI flags or a
    YAML file. Defaults are tuned for the synthetic 100-doc / 25-query
    fixture from `data.loader.generate_synthetic_corpus` and
    `generate_golden_queries`.
    """

    embedding_dim: int = 256
    top_k: int = 5
    apply_router: bool = True
    seed: int = 42
    arms: tuple[str, ...] = (
        "RagOnly",
        "RouterPlusRag",
    )
    mlflow_experiment: str = "bizvision.chatbot"
