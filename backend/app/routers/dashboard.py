"""Aggregated dashboard endpoint — single call drives the home page.

Hot path: serves the home page, so we restrict expensive scans to a
*liquid* subset (the curated large/mid-cap names) instead of the full
2000+ symbol catalogue.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..services import correlation_engine, market_data, news_engine, stock_master

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard() -> dict:
    indices = ["^NSEI", "^NSEBANK", "^INDIAVIX"]
    fx = ["INR=X"]
    commodities = ["CL=F", "GC=F"]
    # Liquid subset — keeps the dashboard snappy even with a 2k-stock master list
    liquid = stock_master.liquid_symbols(limit=60)

    indices_q = market_data.get_quotes(indices + fx + commodities)
    movers = market_data.gainers_losers(liquid, top_n=8)
    sectors = correlation_engine.sector_strength(period="1mo")
    breadth = correlation_engine.market_breadth(liquid[:30])
    fii = news_engine.fii_dii_proxy()

    return {
        "indices": [q.model_dump(mode="json") for q in indices_q],
        "gainers": [q.model_dump(mode="json") for q in movers["gainers"]],
        "losers": [q.model_dump(mode="json") for q in movers["losers"]],
        "most_active": [q.model_dump(mode="json") for q in movers["most_active"]],
        "sectors": sectors,
        "breadth": breadth,
        "fii_dii": fii,
        "disclaimer": (
            "This tool is for educational and research purposes only "
            "and not financial advice."
        ),
    }
