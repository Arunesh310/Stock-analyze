"""GET /api/learning-feedback — what the AI is learning."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from ..services import learning_engine

router = APIRouter(prefix="/api/learning-feedback", tags=["ai-performance"])


@router.get("/recent")
def recent(limit: int = 100, outcome: Optional[str] = None):
    return learning_engine.feedback_recent(limit=limit, outcome=outcome)


@router.get("/top-failure-reasons")
def top_failures(limit: int = 20):
    return learning_engine.feedback_top_categories(outcome="LOSS", limit=limit)


@router.get("/top-success-reasons")
def top_success(limit: int = 20):
    return learning_engine.feedback_top_categories(outcome="WIN", limit=limit)


@router.get("/setups")
def setups(mode: Optional[str] = None):
    return learning_engine.setup_quality(mode=mode)


@router.get("/sectors")
def sectors(mode: Optional[str] = None):
    return learning_engine.sector_performance(mode=mode)


@router.get("/indicators")
def indicators(mode: Optional[str] = None, regime: Optional[str] = None):
    return learning_engine.indicator_performance(mode=mode, regime=regime)


@router.get("/logs")
def logs(limit: int = 100):
    return learning_engine.learning_logs(limit=limit)


@router.post("/run-cycle")
def run_cycle():
    return learning_engine.run_learning_cycle()
