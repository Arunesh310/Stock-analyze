"""Live System Sync Panel — transparent visibility into background pipelines.

Aggregates the freshness of every data pipeline the user depends on:

- Market quotes (yfinance cache hits in the last N minutes)
- News (most recent NewsItem stored in DB)
- AI learning (last AILearningLog event)
- Validation engine (last PredictionOutcome update)
- Market regime classifier (last MarketRegimeSnapshot)
- WebSocket live tick stream (last broadcast)
- Overnight learning cycle (last "overnight_cycle" log)
- Pre-market brief (last "pre_market_brief" log)
- Counts of signals evaluated & learning updates applied in the last 24h
- Time-to-next-session (from market_status)
- Scheduler heartbeat (this process's uptime)
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
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
    """The model class is ``MarketRegime`` — earlier this helper referenced a
    name that doesn't exist, causing the pipeline to silently show ``offline``
    even when fresh regime snapshots existed."""
    try:
        from ..models.prediction_engine import MarketRegime
        with db_session() as db:
            row = (
                db.query(MarketRegime)
                .order_by(MarketRegime.created_at.desc())
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
        cutoff = datetime.utcnow() - timedelta(hours=24)
        with db_session() as db:
            total = db.query(PredictionHistory).count()
            validated = db.query(PredictionOutcome).count()
            evaluated_24h = (
                db.query(PredictionHistory)
                .filter(PredictionHistory.created_at >= cutoff)
                .count()
            )
            return {
                "total_predictions": total,
                "validated": validated,
                "signals_evaluated_24h": evaluated_24h,
            }
    except Exception:
        return {
            "total_predictions": 0,
            "validated": 0,
            "signals_evaluated_24h": 0,
        }


def _learning_updates_24h() -> int:
    """How many weight_changed log entries have been written in the last 24h?
    This is the user-visible 'AI adjustments applied' counter."""
    try:
        from ..models.prediction_engine import AILearningLog
        cutoff = datetime.utcnow() - timedelta(hours=24)
        with db_session() as db:
            return (
                db.query(AILearningLog)
                .filter(
                    AILearningLog.event == "weight_changed",
                    AILearningLog.created_at >= cutoff,
                )
                .count()
            )
    except Exception:
        return 0


def _last_event_at(event: str) -> Optional[datetime]:
    """Return the timestamp of the most-recent AILearningLog row of a kind."""
    try:
        from ..models.prediction_engine import AILearningLog
        with db_session() as db:
            row = (
                db.query(AILearningLog)
                .filter(AILearningLog.event == event)
                .order_by(AILearningLog.created_at.desc())
                .first()
            )
            return row.created_at if row else None
    except Exception:
        return None


def _market_session_eta() -> dict[str, Any]:
    """Time-to-next session boundary, sourced from market_status."""
    try:
        from . import market_status
        snap = market_status.get_status()
        return {
            "state": snap.state,
            "is_open": snap.is_open,
            "label": snap.label,
            "seconds_until_next": snap.seconds_until_next,
            "next_open_at": (
                snap.next_open_at.isoformat() if snap.next_open_at else None
            ),
            "next_close_at": (
                snap.next_close_at.isoformat() if snap.next_close_at else None
            ),
        }
    except Exception:
        return {
            "state": "unknown",
            "is_open": False,
            "label": "Unknown",
            "seconds_until_next": None,
            "next_open_at": None,
            "next_close_at": None,
        }


def get_status() -> dict[str, Any]:
    market_ts = _market_data_last_fetch()
    news_ts = _last_news_at()
    learn_ts = _last_learning_at()
    valid_ts = _last_validation_at()
    regime_ts = _last_regime_at()
    ws_ts = _ws_last_broadcast()
    overnight_ts = _last_event_at("overnight_cycle")
    premarket_ts = _last_event_at("pre_market_brief")

    market_age = _seconds_since(market_ts)
    news_age = _seconds_since(news_ts)
    learn_age = _seconds_since(learn_ts)
    valid_age = _seconds_since(valid_ts)
    regime_age = _seconds_since(regime_ts)
    ws_age = _seconds_since(ws_ts)
    overnight_age = _seconds_since(overnight_ts)
    premarket_age = _seconds_since(premarket_ts)

    counts = _prediction_counts()
    learning_updates_24h = _learning_updates_24h()
    session = _market_session_eta()
    is_open = session.get("is_open", False)

    # ML model snapshot — surfaced as a pipeline so the panel makes it
    # obvious whether the engine is using the learned classifier or just rules.
    try:
        from . import ml_confidence
        ml_state = ml_confidence.status()
    except Exception:
        ml_state = {
            "ready": False,
            "trained_at": None,
            "train_samples": 0,
            "cv_auc": None,
            "cv_accuracy": None,
            "min_required_samples": 30,
        }

    pipelines = [
        {
            "key": "market_data",
            "label": "Market data",
            # Quotes only need to be fresh when market is open; outside session
            # the cache is intentionally cold.
            "status": _status_for(
                market_age,
                fresh_thresh=120 if is_open else 7200,
                ok_thresh=600 if is_open else 86400,
            ),
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
                f"{learning_updates_24h} weight adjustments in last 24h"
                if learning_updates_24h
                else f"{counts['validated']} validated of {counts['total_predictions']} predictions"
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
            # Only treat WS as offline if market is open — outside session we
            # don't expect ticks.
            "label": "Live websocket",
            "status": _status_for(
                ws_age,
                fresh_thresh=30 if is_open else 86400,
                ok_thresh=180 if is_open else 86400,
            ),
            "last_at": ws_ts.isoformat() if ws_ts else None,
            "relative": _fmt_relative(ws_age),
            "detail": "tick broadcast to frontend"
            + ("" if is_open else " (idle when market closed)"),
        },
        {
            "key": "overnight",
            "label": "Overnight learning",
            "status": _status_for(overnight_age, fresh_thresh=86400, ok_thresh=172800),
            "last_at": overnight_ts.isoformat() if overnight_ts else None,
            "relative": _fmt_relative(overnight_age),
            "detail": "validation + learning + recalibration after market close",
        },
        {
            "key": "pre_market",
            "label": "Pre-market brief",
            "status": _status_for(premarket_age, fresh_thresh=86400, ok_thresh=172800),
            "last_at": premarket_ts.isoformat() if premarket_ts else None,
            "relative": _fmt_relative(premarket_age),
            "detail": "global cues, sector pulse, gap candidates, verdict",
        },
        {
            "key": "ml_confidence",
            "label": "ML confidence model",
            "status": (
                "fresh"
                if ml_state.get("ready") and ml_state.get("cv_auc") is not None
                else "ok"
                if ml_state.get("ready")
                else "offline"
            ),
            "last_at": ml_state.get("trained_at"),
            "relative": (
                _fmt_relative(_seconds_since(
                    datetime.fromisoformat(ml_state["trained_at"])
                    if ml_state.get("trained_at") else None
                ))
            ),
            "detail": (
                f"XGBoost on {ml_state.get('train_samples', 0)} trades · "
                f"CV AUC {ml_state.get('cv_auc'):.3f}"
                if ml_state.get("ready") and ml_state.get("cv_auc") is not None
                else f"Not enough data yet — {ml_state.get('train_samples', 0)} / "
                     f"{ml_state.get('min_required_samples', 30)} validated trades"
            ),
        },
    ]

    # Health rule: market_data + ai_learning are essential; WS is essential
    # only when market is open.
    essential = {"market_data", "ai_learning"}
    if is_open:
        essential.add("websocket")
    essential_ok = sum(
        1 for p in pipelines if p["key"] in essential and p["status"] in ("fresh", "ok")
    )
    healthy = sum(1 for p in pipelines if p["status"] in ("fresh", "ok"))
    overall = (
        "healthy"
        if essential_ok == len(essential) and healthy >= 5
        else "degraded"
        if healthy >= 3
        else "offline"
    )

    return {
        "overall_status": overall,
        "uptime_seconds": int(time.time() - _START_TS),
        "pipelines": pipelines,
        "predictions": counts,
        "learning_updates_24h": learning_updates_24h,
        "market_session": session,
        "ml_model": {
            "ready": ml_state.get("ready", False),
            "trained_at": ml_state.get("trained_at"),
            "train_samples": ml_state.get("train_samples", 0),
            "min_required_samples": ml_state.get("min_required_samples", 30),
            "cv_auc": ml_state.get("cv_auc"),
            "cv_accuracy": ml_state.get("cv_accuracy"),
        },
        "now": datetime.utcnow().isoformat(),
    }
