"""Rule-based + scored signal engine.

Combines indicators + patterns + recent price action to produce a final
BUY/SELL/HOLD signal with entry/stoploss/targets and a confidence score.

The LLM (ai_engine.explain_signal) is layered on top to add reasoning text,
but the trading decision itself is **deterministic** so it can be backtested
and reasoned about.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from ..schemas.common import Indicators, Signal
from .indicators import compute_indicators
from .market_data import get_history, get_quality, get_quote
from .patterns import detected_patterns
from . import confidence_engine, quality_engine, scoring_engine


# Per-scan context cache so the breadth/sector calls don't fire 80 times.
# Populated by ``scan_signals`` before fanning out.
_SCAN_CONTEXT: dict = {}


def set_scan_context(*, breadth: float | None, sector_strength: dict | None) -> None:
    """Inject batch context (market breadth, sector strengths) for the
    current scan so each ``build_signal`` doesn't recompute them.
    """
    _SCAN_CONTEXT.clear()
    if breadth is not None:
        _SCAN_CONTEXT["breadth"] = breadth
    if sector_strength is not None:
        _SCAN_CONTEXT["sector_strength"] = sector_strength


def _ctx_breadth() -> float | None:
    return _SCAN_CONTEXT.get("breadth")


def _ctx_sector_strength(sector: str | None) -> float | None:
    if sector is None:
        return None
    ss = _SCAN_CONTEXT.get("sector_strength") or {}
    return ss.get(sector)


def _trend_score(ind: Indicators, last_close: float, weights: dict | None = None) -> float:
    weights = weights or {}
    ema_w = weights.get("ema_stack", 1.0)
    adx_w = weights.get("adx", 1.0)
    score = 0.0
    if ind.ema20 and ind.ema50 and ind.ema200:
        if ind.ema20 > ind.ema50 > ind.ema200:
            score += 25 * ema_w
        elif ind.ema20 < ind.ema50 < ind.ema200:
            score -= 25 * ema_w
        if last_close > ind.ema50:
            score += 10 * ema_w
        else:
            score -= 10 * ema_w
    if ind.adx and ind.adx > 25:
        score *= 1.0 + 0.15 * adx_w  # trending market amplifies the signal
    return score


def _momentum_score(ind: Indicators, weights: dict | None = None) -> float:
    weights = weights or {}
    rsi_w = weights.get("rsi", 1.0)
    macd_w = weights.get("macd", 1.0)
    score = 0.0
    if ind.rsi is not None:
        if 50 < ind.rsi < 70:
            score += 15 * rsi_w
        elif ind.rsi >= 70:
            score -= 5 * rsi_w  # overbought, risky long
        elif 30 < ind.rsi < 50:
            score -= 5 * rsi_w
        elif ind.rsi <= 30:
            score += 10 * rsi_w
    if ind.macd is not None and ind.macd_signal is not None:
        if ind.macd > ind.macd_signal:
            score += 10 * macd_w
        else:
            score -= 10 * macd_w
        if ind.macd_hist is not None and ind.macd_hist > 0:
            score += 5 * macd_w
    return score


def _volatility_adjustment(ind: Indicators) -> float:
    if not ind.volatility_pct:
        return 1.0
    if ind.volatility_pct > 60:
        return 0.7
    if ind.volatility_pct < 15:
        return 1.1
    return 1.0


def _pattern_score(patterns: List[str], pattern_weights: dict | None = None) -> float:
    bull = {"Hammer", "Bullish Engulfing", "Morning Star", "Bullish Marubozu",
            "20-day breakout", "Near 52-week high", "Uptrend (HH/HL)",
            "Volume spike (>2x avg)"}
    bear = {"Shooting Star", "Bearish Engulfing", "Evening Star", "Bearish Marubozu",
            "20-day breakdown", "Near 52-week low", "Downtrend (LH/LL)"}
    pattern_weights = pattern_weights or {}
    s = 0.0
    for p in patterns:
        w = pattern_weights.get(p, 1.0)
        if p in bull:
            s += 8 * w
        elif p in bear:
            s -= 8 * w
    return s


def relative_strength(symbol: str, benchmark: str = "^NSEI") -> Optional[float]:
    """Rolling 20-day return delta vs benchmark, in pct points."""
    try:
        s = get_history(symbol, period="3mo", interval="1d")["Close"].pct_change().tail(20).sum()
        b = get_history(benchmark, period="3mo", interval="1d")["Close"].pct_change().tail(20).sum()
        return round(float((s - b) * 100), 2)
    except Exception:
        return None


def build_signal(symbol: str, mode: str = "swing") -> tuple[Signal, Indicators, list[str]]:
    """Compute deterministic signal for a symbol.

    Returns (signal, indicators, patterns).
    """
    period_map = {"intraday": "5d", "swing": "6mo", "positional": "2y"}
    interval_map = {"intraday": "15m", "swing": "1d", "positional": "1d"}
    period = period_map.get(mode, "6mo")
    interval = interval_map.get(mode, "1d")

    df = get_history(symbol, period=period, interval=interval)
    if df.empty:
        return (
            Signal(symbol=symbol, action="HOLD", confidence=0, reasoning="No data"),
            Indicators(), [],
        )

    ind = compute_indicators(df)
    pats = detected_patterns(df)
    last_close = float(df["Close"].iloc[-1])
    atr = ind.atr or max(last_close * 0.015, 0.5)

    # Adaptive weights learned from past outcomes (default 1.0 if no data yet).
    try:
        from . import market_regime as mr  # local import to avoid cycles at import time
        regime = mr.get_current_regime().regime
    except Exception:
        regime = None
    ind_w = scoring_engine.get_indicator_weights(mode, regime)
    pat_w = scoring_engine.get_pattern_weights(mode)

    score = 0.0
    score += _trend_score(ind, last_close, ind_w)
    score += _momentum_score(ind, ind_w)
    score += _pattern_score(pats, pat_w)
    score *= _volatility_adjustment(ind)

    # Map score to action
    if score >= 25:
        action = "BUY"
    elif score <= -25:
        action = "SELL"
    else:
        action = "HOLD"

    raw_confidence = float(max(0.0, min(99.0, 50 + score * 0.6)))
    confidence = confidence_engine.calibration_correction(raw_confidence, mode)
    probability = round(0.5 + score / 200, 4)
    probability = max(0.05, min(0.95, probability))

    # Data-quality guardrail: AI must never claim certainty on shaky data.
    data_quality = get_quality(symbol)
    quality_penalty = 0.0
    if data_quality.is_synthetic:
        quality_penalty = max(quality_penalty, 30.0)
    if data_quality.is_stale:
        quality_penalty = max(quality_penalty, 15.0)
    if data_quality.score < 70:
        quality_penalty = max(quality_penalty, (70 - data_quality.score) * 0.5)
    if quality_penalty:
        confidence = max(5.0, confidence - quality_penalty)

    # Entry / SL / Targets based on ATR & action
    if action == "BUY":
        entry_low = round(last_close - 0.2 * atr, 2)
        entry_high = round(last_close + 0.2 * atr, 2)
        stoploss = round(last_close - 1.5 * atr, 2)
        target1 = round(last_close + 2 * atr, 2)
        target2 = round(last_close + 4 * atr, 2)
    elif action == "SELL":
        entry_low = round(last_close - 0.2 * atr, 2)
        entry_high = round(last_close + 0.2 * atr, 2)
        stoploss = round(last_close + 1.5 * atr, 2)
        target1 = round(last_close - 2 * atr, 2)
        target2 = round(last_close - 4 * atr, 2)
    else:
        entry_low = entry_high = stoploss = target1 = target2 = None

    rr = None
    if action != "HOLD" and stoploss and target1:
        risk = abs(last_close - stoploss)
        reward = abs(target1 - last_close)
        rr = round(reward / risk, 2) if risk else None

    # ----- Quality Control System (composite quality score + NO-TRADE veto) -----
    # Look up adaptive setup quality (from learning_engine) for this setup name
    setup_win_rate: float | None = None
    setup_n: int = 0
    try:
        from ..database import db_session
        from ..models.prediction_engine import SignalQualityScore
        setup_label = pats[0] if pats else "Generic Setup"
        with db_session() as db:
            row = (
                db.query(SignalQualityScore)
                .filter(
                    SignalQualityScore.setup_name == setup_label,
                    SignalQualityScore.mode == mode,
                )
                .one_or_none()
            )
            if row:
                setup_win_rate = row.win_rate
                setup_n = row.sample_size
    except Exception:
        pass

    # Pull breadth + sector from the per-scan context (set once per scan).
    breadth = _ctx_breadth()
    try:
        from . import stock_master
        sector = stock_master.get_sector(symbol)
    except Exception:
        sector = None
    sector_strength_val = _ctx_sector_strength(sector)

    # Composite indicator edge (already adapted to win/loss history)
    active_inds: list[str] = []
    if ind.ema20 and ind.ema50 and ind.ema200:
        active_inds.append("ema_stack")
    if ind.rsi is not None:
        active_inds.append("rsi")
    if ind.macd is not None:
        active_inds.append("macd")
    if ind.adx is not None and ind.adx > 25:
        active_inds.append("adx")
    indicator_edge = None
    try:
        mult = scoring_engine.composite_indicator_multiplier(mode, regime, active_inds)
        indicator_edge = round((mult - 1.0) * 2, 3)  # 0.5..1.5 → -1..+1
    except Exception:
        pass

    quality = quality_engine.evaluate(
        action=action,
        confidence=confidence,
        rr=rr,
        indicators=ind,
        data_quality=data_quality,
        patterns=pats,
        market_breadth=breadth,
        sector_strength=sector_strength_val,
        setup_win_rate=setup_win_rate,
        setup_sample_size=setup_n,
        indicator_edge=indicator_edge,
    )
    no_trade_reasons = quality.no_trade_reasons
    if no_trade_reasons:
        action = "HOLD"
        confidence = min(confidence, 35.0)
        entry_low = entry_high = stoploss = target1 = target2 = None
        rr = None

    # ----- ML confidence blend (only when model is trained + signal is actionable) -----
    rule_confidence_value = round(confidence, 1)
    ml_confidence_value: float | None = None
    ml_p_win_value: float | None = None
    if action in ("BUY", "SELL"):
        try:
            from . import ml_confidence  # local to avoid import cost when no model
            ml_out = ml_confidence.score_signal(
                action=action,
                mode=mode,
                confidence_rule=confidence,
                score=score,
                entry_ref=last_close,
                stoploss=stoploss,
                target1=target1,
                rr=rr,
                atr=atr,
                market_regime=regime,
                news_sentiment=None,
                sector_strength=sector_strength_val,
                breadth_advancers=None,
                breadth_decliners=None,
                indicators=ind.model_dump(),
                patterns=pats,
            )
            if ml_out is not None:
                ml_confidence_value = ml_out["ml_confidence"]
                ml_p_win_value = ml_out["p_win"]
                confidence = ml_out["blended_confidence"]
        except Exception:
            pass

    reasoning_bits = []
    if ind.ema20 and ind.ema50 and ind.ema200:
        if ind.ema20 > ind.ema50 > ind.ema200:
            reasoning_bits.append("EMA stack (20>50>200) confirms uptrend")
        elif ind.ema20 < ind.ema50 < ind.ema200:
            reasoning_bits.append("EMA stack (20<50<200) confirms downtrend")
    if ind.rsi is not None:
        reasoning_bits.append(f"RSI at {ind.rsi:.1f}")
    if ind.macd is not None and ind.macd_signal is not None:
        reasoning_bits.append(
            "MACD bullish crossover" if ind.macd > ind.macd_signal else "MACD bearish"
        )
    if ind.adx is not None and ind.adx > 25:
        reasoning_bits.append(f"ADX {ind.adx:.0f} indicates trending market")
    if pats:
        reasoning_bits.append("Patterns: " + ", ".join(pats[:5]))
    if quality_penalty > 0:
        reasoning_bits.append(
            f"Signal confidence reduced due to incomplete market data "
            f"(quality={data_quality.score:.0f}/100, source={data_quality.source})"
        )
    if no_trade_reasons:
        reasoning_bits.append("NO TRADE — " + "; ".join(no_trade_reasons))

    if ml_confidence_value is not None:
        reasoning_bits.append(
            f"ML blend: rule {rule_confidence_value:.0f} → ml {ml_confidence_value:.0f} "
            f"→ final {round(confidence, 1):.0f}"
        )

    sig = Signal(
        symbol=symbol,
        action=action,  # type: ignore[arg-type]
        confidence=round(confidence, 1),
        entry_low=entry_low,
        entry_high=entry_high,
        stoploss=stoploss,
        target1=target1,
        target2=target2,
        rr=rr,
        mode=mode,  # type: ignore[arg-type]
        reasoning=" | ".join(reasoning_bits) or "Mixed signals — staying on sidelines.",
        score=round(score, 2),
        probability=probability,
        detected_patterns=pats,
        quality_score=quality.score,
        quality_grade=quality.grade,  # type: ignore[arg-type]
        quality_breakdown=quality.breakdown,
        no_trade_reasons=no_trade_reasons,
        ml_confidence=ml_confidence_value,
        ml_p_win=ml_p_win_value,
        rule_confidence=rule_confidence_value,
    )
    return sig, ind, pats


_ACTIONABLE_GRADES = {"MODERATE", "STRONG", "HIGH_CONVICTION"}


def scan_signals(
    symbols: List[str],
    mode: str = "swing",
    min_conf: float = 60,
    min_grade: str = "MODERATE",
    track: bool = True,
) -> List[Signal]:
    """Run the engine on a list of symbols and return actionable signals.

    Quality control:
    - Only signals with ``quality_grade`` >= ``min_grade`` are returned.
    - Per-scan market context (breadth + sector strength) is computed once
      and shared across all workers, eliminating ~80 redundant API calls.
    - Uses a thread pool so 80 symbols finish in ~1 wall-second.

    When ``track=True`` (default) each actionable signal is persisted to
    ``prediction_history`` via the prediction tracker so the validation
    + learning loop can evaluate it later.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    out: List[Signal] = []
    indicators_by_symbol: dict[str, Indicators] = {}

    if not symbols:
        return out

    # ---- Populate per-scan context once (breadth + sector strength) ----
    try:
        from . import correlation_engine, stock_master
        # Liquid subset for breadth so the snapshot is meaningful and fast
        liq = stock_master.liquid_symbols(80)
        b = correlation_engine.market_breadth(liq)
        total = (b.get("advancers", 0) + b.get("decliners", 0) + b.get("unchanged", 0)) or 1
        breadth_ratio = b.get("advancers", 0) / total
        sec_strength_rows = correlation_engine.sector_strength(period="1mo")
        sec_strength_map = {r["sector"]: r["strength"] for r in sec_strength_rows}
        set_scan_context(breadth=breadth_ratio, sector_strength=sec_strength_map)
    except Exception:
        set_scan_context(breadth=None, sector_strength=None)

    grade_rank = {
        "AVOID": 0, "WEAK": 1, "MODERATE": 2, "STRONG": 3, "HIGH_CONVICTION": 4,
        "NO_TRADE": -1,
    }
    min_rank = grade_rank.get(min_grade, 2)

    def _one(sym: str):
        try:
            return sym, build_signal(sym, mode=mode)
        except Exception:
            return sym, None

    workers = min(12, max(2, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="scan") as pool:
        for fut in as_completed([pool.submit(_one, s) for s in symbols]):
            sym, res = fut.result()
            if res is None:
                continue
            sig, ind, _ = res
            if (
                sig.action in ("BUY", "SELL")
                and sig.confidence >= min_conf
                and grade_rank.get(sig.quality_grade, 0) >= min_rank
            ):
                out.append(sig)
                indicators_by_symbol[sym] = ind
    # Sort by quality first, then confidence
    out.sort(key=lambda s: (s.quality_score, s.confidence), reverse=True)
    if track and out:
        try:
            from . import prediction_tracker
            prediction_tracker.record_signals(out, indicators_by_symbol)
        except Exception:  # pragma: no cover - tracking must never break a scan
            pass
    return out
