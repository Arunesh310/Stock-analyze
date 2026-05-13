"""GET /api/market-regime — current + historical regime snapshots."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import market_regime

router = APIRouter(prefix="/api/market-regime", tags=["ai-performance"])


@router.get("")
def current():
    snap = market_regime.get_current_regime()
    return snap.as_dict()


@router.get("/recent")
def recent(limit: int = 60):
    rows = market_regime.recent_regimes(limit=limit)
    return [
        {
            "id": r.id,
            "regime": r.regime,
            "nifty_trend": r.nifty_trend,
            "breadth_score": r.breadth_score,
            "volatility_index": r.volatility_index,
            "nifty_return_20d": r.nifty_return_20d,
            "advance_decline_ratio": r.advance_decline_ratio,
            "avg_news_sentiment": r.avg_news_sentiment,
            "description": r.description,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/refresh")
def refresh():
    snap = market_regime.persist_regime()
    return snap.as_dict()
