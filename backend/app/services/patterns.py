"""Lightweight candle / chart pattern detection (no TA-Lib dependency)."""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(h - l, 1e-9)


def detect_candle_patterns(df: pd.DataFrame) -> List[str]:
    """Return a list of candle patterns detected on the **most recent** candle
    (and confirmed by the prior 1-2 candles where appropriate).
    """
    if df is None or df.empty or len(df) < 3:
        return []
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    o3, h3, l3, c3 = o.iloc[-3], h.iloc[-3], l.iloc[-3], c.iloc[-3]
    o2, h2, l2, c2 = o.iloc[-2], h.iloc[-2], l.iloc[-2], c.iloc[-2]
    o1, h1, l1, c1 = o.iloc[-1], h.iloc[-1], l.iloc[-1], c.iloc[-1]

    patterns: List[str] = []

    body1, rng1 = _body(o1, c1), _range(h1, l1)
    body2, rng2 = _body(o2, c2), _range(h2, l2)
    upper1 = h1 - max(o1, c1)
    lower1 = min(o1, c1) - l1

    # Doji
    if body1 / rng1 < 0.1:
        patterns.append("Doji")

    # Hammer (bullish reversal)
    if (
        c1 > o1
        and lower1 > 2 * body1
        and upper1 < body1
        and c2 < o2  # prior bearish
    ):
        patterns.append("Hammer")

    # Shooting star (bearish reversal)
    if (
        o1 > c1
        and upper1 > 2 * body1
        and lower1 < body1
        and c2 > o2
    ):
        patterns.append("Shooting Star")

    # Bullish engulfing
    if c2 < o2 and c1 > o1 and c1 > o2 and o1 < c2 and body1 > body2:
        patterns.append("Bullish Engulfing")

    # Bearish engulfing
    if c2 > o2 and c1 < o1 and o1 > c2 and c1 < o2 and body1 > body2:
        patterns.append("Bearish Engulfing")

    # Morning star
    if (
        c3 < o3
        and body2 / _range(h2, l2) < 0.3
        and c1 > o1
        and c1 > (o3 + c3) / 2
    ):
        patterns.append("Morning Star")

    # Evening star
    if (
        c3 > o3
        and body2 / _range(h2, l2) < 0.3
        and c1 < o1
        and c1 < (o3 + c3) / 2
    ):
        patterns.append("Evening Star")

    # Marubozu
    if body1 / rng1 > 0.9:
        patterns.append("Bullish Marubozu" if c1 > o1 else "Bearish Marubozu")

    return patterns


def detect_chart_patterns(df: pd.DataFrame) -> List[str]:
    """Coarse chart-pattern hints based on rolling extremes."""
    if df is None or df.empty or len(df) < 60:
        return []
    out: List[str] = []
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)

    last = close.iloc[-1]
    hi20 = high.rolling(20).max().iloc[-2]  # exclude today
    lo20 = low.rolling(20).min().iloc[-2]
    hi52w = high.rolling(252).max().iloc[-1] if len(df) >= 252 else high.max()
    lo52w = low.rolling(252).min().iloc[-1] if len(df) >= 252 else low.min()

    if last > hi20:
        out.append("20-day breakout")
    if last < lo20:
        out.append("20-day breakdown")
    if last >= hi52w * 0.99:
        out.append("Near 52-week high")
    if last <= lo52w * 1.01:
        out.append("Near 52-week low")

    # Higher highs, higher lows over last ~30 sessions => uptrend
    seg = df.tail(30)
    if (
        seg["High"].iloc[-1] > seg["High"].iloc[0]
        and seg["Low"].iloc[-1] > seg["Low"].iloc[0]
    ):
        out.append("Uptrend (HH/HL)")
    if (
        seg["High"].iloc[-1] < seg["High"].iloc[0]
        and seg["Low"].iloc[-1] < seg["Low"].iloc[0]
    ):
        out.append("Downtrend (LH/LL)")

    # Volume spike
    if "Volume" in df:
        v = df["Volume"].astype(float)
        avg_v = v.rolling(20).mean().iloc[-1]
        if avg_v and v.iloc[-1] > 2 * avg_v:
            out.append("Volume spike (>2x avg)")
    return out


def detected_patterns(df: pd.DataFrame) -> List[str]:
    return detect_candle_patterns(df) + detect_chart_patterns(df)
