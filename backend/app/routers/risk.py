"""Risk-management calculator endpoint."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.risk_manager import calculate_position

router = APIRouter(prefix="/api/risk", tags=["risk"])


class RiskRequest(BaseModel):
    capital: float = Field(gt=0)
    entry: float = Field(gt=0)
    stoploss: float = Field(gt=0)
    target: float | None = None
    risk_per_trade_pct: float = 1.0
    max_portfolio_heat_pct: float = 5.0


@router.post("/calculate")
def calculate(req: RiskRequest) -> dict:
    try:
        plan = calculate_position(
            capital=req.capital,
            entry=req.entry,
            stoploss=req.stoploss,
            target=req.target,
            risk_per_trade_pct=req.risk_per_trade_pct,
            max_portfolio_heat_pct=req.max_portfolio_heat_pct,
        )
        return asdict(plan)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
