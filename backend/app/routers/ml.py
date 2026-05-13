"""ML Confidence endpoints — train, status, retrain.

These expose the XGBoost confidence model. ``/status`` is safe to poll for
the dashboard. ``/retrain`` rebuilds the model from the latest data — it is
expected to be called by the scheduler weekly and on demand from the UI.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import ml_confidence


router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.get("/status")
def ml_status():
    """Snapshot of the trained model — accuracy, AUC, feature importance.

    The CV metrics are walk-forward (no peeking forward) so these are the
    honest out-of-sample numbers, not over-fitted in-sample ones.
    """
    return ml_confidence.status()


@router.post("/retrain")
def ml_retrain():
    """Force a retrain from the latest validated trades.

    Returns the new model metrics. If there aren't enough validated trades
    yet, returns ``trained=False`` with an explanatory message — never an
    error code, so the UI can render the message gracefully.
    """
    try:
        return ml_confidence.retrain()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"retrain failed: {exc}")
