"""Trade Quality Control System.

The "high quantity → high quality" filter. Every actionable signal is
graded on a composite 0..100 ``quality_score`` built from the same
context the AI sees:

1. Technical confirmation (trend + momentum + pattern alignment)
2. Market confirmation (Nifty breadth + sector strength)
3. Sentiment confirmation (volatility regime + data freshness)
4. Historical confirmation (setup quality + indicator edge from learning)
5. Risk geometry (R:R + ATR sanity)

The engine also returns a **NO-TRADE** veto list — if any hard rule is
broken the signal must be downgraded to HOLD regardless of confidence.

Grading:
- 0-40 AVOID    — clear conflicts or data risk
- 40-60 WEAK    — barely qualifies, not actionable
- 60-75 MODERATE
- 75-85 STRONG
- 85+ HIGH_CONVICTION (rare)

Capital preservation > predictive aggression.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..schemas.common import DataQualityOut, Indicators


# ---------------------------------------------------------------------------
# Hard floors — anything below these forces NO-TRADE
# ---------------------------------------------------------------------------

MIN_RR = 1.5                    # was 1.0 — now we demand 1.5 reward/risk
MIN_DATA_QUALITY = 70           # was 50
MIN_CONFIDENCE = 55             # below this confidence is just noise
MIN_ADX_TREND = 20              # was 15
MAX_VOLATILITY = 70             # was 80 — extreme vol is too risky
MAX_RSI_LONG = 78               # severely overbought
MIN_RSI_SHORT = 22              # severely oversold


@dataclass
class QualityResult:
    score: float            # 0..100
    grade: str              # AVOID / WEAK / MODERATE / STRONG / HIGH_CONVICTION / NO_TRADE
    breakdown: dict         # component scores for transparency
    no_trade_reasons: List[str]


def _grade_for(score: float, has_veto: bool) -> str:
    if has_veto:
        return "NO_TRADE"
    if score >= 85:
        return "HIGH_CONVICTION"
    if score >= 75:
        return "STRONG"
    if score >= 60:
        return "MODERATE"
    if score >= 40:
        return "WEAK"
    return "AVOID"


def evaluate(
    *,
    action: str,
    confidence: float,
    rr: Optional[float],
    indicators: Indicators,
    data_quality: DataQualityOut,
    patterns: List[str],
    market_breadth: Optional[float] = None,         # advancers/total ratio 0..1
    sector_strength: Optional[float] = None,        # -100..100
    setup_win_rate: Optional[float] = None,         # 0..100, from learning_engine
    setup_sample_size: int = 0,
    indicator_edge: Optional[float] = None,         # -1..+1, weighted active-indicator edge
) -> QualityResult:
    """Compute the composite quality score + NO-TRADE veto list."""

    no_trade: List[str] = []
    parts: dict = {}

    # ---- Component 1: technical confirmation (max 30) ----
    tech = 0.0
    if indicators.ema20 and indicators.ema50 and indicators.ema200:
        if action == "BUY" and indicators.ema20 > indicators.ema50 > indicators.ema200:
            tech += 12
        elif action == "SELL" and indicators.ema20 < indicators.ema50 < indicators.ema200:
            tech += 12
        elif (
            (action == "BUY" and indicators.ema20 < indicators.ema50)
            or (action == "SELL" and indicators.ema20 > indicators.ema50)
        ):
            tech -= 6  # counter-trend penalty
    if indicators.rsi is not None:
        if action == "BUY" and 50 <= indicators.rsi < 70:
            tech += 5
        elif action == "SELL" and 30 < indicators.rsi <= 50:
            tech += 5
        elif action == "BUY" and indicators.rsi >= MAX_RSI_LONG:
            tech -= 8
        elif action == "SELL" and indicators.rsi <= MIN_RSI_SHORT:
            tech -= 8
    if indicators.macd is not None and indicators.macd_signal is not None:
        bullish_macd = indicators.macd > indicators.macd_signal
        if (action == "BUY" and bullish_macd) or (action == "SELL" and not bullish_macd):
            tech += 5
        else:
            tech -= 4
    if indicators.adx is not None and indicators.adx > 25:
        tech += 4
    if patterns:
        tech += min(4, len(patterns))
    parts["technical"] = round(max(0, min(30, tech)), 2)

    # ---- Component 2: market confirmation (max 20) ----
    market = 10.0  # neutral baseline
    if market_breadth is not None:
        # breadth in [0..1]; >0.55 supportive long, <0.45 supportive short
        if action == "BUY":
            market += (market_breadth - 0.5) * 30  # +9 at 0.8 breadth, -3 at 0.4
        else:
            market += (0.5 - market_breadth) * 30
    if sector_strength is not None:
        # sector_strength in [-100..100]
        if action == "BUY":
            market += sector_strength * 0.05
        else:
            market += -sector_strength * 0.05
    parts["market"] = round(max(0, min(20, market)), 2)

    # ---- Component 3: sentiment / regime (max 15) ----
    sentiment = 10.0
    vol = indicators.volatility_pct or 0
    if vol > MAX_VOLATILITY:
        sentiment -= 6
    elif vol > 50:
        sentiment -= 3
    elif vol < 20:
        sentiment += 3
    if data_quality.is_synthetic:
        sentiment -= 10
    elif data_quality.is_stale:
        sentiment -= 4
    elif data_quality.score >= 90:
        sentiment += 2
    parts["sentiment"] = round(max(0, min(15, sentiment)), 2)

    # ---- Component 4: historical / learning (max 20) ----
    history = 10.0
    if setup_win_rate is not None and setup_sample_size >= 4:
        # Centre on 50% win rate
        history += (setup_win_rate - 50) * 0.2  # +10 at 100% wr, -10 at 0%
    if indicator_edge is not None:
        history += indicator_edge * 8           # +8 at +1 edge
    parts["historical"] = round(max(0, min(20, history)), 2)

    # ---- Component 5: risk geometry (max 15) ----
    risk = 5.0
    if rr is not None:
        if rr >= 3.0:
            risk = 15
        elif rr >= 2.0:
            risk = 12
        elif rr >= MIN_RR:
            risk = 8
        elif rr >= 1.0:
            risk = 3
        else:
            risk = 0
    parts["risk"] = round(risk, 2)

    raw_total = (
        parts["technical"]
        + parts["market"]
        + parts["sentiment"]
        + parts["historical"]
        + parts["risk"]
    )
    # Soft scaling: small confidence multiplier so very low confidence
    # signals can't reach STRONG just on RR + clean charts.
    conf_factor = 0.6 + 0.4 * (max(20.0, min(95.0, confidence)) / 100.0)
    score = max(0.0, min(100.0, raw_total * conf_factor))
    parts["confidence_factor"] = round(conf_factor, 3)
    parts["raw_total"] = round(raw_total, 2)

    # ---------------------------------------------------------------
    # HARD NO-TRADE rules — capital preservation first
    # ---------------------------------------------------------------
    if action in ("BUY", "SELL"):
        if data_quality.is_synthetic:
            no_trade.append("market data unavailable / synthetic")
        elif data_quality.score < MIN_DATA_QUALITY:
            no_trade.append(f"data quality {data_quality.score:.0f} < {MIN_DATA_QUALITY}")
        if confidence < MIN_CONFIDENCE:
            no_trade.append(f"confidence {confidence:.0f} < {MIN_CONFIDENCE} floor")
        if rr is None or rr < MIN_RR:
            no_trade.append(f"R:R {rr or 0:.2f} below {MIN_RR} floor")
        if indicators.adx is not None and indicators.adx < MIN_ADX_TREND:
            no_trade.append(f"ADX {indicators.adx:.0f} — no trend strength")
        if vol > MAX_VOLATILITY:
            no_trade.append(f"volatility {vol:.0f}% extreme")
        if action == "BUY" and indicators.rsi is not None and indicators.rsi >= MAX_RSI_LONG:
            no_trade.append(f"RSI {indicators.rsi:.0f} severely overbought")
        if action == "SELL" and indicators.rsi is not None and indicators.rsi <= MIN_RSI_SHORT:
            no_trade.append(f"RSI {indicators.rsi:.0f} severely oversold")
        if market_breadth is not None:
            if action == "BUY" and market_breadth < 0.35:
                no_trade.append(f"market breadth {market_breadth*100:.0f}% — too weak for longs")
            if action == "SELL" and market_breadth > 0.65:
                no_trade.append(f"market breadth {market_breadth*100:.0f}% — too strong for shorts")
        if sector_strength is not None:
            if action == "BUY" and sector_strength < -25:
                no_trade.append(f"sector strength {sector_strength:.0f} — sector falling")
            if action == "SELL" and sector_strength > 25:
                no_trade.append(f"sector strength {sector_strength:.0f} — sector rising")
        # Repeated-failure veto: if setup has been losing 5+ in a row, refuse it
        if (
            setup_win_rate is not None
            and setup_sample_size >= 5
            and setup_win_rate < 25
        ):
            no_trade.append(
                f"setup has failed {setup_sample_size - int(setup_sample_size * setup_win_rate / 100)} of "
                f"{setup_sample_size} historical trials"
            )

    grade = _grade_for(score, bool(no_trade))
    return QualityResult(
        score=round(score, 1),
        grade=grade,
        breakdown=parts,
        no_trade_reasons=no_trade,
    )
