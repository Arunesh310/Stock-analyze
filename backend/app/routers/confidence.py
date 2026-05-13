"""GET /api/confidence-analysis — confidence calibration."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import confidence_engine

router = APIRouter(prefix="/api/confidence-analysis", tags=["ai-performance"])


@router.get("/buckets")
def buckets():
    return confidence_engine.all_buckets()


@router.post("/recalibrate")
def recalibrate():
    return confidence_engine.recalibrate()
