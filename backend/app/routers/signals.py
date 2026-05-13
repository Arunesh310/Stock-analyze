"""Signal scanning endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query

from ..schemas.common import Signal
from ..services import signal_engine, stock_master, universe

router = APIRouter(prefix="/api/signals", tags=["signals"])

# Cap the scan universe for both endpoints: scanning 2000 stocks per request
# is unrealistic and we'd hammer yfinance.  The curated liquid set gives the
# best signal/noise ratio anyway (institutional flows live in liquid names).
_MAX_SCAN = 80


@router.get("", response_model=List[Signal])
def get_signals(
    mode: str = Query("swing", pattern="^(intraday|swing|positional)$"),
    min_conf: float = 60,
    min_grade: str = Query(
        "MODERATE", pattern="^(AVOID|WEAK|MODERATE|STRONG|HIGH_CONVICTION)$"
    ),
    limit: int = 25,
    sector: str | None = None,
) -> list[Signal]:
    """Scan the liquid universe (or a sector) and return ranked actionable signals.

    Filters by both ``min_conf`` (raw confidence) and ``min_grade`` (composite
    quality grade). Default ``min_grade=MODERATE`` rejects WEAK/AVOID setups.
    """
    if sector:
        syms = universe.symbols_in_sector(sector)[:_MAX_SCAN]
    else:
        syms = stock_master.liquid_symbols(_MAX_SCAN)
    sigs = signal_engine.scan_signals(
        syms, mode=mode, min_conf=min_conf, min_grade=min_grade
    )
    return sigs[:limit]


@router.get("/top-picks", response_model=List[Signal])
def top_picks(mode: str = "swing", limit: int = 10) -> list[Signal]:
    """Highest-quality BUY signals across the liquid universe (STRONG+ only)."""
    sigs = signal_engine.scan_signals(
        stock_master.liquid_symbols(_MAX_SCAN),
        mode=mode,
        min_conf=60,
        min_grade="STRONG",
    )
    buys = [s for s in sigs if s.action == "BUY"]
    return buys[:limit]


@router.get("/opportunities", response_model=List[Signal])
def opportunities(
    mode: str = Query("swing", pattern="^(intraday|swing|positional)$"),
    limit: int = 12,
) -> list[Signal]:
    """Best opportunities right now — high-quality BUY *and* SELL setups.

    Returns at most ``limit`` signals, ranked by composite quality score.
    Empty list means the market has no acceptable setups — capital
    preservation by design.
    """
    sigs = signal_engine.scan_signals(
        stock_master.liquid_symbols(_MAX_SCAN),
        mode=mode,
        min_conf=55,
        min_grade="MODERATE",
    )
    return sigs[:limit]
