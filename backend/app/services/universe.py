"""Backwards-compatibility shim over ``stock_master``.

Everything in this module is preserved API-wise so existing routers and
services keep working, but the data now lives in
``app.services.stock_master`` which is the new single source of truth for
the curated Indian-market universe.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from . import stock_master


# Original public dicts — kept for code that imports them directly.
NSE_UNIVERSE: Dict[str, Tuple[str, str]] = {
    s.symbol: (s.name, s.sector)
    for s in stock_master.all_stocks()
    if s.exchange == "NSE"
}

INDEX_SYMBOLS: Dict[str, str] = {
    s.symbol: s.name for s in stock_master.all_stocks() if s.exchange == "INDEX"
}

FX_COMMODITY_SYMBOLS: Dict[str, str] = {
    s.symbol: s.name
    for s in stock_master.all_stocks()
    if s.exchange in {"FX", "COMM"}
}


def get_sector(symbol: str) -> str:
    return stock_master.get_sector(symbol)


def get_name(symbol: str) -> str:
    return stock_master.get_name(symbol)


def all_symbols() -> List[str]:
    return stock_master.all_symbols()


def symbols_in_sector(sector: str) -> List[str]:
    return stock_master.symbols_in_sector(sector)


def all_sectors() -> List[str]:
    return stock_master.all_sectors()


def search(query: str, limit: int = 25) -> List[Dict[str, str]]:
    """Light substring search. For fuzzy / typo-tolerant search use
    ``symbol_normalizer.search``."""
    return stock_master.search(query, limit=limit)
