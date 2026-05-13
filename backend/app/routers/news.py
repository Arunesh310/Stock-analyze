"""News + sentiment endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query

from ..schemas.common import NewsItem
from ..services import news_engine

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=List[NewsItem])
def list_news(
    limit: int = 50,
    sector: str | None = None,
    symbol: str | None = None,
) -> list[NewsItem]:
    items = news_engine.fetch_news()
    if sector:
        items = [n for n in items if sector in n.impacted_sectors]
    if symbol:
        items = [n for n in items if symbol in n.impacted_symbols]
    return items[:limit]


@router.get("/sentiment")
def market_sentiment() -> dict:
    return news_engine.aggregate_market_sentiment()


@router.get("/fii-dii")
def fii_dii() -> dict:
    """Proxy FII/DII signal blended from news sentiment + index move."""
    return news_engine.fii_dii_proxy()
