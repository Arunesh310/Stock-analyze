"""Live System Sync Panel — transparent visibility into background pipelines.

Aggregates the freshness of every data pipeline the user depends on:

- Market quotes (yfinance cache hits in the last N minutes)
- News (most recent NewsItem stored in DB)
- AI learning (last AILearningLog event)
- Validation engine (last PredictionOutcome update)
- Market regime classifier (last MarketRegimeSnapshot)
- WebSocket live tick stream (last broadcast)
- Scheduler heartbeat (this process's uptime)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from ..database import db_session


_START_TS = time.time()


def _seconds_since(ts: Optional[datetime]) -> Optional[int]:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - ts).total_seconds())


def _fmt_relative(seconds: Optional[int]) -> str:
    if seconds is None:
        return "never"
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _status_for(seconds: Optional[int], fresh_thresh: int, ok_thresh: int) -> str:
    """``fresh`` / ``ok`` / ``stale`` / ``offline`` based on age vs thresholds."""
    if seconds is None:
        return "offline"
    if seconds < fresh_thresh:
        return "fresh"
    if seconds < ok_thresh:
        return "ok"
    return "stale"


def _last_news_at() -> Optional[datetime]:
    """News is cached in-memory in ``news_engine``; surface the most-recent
    item's published time from there (no DB hit)."""
    try:
        from . import news_engine
        cache = getattr(news_engine, "_cache", None)
        if not cache:
            return None
        latest: Optional[datetime] = None
        for _ts, items in cache.values():
            for it in items:
                if it.published and (latest is None or it.published > latest):
                    latest = it.published
        return latest
    except Exception:
        return None


def _last_learning_at() -> Optional[datetime]:
    try:
        from ..models.prediction_engine import AILearningLog
        with db_session() as db:
            row = (
                db.query(AILearningLog)
                .order_by(AILearningLog.created_at.desc())
                .first()
            )
            return row.created_at if row else None
    except Exception:
        return None


def _last_validation_at() -> Optional[datetime]:
    try:
        from ..models.prediction_engine import PredictionOutcome
        with db_session() as db:
            row = (
                db.query(PredictionOutcome)
                .order_by(PredictionOutcome.validated_at.desc())
                .first()
            )
            return row.validated_at if row else None
    except Exception:
        return None


def _last_regime_at() -> Optional[datetime]:
    try:
        from ..models.prediction_engine import MarketRegimeSnapshot
        with db_session() as db:
            row = (
                db.query(MarketRegimeSnapshot)
                .order_by(MarketRegimeSnapshot.created_at.desc())
                .first()
            )
            return row.created_at if row else None
    except Exception:
        return None


def _market_data_last_fetch() -> Optional[datetime]:
    try:
        from . import market_data  # type: ignore
        ts = getattr(market_data, "_LAST_FETCH_TS", None)
        if not ts:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None


def _ws_last_broadcast() -> Optional[datetime]:
    try:
        from ..ws import live  # type: ignore
        ts = getattr(live, "_LAST_BROADCAST_TS", None)
        if not ts:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None


def _prediction_counts() -> dict[str, int]:
    try:
        from ..models.prediction_engine import PredictionHistory, PredictionOutcome
        with db_session() as db:
            total = db.query(PredictionHistory).count()
            validated = db.query(PredictionOutcome).count()
            return {"total_predictions": total, "validated": validated}
    except Exception:
        return {"total_predictions": 0, "validated": 0}


def get_status() -> dict[str, Any]:
    market_ts = _market_data_last_fetch()
    news_ts = _last_news_at()
    learn_ts = _last_learning_at()
    valid_ts = _last_validation_at()
    regime_ts = _last_regime_at()
    ws_ts = _ws_last_broadcast()

    market_age = _seconds_since(market_ts)
    news_age = _seconds_since(news_ts)
    learn_age = _seconds_since(learn_ts)
    valid_age = _seconds_since(valid_ts)
    regime_age = _seconds_since(regime_ts)
    ws_age = _seconds_since(ws_ts)

    counts = _prediction_counts()

    pipelines = [
        {
            "key": "market_data",
            "label": "Market data",
            "status": _status_for(market_age, fresh_thresh=120, ok_thresh=600),
            "last_at": market_ts.isoformat() if market_ts else None,
            "relative": _fmt_relative(market_age),
            "detail": "yfinance + NSE quotes",
        },
        {
            "key": "news",
            "label": "News & sentiment",
            "status": _status_for(news_age, fresh_thresh=900, ok_thresh=3600),
            "last_at": news_ts.isoformat() if news_ts else None,
            "relative": _fmt_relative(news_age),
            "detail": "RSS + macro feeds",
        },
        {
            "key": "ai_learning",
            "label": "AI learning",
            "status": _status_for(learn_age, fresh_thresh=3600, ok_thresh=86400),
            "last_at": learn_ts.isoformat() if learn_ts else None,
            "relative": _fmt_relative(learn_age),
            "detail": (
                f"{counts['validated']} validated of {counts['total_predictions']} predictions"
            ),
        },
        {
            "key": "validation",
            "label": "Prediction validation",
            "status": _status_for(valid_age, fresh_thresh=900, ok_thresh=3600),
            "last_at": valid_ts.isoformat() if valid_ts else None,
            "relative": _fmt_relative(valid_age),
            "detail": "validation_engine outcome check",
        },
        {
            "key": "regime",
            "label": "Market regime",
            "status": _status_for(regime_age, fresh_thresh=900, ok_thresh=3600),
            "last_at": regime_ts.isoformat() if regime_ts else None,
            "relative": _fmt_relative(regime_age),
            "detail": "Nifty / breadth / VIX classifier",
        },
        {
            "key": "websocket",
            "label": "Live websocket",
            "status": _status_for(ws_age, fresh_thresh=30, ok_thresh=180),
            "last_at": ws_ts.isoformat() if ws_ts else None,
            "relative": _fmt_relative(ws_age),
            "detail": "tick broadcast to frontend",
        },
    ]

    healthy = sum(1 for p in pipelines if p["status"] in ("fresh", "ok"))
    overall = (
        "healthy" if healthy >= 5 else
        "degraded" if healthy >= 3 else
        "offline"
    )
    return {
        "overall_status": overall,
        "uptime_seconds": int(time.time() - _START_TS),
        "pipelines": pipelines,
        "predictions": counts,
        "now": datetime.utcnow().isoformat(),
    }
