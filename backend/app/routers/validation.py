"""POST /api/validate-signals — manually trigger the validation engine."""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas.prediction import ValidationRunResult
from ..services import validation_engine, learning_engine, confidence_engine

router = APIRouter(prefix="/api/validate-signals", tags=["ai-performance"])


@router.post("", response_model=ValidationRunResult)
def run_validation(limit: int = 200) -> ValidationRunResult:
    """Validate up to ``limit`` open predictions and refresh the learning layer."""
    result = validation_engine.validate_all_open(limit=limit)
    learning_engine.run_learning_cycle()
    confidence_engine.recalibrate()
    return result


@router.post("/expire", response_model=dict)
def expire_old() -> dict:
    n = validation_engine.expire_stale_predictions()
    return {"expired": n}
