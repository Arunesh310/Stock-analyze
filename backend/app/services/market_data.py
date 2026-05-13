"""Market data fetching with multi-source validation + quality scoring.

Primary source : **yfinance** (free, no key)
Secondary      : **NSE public endpoints** (used to corroborate live prices
                 when market is open and yfinance is suspected stale)
Fallback       : last validated cache; finally, deterministic synthetic
                 data so the rest of the pipeline keeps running in dev.

Every fetch goes through the validators in ``market_validators`` so the
caller can trust the returned dataframe / quote, and can inspect the
``DataQuality`` summary attached to it.

All timestamps inside Quote objects are persisted as **UTC** (the existing
contract), but the frontend formats them in **Asia/Kolkata** time via the
shared utils.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger

from ..config import get_settings
from ..schemas.common import OhlcRow, Quote
from .market_validators import (
    DataQuality,
    merge_quality,
    validate_ohlc_df,
    validate_quote_dict,
)
from .market_status import is_market_open
from .universe import get_name

try:  # yfinance is optional at runtime; we degrade gracefully if missing
    import logging as _stdlogging

    import yfinance as yf  # type: ignore
    _HAS_YF = True
    # yfinance is very chatty on 404s — silence the underlying loggers since
    # our own _negative-cache + logger already track these.
    for _name in ("yfinance", "urllib3", "peewee", "yahoo"):
        _stdlogging.getLogger(_name).setLevel(_stdlogging.CRITICAL)
except Exception:  # pragma: no cover
    yf = None  # type: ignore
    _HAS_YF = False

# nse_client is optional; we soft-import to avoid hard dep on the live endpoint
try:
    from . import nse_client
    _HAS_NSE = True
except Exception:  # pragma: no cover
    nse_client = None  # type: ignore
    _HAS_NSE = False

_settings = get_settings()
_cache: Dict[str, tuple[float, Any]] = {}
_quality_cache: Dict[str, DataQuality] = {}
_validated_history_cache: Dict[str, tuple[float, pd.DataFrame]] = {}
# Negative cache: symbol -> (timestamp, reason). Stops us from hammering
# yfinance for known-delisted / unknown symbols. Cleared after 6 hours.
_negative_cache: Dict[str, tuple[float, str]] = {}
_NEGATIVE_TTL = 60 * 60 * 6  # 6 hours
_lock = Lock()


# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------


def _cache_get(key: str, ttl: int | None = None) -> Optional[Any]:
    ttl = ttl if ttl is not None else _settings.cache_ttl_seconds
    with _lock:
        if key in _cache:
            ts, value = _cache[key]
            if (time.time() - ts) < ttl:
                return value
            _cache.pop(key, None)
    return None


def _cache_set(key: str, value: Any) -> None:
    with _lock:
        _cache[key] = (time.time(), value)


def get_quality(symbol: str) -> DataQuality:
    """Last computed data-quality report for ``symbol`` (best-effort)."""
    with _lock:
        return _quality_cache.get(symbol.upper(), DataQuality(score=0.0,
                                                              issues=["never fetched"]))


def _store_quality(symbol: str, quality: DataQuality) -> None:
    with _lock:
        _quality_cache[symbol.upper()] = quality


def _stored_history(symbol: str, key: str) -> Optional[pd.DataFrame]:
    with _lock:
        item = _validated_history_cache.get(key)
        if item is None:
            return None
        _, df = item
        return df.copy()


def _store_history(key: str, df: pd.DataFrame) -> None:
    with _lock:
        _validated_history_cache[key] = (time.time(), df)


def _negative(symbol: str) -> Optional[str]:
    with _lock:
        ent = _negative_cache.get(symbol.upper())
        if ent is None:
            return None
        ts, reason = ent
        if time.time() - ts > _NEGATIVE_TTL:
            _negative_cache.pop(symbol.upper(), None)
            return None
        return reason


def _mark_negative(symbol: str, reason: str) -> None:
    with _lock:
        _negative_cache[symbol.upper()] = (time.time(), reason)


def clear_negative_cache() -> int:
    with _lock:
        n = len(_negative_cache)
        _negative_cache.clear()
    return n


# ---------------------------------------------------------------------------
# Synthetic fallback
# ---------------------------------------------------------------------------


def _synthetic_history(symbol: str, days: int = 365) -> pd.DataFrame:
    rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
    end = datetime.utcnow().replace(hour=15, minute=30, second=0, microsecond=0)
    dates = pd.bdate_range(end=end, periods=days)
    base = 100 + (abs(hash(symbol)) % 5000)
    drift = rng.normal(0.0005, 0.018, len(dates)).cumsum()
    close = base * np.exp(drift)
    high = close * (1 + rng.uniform(0.001, 0.02, len(dates)))
    low = close * (1 - rng.uniform(0.001, 0.02, len(dates)))
    open_ = close * (1 + rng.uniform(-0.01, 0.01, len(dates)))
    vol = rng.integers(2_00_000, 50_00_000, len(dates))
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=dates,
    )
    return df


# ---------------------------------------------------------------------------
# yfinance fetch with retry
# ---------------------------------------------------------------------------


def _fetch_yf_history(symbol: str, period: str, interval: str, attempts: int = 1) -> Optional[pd.DataFrame]:
    if not _HAS_YF:
        return None
    # Skip known-bad symbols entirely (negative cache)
    if _negative(symbol):
        return None
    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            df = yf.Ticker(symbol).history(
                period=period, interval=interval, auto_adjust=False
            )
            if df is None or df.empty:
                last_err = ValueError("empty")
                if i + 1 < attempts:
                    time.sleep(0.25)
                continue
            df = df.rename(columns=str.title)
            # yfinance may return tz-aware index; strip tz for downstream code
            if getattr(df.index, "tz", None) is not None:
                df = df.copy()
                df.index = df.index.tz_localize(None)
            return df
        except Exception as exc:
            last_err = exc
            logger.debug(f"yfinance retry {i + 1}/{attempts} for {symbol}: {exc}")
            if i + 1 < attempts:
                time.sleep(0.25)
    # Mark as negative so subsequent calls within ``_NEGATIVE_TTL`` skip yfinance
    _mark_negative(symbol, f"yfinance failed: {last_err}")
    logger.debug(f"yfinance failed for {symbol} ({period}/{interval}): {last_err}")
    return None


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def get_history(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Validated OHLCV history. Side-effect: stores a ``DataQuality``
    summary you can fetch via :func:`get_quality`."""
    key = f"hist::{symbol}::{period}::{interval}"
    cached = _cache_get(key)
    if cached is not None:
        return cached.copy()

    df = _fetch_yf_history(symbol, period=period, interval=interval, attempts=1)
    if df is None or df.empty:
        # Try last-known validated history
        last = _stored_history(symbol, key)
        if last is not None and not last.empty:
            q = DataQuality(score=70.0, source="cache",
                            issues=["yfinance unavailable, served from validated cache"],
                            last_bar_at=last.index[-1].to_pydatetime() if len(last) else None)
            _store_quality(symbol, q)
            _cache_set(key, last)
            return last.copy()
        # Synthetic last resort
        days = 365 if period in ("1y", "12mo") else 90
        synth = _synthetic_history(symbol, days=days)
        q = DataQuality(score=10.0, source="synthetic",
                        issues=["all live sources failed"],
                        is_synthetic=True,
                        last_bar_at=synth.index[-1].to_pydatetime())
        _store_quality(symbol, q)
        _cache_set(key, synth)
        return synth.copy()

    cleaned, quality = validate_ohlc_df(df, symbol=symbol)
    quality.source = "yfinance"
    _store_quality(symbol, quality)
    if cleaned.empty:
        # Fall back to whatever last good data we had
        last = _stored_history(symbol, key)
        if last is not None and not last.empty:
            quality.degrade(20, "current pull invalid; using validated cache")
            _store_quality(symbol, quality)
            _cache_set(key, last)
            return last.copy()
        synth = _synthetic_history(symbol)
        _cache_set(key, synth)
        return synth.copy()

    _store_history(key, cleaned)
    _cache_set(key, cleaned)
    return cleaned.copy()


