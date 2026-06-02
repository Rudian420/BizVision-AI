"""
BizVision AI — ML Model Registry

Central in-memory registry of loaded ML models, warmed once on
application startup to avoid cold-start latency on the first request
(see RISK-003 in bugs-and-issues.md).

NOTE: Phase 1 scaffold. The real model loaders (SBERT, XGBoost,
LightGBM, Prophet/LSTM ensemble, ESG classifier) are wired in Phase 3.
For now ``initialize`` registers lightweight placeholder handles so the
inference services and ``/ready`` checks have something to reference.
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.core.logging import get_logger

logger = get_logger(__name__)

# Models expected by each module — used both for warm-up reporting and
# by the typed-mock services to stamp a model_version.
_EXPECTED_MODELS: dict[str, str] = {
    "recruitment": "sbert+xgboost-ensemble",
    "pricing": "lightgbm+ppo",
    "forecasting": "prophet+lstm+xgboost",
    "sustainability": "esg-multilabel",
    "chatbot": "langgraph-rag",
}


class ModelRegistry:
    """Process-wide singleton registry of warmed models."""

    _models: ClassVar[dict[str, Any]] = {}
    _ready: bool = False

    @classmethod
    async def initialize(cls) -> None:
        """Warm all module models. Idempotent; safe on every startup."""
        if cls._ready:
            return
        for module, model_name in _EXPECTED_MODELS.items():
            # Phase 3 will replace this with real model loading.
            cls._models[module] = {"name": model_name, "status": "placeholder"}
            logger.info("Registered model placeholder: {} -> {}", module, model_name)
        cls._ready = True

    @classmethod
    def get(cls, module: str) -> Any | None:
        return cls._models.get(module)

    @classmethod
    def version(cls, module: str) -> str:
        model = cls._models.get(module)
        return model["name"] if model else "uninitialised"

    @classmethod
    def status(cls) -> dict[str, Any]:
        return {
            "ready": cls._ready,
            "loaded": list(cls._models.keys()),
            "expected": list(_EXPECTED_MODELS.keys()),
        }
