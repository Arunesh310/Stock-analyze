"""Overnight Learning Engine.

Runs the heavy-analysis pipeline after the Indian market closes (15:30 IST).
The pipeline is a single deterministic sequence that:

1. Marks any expired predictions.
2. Validates every OPEN prediction against the day's close.
3. Refreshes setup / sector / indicator quality scores (the learning cycle).
4. Re-buckets the confidence calibration table.
5. Snapshots the closing market regime.

A summary of what changed is persisted as an ``AILearningLog`` row with
``event="overnight_cycle"`` so the front-end can render a complete audit
trail of overnight activity.

Idempotent — safe to run multiple times in the same window.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict

from loguru import logger

from ..database import db_session
from ..models.prediction_engine import AILearningLog
from . import (
    confidence_engine,
    learning_engine,
    market_regime,
    validation_engine,
)


def _safe_call(name: str, fn, *args, **kwargs):
    """Run ``fn`` but never let the cycle die on a partial failure."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"overnight_engine[{name}] failed: {exc}")
        return None


def run_overnight_cycle() -> Dict[str, Any]:
    """Execute the full overnight learning pipeline. Returns the summary."""
    started = datetime.utcnow()
    t0 = time.time()

    expired = _safe_call("expire_stale", validation_engine.expire_stale_predictions)
    validation = _safe_call("validate", validation_engine.validate_all_open, limit=500)
    learning = _safe_call("learning", learning_engine.run_learning_cycle)
    calibration = _safe_call("confidence", confidence_engine.recalibrate)
    regime = _safe_call("regime", market_regime.persist_regime)

    duration_s = round(time.time() - t0, 2)

    summary_lines: list[str] = []
    val_dict: dict = {}
    if validation is not None:
        # Use mode="json" so any datetime fields become ISO strings — otherwise
        # they crash the AILearningLog JSON column on commit.
        if hasattr(validation, "model_dump"):
            val_dict = validation.model_dump(mode="json")
        else:
            val_dict = getattr(validation, "__dict__", {}) or {}
            # belt-and-braces: stringify any non-JSON-able values
            for k, v in list(val_dict.items()):
                if hasattr(v, "isoformat"):
                    val_dict[k] = v.isoformat()
        summary_lines.append(
            f"Validated {val_dict.get('scanned', 0)} open trades — "
            f"{val_dict.get('closed', 0)} closed "
            f"({val_dict.get('new_wins', 0)} W / {val_dict.get('new_losses', 0)} L)"
        )
    if learning:
        summary_lines.append(
            f"Refreshed {learning.get('setups_updated', 0)} setups, "
            f"{learning.get('indicators_updated', 0)} indicator/regime pairs, "
            f"{learning.get('weight_changes', 0)} weight adjustments"
        )
    if calibration:
        summary_lines.append(f"Recalibrated {len(calibration)} confidence buckets")
    if expired:
        summary_lines.append(f"Expired {expired} stale predictions")
    if regime:
        regime_label = getattr(regime, "regime", None) or (
            regime.get("regime") if isinstance(regime, dict) else None
        )
        if regime_label:
            summary_lines.append(f"Closing regime: {regime_label.replace('_', ' ')}")

    summary = "; ".join(summary_lines) if summary_lines else "Overnight cycle ran with no changes."

    details = {
        "started_at": started.isoformat(),
        "duration_seconds": duration_s,
        "expired": expired,
        "validation": val_dict,
        "learning": learning,
        "confidence_buckets": len(calibration) if calibration else 0,
        "closing_regime": (
            getattr(regime, "regime", None)
            if regime is not None and not isinstance(regime, dict)
            else (regime.get("regime") if isinstance(regime, dict) else None)
        ),
    }

    try:
        with db_session() as db:
            db.add(
                AILearningLog(
                    event="overnight_cycle",
                    summary=summary,
                    details=details,
                    impact_score=float(
                        (val_dict.get("new_wins") or 0)
                        - (val_dict.get("new_losses") or 0)
                    ),
                )
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"overnight_engine could not write log: {exc}")

    logger.info(f"overnight_cycle complete — {summary}")
    return {
        "ok": True,
        "summary": summary,
        "duration_seconds": duration_s,
        **details,
    }


def latest_run() -> Dict[str, Any] | None:
    """Return the most-recent ``overnight_cycle`` log entry (or None)."""
    try:
        with db_session() as db:
            row = (
                db.query(AILearningLog)
                .filter(AILearningLog.event == "overnight_cycle")
                .order_by(AILearningLog.created_at.desc())
                .first()
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "summary": row.summary,
                "details": row.details or {},
                "impact_score": row.impact_score,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
    except Exception as exc:
        logger.warning(f"overnight_engine.latest_run failed: {exc}")
        return None
