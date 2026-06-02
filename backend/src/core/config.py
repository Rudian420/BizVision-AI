"""
BizVision AI — Application Configuration

Pydantic Settings v2 — environment variables are automatically
loaded from .env file and validated with type safety.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ─── Application ───────────────────────────────────────
    ENVIRONMENT: str = "development"
    APP_NAME: str = "BizVision AI"
    APP_VERSION: str = "1.0.0"

    # ─── API Security ──────────────────────────────────────
    ENABLE_DOCS: bool = True
    ENABLE_RATE_LIMITING: bool = True
    ENABLE_CORS: bool = True

    # ─── CORS ──────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://bizvision-ai.vercel.app",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ─── Database ──────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://bizvision:bizvision123@localhost:5432/bizvision"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # ─── Redis ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ─── JWT ───────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── Storage ───────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET_MODELS: str = "model-artifacts"
    MINIO_BUCKET_DATA: str = "training-data"
    MINIO_BUCKET_REPORTS: str = "generated-reports"
    MINIO_SECURE: bool = False

    # ─── MLflow ────────────────────────────────────────────
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_PREFIX: str = "bizvision"

    # ─── AI / LLM APIs ────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    HUGGINGFACE_TOKEN: str = ""
    HF_HOME: str = "/app/model_cache"

    # ─── LangSmith Tracing ────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "bizvision-ai"

    # ─── Feature Flags ────────────────────────────────────
    ENABLE_EXPERIMENTAL_AGENTS: bool = False
    # When True the recruitment service calls into `ml.recruitment` for real
    # SBERT + XGBoost inference; when False it uses the deterministic mock.
    # Independent of persistence — sessions are persisted to Postgres either way.
    RECRUITMENT_USE_REAL_ML: bool = False
    # Same pattern for pricing — gates all four pricing endpoints into the
    # `ml.pricing` policy ensemble (LightGBM demand / closed-form elasticity /
    # PPO RL). Independent of persistence; ADR-024 applies.
    PRICING_USE_REAL_ML: bool = False
    # Same pattern for forecasting — gates the four forecasting endpoints
    # (`/forecast` · `/sensitivity` · `/what-if` · `/cross-module`) into
    # the `ml.forecasting` classical-arms ensemble (Theta / HoltWinters
    # + baselines). Independent of persistence; ADR-024 applies. The
    # `/sensitivity` endpoint stays closed-form (tornado from
    # perturbation pct, no fitted model needed) — same posture as
    # pricing's `/elasticity`.
    FORECASTING_USE_REAL_ML: bool = False
    # Same pattern for ESG sustainability — gates the model-backed
    # endpoints (`/score` · `/carbon-estimate`) into the
    # `ml.sustainability` classical-arms ensemble
    # (LinearLogisticMultiLabel + CarbonEstimatorModel + industry
    # fairness audit). Independent of persistence; ADR-024 applies. The
    # `/simulate`, `/recommendations`, and `/benchmarks/{industry}`
    # endpoints stay closed-form / reference-data — same posture as
    # pricing's `/elasticity` and forecasting's `/sensitivity`.
    SUSTAINABILITY_USE_REAL_ML: bool = False
    # Same pattern for the financial-advisory chatbot — gates the
    # model-backed endpoints (`/message` REST · WebSocket
    # `stream_response`) into the `ml.chatbot` classical-arms wave-1
    # stack (HashEmbedder + NumpyVectorStore + KeywordRouter +
    # RagResponder + AgentExecutor). Independent of persistence;
    # ADR-024 applies. The `/executive-report` endpoint stays
    # closed-form / static-catalog — same posture as the other
    # modules' reference-data endpoints.
    CHATBOT_USE_REAL_ML: bool = False

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — loaded once per process."""
    return Settings()


settings = get_settings()
