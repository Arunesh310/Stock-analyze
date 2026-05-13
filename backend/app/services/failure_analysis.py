"""Structured Failure Analysis Reports.

For every closed prediction this module produces a single "Failure Analysis
Report" — a human-readable narrative tying together:

- WHAT was predicted (action, confidence, entry/SL/targets, regime)
- WHAT actually happened (outcome, realised PnL %, MFE / MAE)
- WHY it failed (LearningFeedback category + a short list of contributing
  factors derived from the snapshot vs the resolved state)
- WHAT THE AI LEARNED in response (matching AILearningLog weight_changed
  rows recorded within ±2h of validation)

Nothing is computed from scratch — we reuse data already written by
``validation_engine`` and ``learning_engine`` so this stays cheap.

This is the user-visible bridge between "trade failed" and "system
adapted in response."
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import db_session
from ..models.prediction_engine import (
    AILearningLog,
    LearningFeedback,
    PredictionHistory,
    PredictionOutcome,
)


# Maps the terse `category` stored on LearningFeedback to a friendly title
# the dashboard can render in the failure card.
_CATEGORY_TITLES: Dict[str, str] = {
    "no_entry": "Entry zone never reached",
    "regime_mismatch": "Fought the market regime",
    "negative_news": "Negative news overrode the setup",
    "positive_news": "Positive news overrode a short setup",
    "weak_breadth": "Market breadth was negative",
    "overextended": "Bought after the move was already extended",
    "false_breakout": "Classic false breakout — went in our favour, then reversed",
    "sector_weakness": "Sector was already rolling over",
    "sector_strength": "Sector was running too hard to short",
    "volatility_spike": "Volatility was too high for the plan",
    "indicator_failure": "Indicator setup did not follow through",
    "trend_followthrough": "Trade reached target 2 — full trend follow-through",
    "trend_alignment": "Regime tailwind carried the trade to target 1",
    "sector_tailwind": "Sector strength carried the trade to target 1",
    "setup_followthrough": "Setup paid out at first target",
    "unclassified": "No single dominant driver",
}


def _title_for(category: str) -> str:
    return _CATEGORY_TITLES.get(category, category.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Internal: derive a short list of contributing factors per prediction
# ---------------------------------------------------------------------------


def _contributing_factors(
    pred: PredictionHistory, outcome: PredictionOutcome
) -> List[str]:
    """Heuristic checklist of *why* this specific trade probably failed.

    Each item is a short explanatory bullet (10-15 words) keyed off the
    snapshot data we already store. Order: most-impactful first.
    """
    ind = pred.indicators_snapshot or {}
    factors: List[str] = []

    if not outcome.entry_triggered:
        factors.append("Entry zone never traded — signal never converted to a position.")
        return factors

    if (outcome.max_favorable_pct or 0) > 1.0 and outcome.stoploss_hit:
        factors.append(
            f"Move initially favoured us by {outcome.max_favorable_pct:.1f}% before reversing — "
            f"textbook false-breakout pattern."
        )

    if pred.market_regime in {"bearish_trend", "risk_off"} and pred.action == "BUY":
        factors.append(
            f"Regime was {pred.market_regime.replace('_', ' ')} — buying long into selling pressure."
        )
    elif pred.market_regime in {"bullish_trend", "risk_on"} and pred.action == "SELL":
        factors.append(
            f"Regime was {pred.market_regime.replace('_', ' ')} — shorting a trending tape."
        )

    adv = pred.breadth_advancers or 0
    dec = pred.breadth_decliners or 0
    if adv + dec > 0 and dec > adv * 1.3 and pred.action == "BUY":
        factors.append(
            f"Breadth was negative — only {adv} advancers vs {dec} decliners across the index."
        )

    if (pred.sector_strength or 0) < -2 and pred.action == "BUY":
        factors.append(
            f"Sector strength was {pred.sector_strength:+.1f} — the group was already weakening."
        )
    elif (pred.sector_strength or 0) > 2 and pred.action == "SELL":
        factors.append(
            f"Sector strength was {pred.sector_strength:+.1f} — too much demand to fade."
        )

    if (pred.news_sentiment or 0) < -0.2 and pred.action == "BUY":
        factors.append(
            f"News sentiment was {pred.news_sentiment:+.2f} — clearly negative backdrop."
        )
    elif (pred.news_sentiment or 0) > 0.2 and pred.action == "SELL":
        factors.append(
            f"News sentiment was {pred.news_sentiment:+.2f} — short into a positive narrative."
        )

    rsi = ind.get("rsi")
    if rsi is not None and rsi >= 75 and pred.action == "BUY":
        factors.append(f"RSI was already {rsi:.0f} at entry — move was overextended.")
    elif rsi is not None and rsi <= 25 and pred.action == "SELL":
        factors.append(f"RSI was already {rsi:.0f} at entry — too oversold to short.")

    adx = ind.get("adx")
    if adx is not None and adx < 18:
        factors.append(f"ADX was {adx:.0f} — no trend strength to ride.")

    atr = pred.atr_at_entry or 0
    if atr and pred.entry_ref and atr / pred.entry_ref > 0.04:
        factors.append(
            f"ATR was {atr/pred.entry_ref*100:.1f}% of price — daily noise exceeded the trade plan."
        )

    if not factors:
        factors.append(
            "No single obvious cause — indicator setup simply did not follow through."
        )

    return factors[:5]


# ---------------------------------------------------------------------------
# Internal: find learning that was applied AFTER a failure
# ---------------------------------------------------------------------------


def _learning_applied_for(
    db: Session,
    pred: PredictionHistory,
    outcome: PredictionOutcome,
) -> List[Dict[str, Any]]:
    """Return AILearningLog ``weight_changed`` entries written within a 24h
    window after the prediction was validated and whose target (setup,
    indicator) plausibly overlaps with this prediction.
    """
    if outcome.validated_at is None:
        return []
    start = outcome.validated_at - timedelta(hours=2)
    end = outcome.validated_at + timedelta(hours=24)
    rows = (
        db.query(AILearningLog)
        .filter(
            AILearningLog.event == "weight_changed",
            AILearningLog.created_at >= start,
            AILearningLog.created_at <= end,
        )
        .order_by(AILearningLog.created_at.asc())
        .all()
    )
    if not rows:
        return []

    # Patterns / indicators we want to filter changes against — anything else
    # is unrelated and would just be noise on the failure card.
    related_names: set[str] = set()
    related_names.update((pred.detected_patterns or []))
    ind = pred.indicators_snapshot or {}
    if ind.get("rsi") is not None:
        related_names.add("rsi")
    if ind.get("macd") is not None:
        related_names.add("macd")
    if ind.get("adx") is not None:
        related_names.add("adx")
    if ind.get("ema20") is not None:
        related_names.add("ema_stack")
    if ind.get("bb_upper") is not None:
        related_names.add("bollinger")

    related_lc = {n.lower() for n in related_names if n}

    out: List[Dict[str, Any]] = []
    for r in rows:
        details = r.details or {}
        name = str(details.get("name", "")).lower()
        if not name:
            continue
        if related_lc and (name in related_lc or any(n in name for n in related_lc)):
            out.append(
                {
                    "log_id": r.id,
                    "event": r.event,
                    "summary": r.summary,
                    "name": details.get("name"),
                    "type": details.get("type"),
                    "before": details.get("before"),
                    "after": details.get("after"),
                    "win_rate": details.get("win_rate"),
                    "sample_size": details.get("sample_size"),
                    "impact_score": r.impact_score,
                    "created_at": r.created_at.isoformat()
                    if r.created_at
                    else None,
                }
            )
    return out


# ---------------------------------------------------------------------------
# Internal: build a single failure (or success) report
# ---------------------------------------------------------------------------


def _build_report(
    pred: PredictionHistory,
    outcome: PredictionOutcome,
    feedback: Optional[LearningFeedback],
    db: Session,
) -> Dict[str, Any]:
    is_failure = outcome.outcome in {"LOSS", "INVALIDATED", "EXPIRED"} and (
        outcome.realized_pct or 0
    ) <= 0
    factors = _contributing_factors(pred, outcome) if is_failure else []
    learning = _learning_applied_for(db, pred, outcome) if is_failure else []

    category = feedback.category if feedback else (
        "indicator_failure" if is_failure else "unclassified"
    )
    return {
        "prediction_id": pred.id,
        "symbol": pred.symbol,
        "sector": pred.sector,
        "action": pred.action,
        "mode": pred.mode,
        "confidence_at_signal": round(pred.confidence, 1),
        "predicted_at": pred.created_at.isoformat() if pred.created_at else None,
        "validated_at": outcome.validated_at.isoformat()
        if outcome.validated_at
        else None,
        "entry_ref": pred.entry_ref,
        "stoploss": pred.stoploss,
        "target1": pred.target1,
        "target2": pred.target2,
        "rr": pred.rr,
        "outcome": outcome.outcome,
        "realized_pct": outcome.realized_pct,
        "max_favorable_pct": outcome.max_favorable_pct,
        "max_adverse_pct": outcome.max_adverse_pct,
        "target1_hit": outcome.target1_hit,
        "target2_hit": outcome.target2_hit,
        "stoploss_hit": outcome.stoploss_hit,
        "entry_triggered": outcome.entry_triggered,
        "holding_days": outcome.holding_days,
        "market_regime": pred.market_regime,
        "news_sentiment": pred.news_sentiment,
        "sector_strength": pred.sector_strength,
        "breadth_advancers": pred.breadth_advancers,
        "breadth_decliners": pred.breadth_decliners,
        "detected_patterns": pred.detected_patterns or [],
        "category": category,
        "category_title": _title_for(category),
        "narrative": feedback.reason if feedback else None,
        "contributing_factors": factors,
        "learning_applied": learning,
        "is_failure": is_failure,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def recent_failures(
    limit: int = 20,
    mode: Optional[str] = None,
    include_successes: bool = False,
) -> List[Dict[str, Any]]:
    """Return the most-recent closed predictions packaged as failure reports.

    By default only LOSS / EXPIRED-negative / INVALIDATED rows are returned.
    Setting ``include_successes`` is useful for a unified "Recent Outcomes"
    view that mixes wins and losses.
    """
    try:
        with db_session() as db:
            q = (
                db.query(PredictionHistory, PredictionOutcome)
                .join(
                    PredictionOutcome,
                    PredictionOutcome.prediction_id == PredictionHistory.id,
                )
            )
            if not include_successes:
                q = q.filter(
                    PredictionOutcome.outcome.in_(["LOSS", "EXPIRED", "INVALIDATED"])
                )
            else:
                q = q.filter(
                    PredictionOutcome.outcome.in_(
                        ["WIN", "PARTIAL_WIN", "LOSS", "EXPIRED", "INVALIDATED"]
                    )
                )
            if mode:
                q = q.filter(PredictionHistory.mode == mode)

            pairs = (
                q.order_by(PredictionOutcome.validated_at.desc())
                .limit(limit)
                .all()
            )

            # Resolve the LearningFeedback rows in one query to avoid N+1.
            pred_ids = [p.id for p, _ in pairs]
            fb_map: Dict[int, LearningFeedback] = {}
            if pred_ids:
                fbs = (
                    db.query(LearningFeedback)
                    .filter(LearningFeedback.prediction_id.in_(pred_ids))
                    .all()
                )
                for fb in fbs:
                    # Multiple feedbacks possible — keep the latest.
                    existing = fb_map.get(fb.prediction_id)
                    if existing is None or (
                        fb.created_at and existing.created_at and fb.created_at > existing.created_at
                    ):
                        fb_map[fb.prediction_id] = fb

            reports = [
                _build_report(pred, outcome, fb_map.get(pred.id), db)
                for pred, outcome in pairs
            ]
            return reports
    except Exception as exc:
        logger.warning(f"recent_failures failed: {exc}")
        return []


def top_failure_reasons(
    limit: int = 12,
    days: int = 30,
    mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Aggregate the dominant failure categories over a recent window.

    Returns one row per (category, market_condition) with a count, the
    average confidence at signal (so the user can see where the AI was
    overconfident), and a representative example reason.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        with db_session() as db:
            q = (
                db.query(LearningFeedback, PredictionHistory)
                .join(
                    PredictionHistory,
                    PredictionHistory.id == LearningFeedback.prediction_id,
                )
                .filter(
                    LearningFeedback.outcome == "LOSS",
                    LearningFeedback.created_at >= cutoff,
                )
            )
            if mode:
                q = q.filter(PredictionHistory.mode == mode)
            rows = q.all()
            if not rows:
                return []
            counts: Dict[str, dict] = {}
            for fb, _pred in rows:
                key = fb.category
                bucket = counts.setdefault(
                    key,
                    {
                        "category": key,
                        "title": _title_for(key),
                        "count": 0,
                        "avg_confidence_at_signal": 0.0,
                        "example": fb.reason,
                        "regime_breakdown": defaultdict(int),
                    },
                )
                bucket["count"] += 1
                bucket["avg_confidence_at_signal"] += fb.confidence_at_signal or 0.0
                regime = fb.market_condition or "unknown"
                bucket["regime_breakdown"][regime] += 1

            out = []
            for b in counts.values():
                n = max(b["count"], 1)
                out.append(
                    {
                        "category": b["category"],
                        "title": b["title"],
                        "count": b["count"],
                        "avg_confidence_at_signal": round(
                            b["avg_confidence_at_signal"] / n, 1
                        ),
                        "example": b["example"],
                        "regime_breakdown": dict(b["regime_breakdown"]),
                    }
                )
            out.sort(key=lambda x: x["count"], reverse=True)
            return out[:limit]
    except Exception as exc:
        logger.warning(f"top_failure_reasons failed: {exc}")
        return []


def failure_report(prediction_id: int) -> Optional[Dict[str, Any]]:
    """Single full-detail report for one prediction (failure or success)."""
    try:
        with db_session() as db:
            row = (
                db.query(PredictionHistory, PredictionOutcome)
                .join(
                    PredictionOutcome,
                    PredictionOutcome.prediction_id == PredictionHistory.id,
                )
                .filter(PredictionHistory.id == prediction_id)
                .one_or_none()
            )
            if row is None:
                return None
            pred, outcome = row
            fb = (
                db.query(LearningFeedback)
                .filter(LearningFeedback.prediction_id == prediction_id)
                .order_by(LearningFeedback.created_at.desc())
                .first()
            )
            return _build_report(pred, outcome, fb, db)
    except Exception as exc:
        logger.warning(f"failure_report failed: {exc}")
        return None
