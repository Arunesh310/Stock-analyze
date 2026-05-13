"""GET /api/prediction-performance — high-level AI performance dashboard.

Includes overall summary, recent predictions with their outcomes, simulated
P&L, sector / setup / regime breakdowns, and time-series accuracy.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload

from ..database import db_session
from ..models.prediction_engine import (
    PredictionHistory,
    PredictionOutcome,
    SimulatedReturn,
)
from ..schemas.prediction import (
    PerformanceSummary,
    PredictionFullOut,
    PredictionOut,
    OutcomeOut,
    SimulatedReturnOut,
)
from ..services import learning_engine, profit_simulator, confidence_engine

router = APIRouter(prefix="/api/prediction-performance", tags=["ai-performance"])


def _to_full(pred: PredictionHistory) -> PredictionFullOut:
    out = pred.outcome
    sim = pred.simulated
    return PredictionFullOut(
        prediction=PredictionOut(
            id=pred.id,
            symbol=pred.symbol,
            sector=pred.sector,
            action=pred.action,
            mode=pred.mode,
            confidence=pred.confidence,
            probability=pred.probability,
            score=pred.score,
            entry_ref=pred.entry_ref,
            entry_low=pred.entry_low,
            entry_high=pred.entry_high,
            stoploss=pred.stoploss,
            target1=pred.target1,
            target2=pred.target2,
            rr=pred.rr,
            atr_at_entry=pred.atr_at_entry,
            market_regime=pred.market_regime,
            news_sentiment=pred.news_sentiment,
            sector_strength=pred.sector_strength,
            detected_patterns=pred.detected_patterns or [],
            reasoning=pred.reasoning,
            status=pred.status,
            created_at=pred.created_at,
            expires_at=pred.expires_at,
        ),
        outcome=(
            OutcomeOut(
                prediction_id=out.prediction_id,
                outcome=out.outcome,
                direction_correct=out.direction_correct,
                entry_triggered=out.entry_triggered,
                target1_hit=out.target1_hit,
                target2_hit=out.target2_hit,
                stoploss_hit=out.stoploss_hit,
                max_favorable_pct=out.max_favorable_pct,
                max_adverse_pct=out.max_adverse_pct,
                final_price=out.final_price,
                realized_pct=out.realized_pct,
                holding_bars=out.holding_bars,
                holding_days=out.holding_days,
                bars_to_target1=out.bars_to_target1,
                bars_to_stoploss=out.bars_to_stoploss,
                notes=out.notes,
                validated_at=out.validated_at,
            )
            if out
            else None
        ),
        simulated=(
            SimulatedReturnOut(
                prediction_id=sim.prediction_id,
                symbol=pred.symbol,
                action=pred.action,
                capital_invested=sim.capital_invested,
                quantity=sim.quantity,
                entry_price=sim.entry_price,
                exit_price=sim.exit_price,
                exit_reason=sim.exit_reason,
                realized_pnl=sim.realized_pnl,
                realized_pct=sim.realized_pct,
                unrealized_pnl=sim.unrealized_pnl,
                max_gain_pnl=sim.max_gain_pnl,
                max_loss_pnl=sim.max_loss_pnl,
                holding_days=sim.holding_days,
                closed_at=sim.closed_at,
                updated_at=sim.updated_at,
            )
            if sim
            else None
        ),
    )


@router.get("/summary", response_model=PerformanceSummary)
def summary(
    mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$"),
    since_days: Optional[int] = None,
) -> PerformanceSummary:
    base = profit_simulator.summary(mode=mode, since_days=since_days)

    sectors = profit_simulator.by_sector(mode=mode)
    setups = learning_engine.setup_quality(mode=mode)
    regimes = profit_simulator.by_regime(mode=mode)
    best_sector = sectors[0]["sector"] if sectors else None
    worst_sector = sectors[-1]["sector"] if sectors else None
    best_setup = setups[0]["setup_name"] if setups else None
    worst_setup = setups[-1]["setup_name"] if setups else None
    best_regime = regimes[0]["regime"] if regimes else None

    avg_rr = 0.0
    avg_hold = 0.0
    with db_session() as db:
        rows = (
            db.query(PredictionHistory, PredictionOutcome)
            .join(PredictionOutcome, PredictionOutcome.prediction_id == PredictionHistory.id)
            .all()
        )
        rrs = [p.rr for p, _ in rows if p.rr]
        holds = [o.holding_days for _, o in rows if o.holding_days]
        if rrs:
            avg_rr = round(sum(rrs) / len(rrs), 2)
        if holds:
            avg_hold = round(sum(holds) / len(holds), 2)

    confidence_buckets = confidence_engine.all_buckets()
    weighted = [
        b["calibration_gap"] * b["sample_size"] for b in confidence_buckets if b["sample_size"]
    ]
    total_samples = sum(b["sample_size"] for b in confidence_buckets if b["sample_size"])
    gap = sum(weighted) / total_samples if total_samples else 0.0

    return PerformanceSummary(
        total_predictions=base["total_predictions"],
        open_predictions=base["open_predictions"],
        closed_predictions=base["closed_predictions"],
        wins=base["wins"],
        losses=base["losses"],
        win_rate=base["win_rate"],
        avg_return_pct=round(base["cumulative_return_pct"] / max(base["closed_predictions"], 1), 3),
        avg_holding_days=avg_hold,
        total_simulated_pnl=base["total_simulated_pnl"],
        total_simulated_capital=base["total_simulated_capital"],
        cumulative_return_pct=base["cumulative_return_pct"],
        best_sector=best_sector,
        worst_sector=worst_sector,
        best_setup=best_setup,
        worst_setup=worst_setup,
        best_regime=best_regime,
        avg_rr_achieved=avg_rr,
        confidence_calibration_gap=round(gap, 2),
        samples_since=datetime.utcnow() - timedelta(days=since_days) if since_days else None,
    )


@router.get("/recent", response_model=List[PredictionFullOut])
def recent(
    limit: int = 100,
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    mode: Optional[str] = Query(None, pattern="^(intraday|swing|positional)$"),
) -> list[PredictionFullOut]:
    with db_session() as db:
        q = db.query(PredictionHistory).options(
            joinedload(PredictionHistory.outcome),
            joinedload(PredictionHistory.simulated),
        )
        if status:
            q = q.filter(PredictionHistory.status == status)
        if symbol:
            q = q.filter(PredictionHistory.symbol == symbol.upper())
        if mode:
            q = q.filter(PredictionHistory.mode == mode)
        rows = (
            q.order_by(PredictionHistory.created_at.desc()).limit(limit).all()
        )
        return [_to_full(r) for r in rows]


@router.get("/accuracy-trend")
def accuracy_trend(
    bucket: str = Query("month", pattern="^(day|week|month)$"),
    mode: Optional[str] = None,
):
    """Win-rate over time, bucketed by day/week/month."""
    with db_session() as db:
        q = (
            db.query(PredictionHistory, PredictionOutcome)
            .join(PredictionOutcome, PredictionOutcome.prediction_id == PredictionHistory.id)
            .filter(
                PredictionOutcome.outcome.in_(
                    ["WIN", "PARTIAL_WIN", "LOSS", "EXPIRED", "INVALIDATED"]
                )
            )
        )
        if mode:
            q = q.filter(PredictionHistory.mode == mode)
        rows = q.all()
    buckets: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "ret": 0.0, "n": 0})
    for pred, outcome in rows:
        if bucket == "day":
            key = pred.created_at.date().isoformat()
        elif bucket == "week":
            iso = pred.created_at.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
        else:
            key = pred.created_at.strftime("%Y-%m")
        b = buckets[key]
        b["n"] += 1
        b["ret"] += outcome.realized_pct or 0
        # A trade is a win if (a) it hit a target, or (b) the position closed
        # with a positive return (e.g. EXPIRED while still in profit).
        ret = outcome.realized_pct or 0
        if outcome.outcome in {"WIN", "PARTIAL_WIN"} or (
            outcome.outcome == "EXPIRED" and ret > 0
        ):
            b["wins"] += 1
        elif outcome.outcome == "LOSS" or (
            outcome.outcome == "EXPIRED" and ret < 0
        ):
            b["losses"] += 1
    return [
        {
            "bucket": k,
            "sample_size": v["n"],
            "win_rate": round((v["wins"] / max(v["wins"] + v["losses"], 1)) * 100, 2),
            "avg_return_pct": round(v["ret"] / max(v["n"], 1), 3),
        }
        for k, v in sorted(buckets.items())
    ]


@router.get("/setups")
def setups(mode: Optional[str] = None):
    return learning_engine.setup_quality(mode=mode)


@router.get("/sectors")
def sector_breakdown(mode: Optional[str] = None):
    return profit_simulator.by_sector(mode=mode)


@router.get("/regimes")
def regime_breakdown(mode: Optional[str] = None):
    return profit_simulator.by_regime(mode=mode)


@router.get("/heatmap-sector-regime")
def heatmap_sector_regime():
    """2D heatmap data: sector x regime -> win-rate."""
    with db_session() as db:
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
    cells: dict[tuple[str, str], dict] = defaultdict(lambda: {"wins": 0, "n": 0})
    for pred, outcome in rows:
        key = (pred.sector or "Other", pred.market_regime or "unknown")
        c = cells[key]
        c["n"] += 1
        if outcome.outcome in {"WIN", "PARTIAL_WIN"} or (
            outcome.outcome == "EXPIRED" and (outcome.realized_pct or 0) > 0
        ):
            c["wins"] += 1
    return [
        {
            "row": sec,
            "col": reg,
            "value": round((v["wins"] / max(v["n"], 1)) * 100, 2),
            "sample_size": v["n"],
        }
        for (sec, reg), v in cells.items()
    ]
