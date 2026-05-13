"""Confidence calibration.

Buckets predictions by their original ``confidence`` value (0-100) and
computes the realised win-rate per bucket. The "calibration gap" is the
difference between expected confidence and realised win-rate.

Used both by the dashboard and by the scoring engine to apply a
*calibration correction* on freshly generated confidence scores.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from ..database import db_session
from ..models.prediction_engine import (
    AILearningLog,
    ConfidenceAccuracy,
    PredictionHistory,
    PredictionOutcome,
)


BUCKETS = [(0, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]


def _bucket_for(confidence: float) -> tuple[int, int]:
    for low, high in BUCKETS:
        if low <= confidence < high:
            return low, high
    return BUCKETS[-1]


def recalibrate(mode: Optional[str] = None) -> List[dict]:
    """Refresh ConfidenceAccuracy rows based on current outcomes."""
    out: List[dict] = []
    with db_session() as db:
        modes = [mode] if mode else ["intraday", "swing", "positional"]
        for m in modes:
            stats: Dict[tuple[int, int], dict] = {
                b: {"wins": 0, "losses": 0, "ret": 0.0, "n": 0} for b in BUCKETS
            }
            rows = (
                db.query(PredictionHistory, PredictionOutcome)
                .join(
                    PredictionOutcome,
                    PredictionOutcome.prediction_id == PredictionHistory.id,
                )
                .filter(
                    PredictionHistory.mode == m,
                    PredictionOutcome.outcome.in_(
                        ["WIN", "PARTIAL_WIN", "LOSS", "EXPIRED", "INVALIDATED"]
                    ),
                )
                .all()
            )
            for pred, outcome in rows:
                b = _bucket_for(pred.confidence)
                bucket = stats[b]
                bucket["n"] += 1
                if outcome.outcome in {"WIN", "PARTIAL_WIN"} or (
                    outcome.outcome == "EXPIRED" and (outcome.realized_pct or 0) > 0
                ):
                    bucket["wins"] += 1
                elif outcome.outcome == "LOSS" or (
                    outcome.outcome == "INVALIDATED" and (outcome.realized_pct or 0) < 0
                ):
                    bucket["losses"] += 1
                bucket["ret"] += outcome.realized_pct or 0

            for (lo, hi), s in stats.items():
                n = s["n"]
                wins = s["wins"]
                losses = s["losses"]
                win_rate = (wins / max(wins + losses, 1)) * 100 if (wins + losses) else 0.0
                avg_ret = (s["ret"] / n) if n else 0.0
                midpoint = (lo + min(hi, 100)) / 2.0
                gap = round(midpoint - win_rate, 2)
                existing = (
                    db.query(ConfidenceAccuracy)
                    .filter(
                        ConfidenceAccuracy.bucket_low == lo,
                        ConfidenceAccuracy.bucket_high == hi,
                        ConfidenceAccuracy.mode == m,
                    )
                    .one_or_none()
                )
                if existing is None:
                    existing = ConfidenceAccuracy(
                        bucket_low=lo, bucket_high=hi, mode=m
                    )
                    db.add(existing)
                existing.sample_size = n
                existing.wins = wins
                existing.losses = losses
                existing.win_rate = round(win_rate, 2)
                existing.avg_return_pct = round(avg_ret, 3)
                existing.calibration_gap = gap
                existing.updated_at = datetime.utcnow()
                out.append(
                    {
                        "bucket_low": lo,
                        "bucket_high": hi,
                        "mode": m,
                        "sample_size": n,
                        "wins": wins,
                        "losses": losses,
                        "win_rate": round(win_rate, 2),
                        "avg_return_pct": round(avg_ret, 3),
                        "calibration_gap": gap,
                    }
                )

        db.add(
            AILearningLog(
                event="confidence_recalibrated",
                summary=f"Rebuilt confidence buckets for modes={modes}",
                details={"buckets": out},
            )
        )
    return out


def all_buckets() -> List[dict]:
    with db_session() as db:
        rows = db.query(ConfidenceAccuracy).all()
        return [
            {
                "bucket_low": r.bucket_low,
                "bucket_high": r.bucket_high,
                "mode": r.mode,
                "sample_size": r.sample_size,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "avg_return_pct": r.avg_return_pct,
                "calibration_gap": r.calibration_gap,
            }
            for r in rows
        ]


def calibration_correction(confidence: float, mode: str) -> float:
    """Apply a small correction to a raw confidence score using historical
    calibration. Returns a confidence in [5, 99]."""
    if confidence <= 0:
        return 0.0
    try:
        with db_session() as db:
            row = (
                db.query(ConfidenceAccuracy)
                .filter(
                    ConfidenceAccuracy.bucket_low <= confidence,
                    ConfidenceAccuracy.bucket_high > confidence,
                    ConfidenceAccuracy.mode == mode,
                )
                .one_or_none()
            )
            if row is None or row.sample_size < 5:
                return confidence
            # Damp 50% toward the realised win-rate of this bucket
            adj = confidence - 0.5 * (row.calibration_gap or 0)
            return max(5.0, min(99.0, adj))
    except Exception as exc:
        logger.warning(f"calibration_correction failed: {exc}")
        return confidence
