"""Dashboard engine — computes the home-page payload and persists it as a
snapshot in ``AILearningLog`` so the backend can serve it instantly.

Architecture
------------
The heavy work (~30-60 fan-out yfinance calls + sector strength + breadth)
runs on a beefy GitHub Actions runner via ``backend/scripts/run_job.py``,
NOT inside the FastAPI process. This keeps the Render free-tier backend
lightweight (just a read query).

The router falls back to direct compute only when no recent snapshot exists
on the very first request to a fresh backend instance.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from loguru import logger

from ..database import db_session
from ..models.prediction_engine import AILearningLog


_EVENT = "dashboard_snapshot"
# Snapshots older than this are considered stale enough that the router
# should also recompute live if it can. Default 5 minutes.
_STALE_AFTER_SECONDS = 300


def compute_payload() -> Dict[str, Any]:
    """Run every panel concurrently and return the dashboard payload.

    Imports the services locally so this module is cheap to import in CLI
    contexts that only want to call ``latest_snapshot``.
    """
    from . import correlation_engine, market_data, news_engine, stock_master

    indices = ["^NSEI", "^NSEBANK", "^INDIAVIX"]
    fx = ["INR=X"]
    commodities = ["CL=F", "GC=F"]
    liquid = stock_master.liquid_symbols(limit=60)

    with ThreadPoolExecutor(max_workers=4) as ex:
        fut_idx = ex.submit(market_data.get_quotes, indices + fx + commodities)
        fut_movers = ex.submit(market_data.gainers_losers, liquid, 8)
        fut_sectors = ex.submit(correlation_engine.sector_strength, "1mo")
        fut_breadth = ex.submit(correlation_engine.market_breadth, liquid[:30])
        fut_fii = ex.submit(news_engine.fii_dii_proxy)

        indices_q = fut_idx.result()
        movers = fut_movers.result()
        sectors = fut_sectors.result()
        breadth = fut_breadth.result()
        fii = fut_fii.result()

    return {
        "indices": [q.model_dump(mode="json") for q in indices_q],
        "gainers": [q.model_dump(mode="json") for q in movers["gainers"]],
        "losers": [q.model_dump(mode="json") for q in movers["losers"]],
        "most_active": [q.model_dump(mode="json") for q in movers["most_active"]],
        "sectors": sectors,
        "breadth": breadth,
        "fii_dii": fii,
        "disclaimer": (
            "This tool is for educational and research purposes only "
            "and not financial advice."
        ),
    }


def run_and_persist() -> Dict[str, Any]:
    """Compute the dashboard and write it to ``AILearningLog`` so the API
    can serve it without re-running the fan-out."""
    started = time.time()
    payload = compute_payload()
    duration = round(time.time() - started, 2)
    summary = (
        f"Dashboard snapshot · {len(payload['indices'])} indices · "
        f"{len(payload['gainers'])} gainers · "
        f"{len(payload['losers'])} losers · "
        f"computed in {duration}s"
    )
    try:
        with db_session() as db:
            db.add(
                AILearningLog(
                    event=_EVENT,
                    summary=summary,
                    details=payload,
                )
            )
    except Exception as exc:  # pragma: no cover
        logger.warning(f"dashboard_engine could not persist snapshot: {exc}")
    logger.info(f"dashboard_engine: {summary}")
    return payload


def latest_snapshot(max_age_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Return the latest persisted snapshot payload, or ``None`` if there
    is no snapshot or it is older than ``max_age_seconds``."""
    try:
        with db_session() as db:
            row = (
                db.query(AILearningLog)
                .filter(AILearningLog.event == _EVENT)
                .order_by(AILearningLog.created_at.desc())
                .first()
            )
        if row is None or not row.details:
            return None
        if max_age_seconds is not None and row.created_at is not None:
            age = (datetime.utcnow() - row.created_at).total_seconds()
            if age > max_age_seconds:
                return None
        return row.details
    except Exception as exc:
        logger.warning(f"dashboard_engine.latest_snapshot failed: {exc}")
        return None


def is_stale(snapshot_created_at: Optional[datetime]) -> bool:
    if snapshot_created_at is None:
        return True
    return (datetime.utcnow() - snapshot_created_at).total_seconds() > _STALE_AFTER_SECONDS


def snapshot_meta() -> Dict[str, Any]:
    """Lightweight check on whether a snapshot exists + how old it is."""
    try:
        with db_session() as db:
            row = (
                db.query(AILearningLog)
                .filter(AILearningLog.event == _EVENT)
                .order_by(AILearningLog.created_at.desc())
                .first()
            )
        if row is None:
            return {"exists": False, "age_seconds": None, "created_at": None}
        age = (
            int((datetime.utcnow() - row.created_at).total_seconds())
            if row.created_at
            else None
        )
        return {
            "exists": True,
            "age_seconds": age,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "stale": age is not None and age > _STALE_AFTER_SECONDS,
        }
    except Exception:
        return {"exists": False, "age_seconds": None, "created_at": None}
