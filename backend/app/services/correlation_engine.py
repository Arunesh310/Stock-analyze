"""Correlation, sympathy-move and sector-rotation analytics.

These run on top of validated OHLC histories — each "expensive aggregation"
(sector strength, market breadth) is wrapped in a small TTL cache so the
dashboard renders in <500ms when the cache is warm.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .market_data import get_history
from .universe import NSE_UNIVERSE, get_sector, symbols_in_sector, all_sectors


# ---------------------------------------------------------------------------
# Small TTL cache for the costly aggregate calls.
# ---------------------------------------------------------------------------

_AGG_TTL = 60  # seconds; aggregates are slow-moving so 1 minute is fine
_AGG_CACHE: Dict[str, tuple[float, object]] = {}
_AGG_LOCK = Lock()


def _agg_get(key: str):
    with _AGG_LOCK:
        item = _AGG_CACHE.get(key)
        if not item:
            return None
        ts, val = item
        if time.time() - ts > _AGG_TTL:
            return None
        return val


def _agg_set(key: str, value) -> None:
    with _AGG_LOCK:
        _AGG_CACHE[key] = (time.time(), value)


def _returns(symbol: str, period: str = "6mo") -> pd.Series:
    df = get_history(symbol, period=period, interval="1d")
    return df["Close"].pct_change().dropna()


# Per-sector cap — keeps sector_strength fast even with a 2000-stock universe.
_SECTOR_SAMPLE_LIMIT = 10


def correlation_matrix(symbols: List[str], period: str = "6mo") -> pd.DataFrame:
    series = {}
    for s in symbols:
        try:
            r = _returns(s, period=period)
            if not r.empty:
                series[s] = r
        except Exception:
            continue
    if not series:
        return pd.DataFrame()
    df = pd.DataFrame(series).dropna()
    return df.corr().round(3)


def correlations_against(symbol: str, peers: List[str], period: str = "6mo") -> List[dict]:
    """Pairwise Pearson correlation of `symbol` vs each peer."""
    base = _returns(symbol, period=period)
    out: List[dict] = []
    for p in peers:
        if p == symbol:
            continue
        try:
            other = _returns(p, period=period)
            joined = pd.concat([base, other], axis=1, join="inner").dropna()
            if len(joined) < 30:
                continue
            r = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
            out.append({"symbol": symbol, "against": p, "pearson": round(r, 3),
                        "sample": int(len(joined))})
        except Exception:
            continue
    out.sort(key=lambda x: abs(x["pearson"]), reverse=True)
    return out


def sympathy_movers(symbol: str, period: str = "3mo", limit: int = 5) -> List[dict]:
    """Find universe peers that historically move together with `symbol`."""
    sector = get_sector(symbol)
    peers = symbols_in_sector(sector) if sector != "Other" else list(NSE_UNIVERSE.keys())
    return correlations_against(symbol, peers, period=period)[:limit]


def sector_strength(period: str = "1mo") -> List[dict]:
    """Average return of each sector over `period`. Higher = stronger sector.

    Cached for ``_AGG_TTL`` seconds because each invocation can fan out to
    dozens of yfinance requests.
    """
    cache_key = f"sector_strength::{period}"
    hit = _agg_get(cache_key)
    if hit is not None:
        return hit  # type: ignore[return-value]

    # Collect (sector, symbol) pairs to fetch in parallel — much faster than
    # the nested-loop sequential version.
    pairs: list[tuple[str, str]] = []
    for sector in all_sectors():
        syms = symbols_in_sector(sector)[:_SECTOR_SAMPLE_LIMIT]
        for sym in syms:
            pairs.append((sector, sym))

    def _one(sym: str) -> Optional[float]:
        try:
            r = _returns(sym, period=period)
            if r.empty:
                return None
            return float((1 + r).prod() - 1) * 100
        except Exception:
            return None

    sector_to_pts: Dict[str, list[tuple[str, float]]] = {}
    if pairs:
        with ThreadPoolExecutor(max_workers=12, thread_name_prefix="sector") as pool:
            future_map = {pool.submit(_one, sym): (sector, sym) for sector, sym in pairs}
            for fut in as_completed(future_map):
                sector, sym = future_map[fut]
                tot = fut.result()
                if tot is None:
                    continue
                sector_to_pts.setdefault(sector, []).append((sym, tot))

    out: List[dict] = []
    for sector, pts in sector_to_pts.items():
        rets = [p for _, p in pts]
        leaders = sorted(pts, key=lambda x: x[1], reverse=True)
        out.append({
            "sector": sector,
            "strength": round(float(np.mean(rets)), 2),
            "leaders": [s for s, _ in leaders[:3]],
            "laggards": [s for s, _ in leaders[-3:]],
        })
    out.sort(key=lambda x: x["strength"], reverse=True)
    _agg_set(cache_key, out)
    return out


def market_breadth(symbols: List[str]) -> Dict[str, int]:
    """Count of advancers / decliners / unchanged over the latest session.

    Cached + parallelised to keep the home page snappy.
    """
    cache_key = f"breadth::{tuple(sorted(symbols))}"
    hit = _agg_get(cache_key)
    if hit is not None:
        return hit  # type: ignore[return-value]

    def _one(s: str) -> Optional[int]:
        try:
            df = get_history(s, period="5d", interval="1d")
            if len(df) < 2:
                return 0
            chg = df["Close"].iloc[-1] - df["Close"].iloc[-2]
            if chg > 0:
                return 1
            if chg < 0:
                return -1
            return 0
        except Exception:
            return None

    adv = dec = unc = 0
    if symbols:
        with ThreadPoolExecutor(max_workers=12, thread_name_prefix="breadth") as pool:
            for fut in as_completed([pool.submit(_one, s) for s in symbols]):
                r = fut.result()
                if r is None:
                    continue
                if r > 0:
                    adv += 1
                elif r < 0:
                    dec += 1
                else:
                    unc += 1

    result = {"advancers": adv, "decliners": dec, "unchanged": unc}
    _agg_set(cache_key, result)
    return result
