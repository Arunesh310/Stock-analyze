"""Backtesting endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.common import BacktestRequest, BacktestResponse
from ..services import backtest_engine

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest) -> BacktestResponse:
    try:
        res = backtest_engine.backtest(
            symbol=req.symbol,
            strategy=req.strategy,
            period=req.period,
            interval=req.interval,
            fast=req.fast,
            slow=req.slow,
            rsi_low=req.rsi_low,
            rsi_high=req.rsi_high,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return BacktestResponse(symbol=req.symbol, strategy=req.strategy, **res)
