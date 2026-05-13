"""Overnight + Pre-Market endpoints.

These surface the daily learning cycle (post-close) and the morning brief
(pre-open) to the UI. Both can also be triggered on demand so users (and
ops) can manually refresh.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import overnight_engine, pre_market_engine


router = APIRouter(prefix="/api/overnight", tags=["overnight"])


@router.get("/status")
def overnight_status():
    """Latest overnight cycle (or null if it has never run on this instance)."""
    return overnight_engine.latest_run() or {
        "summary": "Overnight cycle has not run yet on this instance.",
        "details": {},
        "created_at": None,
    }


@router.post("/run")
def overnight_run():
    """Trigger an overnight cycle right now. Useful for manual refresh."""
    return overnight_engine.run_overnight_cycle()


pre_market_router = APIRouter(prefix="/api/pre-market", tags=["pre-market"])


@pre_market_router.get("")
def pre_market_brief():
    """Latest pre-market brief. Returns 404-style payload if none yet."""
    brief = pre_market_engine.latest_brief()
    if brief is None:
        return {
            "generated_at": None,
            "global_cues": [],
            "india_vix": None,
            "india_vix_change_pct": None,
            "top_sectors": [],
            "weak_sectors": [],
            "gap_candidates": [],
            "readiness": {"verdict": "UNKNOWN", "score": 0, "bullets": [
                "Pre-market brief has not run yet on this instance."
            ]},
            "notes": [],
        }
    return brief


@pre_market_router.post("/refresh")
def pre_market_refresh():
    """Compute and persist a fresh pre-market brief on demand."""
    try:
        return pre_market_engine.run_pre_market_cycle()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"pre_market refresh failed: {exc}")
