"""Capital Allocation & Goal Planning engine.

Takes a user's capital, profit target, timeframe, and risk tolerance and
returns:

1. A **realism verdict** that explicitly rejects gambling-grade targets
   (e.g. 10% return in 10 minutes) and suggests realistic alternatives.
2. A matched list of liquid stocks whose **expected move** at the
   requested timeframe is large enough to plausibly hit the target,
   ranked by composite quality score.
3. Sized positions respecting a per-trade risk cap so a stoploss hit
   never wipes the user out.

This module is the front-line "don't promise miracles" defence.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Literal, Optional

from ..schemas.common import Signal
from . import signal_engine, stock_master
from .indicators import compute_indicators
from .market_data import get_history


# ---------------------------------------------------------------------------
# Realism thresholds
# ---------------------------------------------------------------------------

# Annualised return ceilings before we call the target "speculative".
# Daily move expectations roughly = annual / sqrt(250) ≈ annual * 6.3%.
_GAMBLING_DAILY_RETURN_PCT = 5.0      # > 5% in a day = high-risk speculation
_UNREALISTIC_DAILY_RETURN_PCT = 15.0  # > 15% in a day = effectively impossible

# Minutes per timeframe label.
_TF_MIN = {
    "1m": 1, "5m": 5, "10m": 10, "15m": 15, "30m": 30,
    "1h": 60, "1d": 375, "1w": 1875, "1mo": 8250,
}
_TF_LABEL = {
    "1m": "1 minute", "5m": "5 minutes", "10m": "10 minutes", "15m": "15 minutes",
    "30m": "30 minutes", "1h": "1 hour", "1d": "1 trading day",
    "1w": "1 trading week", "1mo": "1 trading month",
}
# How realistic is an X% move at this timeframe? Used for ballpark expected-move
# scaling (annualised ~15% baseline volatility for a liquid Indian large-cap).
_EXPECTED_MOVE_PCT_AT_TF = {
    "1m": 0.05, "5m": 0.15, "10m": 0.25, "15m": 0.35, "30m": 0.5,
    "1h": 0.7, "1d": 1.5, "1w": 4.0, "1mo": 8.0,
}


RiskTol = Literal["conservative", "balanced", "aggressive"]
Mode = Literal["intraday", "swing", "positional"]


@dataclass
class _CandidateMeta:
    symbol: str
    sector: str
    name: str
    last_close: float
    expected_move_pct: float
    atr_pct: float
    volatility_pct: float
    signal: Signal


# ---------------------------------------------------------------------------
# Realism engine
# ---------------------------------------------------------------------------


def _realism(
    capital: float, target_amount: float, timeframe: str
) -> tuple[str, str, list[str]]:
    """Return (verdict, message, suggestions)."""
    if capital <= 0:
        return "INVALID", "Capital must be positive.", []
    if target_amount <= 0:
        return "INVALID", "Target profit must be positive.", []
    tf_min = _TF_MIN.get(timeframe)
    if tf_min is None:
        return "INVALID", f"Unknown timeframe '{timeframe}'.", []

    pct = (target_amount / capital) * 100
    # Convert to equivalent daily return for comparison
    daily_equiv = pct * (375 / tf_min) if tf_min < 375 else pct / (tf_min / 375)
    label = _TF_LABEL.get(timeframe, timeframe)

    suggestions: list[str] = []
    if daily_equiv >= _UNREALISTIC_DAILY_RETURN_PCT:
        suggestions.append(
            f"Try ~{capital * 0.01:.0f}–{capital * 0.02:.0f} INR profit "
            f"({1}–{2}% of capital) in {label} — that's still ambitious but achievable in trending names."
        )
        suggestions.append("Extend the timeframe to a full trading day or longer.")
        suggestions.append("Stick to position sizes that risk ≤2% of capital per trade.")
        return (
            "UNREALISTIC",
            (
                f"You're asking for {pct:.1f}% return in {label}. That's roughly "
                f"{daily_equiv:.1f}% per trading day annualised — a regime no professional "
                "trader sustains. Treating this as a goal would push the AI into "
                "gambling-grade setups."
            ),
            suggestions,
        )
    if daily_equiv >= _GAMBLING_DAILY_RETURN_PCT:
        suggestions.append(
            f"A more realistic target: ~{capital * 0.015:.0f} INR profit "
            f"(1.5% of capital) in {label}."
        )
        suggestions.append("Consider risking ≤1% of capital per trade with R:R ≥ 2.")
        return (
            "SPECULATIVE",
            (
                f"You want {pct:.1f}% return in {label} (≈{daily_equiv:.1f}% per day annualised). "
                "That's achievable occasionally but the failure rate is very high. "
                "We'll show only HIGH_CONVICTION setups and you should treat this as a stretch goal."
            ),
            suggestions,
        )
    return (
        "REALISTIC",
        f"Target of {pct:.2f}% return in {label} is realistic for the right setup.",
        suggestions,
    )


# ---------------------------------------------------------------------------
# Expected move estimator
# ---------------------------------------------------------------------------


def _expected_move_pct(
    volatility_pct_annual: float | None, atr_pct: float | None, timeframe: str
) -> float:
    """Heuristic expected absolute move for a symbol at the given timeframe.

    Uses annualised volatility (or ATR%) to scale to the requested window.
    """
    if volatility_pct_annual and volatility_pct_annual > 0:
        base = volatility_pct_annual
    elif atr_pct and atr_pct > 0:
        base = atr_pct * math.sqrt(250)  # approximate annualisation from daily ATR%
    else:
        base = 25.0  # generic Indian large-cap
    tf_min = _TF_MIN.get(timeframe, 375)
    # Square-root scaling of volatility across time
    minutes_per_year = 250 * 375
    scaling = math.sqrt(tf_min / minutes_per_year)
    return base * scaling


# ---------------------------------------------------------------------------
# Stock matching
# ---------------------------------------------------------------------------


def _gather_candidates(
    timeframe: str,
    mode: Mode,
    universe_limit: int = 50,
) -> List[_CandidateMeta]:
    syms = stock_master.liquid_symbols(universe_limit)
    out: List[_CandidateMeta] = []
    period = "6mo" if mode == "swing" else ("5d" if mode == "intraday" else "2y")
    interval = "1d" if mode != "intraday" else "15m"
    for sym in syms:
        try:
            df = get_history(sym, period=period, interval=interval)
            if df.empty:
                continue
            ind = compute_indicators(df)
            last = float(df["Close"].iloc[-1])
            atr_pct = (ind.atr / last * 100) if (ind.atr and last) else None
            exp_pct = _expected_move_pct(ind.volatility_pct, atr_pct, timeframe)
            sig, _, _ = signal_engine.build_signal(sym, mode=mode)
            out.append(
                _CandidateMeta(
                    symbol=sym,
                    sector=stock_master.get_sector(sym),
                    name=stock_master.get_name(sym),
                    last_close=last,
                    expected_move_pct=round(exp_pct, 3),
                    atr_pct=round(atr_pct or 0.0, 3),
                    volatility_pct=round(ind.volatility_pct or 0.0, 2),
                    signal=sig,
                )
            )
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------


def _risk_per_trade_pct(risk_tol: RiskTol) -> float:
    return {
        "conservative": 0.5,
        "balanced": 1.0,
        "aggressive": 2.0,
    }.get(risk_tol, 1.0)


def _size_position(
    *,
    capital: float,
    last_close: float,
    stoploss: float | None,
    risk_pct: float,
) -> tuple[int, float, float]:
    """Return ``(quantity, capital_at_risk, position_value)``."""
    risk_amount = capital * (risk_pct / 100)
    if not stoploss or last_close <= 0:
        qty = max(0, int(capital * 0.3 // last_close)) if last_close > 0 else 0
        return qty, qty * last_close * 0.015, qty * last_close
    risk_per_share = abs(last_close - stoploss)
    if risk_per_share <= 0:
        return 0, 0.0, 0.0
    qty = max(0, int(risk_amount // risk_per_share))
    # Cap: don't allow a single position to exceed 40% of total capital
    max_qty_by_capital = int(capital * 0.4 // last_close) if last_close > 0 else qty
    qty = min(qty, max_qty_by_capital)
    return qty, qty * risk_per_share, qty * last_close


# ---------------------------------------------------------------------------
# Probability of target hit
# ---------------------------------------------------------------------------


def _prob_target_hit(
    needed_pct: float, expected_move_pct: float, quality_score: float
) -> float:
    """Heuristic probability the symbol moves the required % within the timeframe.

    Combines:
    - move-magnitude prior (how big is ``needed_pct`` vs the typical move?)
    - quality_score (better-graded setups have a directional edge)
    """
    if expected_move_pct <= 0:
        return 0.05
    ratio = needed_pct / expected_move_pct
    # Smooth logistic-ish — needed=expected → 50%, needed=2x expected → ~20%
    base = 1.0 / (1.0 + math.exp(2 * (ratio - 1.0)))
    edge = (quality_score - 50) / 100  # -0.5..+0.5
    p = base * (1.0 + max(-0.4, min(0.4, edge)))
    return round(max(0.03, min(0.92, p)), 3)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan(
    *,
    capital: float,
    target_amount: float,
    timeframe: str,
    risk_tolerance: RiskTol = "balanced",
    mode: Mode = "swing",
    max_picks: int = 6,
) -> dict:
    """Return the full plan — verdict + matched picks + sized positions."""
    verdict, message, suggestions = _realism(capital, target_amount, timeframe)
    if verdict == "INVALID":
        return {
            "verdict": verdict,
            "message": message,
            "suggestions": suggestions,
            "picks": [],
            "target_pct": 0.0,
            "timeframe": timeframe,
            "mode": mode,
        }

    target_pct = (target_amount / capital) * 100
    risk_pct = _risk_per_trade_pct(risk_tolerance)
    # Speculative verdict → only HIGH_CONVICTION grade allowed
    if verdict == "SPECULATIVE":
        min_grade = "STRONG"
    else:
        min_grade = "MODERATE"

    candidates = _gather_candidates(timeframe, mode)

    picks: list[dict] = []
    grade_rank = {"AVOID": 0, "WEAK": 1, "MODERATE": 2, "STRONG": 3, "HIGH_CONVICTION": 4}
    min_rank = grade_rank[min_grade]
    for c in candidates:
        sig = c.signal
        # Must be actionable + meet grade
        if sig.action not in ("BUY", "SELL"):
            continue
        if grade_rank.get(sig.quality_grade, 0) < min_rank:
            continue
        # Expected move must be at least ~70% of the requested target
        # (otherwise the move is statistically too small)
        if c.expected_move_pct < target_pct * 0.7:
            continue
        qty, risked, pos_val = _size_position(
            capital=capital,
            last_close=c.last_close,
            stoploss=sig.stoploss,
            risk_pct=risk_pct,
        )
        if qty <= 0:
            continue
        prob = _prob_target_hit(target_pct, c.expected_move_pct, sig.quality_score)
        # Expected ₹ gain at target1 vs ₹ loss at stoploss
        expected_gain = qty * (sig.target1 - c.last_close) if sig.target1 else 0
        if sig.action == "SELL" and sig.target1:
            expected_gain = qty * (c.last_close - sig.target1)
        picks.append(
            {
                "symbol": c.symbol,
                "name": c.name,
                "sector": c.sector,
                "action": sig.action,
                "last_close": c.last_close,
                "entry_low": sig.entry_low,
                "entry_high": sig.entry_high,
                "stoploss": sig.stoploss,
                "target1": sig.target1,
                "target2": sig.target2,
                "rr": sig.rr,
                "quality_score": sig.quality_score,
                "quality_grade": sig.quality_grade,
                "confidence": sig.confidence,
                "expected_move_pct": c.expected_move_pct,
                "volatility_pct": c.volatility_pct,
                "probability_target_hit": prob,
                "quantity": qty,
                "capital_deployed": round(pos_val, 2),
                "capital_at_risk": round(risked, 2),
                "expected_gain_inr": round(expected_gain, 2),
                "reasoning": sig.reasoning,
                "no_trade_reasons": sig.no_trade_reasons,
            }
        )

    # Rank by quality * probability
    picks.sort(
        key=lambda p: (p["quality_score"] * p["probability_target_hit"]),
        reverse=True,
    )
    picks = picks[:max_picks]

    # If no picks, sharpen the message
    if not picks and verdict != "UNREALISTIC":
        message = (
            f"{message} However, no liquid stock currently meets the quality "
            "filter for this target. The disciplined move is to wait."
        )

    return {
        "verdict": verdict,
        "message": message,
        "suggestions": suggestions,
        "target_pct": round(target_pct, 3),
        "timeframe": timeframe,
        "mode": mode,
        "risk_per_trade_pct": risk_pct,
        "picks": picks,
    }
