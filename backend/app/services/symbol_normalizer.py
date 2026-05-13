"""Resolve loosely-typed user input to a canonical yfinance symbol.

Examples handled:

    "reliance"     -> "RELIANCE.NS"
    "Reliance Ind" -> "RELIANCE.NS"
    "HAL"          -> "HAL.NS"
    "hdfc bank"    -> "HDFCBANK.NS"
    " sbin "       -> "SBIN.NS"
    "tata mototrs" -> "TATAMOTORS.NS"   (single-edit typo)
    "RELIANCE.NS"  -> "RELIANCE.NS"     (no-op)
    "500325"       -> "RELIANCE.NS"     (BSE scrip code)

The pipeline is:

  1. Strip / upper-case.
  2. Exact match in stock_master (symbol / NSE / BSE / alias).
  3. Substring scan over symbol + name + aliases.
  4. ``difflib`` SequenceMatcher fuzzy match (>=0.78 ratio) — last resort.

Returns a ``ResolveResult`` carrying the canonical symbol, the matched
metadata and a confidence score, so callers can decide how to act.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import List, Optional

from . import stock_master
from .stock_master import StockMeta


_PUNCT_RE = re.compile(r"[^A-Za-z0-9&^=.\s-]")


@dataclass
class ResolveResult:
    symbol: Optional[str]
    name: Optional[str]
    sector: Optional[str]
    confidence: float       # 0..1
    source: str             # "exact" | "alias" | "substring" | "fuzzy" | "fallback"
    meta: Optional[StockMeta] = None

    @property
    def ok(self) -> bool:
        return self.symbol is not None


def _clean(q: str) -> str:
    if q is None:
        return ""
    s = _PUNCT_RE.sub(" ", q).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize(q: str) -> ResolveResult:
    """Return the best-effort canonical symbol for the input."""
    raw = _clean(q)
    if not raw:
        return ResolveResult(None, None, None, 0.0, "fallback")

    upper = raw.upper()

    # 1. Direct match
    direct = stock_master.find_by_symbol(upper)
    if direct:
        return ResolveResult(
            direct.symbol, direct.name, direct.sector,
            confidence=1.0, source="exact", meta=direct,
        )

    # Accept things like "RELIANCE" (no suffix) – stock_master also indexes by NSE ticker
    nse_only = stock_master.find_by_symbol(upper.replace(" ", ""))
    if nse_only:
        return ResolveResult(
            nse_only.symbol, nse_only.name, nse_only.sector,
            confidence=1.0, source="exact", meta=nse_only,
        )

    # 2. Alias / name match
    alias = stock_master.find_by_alias(raw)
    if alias:
        return ResolveResult(
            alias.symbol, alias.name, alias.sector,
            confidence=0.95, source="alias", meta=alias,
        )

    # 3. Substring scan (cheap)
    hits = stock_master.search(raw, limit=1)
    if hits:
        meta = stock_master.find_by_symbol(hits[0]["symbol"])
        return ResolveResult(
            hits[0]["symbol"], hits[0]["name"], hits[0]["sector"],
            confidence=0.85, source="substring", meta=meta,
        )

    # 4. Fuzzy (last resort) — score against symbol + name pool
    candidates: List[tuple[str, StockMeta]] = []
    for s in stock_master.all_stocks():
        candidates.append((s.symbol.lower(), s))
        if s.nse:
            candidates.append((s.nse.lower(), s))
        candidates.append((s.name.lower(), s))
        for a in s.aliases:
            candidates.append((a.lower(), s))

    target = raw.lower()
    best_ratio = 0.0
    best_meta: Optional[StockMeta] = None
    for key, meta in candidates:
        ratio = difflib.SequenceMatcher(None, key, target).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_meta = meta

    if best_meta and best_ratio >= 0.78:
        return ResolveResult(
            best_meta.symbol, best_meta.name, best_meta.sector,
            confidence=round(best_ratio, 3),
            source="fuzzy", meta=best_meta,
        )

    return ResolveResult(None, None, None, 0.0, "fallback")


def canonical(symbol: str) -> str:
    """Return the canonical yfinance ticker for any string, falling back
    to a sensible NSE-suffixed guess when no match is found."""
    r = normalize(symbol)
    if r.symbol:
        return r.symbol
    s = (symbol or "").strip().upper()
    if not s:
        return ""
    if "." in s or s.startswith("^") or "=" in s:
        return s
    return f"{s}.NS"


def search(query: str, limit: int = 12) -> List[StockMeta]:
    """Rich search used by autocomplete (returns ``StockMeta`` objects).

    See :func:`search_scored` for a variant that also surfaces the matching
    strategy and confidence.
    """
    return [m for m, _, _ in search_scored(query, limit=limit)]


def search_scored(
    query: str, limit: int = 12
) -> List[tuple[StockMeta, float, str]]:
    """Like :func:`search`, but each result also carries ``(confidence, source)``."""
    raw = _clean(query)
    if not raw:
        return [
            (s, 1.0, "exact")
            for s in stock_master.all_stocks()
            if s.exchange == "NSE"
        ][:limit]

    target = raw.lower()
    upper = raw.upper()

    # 1. Exact symbol / NSE ticker / BSE code match first
    out: List[tuple[StockMeta, float, str]] = []
    seen: set[str] = set()

    direct = (
        stock_master.find_by_symbol(upper)
        or stock_master.find_by_symbol(upper.replace(" ", ""))
    )
    if direct and direct.symbol not in seen:
        out.append((direct, 1.0, "exact"))
        seen.add(direct.symbol)

    alias = stock_master.find_by_alias(raw)
    if alias and alias.symbol not in seen:
        out.append((alias, 0.95, "alias"))
        seen.add(alias.symbol)

    # 2. Substring scan (preserves market-cap ordering)
    for h in stock_master.search(raw, limit=limit * 2):
        if h["symbol"] in seen:
            continue
        meta = stock_master.find_by_symbol(h["symbol"])
        if meta is None:
            continue
        out.append((meta, 0.85, "substring"))
        seen.add(meta.symbol)
        if len(out) >= limit:
            return out

    # 3. Fuzzy fallback
    scored: List[tuple[float, StockMeta]] = []
    for s in stock_master.all_stocks():
        if s.symbol in seen:
            continue
        keys = [s.symbol.lower(), s.name.lower()]
        if s.nse:
            keys.append(s.nse.lower())
        keys.extend(a.lower() for a in s.aliases)
        best = max(
            difflib.SequenceMatcher(None, k, target).ratio() for k in keys if k
        )
        if best >= 0.55:
            scored.append((best, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    for score, m in scored:
        if len(out) >= limit:
            break
        out.append((m, round(score, 3), "fuzzy"))
    return out[:limit]
