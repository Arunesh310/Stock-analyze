"""Aggregations on top of ``SimulatedReturn`` rows for the dashboards.

The actual per-trade simulation lives inside ``validation_engine`` — this
module focuses on *portfolio-level* numbers:

- cumulative P&L curve (equity curve)
- per-sector / per-regime breakdowns
- portfolio risk metrics: CAGR, Sharpe, max drawdown, profit factor, expectancy

The simulation assumes each signal allocates a fixed ``₹10,000`` (or whatever
the tracker stored as ``capital_invested``), so portfolio equity = sum of
realised PnL across all closed trades on a date basis.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from ..database import db_session
from ..models.prediction_engine import (
    PredictionHistory,
    PredictionOutcome,
    SimulatedReturn,
)


def equity_curve(
    since_days: Optional[int] = 365,
    mode: Optional[str] = None,
) -> list[dict]:
    """Cumulative P&L over time (daily resolution) on closed trades.

    Each closed simulated trade contributes its realised P&L on its close date.
    """
    with db_session() as db:
        q = (
            db.query(SimulatedReturn, PredictionHistory)
            .join(PredictionHistory, PredictionHistory.id == SimulatedReturn.prediction_id)
            .filter(SimulatedReturn.closed_at.is_not(None))
        )
        if mode:
            q = q.filter(PredictionHistory.mode == mode)
        if since_days:
            q = q.filter(SimulatedReturn.closed_at >= datetime.utcnow() - timedelta(days=since_days))
        rows_raw = q.order_by(SimulatedReturn.closed_at.asc()).all()
        rows = [
            (s.closed_at, s.realized_pnl or 0.0, s.capital_invested or 0.0)
            for s, _ in rows_raw
        ]

    if not rows:
        return []

    by_day: dict[str, dict] = {}
    for closed_at, pnl, cap in rows:
        day = closed_at.date().isoformat()
        d = by_day.setdefault(
            day,
            {"date": day, "trades": 0, "pnl": 0.0, "capital": 0.0},
        )
        d["trades"] += 1
        d["pnl"] += pnl
        d["capital"] += cap

    out: List[dict] = []
    cum_pnl = 0.0
    cum_cap = 0.0
    for day in sorted(by_day.keys()):
        d = by_day[day]
        cum_pnl += d["pnl"]
        cum_cap += d["capital"]
        out.append(
            {
                "date": day,
                "closed_trades": d["trades"],
                "daily_pnl": round(d["pnl"], 2),
                "cumulative_pnl": round(cum_pnl, 2),
                "cumulative_pct": round((cum_pnl / cum_cap) * 100, 3) if cum_cap else 0.0,
            }
        )
    return out


def by_sector(mode: Optional[str] = None) -> list[dict]:
    with db_session() as db:
        rows = _closed_rows(db, mode=mode)
        buckets: dict[str, dict] = {}
        for sim, pred in rows:
            sec = pred.sector or "Other"
            b = buckets.setdefault(
                sec,
                {"sector": sec, "trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "capital": 0.0},
            )
            b["trades"] += 1
            b["pnl"] += sim.realized_pnl or 0
            b["capital"] += sim.capital_invested or 0
            if (sim.realized_pnl or 0) > 0:
                b["wins"] += 1
            elif (sim.realized_pnl or 0) < 0:
                b["losses"] += 1
        out = []
        for sec, b in buckets.items():
            wr = (b["wins"] / b["trades"] * 100) if b["trades"] else 0
            ret = (b["pnl"] / b["capital"] * 100) if b["capital"] else 0
            out.append(
                {
                    "sector": sec,
                    "trades": b["trades"],
                    "wins": b["wins"],
                    "losses": b["losses"],
                    "win_rate": round(wr, 2),
                    "pnl": round(b["pnl"], 2),
                    "return_pct": round(ret, 3),
                }
            )
        out.sort(key=lambda x: x["pnl"], reverse=True)
        return out


def by_regime(mode: Optional[str] = None) -> list[dict]:
    with db_session() as db:
        rows = _closed_rows(db, mode=mode)
        buckets: dict[str, dict] = {}
        for sim, pred in rows:
            reg = pred.market_regime or "unknown"
            b = buckets.setdefault(
                reg,
                {"regime": reg, "trades": 0, "wins": 0, "pnl": 0.0, "capital": 0.0},
            )
            b["trades"] += 1
            b["pnl"] += sim.realized_pnl or 0
            b["capital"] += sim.capital_invested or 0
            if (sim.realized_pnl or 0) > 0:
                b["wins"] += 1
        out = []
        for reg, b in buckets.items():
            wr = (b["wins"] / b["trades"] * 100) if b["trades"] else 0
            ret = (b["pnl"] / b["capital"] * 100) if b["capital"] else 0
            out.append(
                {
                    "regime": reg,
                    "trades": b["trades"],
                    "win_rate": round(wr, 2),
                    "pnl": round(b["pnl"], 2),
                    "return_pct": round(ret, 3),
                }
            )
        out.sort(key=lambda x: x["pnl"], reverse=True)
        return out


def _closed_rows(db: Session, mode: Optional[str] = None):
    q = (
        db.query(SimulatedReturn, PredictionHistory)
        .join(PredictionHistory, PredictionHistory.id == SimulatedReturn.prediction_id)
        .filter(SimulatedReturn.closed_at.is_not(None))
    )
    if mode:
        q = q.filter(PredictionHistory.mode == mode)
    return q.all()


def _is_win(pred: PredictionHistory, sim: SimulatedReturn) -> bool:
    """Treat any closed trade with positive realised PnL as a win.

    Why this is more accurate than "status in {TARGET1_HIT, TARGET2_HIT}":
    EXPIRED trades that ended in profit are real wins; INVALIDATED trades
    that never entered are not losses; partial wins still count as wins.
    """
    if not sim.closed_at:
        return False
    if pred.status == "STOPLOSS_HIT":
        return False
    return (sim.realized_pnl or 0) > 0


def _is_loss(pred: PredictionHistory, sim: SimulatedReturn) -> bool:
    if not sim.closed_at:
        return False
    if pred.status == "STOPLOSS_HIT":
        return True
    return (sim.realized_pnl or 0) < 0


def summary(mode: Optional[str] = None, since_days: Optional[int] = None) -> dict:
    with db_session() as db:
        sim_q = (
            db.query(SimulatedReturn, PredictionHistory)
            .join(PredictionHistory, PredictionHistory.id == SimulatedReturn.prediction_id)
        )
        if mode:
            sim_q = sim_q.filter(PredictionHistory.mode == mode)
        if since_days:
            cutoff = datetime.utcnow() - timedelta(days=since_days)
            sim_q = sim_q.filter(PredictionHistory.created_at >= cutoff)
        rows = sim_q.all()

        total = len(rows)
        open_n = sum(1 for s, _ in rows if not s.closed_at)
        closed = total - open_n

        wins = sum(1 for s, p in rows if _is_win(p, s))
        losses = sum(1 for s, p in rows if _is_loss(p, s))
        decided = wins + losses
        win_rate = (wins / decided * 100) if decided else 0.0

        total_pnl = sum((s.realized_pnl or 0) for s, _ in rows if s.closed_at)
        total_cap = sum((s.capital_invested or 0) for s, _ in rows if s.closed_at)
        cum_pct = (total_pnl / total_cap) * 100 if total_cap else 0.0

        return {
            "total_predictions": total,
            "open_predictions": open_n,
            "closed_predictions": closed,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "total_simulated_pnl": round(total_pnl, 2),
            "total_simulated_capital": round(total_cap, 2),
            "cumulative_return_pct": round(cum_pct, 3),
        }


# ---------------------------------------------------------------------------
# Portfolio risk metrics
# ---------------------------------------------------------------------------


def portfolio_metrics(
    mode: Optional[str] = None,
    since_days: Optional[int] = None,
) -> dict:
    """Trade-by-trade risk metrics on closed simulated trades.

    Returns CAGR, Sharpe-like ratio, max drawdown, profit factor, expectancy,
    average win, average loss, and best/worst trade percentages.

    Sharpe here is computed on per-trade %-returns (not annualised daily),
    so it's a *quality* number rather than a literal portfolio Sharpe ratio.
    """
    with db_session() as db:
        q = (
            db.query(SimulatedReturn, PredictionHistory)
            .join(PredictionHistory, PredictionHistory.id == SimulatedReturn.prediction_id)
            .filter(SimulatedReturn.closed_at.is_not(None))
        )
        if mode:
            q = q.filter(PredictionHistory.mode == mode)
        if since_days:
            cutoff = datetime.utcnow() - timedelta(days=since_days)
            q = q.filter(PredictionHistory.created_at >= cutoff)
        rows_raw = q.order_by(SimulatedReturn.closed_at.asc()).all()
        # Eagerly materialise the columns we care about so we can use the
        # data after the session is closed.
        rows = [
            (
                {
                    "realized_pct": s.realized_pct,
                    "realized_pnl": s.realized_pnl,
                    "capital_invested": s.capital_invested,
                    "closed_at": s.closed_at,
                },
                {"mode": p.mode, "symbol": p.symbol},
            )
            for s, p in rows_raw
        ]

    if not rows:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "profit_factor": 0.0,
            "expectancy_pct": 0.0,
            "expectancy_inr": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_inr": 0.0,
            "sharpe": 0.0,
            "cagr_pct": 0.0,
            "total_pnl": 0.0,
            "total_capital_deployed": 0.0,
            "first_trade_at": None,
            "last_trade_at": None,
        }

    pcts = [(s["realized_pct"] or 0.0) for s, _ in rows]
    pnls = [(s["realized_pnl"] or 0.0) for s, _ in rows]
    caps = [(s["capital_invested"] or 0.0) for s, _ in rows]

    wins_pct = [p for p in pcts if p > 0]
    losses_pct = [p for p in pcts if p < 0]
    wins_pnl = [p for p in pnls if p > 0]
    losses_pnl = [p for p in pnls if p < 0]

    n = len(rows)
    win_rate = (len(wins_pct) / n) * 100 if n else 0.0
    avg_ret = sum(pcts) / n if n else 0.0
    avg_win = sum(wins_pct) / len(wins_pct) if wins_pct else 0.0
    avg_loss = sum(losses_pct) / len(losses_pct) if losses_pct else 0.0
    best = max(pcts) if pcts else 0.0
    worst = min(pcts) if pcts else 0.0

    gross_win = sum(wins_pnl) or 0.0
    gross_loss = abs(sum(losses_pnl)) or 0.0
    profit_factor = gross_win / gross_loss if gross_loss else (math.inf if gross_win else 0.0)

    # Expectancy = (avg_win * win_rate) - (|avg_loss| * loss_rate)
    loss_rate = (len(losses_pct) / n) if n else 0.0
    expectancy_pct = (avg_win * (win_rate / 100)) - (abs(avg_loss) * loss_rate)
    expectancy_inr = sum(pnls) / n if n else 0.0

    # Sharpe-like on trade %-returns
    mean = avg_ret
    var = sum((p - mean) ** 2 for p in pcts) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(var)
    sharpe = (mean / std) if std > 0 else 0.0

    # CAGR — based on (1 + cumulative_return) over the active period.
    # Guard against the catastrophic-loss case where the portfolio is wiped
    # out (cum_pct <= -1): CAGR is mathematically -100% in that scenario.
    first_date = rows[0][0]["closed_at"]
    last_date = rows[-1][0]["closed_at"]
    days = max(1, (last_date - first_date).days)
    total_pnl = sum(pnls)
    total_cap = sum(caps)
    cum_pct = (total_pnl / total_cap) if total_cap else 0.0
    years = days / 365.25
    # CAGR is only meaningful with enough history — annualising a few days
    # of trades produces astronomical numbers that confuse users.
    if years <= 0 or days < 30:
        cagr = 0.0
    elif cum_pct <= -1:
        cagr = -100.0
    else:
        cagr = ((1 + cum_pct) ** (1 / years) - 1) * 100

    # Equity curve in PnL terms for max drawdown calculation
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        cum += pnl
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd
    max_dd_pct = (max_dd / total_cap * 100) if total_cap else 0.0

    return {
        "trades": n,
        "wins": len(wins_pct),
        "losses": len(losses_pct),
        "win_rate": round(win_rate, 2),
        "avg_return_pct": round(avg_ret, 3),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "best_trade_pct": round(best, 3),
        "worst_trade_pct": round(worst, 3),
        "profit_factor": round(profit_factor, 3) if math.isfinite(profit_factor) else None,
        "expectancy_pct": round(expectancy_pct, 3),
        "expectancy_inr": round(expectancy_inr, 2),
        "max_drawdown_inr": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 3),
        "sharpe": round(sharpe, 3),
        "cagr_pct": round(cagr, 3),
        "total_pnl": round(total_pnl, 2),
        "total_capital_deployed": round(total_cap, 2),
        "first_trade_at": first_date.isoformat() if first_date else None,
        "last_trade_at": last_date.isoformat() if last_date else None,
    }
