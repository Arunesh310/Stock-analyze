"""Persists every actionable signal as a ``PredictionHistory`` row.

The tracker is the gateway between the deterministic signal engine and the
validation / learning subsystem.  It also creates the corresponding
``SimulatedReturn`` row (initially OPEN) so the profit dashboard always
reflects every signal.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional

from loguru import logger
from sqlalchemy.orm import Session

from ..database import db_session
from ..models.prediction_engine import (
    PredictionHistory,
    SimulatedReturn,
)
from ..schemas.common import Indicators, Signal
from . import market_regime, news_engine, correlation_engine, universe


DEFAULT_CAPITAL = 10_000.0  # ₹ per simulated trade

# How long a prediction stays "open" before being marked EXPIRED.
EXPIRY_DAYS = {
    "intraday": 1,
    "swing": 30,
    "positional": 180,
}


def _expiry_for(mode: str, when: datetime) -> datetime:
    return when + timedelta(days=EXPIRY_DAYS.get(mode, 30))


def _has_recent_open(db: Session, symbol: str, action: str, mode: str) -> bool:
    """De-dupe: avoid storing the same signal repeatedly on every refresh."""
    cutoff = datetime.utcnow() - timedelta(hours=4)
    return (
        db.query(PredictionHistory)
        .filter(
            PredictionHistory.symbol == symbol,
            PredictionHistory.action == action,
            PredictionHistory.mode == mode,
            PredictionHistory.status == "OPEN",
            PredictionHistory.created_at >= cutoff,
        )
        .first()
        is not None
    )


def record_signal(
    signal: Signal,
    indicators: Indicators,
    *,
    capital: float = DEFAULT_CAPITAL,
    db: Optional[Session] = None,
) -> Optional[PredictionHistory]:
    """Persist a single signal as PredictionHistory + SimulatedReturn.

    Only BUY/SELL signals are tracked.  Returns the stored row (or None if it
    was deduplicated / skipped).
    """
    if signal.action not in ("BUY", "SELL"):
        return None
    if signal.entry_low is None or signal.stoploss is None or signal.target1 is None:
        return None

    def _do(inner: Session) -> Optional[PredictionHistory]:
        if _has_recent_open(inner, signal.symbol, signal.action, signal.mode):
            return None

        # Context snapshots
        try:
            regime = market_regime.get_current_regime()
        except Exception as exc:
            logger.warning(f"record_signal: regime snapshot failed: {exc}")
            regime = None
        try:
            sentiment = news_engine.aggregate_market_sentiment()
            avg_sent = float(sentiment.get("avg_sentiment", 0.0))
        except Exception:
            avg_sent = 0.0
        try:
            sec_strength = next(
                (
                    s["strength"]
                    for s in correlation_engine.sector_strength(period="1mo")
                    if s["sector"] == universe.get_sector(signal.symbol)
                ),
                None,
            )
        except Exception:
            sec_strength = None
        try:
            breadth = correlation_engine.market_breadth(universe.all_symbols()[:30])
        except Exception:
            breadth = {"advancers": None, "decliners": None}

        entry_ref = float(signal.entry_low or 0) + (
            (float(signal.entry_high or signal.entry_low) - float(signal.entry_low)) / 2
            if signal.entry_high
            else 0
        )
        if entry_ref <= 0 and signal.entry_low:
            entry_ref = float(signal.entry_low)

        row = PredictionHistory(
            symbol=signal.symbol,
            sector=universe.get_sector(signal.symbol),
            action=signal.action,
            mode=signal.mode,
            confidence=signal.confidence,
            probability=signal.probability,
            score=signal.score,
            entry_ref=round(entry_ref, 4),
            entry_low=signal.entry_low,
            entry_high=signal.entry_high,
            stoploss=signal.stoploss,
            target1=signal.target1,
            target2=signal.target2,
            rr=signal.rr,
            atr_at_entry=indicators.atr,
            reasoning=signal.reasoning,
            detected_patterns=list(signal.detected_patterns or []),
            indicators_snapshot=indicators.model_dump(),
            market_regime=regime.regime if regime else None,
            regime_snapshot=regime.as_dict() if regime else None,
            news_sentiment=avg_sent,
            sector_strength=sec_strength,
            breadth_advancers=breadth.get("advancers"),
            breadth_decliners=breadth.get("decliners"),
            status="OPEN",
            expires_at=_expiry_for(signal.mode, datetime.utcnow()),
        )
        inner.add(row)
        inner.flush()  # need row.id for SimulatedReturn

        qty = round(capital / entry_ref, 4) if entry_ref else 0.0
        sim = SimulatedReturn(
            prediction_id=row.id,
            capital_invested=capital,
            quantity=qty,
            entry_price=round(entry_ref, 4),
        )
        inner.add(sim)
        return row

    try:
        if db is not None:
            return _do(db)
        with db_session() as inner:
            return _do(inner)
    except Exception as exc:
        logger.warning(f"record_signal failed for {signal.symbol}: {exc}")
        return None


def record_signals(signals: Iterable[Signal], indicators_by_symbol: dict[str, Indicators]) -> int:
    """Convenience batch wrapper. Returns count of newly tracked signals."""
    n = 0
    with db_session() as db:
        for sig in signals:
            ind = indicators_by_symbol.get(sig.symbol) or Indicators()
            if record_signal(sig, ind, db=db) is not None:
                n += 1
    return n
