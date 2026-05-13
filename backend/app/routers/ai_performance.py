"""GET /api/ai-performance — single-call rollup for the home performance widget.

Pulls a compact subset of:
- /api/prediction-performance/summary
- /api/market-regime
- recent learning log
- latest cumulative-profit point

so the frontend can render the AI sidebar widget with one request.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from ..services import (
    confidence_engine,
    learning_engine,
    market_regime,
    profit_simulator,
)

router = APIRouter(prefix="/api/ai-performance", tags=["ai-performance"])


@router.get("")
def rollup():
    base = profit_simulator.summary()
    regime = market_regime.get_current_regime()
    eq = profit_simulator.equity_curve(since_days=180)
    last_eq = eq[-1] if eq else None
    logs = learning_engine.learning_logs(limit=5)
    buckets = confidence_engine.all_buckets()
    overall_gap = 0.0
    sample = 0
    for b in buckets:
        if b.get("sample_size"):
            overall_gap += b["calibration_gap"] * b["sample_size"]
            sample += b["sample_size"]
    if sample:
        overall_gap = overall_gap / sample
    return {
        "as_of": datetime.utcnow().isoformat(),
        "summary": base,
        "regime": regime.as_dict(),
        "last_equity_point": last_eq,
        "calibration_gap": round(overall_gap, 2),
        "recent_learning": logs,
        "disclaimer": (
            "Educational only — not financial advice. All performance metrics "
            "are computed against historical OHLC and represent simulated, "
            "not actual, trading."
        ),
    }
