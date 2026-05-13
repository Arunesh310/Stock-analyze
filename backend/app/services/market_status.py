"""Indian (NSE/BSE) market session detector.

The engine reports a coarse session state plus useful timing context so
the frontend can display a credible "market open / closed / pre-open"
indicator and adjust its refresh cadence:

- ``preopen``   : 09:00 – 09:15 IST on a trading day
- ``regular``   : 09:15 – 15:30 IST on a trading day
- ``afterhours``: 15:30 – 16:00 IST on a trading day  (post-close window)
- ``closed``    : weekends, fixed holidays, all other times

Holidays are stored as fixed-date strings; extend ``_HOLIDAYS_*`` as you go.
Everything is pure-Python (no extra deps) and tz-aware.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional


IST = timezone(timedelta(hours=5, minutes=30))

PRE_OPEN_START = time(9, 0)
REGULAR_START = time(9, 15)
REGULAR_END = time(15, 30)
AFTER_HOURS_END = time(16, 0)


# Known full-day NSE holidays. Curated; safe to extend over time.
_HOLIDAYS = {
    # 2025
    "2025-01-26",  # Republic Day
    "2025-02-26",  # Maha Shivratri
    "2025-03-14",  # Holi
    "2025-03-31",  # Ramadan Eid
    "2025-04-10",  # Mahavir Jayanti
    "2025-04-14",  # Ambedkar Jayanti
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-08-15",  # Independence Day
    "2025-08-27",  # Ganesh Chaturthi
    "2025-10-02",  # Gandhi Jayanti
    "2025-10-21",  # Diwali Laxmi Pujan (muhurat trading)
    "2025-10-22",  # Diwali Balipratipada
    "2025-11-05",  # Guru Nanak Jayanti
    "2025-12-25",  # Christmas
    # 2026
    "2026-01-26",
    "2026-02-16",
    "2026-03-04",
    "2026-03-19",
    "2026-04-03",
    "2026-04-14",
    "2026-05-01",
    "2026-08-15",
    "2026-10-02",
    "2026-11-09",
    "2026-12-25",
    # 2027 (placeholder fixed dates)
    "2027-01-26",
    "2027-08-15",
    "2027-10-02",
    "2027-12-25",
}


@dataclass
class MarketStatus:
    state: str                # "preopen" | "regular" | "afterhours" | "closed"
    is_open: bool             # True only when state == "regular"
    is_trading_day: bool
    now_ist: datetime
    next_open_at: Optional[datetime]
    next_close_at: Optional[datetime]
    label: str
    seconds_until_next: Optional[int]

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "is_open": self.is_open,
            "is_trading_day": self.is_trading_day,
            "now_ist": self.now_ist.isoformat(),
            "next_open_at": self.next_open_at.isoformat() if self.next_open_at else None,
            "next_close_at": self.next_close_at.isoformat() if self.next_close_at else None,
            "label": self.label,
            "seconds_until_next": self.seconds_until_next,
        }


def _is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:  # Sat/Sun
        return False
    if d.isoformat() in _HOLIDAYS:
        return False
    return True


def _next_trading_day(d: date) -> date:
    nxt = d + timedelta(days=1)
    while not _is_trading_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def get_status(now: Optional[datetime] = None) -> MarketStatus:
    """Return the current market session status."""
    now_ist = (now or datetime.now(timezone.utc)).astimezone(IST)
    today = now_ist.date()
    t = now_ist.time().replace(microsecond=0)

    trading_today = _is_trading_day(today)
    open_dt = datetime.combine(today, REGULAR_START, tzinfo=IST)
    close_dt = datetime.combine(today, REGULAR_END, tzinfo=IST)
    preopen_dt = datetime.combine(today, PRE_OPEN_START, tzinfo=IST)
    after_dt = datetime.combine(today, AFTER_HOURS_END, tzinfo=IST)

    if trading_today and PRE_OPEN_START <= t < REGULAR_START:
        state = "preopen"
        next_open = open_dt
        next_close = close_dt
        label = "Pre-open"
        secs = int((next_open - now_ist).total_seconds())
    elif trading_today and REGULAR_START <= t < REGULAR_END:
        state = "regular"
        next_open = None
        next_close = close_dt
        label = "Market Open"
        secs = int((next_close - now_ist).total_seconds())
    elif trading_today and REGULAR_END <= t < AFTER_HOURS_END:
        state = "afterhours"
        next_open = datetime.combine(_next_trading_day(today), REGULAR_START, tzinfo=IST)
        next_close = None
        label = "After hours"
        secs = int((next_open - now_ist).total_seconds())
    else:
        state = "closed"
        # If it's pre-9am on a trading day, next_open is today's open
        if trading_today and t < PRE_OPEN_START:
            next_open = preopen_dt
        else:
            next_open = datetime.combine(
                _next_trading_day(today), REGULAR_START, tzinfo=IST
            )
        next_close = None
        label = "Market Closed"
        secs = int((next_open - now_ist).total_seconds())

    return MarketStatus(
        state=state,
        is_open=(state == "regular"),
        is_trading_day=trading_today,
        now_ist=now_ist,
        next_open_at=next_open,
        next_close_at=next_close,
        label=label,
        seconds_until_next=max(0, secs) if secs is not None else None,
    )


def is_market_open(now: Optional[datetime] = None) -> bool:
    return get_status(now).is_open


def now_ist() -> datetime:
    return datetime.now(timezone.utc).astimezone(IST)
