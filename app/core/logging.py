"""
Logging helpers with a loguru-to-stdlib fallback.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    from loguru import logger as _loguru_logger
except ImportError:  # pragma: no cover - exercised only in minimal environments
    _loguru_logger = None


def _build_stdlib_logger(log_level: str) -> logging.Logger:
    logger = logging.getLogger("automind")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def setup_logging(log_level: str = "INFO"):
    """Configure logging and return a logger instance."""
    if _loguru_logger is None:
        return _build_stdlib_logger(log_level)

    _loguru_logger.remove()
    _loguru_logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    _loguru_logger.add(
        log_path / "app_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level=log_level,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    _loguru_logger.add(
        log_path / "error_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="90 days",
        level="ERROR",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    return _loguru_logger


logger = setup_logging()
