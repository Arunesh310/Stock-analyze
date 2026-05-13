"""Loguru-based logging setup."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from .config import get_settings


def setup_logging() -> None:
    """Configure loguru sinks (stdout + rotating file)."""
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "bharatquant.log",
        rotation="20 MB",
        retention="14 days",
        level=settings.log_level,
        enqueue=True,
        encoding="utf-8",
    )

    logger.info("Logging initialised. Level=%s" % settings.log_level)
