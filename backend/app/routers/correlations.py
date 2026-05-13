"""Correlation & sympathy-mover endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import correlation_engine, stock_master

router = APIRouter(prefix="/api/correlations", tags=["correlations"])


@router.get("/{symbol}")
def correlations_for(symbol: str, period: str = "6mo", limit: int = 10) -> list[dict]:
    return correlation_engine.correlations_against(
        symbol, stock_master.liquid_symbols(80), period=period
    )[:limit]


@router.get("/{symbol}/sympathy")
def sympathy(symbol: str, limit: int = 5) -> list[dict]:
    return correlation_engine.sympathy_movers(symbol, limit=limit)