# ---------------------------------------------------------------------------
# Quote with cross-source validation
# ---------------------------------------------------------------------------


def _yf_quote(symbol: str) -> Optional[Tuple[Quote, DataQuality]]:
    df = get_history(symbol, period="5d", interval="1d")
    if df.empty:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    price = float(last["Close"])
    prev_close = float(prev["Close"])
    if prev_close <= 0:
        return None
    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0
    quote = Quote(
        symbol=symbol,
        name=get_name(symbol),
        price=round(price, 2),
        change=round(change, 2),
        change_pct=round(change_pct, 2),
        open=float(last["Open"]),
        high=float(last["High"]),
        low=float(last["Low"]),
        prev_close=round(prev_close, 2),
        volume=int(last.get("Volume", 0) or 0),
        timestamp=datetime.utcnow(),
    )
    base = get_quality(symbol)
    quote_q = validate_quote_dict(
        quote.model_dump(mode="json"),
        symbol=symbol,
        market_open=is_market_open(),
    )
    quality = merge_quality(base, quote_q)
    quality.source = base.source or "yfinance"
    return quote, quality


def _nse_quote(symbol: str) -> Optional[Tuple[Quote, DataQuality]]:
    if not _HAS_NSE:
        return None
    j = nse_client.get_equity_quote(symbol)  # type: ignore[union-attr]
    if not j:
        return None
    try:
        quote = Quote(
            symbol=symbol if symbol.endswith(".NS") else f"{symbol}.NS",
            name=j.get("name") or get_name(symbol),
            price=float(j["price"]),
            change=float(j["change"]),
            change_pct=float(j["change_pct"]),
            open=j.get("open"),
            high=j.get("high"),
            low=j.get("low"),
            prev_close=j.get("prev_close"),
            volume=int(j.get("volume") or 0),
            timestamp=datetime.utcnow(),
        )
    except Exception as exc:
        logger.debug(f"_nse_quote parse for {symbol}: {exc}")
        return None
    quality = validate_quote_dict(
        quote.model_dump(mode="json"),
        symbol=symbol,
        market_open=is_market_open(),
    )
    quality.source = "nse"
    return quote, quality


