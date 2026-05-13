"""GET /api/simulated-returns — cumulative simulated profit dashboard."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..services import profit_simulator

router = APIRouter(prefix="/api/simulated-returns", tags=["ai-performance"])


@router.get("/equity-curve")
def equity_curve(
    since_days: Optional[int] = Query(365, ge=1, le=3650),
    mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$"),
):
    return profit_simulator.equity_curve(since_days=since_days, mode=mode)


@router.get("/by-sector")
def by_sector(mode: Optional[str] = None):
    return profit_simulator.by_sector(mode=mode)


@router.get("/by-regime")
def by_regime(mode: Optional[str] = None):
    return profit_simulator.by_regime(mode=mode)


@router.get("/summary")
def summary(mode: Optional[str] = None, since_days: Optional[int] = None):
    return profit_simulator.summary(mode=mode, since_days=since_days)


@router.get("/portfolio-metrics")
def portfolio_metrics(
    mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$"),
    since_days: Optional[int] = None,
):
    """Portfolio risk metrics: CAGR, Sharpe, max drawdown, profit factor, expectancy."""
    return profit_simulator.portfolio_metrics(mode=mode, since_days=since_days)
