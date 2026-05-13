"""Sector rotation and breadth endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from ..services import correlation_engine, stock_master, universe

router = APIRouter(prefix="/api/sectors", tags=["sectors"])


@router.get("")
def list_sectors() -> list[str]:
    return universe.all_sectors()


@router.get("/strength")
def sector_strength(period: str = "1mo") -> List[dict]:
    return correlation_engine.sector_strength(period=period)


@router.get("/breadth")
def market_breadth() -> dict:
    return correlation_engine.market_breadth(stock_master.liquid_symbols(80))
