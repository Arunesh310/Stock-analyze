"""Loguru-based logging setup."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

from .config import get_settings


def _serverless() -> bool:
    return any(
        os.environ.get(k)
        for k in ("SERVERLESS", "VERCEL", "AWS_LAMBDA_FUNCTION_NAME")
    )


def setup_logging() -> None:
    """Configure loguru sinks (stdout always; rotating file when writable)."""
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

    # On Vercel / Lambda the only writable path is /tmp. Skip file logging
    # entirely on serverless — stdout is captured by the platform anyway.
    if _serverless():
        logger.info(
            "Logging initialised (serverless mode — stdout only). Level={}",
            settings.log_level,
        )
        return

    try:
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
    except OSError:
        # Read-only filesystem (containerised host) — stdout-only is fine.
        pass

    logger.info("Logging initialised. Level={}", settings.log_level)
