"""Failure Analysis endpoints — explainable post-mortems on closed predictions."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services import failure_analysis


router = APIRouter(prefix="/api/failures", tags=["failures"])


@router.get("/recent")
def recent(
    limit: int = Query(20, ge=1, le=100),
    mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$"),
    include_successes: bool = Query(False),
):
    """Most-recent closed predictions, packaged as failure-analysis reports.

    Each item includes the snapshot of market conditions at signal time,
    the actual outcome, contributing failure factors, and any AI learning
    that was applied within 24h of validation.
    """
    return failure_analysis.recent_failures(
        limit=limit, mode=mode, include_successes=include_successes
    )


@router.get("/top-reasons")
def top_reasons(
    limit: int = Query(12, ge=1, le=40),
    days: int = Query(30, ge=1, le=365),
    mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$"),
):
    """Top failure categories over the recent window with counts + a
    representative example. Useful for the 'why are we losing?' dashboard."""
    return failure_analysis.top_failure_reasons(limit=limit, days=days, mode=mode)


@router.get("/{prediction_id}")
def one(prediction_id: int):
    """Full failure-analysis report for a single prediction id."""
    report = failure_analysis.failure_report(prediction_id)
    if report is None:
        raise HTTPException(status_code=404, detail="prediction not found")
    return report
