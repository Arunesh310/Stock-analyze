"""FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager


def _is_serverless() -> bool:
    """True when running on Vercel / Lambda — disables background loops."""
    return any(
        os.environ.get(k)
        for k in ("SERVERLESS", "VERCEL", "AWS_LAMBDA_FUNCTION_NAME")
    )

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import get_settings
from .database import init_db
from .logger import setup_logging
from .routers import (
    ai_evolution,
    ai_performance,
    alerts,
    analyze,
    backtest,
    capital_planner,
    chat,
    confidence,
    correlations,
    dashboard,
    learning_feedback,
    market_regime,
    market_status as market_status_router,
    news,
    prediction_performance,
    risk,
    sectors,
    signals,
    simulated_returns,
    stocks,
    sync_status as sync_status_router,
    validation,
    watchlist,
)
from .scheduler import start_scheduler, shutdown_scheduler
from .ws import live as ws_live


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    serverless = _is_serverless()
    logger.info(f"BharatQuant backend starting up (serverless={serverless})")
    if not serverless:
        loop = asyncio.get_event_loop()
        ws_live.start_background_tasks(loop)
        start_scheduler()
    else:
        logger.info("Skipping scheduler + WS — run on a persistent host for full features.")
    yield
    logger.info("BharatQuant backend shutting down")
    if not serverless:
        shutdown_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BharatQuant API",
        description=(
            "AI-powered Indian stock-market analysis & signal platform. "
            "Educational use only — not financial advice."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "name": "BharatQuant API",
            "version": "0.1.0",
            "docs": "/docs",
            "disclaimer": (
                "This tool is for educational and research purposes only "
                "and not financial advice."
            ),
        }

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        from .services.ai_engine import get_client

        return {
            "status": "ok",
            "ollama": get_client().is_alive(),
        }

    # REST routers
    app.include_router(stocks.router)
    app.include_router(analyze.router)
    app.include_router(signals.router)
    app.include_router(news.router)
    app.include_router(sectors.router)
    app.include_router(correlations.router)
    app.include_router(watchlist.router)
    app.include_router(backtest.router)
    app.include_router(alerts.router)
    app.include_router(chat.router)
    app.include_router(dashboard.router)
    app.include_router(risk.router)

    # Prediction-validation + learning + profitability engine
    app.include_router(prediction_performance.router)
    app.include_router(validation.router)
    app.include_router(simulated_returns.router)
    app.include_router(learning_feedback.router)
    app.include_router(confidence.router)
    app.include_router(market_regime.router)
    app.include_router(ai_performance.router)
    app.include_router(ai_evolution.router)
    app.include_router(capital_planner.router)
    app.include_router(sync_status_router.router)
    app.include_router(market_status_router.router)

    # WebSocket (skipped on serverless — clients fall back to polling)
    if not _is_serverless():
        app.include_router(ws_live.router)

    return app


app = create_app()
