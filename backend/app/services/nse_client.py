"""Lightweight NSE public-endpoint client (secondary data source).

This is *best-effort*: NSE rate-limits and requires a warm-up cookie hop.
We:

- send realistic browser headers,
- warm up the session by hitting the public home page,
- cache the resulting cookies for ~15 minutes,
- gracefully time out and return None on any failure,
- only ever read public endpoints (no auth needed).

The primary source remains yfinance — this client is used by
``market_data`` as a corroborator / fallback when yfinance disagrees,
returns stale data, or fails outright.
"""
from __future__ import annotations

import time
from datetime import datetime
from threading import Lock
from typing import Optional

import httpx
from loguru import logger


_HOME = "https://www.nseindia.com"
_QUOTE = "https://www.nseindia.com/api/quote-equity?symbol={sym}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

_CACHE_TTL = 8  # seconds
_COOKIE_TTL = 60 * 15

_lock = Lock()
_cookies: dict = {}
_cookies_at = 0.0
_quote_cache: dict[str, tuple[float, dict]] = {}


def _warmup(client: httpx.Client) -> None:
    global _cookies, _cookies_at
    if _cookies and (time.time() - _cookies_at) < _COOKIE_TTL:
        return
    try:
        r = client.get(_HOME, headers=_HEADERS, timeout=4)
        r.raise_for_status()
        _cookies = dict(r.cookies)
        _cookies_at = time.time()
    except Exception as exc:
        logger.debug(f"nse warmup failed: {exc}")


def get_equity_quote(symbol: str) -> Optional[dict]:
    """Fetch a normalised equity quote dict from NSE for the bare NSE ticker.

    ``symbol`` may include the ``.NS`` suffix (it will be stripped).
    Returns a dict with: price, prev_close, open, high, low, volume,
    change, change_pct, timestamp, source="nse". Returns ``None`` on
    any failure.
    """
    raw = (symbol or "").strip().upper().replace(".NS", "")
    if not raw or raw.startswith("^") or "=" in raw:
        return None

    # in-memory micro-cache
    now = time.time()
    with _lock:
        if raw in _quote_cache:
            ts, val = _quote_cache[raw]
            if now - ts < _CACHE_TTL:
                return dict(val)

    try:
        with httpx.Client(timeout=4, headers=_HEADERS, follow_redirects=True) as client:
            _warmup(client)
            r = client.get(
                _QUOTE.format(sym=raw),
                headers=_HEADERS,
                cookies=_cookies,
                timeout=4,
            )
            if r.status_code != 200:
                return None
            j = r.json()
    except Exception as exc:
        logger.debug(f"nse quote failed for {raw}: {exc}")
        return None

    try:
        pi = j.get("priceInfo") or {}
        info = j.get("info") or {}
        meta = j.get("metadata") or {}
        last = float(pi.get("lastPrice"))
        prev = float(pi.get("previousClose") or 0)
        change = float(pi.get("change") or (last - prev))
        change_pct = float(pi.get("pChange") or ((change / prev * 100) if prev else 0))
        result = {
            "symbol": f"{raw}.NS",
            "name": info.get("companyName") or meta.get("companyName") or raw,
            "price": last,
            "prev_close": prev,
            "open": float(pi.get("open") or 0) or None,
            "high": float((pi.get("intraDayHighLow") or {}).get("max") or 0) or None,
            "low": float((pi.get("intraDayHighLow") or {}).get("min") or 0) or None,
            "volume": int(pi.get("totalTradedVolume") or meta.get("totalTradedVolume") or 0),
            "change": round(change, 4),
            "change_pct": round(change_pct, 3),
            "timestamp": datetime.utcnow().isoformat(),
            "source": "nse",
        }
        with _lock:
            _quote_cache[raw] = (now, dict(result))
        return result
    except Exception as exc:
        logger.debug(f"nse quote parse failed for {raw}: {exc}")
        return None
