"""Aggregated dashboard endpoint — single call drives the home page.

Hot path: serves the home page, so we restrict expensive scans to a
*liquid* subset (the curated large/mid-cap names) instead of the full
2000+ symbol catalogue, and cache the result in-process for a short TTL so
repeat hits (every visitor refresh) never re-fetch yfinance.

The cache is process-local — Render free tier runs one worker so this is
sufficient. The first cold hit still takes ~20-40s on Render's 0.5 CPU
because we fan out yfinance calls for ~90 symbols, but every subsequent
hit within the TTL window returns instantly.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from loguru import logger

from ..services import correlation_engine, market_data, news_engine, stock_master

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# Cache TTL: 60s is short enough to feel "live" during market hours and long
# enough to absorb every refresh from the home page on a busy minute.
_CACHE_TTL_SECONDS = 60
_cache_lock = threading.Lock()
_cache_payload: dict | None = None
_cache_set_at: float = 0.0


def _compute_dashboard() -> dict:
    """Heavy path — fan out the four independent fetches in parallel."""
    indices = ["^NSEI", "^NSEBANK", "^INDIAVIX"]
    fx = ["INR=X"]
    commodities = ["CL=F", "GC=F"]
    liquid = stock_master.liquid_symbols(limit=60)

    # All four calls are independent I/O — run them concurrently so the
    # wall-time is the slowest one, not the sum.
    with ThreadPoolExecutor(max_workers=4) as ex:
        fut_idx = ex.submit(market_data.get_quotes, indices + fx + commodities)
        fut_movers = ex.submit(market_data.gainers_losers, liquid, 8)
        fut_sectors = ex.submit(correlation_engine.sector_strength, "1mo")
        fut_breadth = ex.submit(correlation_engine.market_breadth, liquid[:30])
        fut_fii = ex.submit(news_engine.fii_dii_proxy)

        indices_q = fut_idx.result()
        movers = fut_movers.result()
        sectors = fut_sectors.result()
        breadth = fut_breadth.result()
        fii = fut_fii.result()

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


@router.get("")
def dashboard() -> dict:
    global _cache_payload, _cache_set_at

    now = time.time()
    cached = _cache_payload
    if cached is not None and (now - _cache_set_at) < _CACHE_TTL_SECONDS:
        return cached

    # Single-flight: only one request actually computes; siblings wait and
    # then return the freshly cached value. This avoids the thundering-herd
    # situation where 5 visitors arriving in the same second each spawn a
    # 30s yfinance fan-out.
    with _cache_lock:
        # Re-check under the lock — another thread may have populated.
        cached = _cache_payload
        if cached is not None and (time.time() - _cache_set_at) < _CACHE_TTL_SECONDS:
            return cached
        try:
            payload = _compute_dashboard()
            _cache_payload = payload
            _cache_set_at = time.time()
            return payload
        except Exception as exc:
            logger.warning(f"dashboard compute failed: {exc}")
            # If we have a stale cache, prefer serving it over a hard error.
            if _cache_payload is not None:
                return _cache_payload
            raise
