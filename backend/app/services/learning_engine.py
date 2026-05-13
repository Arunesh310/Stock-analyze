"""Failure analysis + adaptive weight learning.

After every validation cycle this module:

1. Re-aggregates per-setup, per-sector, per-indicator and per-regime
   performance from closed predictions.
2. Updates ``SignalQualityScore``, ``SectorPerformance``,
   ``IndicatorPerformance`` rows.
3. Adjusts ``weight_multiplier`` / ``weight`` such that consistently
   failing setups / indicators get down-weighted (and successful ones
   get up-weighted, capped at +/-50%).
4. Writes a human-readable summary into ``AILearningLog``.

The adjusted weights are consumed by ``scoring_engine`` which the signal
engine reads at signal-generation time.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from loguru import logger
from sqlalchemy.orm import Session

from ..database import db_session
from ..models.prediction_engine import (
    AILearningLog,
    IndicatorPerformance,
    LearningFeedback,
    PredictionHistory,
    PredictionOutcome,
    SectorPerformance,
    SignalQualityScore,
)


# ---------------------------------------------------------------------------
# Setup name extraction
# ---------------------------------------------------------------------------


def _setup_name_for(pred: PredictionHistory) -> str:
    """Coarse-grained 'setup' identity used to group similar trades."""
    pats = pred.detected_patterns or []
    if not pats:
        if (pred.indicators_snapshot or {}).get("rsi") and pred.indicators_snapshot["rsi"] >= 70:
            return "RSI Overbought"
        if (pred.indicators_snapshot or {}).get("rsi") and pred.indicators_snapshot["rsi"] <= 30:
            return "RSI Oversold"
        return "Generic Setup"
    # Use the first pattern (most specific) as the setup label
    return pats[0]


# ---------------------------------------------------------------------------
# Setup quality
# ---------------------------------------------------------------------------


def _refresh_setup_quality(db: Session) -> tuple[List[dict], List[dict]]:
    """Refresh setup quality scores. Returns ``(rows, deltas)``.

    ``deltas`` is a list of ``{setup, mode, before, after, win_rate, sample_size}``
    for setups whose weight multiplier moved by more than 0.05.
    """
    rows = (
        db.query(PredictionHistory, PredictionOutcome)
        .join(PredictionOutcome, PredictionOutcome.prediction_id == PredictionHistory.id)
        .filter(
            PredictionOutcome.outcome.in_(
                ["WIN", "PARTIAL_WIN", "LOSS", "EXPIRED", "INVALIDATED"]
            )
        )
        .all()
    )

    buckets: Dict[tuple[str, str], Dict] = defaultdict(
        lambda: {"wins": 0, "losses": 0, "ret": 0.0, "n": 0}
    )
    for pred, outcome in rows:
        key = (_setup_name_for(pred), pred.mode)
        b = buckets[key]
        b["n"] += 1
        b["ret"] += outcome.realized_pct or 0
        if outcome.outcome in {"WIN", "PARTIAL_WIN"}:
            b["wins"] += 1
        elif outcome.outcome == "LOSS":
            b["losses"] += 1
        elif outcome.outcome == "EXPIRED":
            if (outcome.realized_pct or 0) > 0:
                b["wins"] += 1
            else:
                b["losses"] += 1

    out: List[dict] = []
    deltas: List[dict] = []
    for (setup, mode), b in buckets.items():
        total = b["wins"] + b["losses"] or 1
        wr = b["wins"] / total * 100
        avg = b["ret"] / b["n"] if b["n"] else 0
        # Quality: 0..100 — combines win-rate and avg return
        quality = max(0.0, min(100.0, wr * 0.6 + (avg + 3) * 5))
        # Weight: 0.5..1.5, depends on edge above 50% win-rate
        weight = max(0.5, min(1.5, 1.0 + (wr - 50) / 100))
        # Need at least 4 samples before we trust the edge enough to move weight
        if b["n"] < 4:
            weight = 1.0
        # Aggressive failure penalty: 5+ trials with <25% wr → floor immediately
        if b["n"] >= 5 and wr < 25:
            weight = 0.5
        # And reward sustained winners: 5+ trials with >70% wr → push to ceiling
        elif b["n"] >= 5 and wr > 70:
            weight = max(weight, 1.4)

        row = (
            db.query(SignalQualityScore)
            .filter(
                SignalQualityScore.setup_name == setup,
                SignalQualityScore.mode == mode,
            )
            .one_or_none()
        )
        prev_weight = float(row.weight_multiplier) if row is not None else 1.0
        if row is None:
            row = SignalQualityScore(setup_name=setup, mode=mode)
            db.add(row)
        row.sample_size = b["n"]
        row.wins = b["wins"]
        row.losses = b["losses"]
        row.win_rate = round(wr, 2)
        row.avg_return_pct = round(avg, 3)
        row.quality_score = round(quality, 2)
        row.weight_multiplier = round(weight, 3)
        row.last_updated = datetime.utcnow()
        out.append(
            {
                "setup_name": setup,
                "mode": mode,
                "sample_size": b["n"],
                "wins": b["wins"],
                "losses": b["losses"],
                "win_rate": round(wr, 2),
                "avg_return_pct": round(avg, 3),
                "quality_score": round(quality, 2),
                "weight_multiplier": round(weight, 3),
            }
        )
        if abs(round(weight, 3) - round(prev_weight, 3)) >= 0.05:
            deltas.append(
                {
                    "type": "setup",
                    "name": setup,
                    "mode": mode,
                    "before": round(prev_weight, 3),
                    "after": round(weight, 3),
                    "win_rate": round(wr, 2),
                    "sample_size": b["n"],
                }
            )
    return out, deltas


# ---------------------------------------------------------------------------
# Sector performance
# ---------------------------------------------------------------------------


def _refresh_sector_performance(db: Session) -> List[dict]:
    rows = (
        db.query(PredictionHistory, PredictionOutcome)
        .join(PredictionOutcome, PredictionOutcome.prediction_id == PredictionHistory.id)
        .filter(
            PredictionOutcome.outcome.in_(
                ["WIN", "PARTIAL_WIN", "LOSS", "EXPIRED", "INVALIDATED"]
            )
        )
        .all()
    )
    buckets: Dict[tuple[str, str], Dict] = defaultdict(
        lambda: {"wins": 0, "losses": 0, "ret": 0.0, "n": 0}
    )
    for pred, outcome in rows:
        key = (pred.sector or "Other", pred.mode)
        b = buckets[key]
        b["n"] += 1
        b["ret"] += outcome.realized_pct or 0
        if outcome.outcome in {"WIN", "PARTIAL_WIN"}:
            b["wins"] += 1
        elif outcome.outcome == "LOSS":
            b["losses"] += 1

    out: List[dict] = []
    for (sec, mode), b in buckets.items():
        total = b["wins"] + b["losses"] or 1
        wr = b["wins"] / total * 100
        avg = b["ret"] / b["n"] if b["n"] else 0
        row = (
            db.query(SectorPerformance)
            .filter(
                SectorPerformance.sector == sec,
                SectorPerformance.mode == mode,
            )
            .one_or_none()
        )
        if row is None:
            row = SectorPerformance(sector=sec, mode=mode)
            db.add(row)
        row.sample_size = b["n"]
        row.wins = b["wins"]
        row.losses = b["losses"]
        row.win_rate = round(wr, 2)
        row.avg_return_pct = round(avg, 3)
        row.last_updated = datetime.utcnow()
        out.append(
            {
                "sector": sec,
                "mode": mode,
                "sample_size": b["n"],
                "wins": b["wins"],
                "losses": b["losses"],
                "win_rate": round(wr, 2),
                "avg_return_pct": round(avg, 3),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Indicator performance
# ---------------------------------------------------------------------------


# Map of indicator -> predicate (closure built per-prediction) that returns
# True iff the indicator was "bullish" at signal time.
def _indicator_signals(pred: PredictionHistory) -> Dict[str, str]:
    """Return dict of indicator -> "bullish" / "bearish" / "neutral"."""
    out: Dict[str, str] = {}
    ind = pred.indicators_snapshot or {}
    last = pred.entry_ref

    rsi = ind.get("rsi")
    if rsi is not None:
        if rsi > 60:
            out["rsi"] = "bullish"
        elif rsi < 40:
            out["rsi"] = "bearish"
        else:
            out["rsi"] = "neutral"

    macd = ind.get("macd")
    macd_sig = ind.get("macd_signal")
    if macd is not None and macd_sig is not None:
        out["macd"] = "bullish" if macd > macd_sig else "bearish"

    ema20 = ind.get("ema20")
    ema50 = ind.get("ema50")
    ema200 = ind.get("ema200")
    if ema20 and ema50 and ema200:
        if ema20 > ema50 > ema200:
            out["ema_stack"] = "bullish"
        elif ema20 < ema50 < ema200:
            out["ema_stack"] = "bearish"
        else:
            out["ema_stack"] = "neutral"

    bb_u = ind.get("bb_upper")
    bb_l = ind.get("bb_lower")
    if last and bb_u and bb_l:
        if last >= bb_u:
            out["bollinger"] = "bullish"
        elif last <= bb_l:
            out["bollinger"] = "bearish"

    adx = ind.get("adx")
    if adx is not None:
        out["adx"] = "trending" if adx > 25 else "ranging"

    for p in pred.detected_patterns or []:
        out[f"pattern:{p}"] = "bullish" if pred.action == "BUY" else "bearish"

    return out


def _refresh_indicator_performance(db: Session) -> tuple[List[dict], List[dict]]:
    rows = (
        db.query(PredictionHistory, PredictionOutcome)
        .join(PredictionOutcome, PredictionOutcome.prediction_id == PredictionHistory.id)
        .filter(
            PredictionOutcome.outcome.in_(
                ["WIN", "PARTIAL_WIN", "LOSS", "EXPIRED", "INVALIDATED"]
            )
        )
        .all()
    )
    buckets: Dict[tuple[str, str, str], Dict] = defaultdict(
        lambda: {"wins": 0, "losses": 0, "n": 0}
    )
    for pred, outcome in rows:
        regime = pred.market_regime or "unknown"
        won = outcome.outcome in {"WIN", "PARTIAL_WIN"} or (
            outcome.outcome == "EXPIRED" and (outcome.realized_pct or 0) > 0
        )
        lost = outcome.outcome == "LOSS" or (
            outcome.outcome == "EXPIRED" and (outcome.realized_pct or 0) < 0
        )
        for ind, state in _indicator_signals(pred).items():
            # Only count when the indicator was *aligned* with the action.
            aligned = (
                (state == "bullish" and pred.action == "BUY")
                or (state == "bearish" and pred.action == "SELL")
                or state in {"trending"}
            )
            if not aligned:
                continue
            for regime_key in (regime, "any"):
                b = buckets[(ind, regime_key, pred.mode)]
                b["n"] += 1
                if won:
                    b["wins"] += 1
                elif lost:
                    b["losses"] += 1

    out: List[dict] = []
    deltas: List[dict] = []
    for (ind, regime, mode), b in buckets.items():
        total = b["wins"] + b["losses"] or 1
        wr = b["wins"] / total * 100
        edge = round((wr - 50) / 50, 3)  # -1..+1
        # Map edge to a weight in [0.5, 1.5]
        if b["n"] < 4:
            weight = 1.0
        else:
            weight = max(0.5, min(1.5, 1.0 + edge * 0.5))
        # Aggressive penalty for repeated failures
        if b["n"] >= 5 and wr < 30:
            weight = 0.5
        elif b["n"] >= 5 and wr > 70:
            weight = max(weight, 1.4)
        row = (
            db.query(IndicatorPerformance)
            .filter(
                IndicatorPerformance.indicator == ind,
                IndicatorPerformance.regime == regime,
                IndicatorPerformance.mode == mode,
            )
            .one_or_none()
        )
        prev_weight = float(row.weight) if row is not None else 1.0
        if row is None:
            row = IndicatorPerformance(indicator=ind, regime=regime, mode=mode)
            db.add(row)
        row.sample_size = b["n"]
        row.wins = b["wins"]
        row.losses = b["losses"]
        row.win_rate = round(wr, 2)
        row.edge_score = edge
        row.weight = round(weight, 3)
        row.last_updated = datetime.utcnow()
        out.append(
            {
                "indicator": ind,
                "regime": regime,
                "mode": mode,
                "sample_size": b["n"],
                "wins": b["wins"],
                "losses": b["losses"],
                "win_rate": round(wr, 2),
                "edge_score": edge,
                "weight": round(weight, 3),
            }
        )
        if abs(round(weight, 3) - round(prev_weight, 3)) >= 0.05:
            deltas.append(
                {
                    "type": "indicator",
                    "name": ind,
                    "regime": regime,
                    "mode": mode,
                    "before": round(prev_weight, 3),
                    "after": round(weight, 3),
                    "win_rate": round(wr, 2),
                    "sample_size": b["n"],
                }
            )
    return out, deltas


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _humanise_delta(d: dict) -> str:
    """Translate a weight-change dict into a one-line summary."""
    direction = "lifted" if d["after"] > d["before"] else "reduced"
    if d["type"] == "indicator":
        regime = d.get("regime", "any")
        regime_str = f"in {regime.replace('_', ' ')} regime" if regime not in {"any", "unknown"} else "across regimes"
        return (
            f"{d['name'].upper()} weight {direction} {d['before']:.2f} → {d['after']:.2f} "
            f"{regime_str} (win-rate {d['win_rate']:.0f}%, n={d['sample_size']})"
        )
    return (
        f"Setup '{d['name']}' weight {direction} {d['before']:.2f} → {d['after']:.2f} "
        f"on {d['mode']} (win-rate {d['win_rate']:.0f}%, n={d['sample_size']})"
    )


def run_learning_cycle() -> dict:
    """Re-run all learning aggregations and emit transparent change logs.

    Each cycle writes one summary log + one individual log per non-trivial
    weight change so users can audit exactly *what* the AI updated.
    """
    out: Dict[str, object] = {}
    try:
        with db_session() as db:
            setups, setup_deltas = _refresh_setup_quality(db)
            sectors = _refresh_sector_performance(db)
            indicators, ind_deltas = _refresh_indicator_performance(db)
            all_deltas = setup_deltas + ind_deltas
            out = {
                "setups_updated": len(setups),
                "sectors_updated": len(sectors),
                "indicators_updated": len(indicators),
                "weight_changes": len(all_deltas),
            }
            # One per material change for fine-grained audit trail
            for d in all_deltas[:50]:  # cap to avoid log spam
                impact = abs(d["after"] - d["before"]) * d["sample_size"]
                db.add(
                    AILearningLog(
                        event="weight_changed",
                        summary=_humanise_delta(d),
                        details=d,
                        impact_score=round(impact, 3),
                    )
                )
            db.add(
                AILearningLog(
                    event="weights_adjusted",
                    summary=(
                        f"Learning cycle: refreshed {len(setups)} setups, "
                        f"{len(sectors)} sectors, {len(indicators)} indicator/regime pairs"
                        + (f", {len(all_deltas)} weight changes" if all_deltas else "")
                    ),
                    details=out,
                )
            )
    except Exception as exc:
        logger.warning(f"run_learning_cycle failed: {exc}")
    return out


def setup_quality(mode: str | None = None) -> List[dict]:
    with db_session() as db:
        q = db.query(SignalQualityScore)
        if mode:
            q = q.filter(SignalQualityScore.mode == mode)
        return [
            {
                "setup_name": r.setup_name,
                "mode": r.mode,
                "sample_size": r.sample_size,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "avg_return_pct": r.avg_return_pct,
                "quality_score": r.quality_score,
                "weight_multiplier": r.weight_multiplier,
            }
            for r in q.order_by(SignalQualityScore.quality_score.desc()).all()
        ]


def indicator_performance(mode: str | None = None, regime: str | None = None) -> List[dict]:
    with db_session() as db:
        q = db.query(IndicatorPerformance)
        if mode:
            q = q.filter(IndicatorPerformance.mode == mode)
        if regime:
            q = q.filter(IndicatorPerformance.regime == regime)
        return [
            {
                "indicator": r.indicator,
                "regime": r.regime,
                "mode": r.mode,
                "sample_size": r.sample_size,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "edge_score": r.edge_score,
                "weight": r.weight,
            }
            for r in q.order_by(IndicatorPerformance.edge_score.desc()).all()
        ]


def sector_performance(mode: str | None = None) -> List[dict]:
    with db_session() as db:
        q = db.query(SectorPerformance)
        if mode:
            q = q.filter(SectorPerformance.mode == mode)
        return [
            {
                "sector": r.sector,
                "mode": r.mode,
                "sample_size": r.sample_size,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "avg_return_pct": r.avg_return_pct,
            }
            for r in q.order_by(SectorPerformance.win_rate.desc()).all()
        ]


def feedback_recent(limit: int = 100, outcome: str | None = None) -> List[dict]:
    with db_session() as db:
        q = db.query(LearningFeedback)
        if outcome:
            q = q.filter(LearningFeedback.outcome == outcome)
        rows = q.order_by(LearningFeedback.created_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "prediction_id": r.prediction_id,
                "outcome": r.outcome,
                "category": r.category,
                "reason": r.reason,
                "market_condition": r.market_condition,
                "sector_condition": r.sector_condition,
                "confidence_at_signal": r.confidence_at_signal,
                "created_at": r.created_at,
            }
            for r in rows
        ]


def feedback_top_categories(outcome: str = "LOSS", limit: int = 20) -> List[dict]:
    with db_session() as db:
        rows = (
            db.query(LearningFeedback)
            .filter(LearningFeedback.outcome == outcome)
            .all()
        )
        counts: Dict[str, int] = defaultdict(int)
        sample_reason: Dict[str, str] = {}
        for r in rows:
            counts[r.category] += 1
            sample_reason.setdefault(r.category, r.reason)
        items = [
            {"category": k, "count": v, "example": sample_reason[k]}
            for k, v in counts.items()
        ]
        items.sort(key=lambda x: x["count"], reverse=True)
        return items[:limit]


def learning_logs(limit: int = 100) -> List[dict]:
    with db_session() as db:
        rows = (
            db.query(AILearningLog)
            .order_by(AILearningLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "event": r.event,
                "summary": r.summary,
                "details": r.details or {},
                "impact_score": r.impact_score,
                "created_at": r.created_at,
            }
            for r in rows
        ]
