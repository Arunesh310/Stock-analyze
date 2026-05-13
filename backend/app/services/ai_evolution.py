"""AI Evolution Analytics — visibility into how the AI is actually learning.

This service computes the metrics that drive the AI Evolution dashboard:

- **Rolling-window accuracy** (7d / 30d / 90d / all-time) so users can see
  whether the engine is improving over time.
- **Signal-conversion stats** (BUY vs SELL vs HOLD success, target/stop
  hit rates, false-breakout rate).
- **Improvement score** — a composite 0..100 number that summarises the
  most recent 30-day window versus the prior 30 days.
- **Recent learning changes** — human-readable log of the actual weight
  adjustments the AI applied in the last N cycles.
- **Strategy performance** — per-strategy (breakout / momentum / RSI /
  trend) win-rate, avg return, profit factor.

All metrics are computed from the existing prediction-history /
prediction-outcome / simulated-return tables — no schema changes required.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..database import db_session
from ..models.prediction_engine import (
    AILearningLog,
    PredictionHistory,
    PredictionOutcome,
    SimulatedReturn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_WIN_OUTCOMES = {"WIN", "PARTIAL_WIN"}
_LOSS_OUTCOMES = {"LOSS"}


def _is_win(outcome: PredictionOutcome) -> bool:
    if outcome is None:
        return False
    if outcome.outcome in _WIN_OUTCOMES:
        return True
    if outcome.outcome == "EXPIRED" and (outcome.realized_pct or 0) > 0:
        return True
    return False


def _is_loss(outcome: PredictionOutcome) -> bool:
    if outcome is None:
        return False
    if outcome.outcome in _LOSS_OUTCOMES:
        return True
    if outcome.outcome == "EXPIRED" and (outcome.realized_pct or 0) < 0:
        return True
    return False


def _closed_pairs(
    since: Optional[datetime] = None,
    mode: Optional[str] = None,
) -> List[tuple[PredictionHistory, PredictionOutcome]]:
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
        if since:
            q = q.filter(PredictionHistory.created_at >= since)
        if mode:
            q = q.filter(PredictionHistory.mode == mode)
        rows = q.all()
        # Materialise into plain tuples since the session is about to close.
        return [
            (
                _Snapshot(
                    id=p.id, symbol=p.symbol, sector=p.sector, mode=p.mode,
                    action=p.action, confidence=p.confidence,
                    market_regime=p.market_regime,
                    created_at=p.created_at, status=p.status,
                    detected_patterns=p.detected_patterns or [],
                ),
                _OutcomeSnapshot(
                    outcome=o.outcome, target1_hit=o.target1_hit,
                    target2_hit=o.target2_hit, stoploss_hit=o.stoploss_hit,
                    entry_triggered=o.entry_triggered,
                    realized_pct=o.realized_pct or 0.0,
                    max_favorable_pct=o.max_favorable_pct or 0.0,
                    max_adverse_pct=o.max_adverse_pct or 0.0,
                    holding_days=o.holding_days or 0.0,
                ),
            )
            for p, o in rows
        ]


class _Snapshot:
    __slots__ = ("id", "symbol", "sector", "mode", "action", "confidence",
                 "market_regime", "created_at", "status", "detected_patterns")

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class _OutcomeSnapshot:
    __slots__ = ("outcome", "target1_hit", "target2_hit", "stoploss_hit",
                 "entry_triggered", "realized_pct", "max_favorable_pct",
                 "max_adverse_pct", "holding_days")

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Rolling-window accuracy
# ---------------------------------------------------------------------------


def _window_stats(pairs: List[tuple]) -> Dict[str, Any]:
    """Aggregate stats for a set of (prediction, outcome) pairs."""
    if not pairs:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "best_return_pct": 0.0,
            "worst_return_pct": 0.0,
        }
    wins = sum(1 for _, o in pairs if _is_win(o))
    losses = sum(1 for _, o in pairs if _is_loss(o))
    decided = wins + losses or 1
    returns = [o.realized_pct for _, o in pairs]
    return {
        "trades": len(pairs),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / decided) * 100, 2),
        "avg_return_pct": round(sum(returns) / len(returns), 3) if returns else 0.0,
        "best_return_pct": round(max(returns), 3) if returns else 0.0,
        "worst_return_pct": round(min(returns), 3) if returns else 0.0,
    }


def rolling_windows(mode: Optional[str] = None) -> Dict[str, Any]:
    """7d / 30d / 90d / all-time stats — the headline 'is the AI improving?' chart."""
    now = datetime.utcnow()
    all_pairs = _closed_pairs(mode=mode)
    windows = {
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "90d": now - timedelta(days=90),
        "all_time": None,
    }
    out: Dict[str, Any] = {}
    for label, cutoff in windows.items():
        if cutoff is None:
            subset = all_pairs
        else:
            subset = [(p, o) for p, o in all_pairs if p.created_at >= cutoff]
        out[label] = _window_stats(subset)
    return out


# ---------------------------------------------------------------------------
# Signal conversion: BUY vs SELL success
# ---------------------------------------------------------------------------


def signal_conversion(mode: Optional[str] = None) -> Dict[str, Any]:
    pairs = _closed_pairs(mode=mode)
    buckets: Dict[str, Dict[str, int]] = {
        "BUY": defaultdict(int),
        "SELL": defaultdict(int),
    }
    target1_hits = 0
    target2_hits = 0
    stoploss_hits = 0
    entries_failed = 0
    false_breakouts = 0
    for p, o in pairs:
        side = p.action if p.action in ("BUY", "SELL") else "BUY"
        b = buckets[side]
        b["trades"] += 1
        if _is_win(o):
            b["wins"] += 1
        elif _is_loss(o):
            b["losses"] += 1
        if o.target1_hit:
            target1_hits += 1
        if o.target2_hit:
            target2_hits += 1
        if o.stoploss_hit:
            stoploss_hits += 1
        if o.entry_triggered is False:
            entries_failed += 1
        # False breakout = max favourable >1% but ended in loss / no target
        if (
            o.max_favorable_pct > 1.0
            and not o.target1_hit
            and (o.stoploss_hit or _is_loss(o))
        ):
            false_breakouts += 1

    total = len(pairs) or 1

    def _rate(b: Dict[str, int]) -> Dict[str, Any]:
        decided = (b.get("wins", 0) + b.get("losses", 0)) or 1
        return {
            "trades": b.get("trades", 0),
            "wins": b.get("wins", 0),
            "losses": b.get("losses", 0),
            "win_rate": round((b.get("wins", 0) / decided) * 100, 2),
        }

    return {
        "total_signals": len(pairs),
        "buy": _rate(buckets["BUY"]),
        "sell": _rate(buckets["SELL"]),
        "target1_hit_rate": round(target1_hits / total * 100, 2),
        "target2_hit_rate": round(target2_hits / total * 100, 2),
        "stoploss_hit_rate": round(stoploss_hits / total * 100, 2),
        "entry_failure_rate": round(entries_failed / total * 100, 2),
        "false_breakout_rate": round(false_breakouts / total * 100, 2),
    }


# ---------------------------------------------------------------------------
# Improvement score
# ---------------------------------------------------------------------------


def improvement_score(mode: Optional[str] = None) -> Dict[str, Any]:
    """Composite 0..100 score comparing the last 30 days vs the prior 30 days.

    Considers:
    - change in win rate
    - change in average return
    - change in calibration (does 80% conf still beat 50% conf?)
    - reduction in stoploss hits
    """
    now = datetime.utcnow()
    cur_cutoff = now - timedelta(days=30)
    prev_cutoff = now - timedelta(days=60)

    all_pairs = _closed_pairs(mode=mode)
    cur = [(p, o) for p, o in all_pairs if p.created_at >= cur_cutoff]
    prev = [(p, o) for p, o in all_pairs if prev_cutoff <= p.created_at < cur_cutoff]

    cur_stats = _window_stats(cur)
    prev_stats = _window_stats(prev)

    # Deltas (cur - prev) on each dimension
    d_wr = cur_stats["win_rate"] - prev_stats["win_rate"]
    d_ret = cur_stats["avg_return_pct"] - prev_stats["avg_return_pct"]

    # Calibration delta: hi-conf vs low-conf win-rate spread
    def _calibration(pairs: List[tuple]) -> float:
        hi = [(p, o) for p, o in pairs if (p.confidence or 0) >= 70]
        lo = [(p, o) for p, o in pairs if 40 <= (p.confidence or 0) < 60]
        if not hi or not lo:
            return 0.0
        hi_wr = sum(1 for _, o in hi if _is_win(o)) / max(
            sum(1 for _, o in hi if _is_win(o) or _is_loss(o)), 1
        )
        lo_wr = sum(1 for _, o in lo if _is_win(o)) / max(
            sum(1 for _, o in lo if _is_win(o) or _is_loss(o)), 1
        )
        return (hi_wr - lo_wr) * 100

    cur_calib = _calibration(cur)
    prev_calib = _calibration(prev)
    d_calib = cur_calib - prev_calib

    # Stoploss hit rate (lower is better)
    def _sl_rate(pairs: List[tuple]) -> float:
        if not pairs:
            return 0.0
        return sum(1 for _, o in pairs if o.stoploss_hit) / len(pairs) * 100

    cur_sl = _sl_rate(cur)
    prev_sl = _sl_rate(prev)
    d_sl = prev_sl - cur_sl  # positive if we reduced SL hits

    # Combine into 0..100 (50 = neutral) — weights tuned to be sensible
    raw = (
        50
        + d_wr * 1.5     # +15 pts for +10pp win-rate improvement
        + d_ret * 5      # +25 pts for +5% avg return improvement
        + d_calib * 0.5  # +5 pts for +10pp calibration spread improvement
        + d_sl * 0.5     # +5 pts for -10pp stoploss hit improvement
    )
    score = max(0.0, min(100.0, raw))

    # Narrative
    narrative_bits: List[str] = []
    if d_wr > 5:
        narrative_bits.append(f"Win-rate improved {d_wr:+.1f} pp vs prior 30 days.")
    elif d_wr < -5:
        narrative_bits.append(f"Win-rate declined {d_wr:+.1f} pp vs prior 30 days.")
    if d_ret > 0.5:
        narrative_bits.append(f"Average return per trade rose {d_ret:+.2f} %.")
    elif d_ret < -0.5:
        narrative_bits.append(f"Average return per trade fell {d_ret:+.2f} %.")
    if d_calib > 5:
        narrative_bits.append(
            f"Confidence calibration improved by {d_calib:.1f} pp — high-confidence "
            "signals are outperforming low-confidence ones more clearly."
        )
    elif d_calib < -5:
        narrative_bits.append(
            f"Confidence calibration weakened by {d_calib:.1f} pp — high-confidence "
            "signals are no longer beating low-confidence signals enough."
        )
    if d_sl > 2:
        narrative_bits.append(f"Stoploss hit-rate reduced by {d_sl:.1f} pp.")
    elif d_sl < -2:
        narrative_bits.append(f"Stoploss hits *rose* {abs(d_sl):.1f} pp — risk filter regressed.")

    if not narrative_bits:
        if cur_stats["trades"] < 5:
            narrative_bits.append(
                "Too few closed trades in the last 30 days to measure improvement."
            )
        else:
            narrative_bits.append("Performance roughly unchanged vs the prior 30 days.")

    return {
        "score": round(score, 1),
        "current_window": cur_stats,
        "previous_window": prev_stats,
        "deltas": {
            "win_rate_pp": round(d_wr, 2),
            "avg_return_pct": round(d_ret, 3),
            "calibration_pp": round(d_calib, 2),
            "stoploss_rate_pp": round(d_sl, 2),
        },
        "current_calibration": round(cur_calib, 2),
        "narrative": " ".join(narrative_bits),
    }


# ---------------------------------------------------------------------------
# Recent learning changes (human-readable)
# ---------------------------------------------------------------------------


def recent_changes(limit: int = 30) -> List[dict]:
    """Most recent AI weight adjustments + cycle summaries.

    Pulls from ``AILearningLog`` — the event types we surface are
    ``weight_changed`` (one per delta) and ``weights_adjusted`` (cycle summary).
    """
    with db_session() as db:
        rows = (
            db.query(AILearningLog)
            .filter(AILearningLog.event.in_(["weight_changed", "weights_adjusted", "regime_change"]))
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
                "impact_score": r.impact_score or 0.0,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Strategy performance leaderboard
# ---------------------------------------------------------------------------


_STRATEGY_KEYWORDS: Dict[str, List[str]] = {
    "Breakout": ["breakout", "Near 52-week high", "20-day breakout"],
    "Reversal / RSI": ["Hammer", "Bullish Engulfing", "Morning Star", "RSI Oversold",
                        "Shooting Star", "Bearish Engulfing", "Evening Star", "RSI Overbought"],
    "Trend continuation": ["Uptrend (HH/HL)", "Downtrend (LH/LL)", "Marubozu"],
    "Volume spike": ["Volume spike"],
    "Pattern-less": ["Generic Setup"],
}


def _strategy_for(pred: _Snapshot) -> str:
    for pat in pred.detected_patterns or []:
        for strat, kws in _STRATEGY_KEYWORDS.items():
            for kw in kws:
                if kw.lower() in pat.lower():
                    return strat
    return "Other"


def strategy_performance(mode: Optional[str] = None) -> List[dict]:
    pairs = _closed_pairs(mode=mode)
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"trades": 0, "wins": 0, "losses": 0, "ret": [], "wins_pnl": 0.0, "losses_pnl": 0.0}
    )
    for p, o in pairs:
        strat = _strategy_for(p)
        b = buckets[strat]
        b["trades"] += 1
        b["ret"].append(o.realized_pct)
        if _is_win(o):
            b["wins"] += 1
            b["wins_pnl"] += max(o.realized_pct, 0)
        elif _is_loss(o):
            b["losses"] += 1
            b["losses_pnl"] += abs(min(o.realized_pct, 0))
    out: List[dict] = []
    for strat, b in buckets.items():
        decided = b["wins"] + b["losses"] or 1
        wr = b["wins"] / decided * 100
        avg = sum(b["ret"]) / len(b["ret"]) if b["ret"] else 0.0
        pf = b["wins_pnl"] / b["losses_pnl"] if b["losses_pnl"] > 0 else (
            float("inf") if b["wins_pnl"] > 0 else 0.0
        )
        out.append(
            {
                "strategy": strat,
                "trades": b["trades"],
                "wins": b["wins"],
                "losses": b["losses"],
                "win_rate": round(wr, 2),
                "avg_return_pct": round(avg, 3),
                "profit_factor": round(pf, 2) if pf != float("inf") else None,
            }
        )
    out.sort(key=lambda x: (x["win_rate"], x["trades"]), reverse=True)
    return out


# ---------------------------------------------------------------------------
# Regime × Strategy matrix
# ---------------------------------------------------------------------------


def regime_strategy_matrix(mode: Optional[str] = None) -> List[dict]:
    pairs = _closed_pairs(mode=mode)
    cells: Dict[tuple[str, str], Dict[str, int]] = defaultdict(
        lambda: {"trades": 0, "wins": 0}
    )
    for p, o in pairs:
        key = (p.market_regime or "unknown", _strategy_for(p))
        c = cells[key]
        c["trades"] += 1
        if _is_win(o):
            c["wins"] += 1
    out: List[dict] = []
    for (regime, strat), c in cells.items():
        wr = (c["wins"] / c["trades"] * 100) if c["trades"] else 0
        out.append(
            {
                "regime": regime,
                "strategy": strat,
                "trades": c["trades"],
                "wins": c["wins"],
                "win_rate": round(wr, 2),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Per-prediction outcome lookup (for "Signal outcome visibility")
# ---------------------------------------------------------------------------


def recent_signal_outcomes(limit: int = 50) -> List[dict]:
    """Most recent predictions with their validated outcomes — used for the
    signal-card outcome overlay so users can see *what actually happened*.
    """
    with db_session() as db:
        rows = (
            db.query(PredictionHistory, PredictionOutcome, SimulatedReturn)
            .outerjoin(PredictionOutcome, PredictionOutcome.prediction_id == PredictionHistory.id)
            .outerjoin(SimulatedReturn, SimulatedReturn.prediction_id == PredictionHistory.id)
            .order_by(PredictionHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        out: List[dict] = []
        for pred, outcome, sim in rows:
            verdict = "OPEN"
            if outcome is not None:
                if _is_win(outcome):
                    verdict = "SUCCESS"
                elif _is_loss(outcome):
                    verdict = "FAILED"
                elif outcome.outcome == "INVALIDATED":
                    verdict = "NO ENTRY"
                elif outcome.outcome == "EXPIRED":
                    verdict = "EXPIRED"
            out.append(
                {
                    "id": pred.id,
                    "symbol": pred.symbol,
                    "action": pred.action,
                    "confidence": pred.confidence,
                    "mode": pred.mode,
                    "created_at": pred.created_at.isoformat() if pred.created_at else None,
                    "verdict": verdict,
                    "return_pct": (outcome.realized_pct if outcome else None),
                    "target1_hit": (outcome.target1_hit if outcome else None),
                    "target2_hit": (outcome.target2_hit if outcome else None),
                    "stoploss_hit": (outcome.stoploss_hit if outcome else None),
                    "max_favorable_pct": (outcome.max_favorable_pct if outcome else None),
                    "max_adverse_pct": (outcome.max_adverse_pct if outcome else None),
                    "holding_days": (outcome.holding_days if outcome else None),
                    "realized_pnl": (sim.realized_pnl if sim else None),
                }
            )
        return out
