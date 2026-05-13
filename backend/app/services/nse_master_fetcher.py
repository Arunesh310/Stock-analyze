"""Pull NSE's official equity list once a day and cache it.

Endpoint: https://archives.nseindia.com/content/equities/EQUITY_L.csv
Columns we care about: SYMBOL, NAME OF COMPANY, ISIN NUMBER

The fetcher is *best effort*:
- if internet works, we cache the CSV under ``backend/.cache/nse_equity_l.csv``.
- if it fails, we silently fall back to the bundled ``nse_extended.py`` list.

Loaders return a list of dicts shaped like StockMeta-compatible entries so
``stock_master`` can merge them without surprises.
"""
from __future__ import annotations

import csv
import io
import os
import time
from pathlib import Path
from typing import Iterable, Optional

import httpx
from loguru import logger


URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

def _default_cache_dir() -> Path:
    # On serverless (read-only filesystem) the only writable path is /tmp.
    if any(os.environ.get(k) for k in ("SERVERLESS", "VERCEL", "AWS_LAMBDA_FUNCTION_NAME")):
        return Path("/tmp") / "bharatquant_cache"
    return Path(__file__).resolve().parents[2] / ".cache"


_CACHE_DIR = _default_cache_dir()
_CACHE_FILE = _CACHE_DIR / "nse_equity_l.csv"
_REFRESH_SECONDS = 60 * 60 * 24  # 24h


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/csv,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


def _cache_is_fresh() -> bool:
    if not _CACHE_FILE.exists():
        return False
    age = time.time() - _CACHE_FILE.stat().st_mtime
    return age < _REFRESH_SECONDS


def _download() -> Optional[str]:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with httpx.Client(headers=_HEADERS, timeout=10, follow_redirects=True) as c:
            # NSE archive sometimes redirects after a session cookie hop.
            c.get("https://www.nseindia.com/", timeout=4)
            r = c.get(URL, timeout=10)
        if r.status_code != 200 or not r.text.startswith("SYMBOL"):
            logger.debug(f"NSE EQUITY_L.csv unexpected response: {r.status_code}")
            return None
        _CACHE_FILE.write_text(r.text, encoding="utf-8")
        return r.text
    except Exception as exc:
        logger.debug(f"NSE EQUITY_L.csv download failed: {exc}")
        return None


def _load_text() -> Optional[str]:
    if _cache_is_fresh():
        try:
            return _CACHE_FILE.read_text(encoding="utf-8")
        except Exception:
            pass
    text = _download()
    if text is None and _CACHE_FILE.exists():
        try:
            return _CACHE_FILE.read_text(encoding="utf-8")
        except Exception:
            return None
    return text


def fetch_equity_rows() -> list[dict]:
    """Returns a list of {symbol, name, isin, series} dicts (NSE only).

    Empty list on failure.
    """
    text = _load_text()
    if not text:
        return []
    out: list[dict] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            sym = (row.get("SYMBOL") or "").strip()
            name = (row.get("NAME OF COMPANY") or "").strip()
            isin = (row.get(" ISIN NUMBER") or row.get("ISIN NUMBER") or "").strip()
            series = (row.get(" SERIES") or row.get("SERIES") or "").strip()
            if sym and name and series in {"EQ", "BE", "BZ", "SM"}:
                out.append(
                    {
                        "symbol": f"{sym}.NS",
                        "nse": sym,
                        "name": name,
                        "isin": isin,
                        "series": series,
                    }
                )
    except Exception as exc:
        logger.debug(f"NSE EQUITY_L.csv parse failed: {exc}")
    return out


def cache_path() -> Path:
    return _CACHE_FILE