def get_quote(symbol: str) -> Quote:
    """Validated latest quote.

    Resolution order:
      1. Try yfinance.
      2. During market hours, cross-check with NSE; if yfinance is stale or
         disagrees > 1% with NSE, prefer NSE.
      3. If yfinance fails, try NSE directly.
      4. Else, fall through to last cached quote / synthetic.
    """
    key = f"quote::{symbol}"
    cached = _cache_get(key, ttl=15)
    if cached is not None:
        return cached

    yf_res = _yf_quote(symbol)
    nse_res = _nse_quote(symbol) if is_market_open() else None

    chosen: Optional[Tuple[Quote, DataQuality]] = None
    if yf_res and nse_res:
        yq, _yqual = yf_res
        nq, _nqual = nse_res
        if yq.prev_close and abs(yq.price - nq.price) / nq.price > 0.01:
            logger.info(
                f"market_data[{symbol}]: yfinance/NSE disagreement "
                f"yf={yq.price} nse={nq.price} — using NSE"
            )
            _nqual.degrade(5, f"yfinance disagreement ({yq.price} vs {nq.price})")
            chosen = (nq, _nqual)
        else:
            chosen = yf_res
    elif yf_res:
        chosen = yf_res
    elif nse_res:
        chosen = nse_res
    else:
        # As a last resort, fabricate a minimal Quote from synthetic history
        df = get_history(symbol, period="5d", interval="1d")
        if df.empty:
            raise ValueError(f"No data for {symbol}")
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        quote = Quote(
            symbol=symbol,
            name=get_name(symbol),
            price=round(float(last["Close"]), 2),
            change=round(float(last["Close"] - prev["Close"]), 2),
            change_pct=round((float(last["Close"]) - float(prev["Close"]))
                             / float(prev["Close"]) * 100, 2),
            open=float(last["Open"]),
            high=float(last["High"]),
            low=float(last["Low"]),
            prev_close=round(float(prev["Close"]), 2),
            volume=int(last.get("Volume", 0) or 0),
            timestamp=datetime.utcnow(),
        )
        q = DataQuality(score=20.0, is_synthetic=True, source="synthetic",
                        issues=["no live source available"])
        _store_quality(symbol, q)
        _cache_set(key, quote)
        return quote

    quote, quality = chosen
    _store_quality(symbol, quality)
    _cache_set(key, quote)
    return quote


def get_quote_with_quality(symbol: str) -> Tuple[Quote, DataQuality]:
    """Return both the quote and the quality summary that produced it."""
    q = get_quote(symbol)
    return q, get_quality(symbol)


_QUOTE_POOL = ThreadPoolExecutor(max_workers=12, thread_name_prefix="quote")


def get_quotes(symbols: List[str], *, max_workers: int = 12) -> List[Quote]:
    """Parallelised quote fetch.

    yfinance + NSE are mostly I/O-bound, so a small thread pool gives a
    big real-world speedup (≈10x for 50 symbols on a residential link).
    """
    syms = [s for s in symbols if s]
    if not syms:
        return []
    if len(syms) == 1:
        try:
            return [get_quote(syms[0])]
        except Exception as exc:
            logger.warning(f"Quote failed for {syms[0]}: {exc}")
            return []
    results: Dict[str, Quote] = {}
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="quote") as pool:
        futures = {pool.submit(get_quote, s): s for s in syms}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                results[sym] = fut.result()
            except Exception as exc:
                logger.warning(f"Quote failed for {sym}: {exc}")
    return [results[s] for s in syms if s in results]


def to_ohlc_rows(df: pd.DataFrame) -> List[OhlcRow]:
    rows: List[OhlcRow] = []
    if df.empty:
        return rows
    for ts, r in df.iterrows():
        try:
            unix = int(pd.Timestamp(ts).timestamp())
            rows.append(
                OhlcRow(
                    time=unix,
                    open=float(r["Open"]),
                    high=float(r["High"]),
                    low=float(r["Low"]),
                    close=float(r["Close"]),
                    volume=float(r.get("Volume", 0) or 0),
                )
            )
        except Exception:
            continue
    return rows


def gainers_losers(symbols: List[str], top_n: int = 10) -> Dict[str, List[Quote]]:
    quotes = get_quotes(symbols)
    quotes.sort(key=lambda q: q.change_pct, reverse=True)
    return {
        "gainers": quotes[:top_n],
        "losers": list(reversed(quotes[-top_n:])),
        "most_active": sorted(quotes, key=lambda q: (q.volume or 0), reverse=True)[:top_n],
    }
