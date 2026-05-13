"""GET /api/ai-evolution — transparent AI learning + evolution metrics."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..services import ai_evolution

router = APIRouter(prefix="/api/ai-evolution", tags=["ai-performance"])


@router.get("/rolling")
def rolling(mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$")):
    """7d / 30d / 90d / all-time accuracy + return."""
    return ai_evolution.rolling_windows(mode=mode)


@router.get("/signal-conversion")
def conversion(mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$")):
    """BUY vs SELL success, target hit %, stoploss %, false-breakout %."""
    return ai_evolution.signal_conversion(mode=mode)


@router.get("/improvement-score")
def improvement(mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$")):
    """Composite improvement metric: last 30 days vs prior 30 days."""
    return ai_evolution.improvement_score(mode=mode)


@router.get("/recent-changes")
def changes(limit: int = Query(30, ge=1, le=200)):
    """Recent AI weight adjustments and learning-cycle events."""
    return ai_evolution.recent_changes(limit=limit)


@router.get("/strategy-performance")
def strategies(mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$")):
    """Per-strategy leaderboard: win-rate, avg return, profit factor."""
    return ai_evolution.strategy_performance(mode=mode)


@router.get("/regime-strategy-matrix")
def regime_strategy(mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$")):
    """Win-rate of each strategy in each market regime."""
    return ai_evolution.regime_strategy_matrix(mode=mode)


@router.get("/recent-outcomes")
def outcomes(limit: int = Query(50, ge=1, le=200)):
    """Recent predictions paired with their actual outcomes (success/fail)."""
    return ai_evolution.recent_signal_outcomes(limit=limit)
