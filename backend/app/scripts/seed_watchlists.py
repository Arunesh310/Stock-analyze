"""Seed a few default watchlists.

Run:
    python -m app.scripts.seed_watchlists
"""
from __future__ import annotations

from loguru import logger

from ..database import db_session, init_db
from ..logger import setup_logging
from ..models.watchlist import Watchlist, WatchlistItem


DEFAULTS: dict[str, list[str]] = {
    "Nifty Heavyweights": [
        "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
        "HINDUNILVR.NS", "ITC.NS", "BHARTIARTL.NS",
    ],
    "Defence Theme": ["HAL.NS", "BEL.NS", "BDL.NS", "MAZDOCK.NS", "PARAS.NS"],
    "Railways Theme": ["IRFC.NS", "RVNL.NS", "IRCTC.NS", "RAILTEL.NS", "TITAGARH.NS"],
    "Banking Pack": [
        "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS",
        "KOTAKBANK.NS", "INDUSINDBK.NS",
    ],
}


def main() -> None:
    setup_logging()
    init_db()
    with db_session() as db:
        for name, syms in DEFAULTS.items():
            existing = db.query(Watchlist).filter_by(name=name).first()
            if existing:
                logger.info(f"Watchlist already exists: {name}")
                continue
            wl = Watchlist(name=name, items=[WatchlistItem(symbol=s) for s in syms])
            db.add(wl)
        db.flush()
    logger.info("Default watchlists seeded.")


if __name__ == "__main__":
    main()
