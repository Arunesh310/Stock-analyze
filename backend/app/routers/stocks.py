"""Stock metadata, quotes, OHLC, search, resolve, trending.

Search has been upgraded to:
- fuzzy / partial / alias matching
- optional price+change enrichment (``with_prices=true``)
- a separate ``/resolve`` endpoint for normalising free-text input
- a ``/trending`` endpoint that returns the day's biggest movers
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from ..schemas.common import (
    DataQualityOut,
    OhlcRow,
    Quote,
    QuoteWithQuality,
    ResolveOut,
    SearchHit,
)
from ..services import market_data, stock_master, symbol_normalizer, universe

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


def _to_search_hit(meta, *, with_prices: bool, confidence: float = 1.0,
                   source: str = "exact") -> SearchHit:
    hit = SearchHit(
        symbol=meta.symbol,
        name=meta.name,
        sector=meta.sector,
        industry=meta.industry,
        exchange=meta.exchange,
        market_cap=meta.market_cap,
        nse=meta.nse,
        bse=meta.bse,
        match_confidence=confidence,
        match_source=source,
    )
    if with_prices and meta.exchange in {"NSE", "BSE", "INDEX", "FX", "COMM"}:
        try:
            q = market_data.get_quote(meta.symbol)
            hit.price = q.price
            hit.change = q.change
            hit.change_pct = q.change_pct
        except Exception as exc:
            logger.debug(f"price enrich failed for {meta.symbol}: {exc}")
    return hit


@router.get("/search", response_model=List[SearchHit])
def search_symbols(
    q: str = Query("", min_length=0),
    limit: int = 12,
    with_prices: bool = False,
) -> List[SearchHit]:
    """Fuzzy / alias search across the curated NSE + BSE universe."""
    results = symbol_normalizer.search_scored(q, limit=limit)
    return [
        _to_search_hit(m, with_prices=with_prices, confidence=conf, source=src)
        for m, conf, src in results
    ]


@router.get("/resolve", response_model=ResolveOut)
def resolve_symbol(q: str = Query(..., min_length=1)) -> ResolveOut:
    """Normalise free-text input to a canonical yfinance symbol.

    When no plausible match is found we explicitly report ``listed=False``
    so the UI can say "X is not publicly listed on NSE/BSE" instead of
    rendering a 404 page.
    """
    r = symbol_normalizer.normalize(q)
    if r.ok:
        return ResolveOut(
            input=q, symbol=r.symbol, name=r.name, sector=r.sector,
            confidence=r.confidence, source=r.source, listed=True,
        )
    suggestions = [
        m.symbol for m, _, _ in symbol_normalizer.search_scored(q, limit=5)
    ]
    return ResolveOut(
        input=q,
        symbol=None,
        name=None,
        sector=None,
        confidence=0.0,
        source="not_listed",
        listed=False,
        message=(
            f"\"{q.strip()}\" is not publicly listed on NSE/BSE. "
            "It may be a private company or a brand of a listed parent — "
            "no live market data is available."
        ),
        suggestions=suggestions,
    )


@router.get("/universe")
def get_universe() -> list[dict]:
    return [
        {
            "symbol": s.symbol,
            "name": s.name,
            "sector": s.sector,
            "industry": s.industry,
            "market_cap": s.market_cap,
            "exchange": s.exchange,
        }
        for s in stock_master.all_stocks()
        if s.exchange == "NSE"
    ]


@router.get("/sectors")
def list_sectors() -> list[str]:
    return universe.all_sectors()


@router.get("/trending", response_model=List[SearchHit])
def trending(limit: int = 12) -> List[SearchHit]:
    """Top movers across the curated universe (by |change %|)."""
    syms = universe.all_symbols()[:60]
    quotes = market_data.get_quotes(syms)
    quotes.sort(key=lambda q: abs(q.change_pct), reverse=True)
    out: List[SearchHit] = []
    for q in quotes[:limit]:
        meta = stock_master.find_by_symbol(q.symbol)
        if meta is None:
            continue
        hit = _to_search_hit(meta, with_prices=False)
        hit.price = q.price
        hit.change = q.change
        hit.change_pct = q.change_pct
        out.append(hit)
    return out


@router.get("/{symbol}", response_model=Quote)
def get_quote(symbol: str) -> Quote:
    sym = symbol_normalizer.canonical(symbol)
    try:
        return market_data.get_quote(sym)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{symbol}/quote-quality", response_model=QuoteWithQuality)
def get_quote_with_quality(symbol: str) -> QuoteWithQuality:
    sym = symbol_normalizer.canonical(symbol)
    try:
        q, qual = market_data.get_quote_with_quality(sym)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return QuoteWithQuality(
        quote=q,
        quality=DataQualityOut(**qual.as_dict()),
    )


@router.get("/{symbol}/quality", response_model=DataQualityOut)
def get_symbol_quality(symbol: str) -> DataQualityOut:
    sym = symbol_normalizer.canonical(symbol)
    # Trigger at least one fetch so the quality cache is populated
    try:
        market_data.get_quote(sym)
    except Exception:
        pass
    return DataQualityOut(**market_data.get_quality(sym).as_dict())


@router.get("/{symbol}/ohlc", response_model=List[OhlcRow])
def get_ohlc(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
) -> List[OhlcRow]:
    sym = symbol_normalizer.canonical(symbol)
    try:
        df = market_data.get_history(sym, period=period, interval=interval)
        return market_data.to_ohlc_rows(df)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/quotes/batch")
def batch_quotes(symbols: str) -> list[Quote]:
    """`symbols` is a comma-separated list (free-text resolution allowed)."""
    raw = [s.strip() for s in symbols.split(",") if s.strip()]
    syms = [symbol_normalizer.canonical(s) for s in raw if s]
    return market_data.get_quotes(syms)
