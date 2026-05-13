"""Data sanity checks + quality scoring for market data.

The platform must NOT feed unvalidated data to the AI engine, charts or
the user. This module exposes pure functions used by:

- ``market_data`` (post-fetch validation, fall-through to alternative sources)
- ``signal_engine`` (lowers confidence when data quality is poor)
- chart endpoints (skip corrupted candles)
- the new ``DataQuality`` schema returned alongside quotes / OHLC

Everything here is deterministic and side-effect free except for ``loguru``
debug logs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger


# Trading-hours bounds for "stale" detection (Asia/Kolkata)
_IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class DataQuality:
    score: float = 100.0          # 0..100 (higher = better)
    issues: List[str] = field(default_factory=list)
    is_stale: bool = False
    is_synthetic: bool = False
    source: str = "yfinance"
    last_bar_at: Optional[datetime] = None

    def degrade(self, points: float, reason: str) -> None:
        self.score = max(0.0, round(self.score - points, 2))
        self.issues.append(reason)

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "issues": list(self.issues),
            "is_stale": self.is_stale,
            "is_synthetic": self.is_synthetic,
            "source": self.source,
            "last_bar_at": self.last_bar_at.isoformat() if self.last_bar_at else None,
        }


# ---------------------------------------------------------------------------
# OHLC integrity
# ---------------------------------------------------------------------------


def _is_finite(x: float | None) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(float(x))


def _row_ok(open_: float, high: float, low: float, close: float, volume: float | None) -> tuple[bool, Optional[str]]:
    """Return (ok, reason). ``volume`` may be None for some intervals."""
    for label, v in (("open", open_), ("high", high), ("low", low), ("close", close)):
        if not _is_finite(v) or v <= 0:
            return False, f"non-positive/NaN {label}"
    if volume is not None and _is_finite(volume) and volume < 0:
        return False, "negative volume"
    if high < max(open_, close):
        return False, "high < max(open, close)"
    if low > min(open_, close):
        return False, "low > min(open, close)"
    if high < low:
        return False, "high < low"
    return True, None


def validate_ohlc_df(
    df: pd.DataFrame,
    *,
    symbol: str = "?",
    max_jump_pct: float = 35.0,
) -> tuple[pd.DataFrame, DataQuality]:
    """Drop obviously-broken bars and produce a ``DataQuality`` summary.

    - Negative / NaN / non-positive prices -> dropped.
    - High < max(O,C) or Low > min(O,C) -> dropped.
    - Single-bar percentage jumps > ``max_jump_pct`` -> dropped (unless
      consistently followed by similar bars; we keep the change but log).
    - Duplicated timestamps -> the latest row wins.
    - Resulting dataframe is sorted by index ascending.
    """
    quality = DataQuality()
    if df is None or len(df) == 0:
        quality.degrade(100, "empty dataframe")
        return df if df is not None else pd.DataFrame(), quality

    needed = {"Open", "High", "Low", "Close"}
    missing = needed - set(df.columns)
    if missing:
        quality.degrade(80, f"missing columns: {missing}")
        return pd.DataFrame(), quality

    work = df.copy()
    work = work[~work.index.duplicated(keep="last")]
    work = work.sort_index()

    # Drop broken candles
    keep_mask = []
    dropped = 0
    for ts, row in work.iterrows():
        ok, reason = _row_ok(
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            float(row["Volume"]) if "Volume" in work else None,
        )
        if not ok:
            dropped += 1
            keep_mask.append(False)
            logger.debug(f"validate_ohlc[{symbol}] drop {ts}: {reason}")
        else:
            keep_mask.append(True)
    if dropped:
        quality.degrade(min(20, dropped * 2), f"{dropped} corrupted candle(s)")
    work = work[pd.Series(keep_mask, index=work.index)]

    if work.empty:
        quality.degrade(40, "all bars rejected")
        return work, quality

    # Impossible price jumps
    pct = work["Close"].pct_change().abs() * 100
    jumps = pct[pct > max_jump_pct]
    if not jumps.empty:
        # Heuristic: only drop a single isolated spike (next bar mean-reverts).
        for ts in jumps.index:
            i = work.index.get_loc(ts)
            if i == 0 or i >= len(work) - 1:
                continue
            prev_close = float(work["Close"].iloc[i - 1])
            this_close = float(work["Close"].iloc[i])
            next_close = float(work["Close"].iloc[i + 1])
            recovers = abs(next_close - prev_close) / prev_close * 100 < max_jump_pct / 2
            if recovers:
                work = work.drop(index=ts)
                quality.degrade(5, f"isolated {pct[ts]:.1f}% spike dropped")

    # Missing-data sanity (intra-day specifically)
    if len(work) > 1:
        gaps = pd.Series(work.index).diff().dt.total_seconds().dropna()
        if not gaps.empty:
            median_gap = gaps.median()
            big = (gaps > median_gap * 5).sum()
            if big > max(2, int(len(work) * 0.05)):
                quality.degrade(5, "irregular bar spacing")

    quality.last_bar_at = work.index[-1].to_pydatetime() if len(work) else None
    return work, quality


# ---------------------------------------------------------------------------
# Quote sanity & freshness
# ---------------------------------------------------------------------------


def validate_quote_dict(
    q: Dict,
    *,
    symbol: str,
    last_bar_at: Optional[datetime] = None,
    market_open: bool = True,
) -> DataQuality:
    """Sanity-check a Quote-like dict and produce its quality summary."""
    quality = DataQuality()
    price = q.get("price")
    prev = q.get("prev_close")
    high = q.get("high")
    low = q.get("low")
    open_ = q.get("open")

    if not _is_finite(price) or (price is not None and price <= 0):
        quality.degrade(60, "invalid price")
    if prev is not None:
        if not _is_finite(prev) or prev <= 0:
            quality.degrade(20, "invalid prev close")
        elif _is_finite(price):
            chg_pct = abs(price - prev) / prev * 100
            if chg_pct > 35:
                quality.degrade(20, f"{chg_pct:.1f}% jump vs prev close")
    if high is not None and low is not None and _is_finite(high) and _is_finite(low):
        if high < low:
            quality.degrade(25, "high < low")
        if _is_finite(price) and (price > high * 1.02 or price < low * 0.98):
            quality.degrade(10, "live price outside session range")

    ts = q.get("timestamp") or last_bar_at
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            ts = None
    if ts is not None:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        if market_open and age_min > 5:
            quality.is_stale = True
            quality.degrade(min(20, age_min / 5), f"data {age_min:.0f} min stale")
        if not market_open and age_min > 60 * 24 * 5:
            quality.degrade(5, "no recent data even outside trading hours")
    quality.last_bar_at = ts if isinstance(ts, datetime) else None
    return quality


def merge_quality(a: DataQuality, b: DataQuality) -> DataQuality:
    """Combine two quality reports (e.g. quote + OHLC)."""
    out = DataQuality()
    out.score = round(min(a.score, b.score), 2)
    out.issues = list(dict.fromkeys(a.issues + b.issues))
    out.is_stale = a.is_stale or b.is_stale
    out.is_synthetic = a.is_synthetic or b.is_synthetic
    out.source = a.source or b.source
    out.last_bar_at = a.last_bar_at or b.last_bar_at
    return out
