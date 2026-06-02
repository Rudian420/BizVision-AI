"""
BizVision AI — Structured Logging

Configures Loguru as the single logging sink and routes the standard
library `logging` module (used by uvicorn, sqlalchemy, etc.) through it
so every line shares one structured format.

Falls back to plain stdlib logging if Loguru is unavailable.
"""

from __future__ import annotations

import logging
import sys

from src.core.config import settings

try:
    from loguru import logger as _loguru_logger

    _HAS_LOGURU = True
except ImportError:  # pragma: no cover - loguru is a declared dependency
    _loguru_logger = None  # type: ignore[assignment]
    _HAS_LOGURU = False


class InterceptHandler(logging.Handler):
    """Redirect stdlib logging records into Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _loguru_logger.level(record.levelname).name
        except (ValueError, AttributeError):
            level = record.levelno

        # Find the caller frame so the source location is accurate.
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    """Initialise application-wide logging. Idempotent."""
    log_level = "DEBUG" if settings.is_development else "INFO"

    if not _HAS_LOGURU:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            stream=sys.stdout,
        )
        logging.getLogger(__name__).info("Logging configured (stdlib fallback).")
        return

    _loguru_logger.remove()
    _loguru_logger.add(
        sys.stdout,
        level=log_level,
        backtrace=settings.is_development,
        diagnose=settings.is_development,
        serialize=settings.is_production,  # JSON logs in production
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # Route stdlib + framework loggers through Loguru.
    intercept = InterceptHandler()
    logging.root.handlers = [intercept]
    logging.root.setLevel(log_level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        std_logger = logging.getLogger(name)
        std_logger.handlers = [intercept]
        std_logger.propagate = False

    _loguru_logger.info("Logging configured (Loguru, level={}).", log_level)


def get_logger(name: str | None = None):
    """Return the shared application logger."""
    if _HAS_LOGURU:
        return _loguru_logger
    return logging.getLogger(name or "bizvision")
