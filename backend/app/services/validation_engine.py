"""Prediction outcome validation.

For every OPEN ``PredictionHistory`` row, this module:

1. Pulls the actual price history *after* the signal was generated.
2. Determines whether the trade would have triggered (entry zone touched).
3. Walks bar-by-bar to detect:
     - target1 hit
     - target2 hit
     - stoploss hit
     - max favourable / adverse excursion
4. Writes / updates a ``PredictionOutcome`` row.
5. Updates the matching ``SimulatedReturn`` row with realised / unrealised
   P&L using the originally allocated capital (default ₹10,000).
6. Generates ``LearningFeedback`` rows that explain *why* a trade
   succeeded or failed (used by the learning engine downstream).

Pure data — no investment advice. All numbers are based on freely-available
historical OHLC from `market_data.get_history`.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from ..database import db_session
from ..models.prediction_engine import (
    AILearningLog,
    LearningFeedback,
    PredictionHistory,
    PredictionOutcome,
    SimulatedReturn,
)
from ..schemas.prediction import ValidationRunResult
from . import market_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_signal_history(pred: PredictionHistory) -> pd.DataFrame:
    """Daily bars from the day *after* the signal until now (or expiry)."""
    end = min(datetime.utcnow(), pred.expires_at or datetime.utcnow())
    days_needed = max((end - pred.created_at).days + 5, 7)
    if days_needed > 365 * 2:
        period = "2y"
    elif days_needed > 365:
        period = "1y"
    elif days_needed > 180:
        period = "6mo"
    elif days_needed > 90:
        period = "3mo"
    else:
        period = "1mo"
    interval = "15m" if pred.mode == "intraday" else "1d"
    df = market_data.get_history(pred.symbol, period=period, interval=interval)
    if df.empty:
        return df
    # yfinance sometimes returns tz-aware indexes — coerce to tz-naive so
    # comparisons against `datetime.utcnow()`-based values don't blow up.
    if getattr(df.index, "tz", None) is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    cutoff = pd.Timestamp(pred.created_at)
    if getattr(cutoff, "tz", None) is not None:
        cutoff = cutoff.tz_localize(None)
    df = df[df.index >= cutoff]
    return df


def _bar_index_of_hit(df: pd.DataFrame, level: float, side: str) -> Optional[int]:
    """Index of the first bar whose range crosses ``level``.

    ``side`` is 'above' (looking for highs >= level) or 'below'
    (looking for lows <= level).
    """
    if df.empty:
        return None
    if side == "above":
        cond = df["High"] >= level
    else:
        cond = df["Low"] <= level
    if not cond.any():
        return None
    return int(cond.values.argmax())


def _classify_failure_reason(pred: PredictionHistory, outcome: PredictionOutcome) -> tuple[str, str]:
    """Return (category, human reason). Light heuristic."""
    ind = pred.indicators_snapshot or {}
    if not outcome.entry_triggered:
        return "no_entry", "Price never came into the entry zone."
    if pred.market_regime in {"bearish_trend", "risk_off"} and pred.action == "BUY":
        return "regime_mismatch", "Bought into a bearish/risk-off regime."
    if pred.market_regime in {"bullish_trend", "risk_on"} and pred.action == "SELL":
        return "regime_mismatch", "Shorted into a bullish/risk-on regime."
    if (pred.news_sentiment or 0) < -0.2 and pred.action == "BUY":
        return "negative_news", "Strong negative news sentiment overrode the setup."
    if (pred.news_sentiment or 0) > 0.2 and pred.action == "SELL":
        return "positive_news", "Strong positive news sentiment overrode the setup."
    if (pred.breadth_decliners or 0) > (pred.breadth_advancers or 0) and pred.action == "BUY":
        return "weak_breadth", "Market breadth was negative — too few stocks participating."
    rsi = ind.get("rsi")
    if rsi is not None and rsi >= 75 and pred.action == "BUY":
        return "overextended", f"RSI was extended at {rsi:.0f} — entered too late."
    if outcome.max_favorable_pct and outcome.max_favorable_pct > 1.0:
        return "false_breakout", (
            "Setup initially went favourable but reversed before hitting target — "
            "classic false-breakout pattern."
        )
    if (pred.sector_strength or 0) < -3 and pred.action == "BUY":
        return "sector_weakness", "The sector was rolling over while we bought."
    if (pred.sector_strength or 0) > 3 and pred.action == "SELL":
        return "sector_strength", "Sector was running while we tried to fade it."
    atr = pred.atr_at_entry or 0
    if atr and pred.entry_ref and atr / pred.entry_ref > 0.04:
        return "volatility_spike", "Volatility was very high — wider noise than the trade plan."
    return "indicator_failure", "Indicator setup did not translate into follow-through."


def _classify_success_reason(pred: PredictionHistory, outcome: PredictionOutcome) -> tuple[str, str]:
    if outcome.target2_hit:
        return "trend_followthrough", "Trade reached the second target — full trend follow-through."
    if outcome.target1_hit and (pred.market_regime or "").endswith("trend"):
        return "trend_alignment", "Worked because the regime was aligned with the trade direction."
    if outcome.target1_hit and (pred.sector_strength or 0) * (1 if pred.action == "BUY" else -1) > 0:
        return "sector_tailwind", "Sector strength supported the move."
    if outcome.target1_hit:
        return "setup_followthrough", "Setup played out — partial win at first target."
    return "unclassified", "Trade closed positive without a single dominant driver."


# ---------------------------------------------------------------------------
# Outcome computation
# ---------------------------------------------------------------------------


def _compute_outcome(pred: PredictionHistory) -> Optional[PredictionOutcome]:
    df = _post_signal_history(pred)
    if df.empty:
        return None

    entry_low = float(pred.entry_low) if pred.entry_low is not None else None
    entry_high = float(pred.entry_high) if pred.entry_high is not None else entry_low
    sl = float(pred.stoploss) if pred.stoploss is not None else None
    t1 = float(pred.target1) if pred.target1 is not None else None
    t2 = float(pred.target2) if pred.target2 is not None else None
    direction_is_buy = pred.action == "BUY"

    entry_triggered = False
    entry_bar_idx = 0
    if entry_low is not None and entry_high is not None:
        # For a long, entry triggers when price comes into the entry zone or below the high.
        # For a short, it triggers when price reaches the entry zone or above the low.
        if direction_is_buy:
            cond = df["Low"] <= entry_high
        else:
            cond = df["High"] >= entry_low
        if cond.any():
            entry_triggered = True
            entry_bar_idx = int(cond.values.argmax())

    sub = df.iloc[entry_bar_idx:] if entry_triggered else df
    if sub.empty:
        return None
    entry_price = (
        float(pred.entry_ref) if pred.entry_ref else float(sub["Close"].iloc[0])
    )

    # MFE / MAE on the post-entry window
    if direction_is_buy:
        max_fav = float((sub["High"].max() / entry_price - 1) * 100)
        max_adv = float((sub["Low"].min() / entry_price - 1) * 100)
    else:
        max_fav = float((1 - sub["Low"].min() / entry_price) * 100)
        max_adv = float((1 - sub["High"].max() / entry_price) * 100)

    # Targets / stoploss
    t1_idx = _bar_index_of_hit(sub, t1, "above" if direction_is_buy else "below") if t1 else None
    t2_idx = _bar_index_of_hit(sub, t2, "above" if direction_is_buy else "below") if t2 else None
    sl_idx = _bar_index_of_hit(sub, sl, "below" if direction_is_buy else "above") if sl else None

    # Conservative: if both hit, whichever came first wins.
    target1_hit = t1_idx is not None
    target2_hit = t2_idx is not None
    stoploss_hit = sl_idx is not None
    if target1_hit and stoploss_hit and sl_idx < t1_idx:
        target1_hit = False
        target2_hit = False
    if target2_hit and stoploss_hit and sl_idx < t2_idx:
        target2_hit = False

    # Final outcome label
    if not entry_triggered:
        outcome_label = "INVALIDATED"
        final_price = float(df["Close"].iloc[-1])
        realized_pct = 0.0
        holding_bars = 0
    elif target2_hit:
        outcome_label = "WIN"
        final_price = t2 if direction_is_buy else t2
        realized_pct = (t2 / entry_price - 1) * 100 if direction_is_buy else (1 - t2 / entry_price) * 100
        holding_bars = (t2_idx or 0) + 1
    elif target1_hit:
        outcome_label = "PARTIAL_WIN"
        final_price = t1
        realized_pct = (t1 / entry_price - 1) * 100 if direction_is_buy else (1 - t1 / entry_price) * 100
        holding_bars = (t1_idx or 0) + 1
    elif stoploss_hit:
        outcome_label = "LOSS"
        final_price = sl
        realized_pct = (sl / entry_price - 1) * 100 if direction_is_buy else (1 - sl / entry_price) * 100
        holding_bars = (sl_idx or 0) + 1
    elif pred.expires_at and datetime.utcnow() >= pred.expires_at:
        outcome_label = "EXPIRED"
        final_price = float(sub["Close"].iloc[-1])
        realized_pct = (final_price / entry_price - 1) * 100 if direction_is_buy else (1 - final_price / entry_price) * 100
        holding_bars = len(sub)
    else:
        outcome_label = "OPEN"
        final_price = float(sub["Close"].iloc[-1])
        realized_pct = (final_price / entry_price - 1) * 100 if direction_is_buy else (1 - final_price / entry_price) * 100
        holding_bars = len(sub)

    direction_correct: Optional[bool]
    if outcome_label in {"WIN", "PARTIAL_WIN"}:
        direction_correct = True
    elif outcome_label == "LOSS":
        direction_correct = False
    elif outcome_label in {"EXPIRED", "OPEN"}:
        direction_correct = realized_pct > 0
    else:
        direction_correct = None

    return PredictionOutcome(
        prediction_id=pred.id,
        outcome=outcome_label,
        direction_correct=direction_correct,
        entry_triggered=entry_triggered,
        target1_hit=target1_hit,
        target2_hit=target2_hit,
        stoploss_hit=stoploss_hit,
        max_favorable_pct=round(max_fav, 3),
        max_adverse_pct=round(max_adv, 3),
        final_price=round(final_price, 4) if final_price else None,
        realized_pct=round(realized_pct, 3),
        holding_bars=int(holding_bars),
        holding_days=round((sub.index[-1] - sub.index[0]).total_seconds() / 86400, 2)
        if len(sub) > 1
        else 0.0,
        bars_to_target1=int(t1_idx) + 1 if t1_idx is not None else None,
        bars_to_stoploss=int(sl_idx) + 1 if sl_idx is not None else None,
    )


DEFAULT_TRADE_CAPITAL = 10_000.0


def _update_simulation(
    pred: PredictionHistory, outcome: PredictionOutcome, db: Session
) -> SimulatedReturn:
    sim = (
        db.query(SimulatedReturn)
        .filter(SimulatedReturn.prediction_id == pred.id)
        .one_or_none()
    )
    if sim is None:
        # ``prediction_tracker.record_signal`` creates SimulatedReturn at signal
        # time; this fallback handles legacy rows / direct test inserts.
        entry_price = float(pred.entry_ref or pred.entry_low or 0)
        qty = (DEFAULT_TRADE_CAPITAL / entry_price) if entry_price else 0.0
        sim = SimulatedReturn(
            prediction_id=pred.id,
            capital_invested=DEFAULT_TRADE_CAPITAL,
            quantity=round(qty, 4),
            entry_price=round(entry_price, 4),
        )
        db.add(sim)
        db.flush()

    direction = 1 if pred.action == "BUY" else -1
    final_price = outcome.final_price or sim.entry_price or 0.0
    pct = (
        (final_price / sim.entry_price - 1) * 100 * direction
        if sim.entry_price
        else 0.0
    )
    pnl = (sim.capital_invested or 0) * pct / 100

    # Track peak favourable / adverse PnL across the life of the trade
    mfe_pnl = (sim.capital_invested or 0) * (outcome.max_favorable_pct or 0) / 100
    mae_pnl = (sim.capital_invested or 0) * (outcome.max_adverse_pct or 0) / 100
    sim.max_gain_pnl = max(sim.max_gain_pnl or 0.0, mfe_pnl)
    sim.max_loss_pnl = min(sim.max_loss_pnl or 0.0, mae_pnl)

    is_closed = outcome.outcome in {"WIN", "PARTIAL_WIN", "LOSS", "EXPIRED", "INVALIDATED"}
    if is_closed:
        sim.realized_pnl = round(pnl, 2)
        sim.realized_pct = round(pct, 3)
        sim.unrealized_pnl = 0.0
        sim.exit_price = round(final_price, 4) if final_price else None
        sim.exit_reason = (
            "TARGET2"
            if outcome.target2_hit
            else "TARGET1"
            if outcome.target1_hit
            else "STOPLOSS"
            if outcome.stoploss_hit
            else "EXPIRED"
            if outcome.outcome == "EXPIRED"
            else "INVALIDATED"
        )
        sim.closed_at = datetime.utcnow()
        sim.holding_days = outcome.holding_days
    else:
        sim.unrealized_pnl = round(pnl, 2)
        sim.realized_pct = round(pct, 3)
        sim.exit_price = round(final_price, 4) if final_price else None

    return sim


def _record_feedback(pred: PredictionHistory, outcome: PredictionOutcome, db: Session) -> None:
    """Generate a LearningFeedback row that explains the outcome."""
    if outcome.outcome in {"OPEN"}:
        return
    if outcome.outcome in {"LOSS", "INVALIDATED", "EXPIRED"} and (outcome.realized_pct or 0) <= 0:
        category, reason = _classify_failure_reason(pred, outcome)
        feedback_outcome = "LOSS"
    elif outcome.outcome in {"WIN", "PARTIAL_WIN"}:
        category, reason = _classify_success_reason(pred, outcome)
        feedback_outcome = "WIN"
    else:
        # EXPIRED but positive: treat as win.
        category, reason = _classify_success_reason(pred, outcome)
        feedback_outcome = "WIN" if (outcome.realized_pct or 0) > 0 else "LOSS"

    fb = LearningFeedback(
        prediction_id=pred.id,
        outcome=feedback_outcome,
        category=category,
        reason=reason,
        market_condition=pred.market_regime,
        indicator_state=pred.indicators_snapshot,
        sector_condition=pred.sector,
        confidence_at_signal=pred.confidence,
    )
    db.add(fb)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_prediction(pred: PredictionHistory, db: Session) -> Optional[PredictionOutcome]:
    """Validate one prediction; upsert outcome + sim row + feedback."""
    try:
        result = _compute_outcome(pred)
    except Exception as exc:
        logger.warning(f"validate_prediction failed for {pred.symbol}#{pred.id}: {exc}")
        return None
    if result is None:
        return None

    existing = (
        db.query(PredictionOutcome)
        .filter(PredictionOutcome.prediction_id == pred.id)
        .one_or_none()
    )
    if existing:
        for f in (
            "outcome", "direction_correct", "entry_triggered",
            "target1_hit", "target2_hit", "stoploss_hit",
            "max_favorable_pct", "max_adverse_pct", "final_price",
            "realized_pct", "holding_bars", "holding_days",
            "bars_to_target1", "bars_to_stoploss",
        ):
            setattr(existing, f, getattr(result, f))
        existing.validated_at = datetime.utcnow()
        outcome = existing
    else:
        outcome = result
        db.add(outcome)
        db.flush()

    _update_simulation(pred, outcome, db)

    # Lifecycle transitions on the prediction itself
    if outcome.target2_hit:
        pred.status = "TARGET2_HIT"
    elif outcome.target1_hit:
        pred.status = "TARGET1_HIT"
    elif outcome.stoploss_hit:
        pred.status = "STOPLOSS_HIT"
    elif outcome.outcome == "INVALIDATED":
        pred.status = "INVALIDATED"
    elif outcome.outcome == "EXPIRED":
        pred.status = "EXPIRED"
    else:
        pred.status = "OPEN"

    if pred.status != "OPEN":
        _record_feedback(pred, outcome, db)

    return outcome


def validate_all_open(limit: int = 200) -> ValidationRunResult:
    """Validate up to ``limit`` open predictions and return a summary."""
    scanned = closed = still_open = new_wins = new_losses = 0
    with db_session() as db:
        rows = (
            db.query(PredictionHistory)
            .filter(PredictionHistory.status == "OPEN")
            .order_by(PredictionHistory.created_at.asc())
            .limit(limit)
            .all()
        )
        for pred in rows:
            scanned += 1
            outcome = validate_prediction(pred, db)
            if outcome is None:
                still_open += 1
                continue
            if pred.status == "OPEN":
                still_open += 1
            else:
                closed += 1
                if pred.status in {"TARGET1_HIT", "TARGET2_HIT"}:
                    new_wins += 1
                elif pred.status == "STOPLOSS_HIT":
                    new_losses += 1
        log = AILearningLog(
            event="validation_cycle",
            summary=(
                f"Validated {scanned} open predictions — "
                f"{closed} closed ({new_wins} W / {new_losses} L), "
                f"{still_open} still open."
            ),
            details={
                "scanned": scanned,
                "closed": closed,
                "still_open": still_open,
                "new_wins": new_wins,
                "new_losses": new_losses,
            },
            impact_score=float(new_wins - new_losses),
        )
        db.add(log)

    return ValidationRunResult(
        scanned=scanned,
        closed=closed,
        still_open=still_open,
        new_wins=new_wins,
        new_losses=new_losses,
        learning_events=1,
    )


def expire_stale_predictions() -> int:
    """Mark any OPEN prediction past `expires_at` as EXPIRED."""
    cutoff = datetime.utcnow()
    n = 0
    with db_session() as db:
        rows = (
            db.query(PredictionHistory)
            .filter(
                PredictionHistory.status == "OPEN",
                PredictionHistory.expires_at.is_not(None),
                PredictionHistory.expires_at <= cutoff,
            )
            .all()
        )
        for pred in rows:
            validate_prediction(pred, db)
            n += 1
    return n
