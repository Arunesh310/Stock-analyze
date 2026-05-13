"""News aggregation + lightweight sentiment + sector mapping.

We use only **free RSS feeds** so no paid APIs are required.
A small lexicon-based sentiment scorer is included; it works offline and is
fast enough for streaming use. The LLM (ai_engine) can also be invoked for
narrative analysis on demand.
"""
from __future__ import annotations

import time
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

from loguru import logger

from ..config import get_settings
from ..schemas.common import NewsItem
from .universe import NSE_UNIVERSE, all_sectors

_settings = get_settings()
_cache: Dict[str, tuple[float, List[NewsItem]]] = {}
_lock = Lock()
_TTL = 300  # 5 minutes

# Tiny lexicon for offline sentiment
POSITIVE_WORDS = {
    "surge", "rally", "gain", "profit", "beat", "growth", "bullish", "rise",
    "upgrade", "expand", "record", "high", "outperform", "boost", "jump",
    "rebound", "win", "strong", "soar", "buy", "uptick",
}
NEGATIVE_WORDS = {
    "fall", "drop", "decline", "loss", "miss", "bearish", "downgrade", "cut",
    "slump", "plunge", "weak", "low", "underperform", "crash", "concern",
    "warn", "probe", "fraud", "ban", "tariff", "default", "lawsuit", "raid",
}

# Sector trigger keywords -> sector name (used by `impacted_sectors`)
SECTOR_KEYWORDS: Dict[str, List[str]] = {
    "Banking": ["bank", "rbi", "repo", "interest rate", "loan", "deposit", "credit"],
    "IT": ["it services", "tech", "infosys", "tcs", "cognizant", "h1b", "us economy"],
    "Energy": ["crude", "oil", "opec", "petroleum", "energy"],
    "Oil & Gas": ["crude", "oil", "ongc", "petrol", "diesel", "lpg", "gas price"],
    "Metals": ["steel", "iron", "copper", "aluminium", "metal"],
    "Auto": ["auto", "ev", "vehicle", "car sales", "two-wheeler", "tata motors"],
    "FMCG": ["fmcg", "consumer", "monsoon", "rural demand"],
    "Pharma": ["pharma", "drug", "fda", "vaccine", "medicine"],
    "Defence": ["defence", "defense", "army", "navy", "border", "war",
                "military", "drone", "missile", "BEL", "HAL"],
    "Railways": ["railway", "rail vikas", "irfc", "vande bharat", "train"],
    "Power": ["power", "discom", "electricity", "renewable", "solar", "wind"],
    "Realty": ["real estate", "housing", "property", "builder", "rera"],
    "Telecom": ["telecom", "5g", "spectrum", "jio", "airtel"],
    "Aviation": ["aviation", "airline", "indigo", "air india"],
    "Cement": ["cement", "infrastructure", "construction"],
    "Paints": ["paints", "asian paints", "berger"],
}

# Symbol-trigger keywords (company name aliases)
SYMBOL_ALIASES: Dict[str, List[str]] = {
    sym: [name.lower(), sym.split(".")[0].lower()]
    for sym, (name, _) in NSE_UNIVERSE.items()
}


def _score_sentiment(text: str) -> float:
    if not text:
        return 0.0
    t = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def _impacted_sectors(text: str) -> List[str]:
    t = (text or "").lower()
    out = []
    for sector, kws in SECTOR_KEYWORDS.items():
        if any(kw in t for kw in kws):
            out.append(sector)
    return out


def _impacted_symbols(text: str) -> List[str]:
    t = (text or "").lower()
    out: List[str] = []
    for sym, aliases in SYMBOL_ALIASES.items():
        if any(a in t for a in aliases if len(a) > 3):
            out.append(sym)
    return out[:10]


def _impact_score(item: NewsItem) -> float:
    """Heuristic 0..1: more impactful when many sectors/symbols and strong sentiment."""
    base = min(1.0, 0.2 + 0.1 * len(item.impacted_sectors) + 0.05 * len(item.impacted_symbols))
    return round(base * (0.5 + abs(item.sentiment) / 2), 3)


def fetch_news(limit_per_feed: int = 20) -> List[NewsItem]:
    """Fetch + parse all configured RSS feeds. Cached for 5 min."""
    key = "all_news"
    now = time.time()
    with _lock:
        if key in _cache and (now - _cache[key][0] < _TTL):
            return _cache[key][1]

    try:
        import feedparser  # type: ignore
    except Exception:
        logger.warning("feedparser not installed, returning empty news list")
        return []

    items: List[NewsItem] = []
    for feed_url in _settings.news_feeds:
        try:
            d = feedparser.parse(feed_url)
            source = d.feed.get("title", feed_url)
            for entry in d.entries[:limit_per_feed]:
                title = entry.get("title", "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                link = entry.get("link", "")
                published: Optional[datetime] = None
                if "published_parsed" in entry and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except Exception:
                        published = None
                blob = f"{title}. {summary}"
                sentiment = _score_sentiment(blob)
                impacted_sectors = _impacted_sectors(blob)
                impacted_symbols = _impacted_symbols(blob)
                ni = NewsItem(
                    title=title,
                    summary=summary[:400],
                    link=link,
                    source=source,
                    published=published,
                    sentiment=sentiment,
                    impacted_sectors=impacted_sectors,
                    impacted_symbols=impacted_symbols,
                )
                ni.impact_score = _impact_score(ni)
                items.append(ni)
        except Exception as exc:
            logger.warning(f"Feed parse error {feed_url}: {exc}")

    items.sort(
        key=lambda n: (n.published or datetime(1970, 1, 1)),
        reverse=True,
    )
    with _lock:
        _cache[key] = (now, items)
    return items


def aggregate_market_sentiment(items: Optional[List[NewsItem]] = None) -> dict:
    items = items or fetch_news()
    if not items:
        return {"avg_sentiment": 0.0, "samples": 0,
                "by_sector": {}, "top_positive": [], "top_negative": []}
    sentiments = [n.sentiment for n in items]
    avg = round(sum(sentiments) / len(sentiments), 3)
    by_sector: Dict[str, List[float]] = {s: [] for s in all_sectors()}
    for n in items:
        for sec in n.impacted_sectors:
            by_sector.setdefault(sec, []).append(n.sentiment)
    by_sector_avg = {
        sec: round(sum(v) / len(v), 3) for sec, v in by_sector.items() if v
    }
    sorted_items = sorted(items, key=lambda x: x.sentiment, reverse=True)
    return {
        "avg_sentiment": avg,
        "samples": len(items),
        "by_sector": by_sector_avg,
        "top_positive": [n.title for n in sorted_items[:3]],
        "top_negative": [n.title for n in sorted_items[-3:]],
    }


def fii_dii_proxy() -> dict:
    """Return a *proxy* FII/DII sentiment derived from news + index move.

    Real FII/DII numbers are released only after market close on NSE.
    This proxy lets us show something useful in the dashboard at all times.
    """
    from .market_data import get_quote
    items = fetch_news()
    sent = aggregate_market_sentiment(items)
    try:
        nifty = get_quote("^NSEI")
        nifty_chg = nifty.change_pct
    except Exception:
        nifty_chg = 0.0
    fii = round(sent["avg_sentiment"] * 1500 + nifty_chg * 300, 1)
    dii = round((-sent["avg_sentiment"] * 800) + (nifty_chg * 200), 1)
    return {
        "fii_proxy_cr": fii,
        "dii_proxy_cr": dii,
        "nifty_change_pct": nifty_chg,
        "news_sentiment": sent["avg_sentiment"],
        "samples": sent["samples"],
    }
