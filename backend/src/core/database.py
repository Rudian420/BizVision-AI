"""
BizVision AI — Async Database Engine

SQLAlchemy 2.0 async configuration with pgvector support.
Connection pool tuned for ML inference workloads (fewer, longer-lived connections).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import settings


# ── Engine Configuration ──────────────────────────────────────────
# NullPool used in test/migration context; connection pool in production
def create_engine(database_url: str | None = None) -> AsyncEngine:
    url = database_url or settings.DATABASE_URL
    return create_async_engine(
        url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,  # Detect stale connections
        echo=settings.is_development,  # Log SQL in dev
    )


engine = create_engine()

# ── Session Factory ───────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent lazy-load errors after commit
    autocommit=False,
    autoflush=False,
)


# ── Base Model ────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


# ── Dependency Injection ──────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.
    Session is automatically committed on success and rolled back on error.

    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
