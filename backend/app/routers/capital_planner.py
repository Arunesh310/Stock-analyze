"""POST /api/capital-planner — realism-checked stock picks for a capital target."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services import capital_planner

router = APIRouter(prefix="/api/capital-planner", tags=["planner"])


class PlanRequest(BaseModel):
    capital: float = Field(gt=0, le=1_000_000_000, description="Capital in INR")
    target_amount: float = Field(gt=0, description="Profit target in INR")
    timeframe: Literal["1m", "5m", "10m", "15m", "30m", "1h", "1d", "1w", "1mo"] = "1d"
    risk_tolerance: Literal["conservative", "balanced", "aggressive"] = "balanced"
    mode: Literal["intraday", "swing", "positional"] = "swing"
    max_picks: int = Field(6, ge=1, le=20)


@router.post("")
def plan(req: PlanRequest):
    return capital_planner.plan(
        capital=req.capital,
        target_amount=req.target_amount,
        timeframe=req.timeframe,
        risk_tolerance=req.risk_tolerance,
        mode=req.mode,
        max_picks=req.max_picks,
    )
