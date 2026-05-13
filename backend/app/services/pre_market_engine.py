"""Pre-Market Preparation Engine.

Runs before the opening bell (08:30 IST) and assembles a one-shot brief:

- Global cues  : Dow, S&P, Nasdaq, Nikkei, Hang Seng overnight % changes
- Volatility   : ^INDIAVIX latest level + change
- Sector view  : strongest / weakest sectors based on yesterday's closes
- Watchlist    : top 'gap candidates' — symbols with the strongest day-prior
                 closing momentum in the curated universe
- Readiness    : a structured verdict (FAVORABLE / NEUTRAL / RISKY) with the
                 contributing reasons so the user understands *why* the AI
                 thinks tomorrow's session is or isn't favourable.

The brief is persisted as an ``AILearningLog`` row with
``event="pre_market_brief"`` so the front-end always reads the latest
snapshot without re-running yfinance fetches per request.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from ..database import db_session
from ..models.prediction_engine import AILearningLog
from . import market_data, universe


# Symbol → friendly label for the global-cues panel
_GLOBAL_CUES: list[tuple[str, str]] = [
    ("^GSPC", "S&P 500"),
    ("^IXIC", "Nasdaq"),
    ("^DJI", "Dow Jones"),
    ("^N225", "Nikkei 225"),
    ("^HSI", "Hang Seng"),
    ("^FTSE", "FTSE 100"),
    ("^GDAXI", "DAX"),
    ("CL=F", "WTI Crude"),
    ("GC=F", "Gold"),
    ("INR=X", "USD/INR"),
]


@dataclass
class CuePoint:
    symbol: str
    label: str
    last: Optional[float]
    change_pct: Optional[float]


@dataclass
class SectorPulse:
    sector: str
    avg_change_pct: float
    sample_size: int
    direction: str  # "up" | "down" | "flat"


@dataclass
class GapCandidate:
    symbol: str
    name: str
    sector: str
    last_close: float
    change_pct_1d: float
    change_pct_5d: float
    note: str


@dataclass
class ReadinessVerdict:
    verdict: str  # FAVORABLE | NEUTRAL | RISKY
    score: int  # -100..+100
    bullets: list[str] = field(default_factory=list)


@dataclass
class PreMarketBrief:
    generated_at: str
    global_cues: list[CuePoint]
    india_vix: Optional[float]
    india_vix_change_pct: Optional[float]
    top_sectors: list[SectorPulse]
    weak_sectors: list[SectorPulse]
    gap_candidates: list[GapCandidate]
    readiness: ReadinessVerdict
    notes: list[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "global_cues": [asdict(c) for c in self.global_cues],
            "india_vix": self.india_vix,
            "india_vix_change_pct": self.india_vix_change_pct,
            "top_sectors": [asdict(s) for s in self.top_sectors],
            "weak_sectors": [asdict(s) for s in self.weak_sectors],
            "gap_candidates": [asdict(g) for g in self.gap_candidates],
            "readiness": asdict(self.readiness),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _last_two_closes(symbol: str) -> Optional[tuple[float, float]]:
    """Return (previous_close, latest_close) using a short daily history."""
    try:
        df = market_data.get_history(symbol, period="1mo", interval="1d")
        if df.empty or len(df) < 2:
            return None
        closes = df["Close"].dropna()
        if len(closes) < 2:
            return None
        return float(closes.iloc[-2]), float(closes.iloc[-1])
    except Exception as exc:
        logger.debug(f"_last_two_closes failed for {symbol}: {exc}")
        return None


def _cue_point(symbol: str, label: str) -> CuePoint:
    pair = _last_two_closes(symbol)
    if pair is None:
        return CuePoint(symbol=symbol, label=label, last=None, change_pct=None)
    prev, last = pair
    change = (last / prev - 1) * 100 if prev else None
    return CuePoint(
        symbol=symbol,
        label=label,
        last=round(last, 2),
        change_pct=round(change, 2) if change is not None else None,
    )


def _global_cues_parallel() -> list[CuePoint]:
    """Fetch the global cues concurrently — each is independent I/O."""
    out: list[CuePoint] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for cue in ex.map(lambda s: _cue_point(s[0], s[1]), _GLOBAL_CUES):
            out.append(cue)
    return out


def _india_vix() -> tuple[Optional[float], Optional[float]]:
    pair = _last_two_closes("^INDIAVIX")
    if pair is None:
        return None, None
    prev, last = pair
    change = (last / prev - 1) * 100 if prev else None
    return round(last, 2), round(change, 2) if change is not None else None


def _yesterday_change_pct(symbol: str) -> Optional[tuple[float, float, float]]:
    """Return (last_close, change_pct_1d, change_pct_5d)."""
    try:
        df = market_data.get_history(symbol, period="1mo", interval="1d")
        closes = df["Close"].dropna() if not df.empty else pd.Series(dtype=float)
        if len(closes) < 2:
            return None
        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2])
        one_d = (last / prev - 1) * 100 if prev else 0.0
        if len(closes) >= 6:
            five_d = (last / float(closes.iloc[-6]) - 1) * 100
        else:
            five_d = (last / float(closes.iloc[0]) - 1) * 100
        return round(last, 2), round(one_d, 2), round(five_d, 2)
    except Exception as exc:
        logger.debug(f"_yesterday_change_pct failed for {symbol}: {exc}")
        return None


def _sector_pulse(symbols: List[str], sector: str) -> Optional[SectorPulse]:
    """Average yesterday's % change for stocks in ``sector``."""
    if not symbols:
        return None
    changes: list[float] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(_yesterday_change_pct, symbols):
            if res is not None:
                changes.append(res[1])
    if not changes:
        return None
    avg = sum(changes) / len(changes)
    direction = "up" if avg > 0.3 else ("down" if avg < -0.3 else "flat")
    return SectorPulse(
        sector=sector,
        avg_change_pct=round(avg, 2),
        sample_size=len(changes),
        direction=direction,
    )


def _sector_view(sample_per_sector: int = 8) -> tuple[list[SectorPulse], list[SectorPulse]]:
    """Compute strongest and weakest sectors based on day-prior performance."""
    pulses: list[SectorPulse] = []
    for sec in universe.all_sectors():
        syms = universe.symbols_in_sector(sec)[:sample_per_sector]
        pulse = _sector_pulse(syms, sec)
        if pulse is not None and pulse.sample_size >= 3:
            pulses.append(pulse)
    pulses.sort(key=lambda p: p.avg_change_pct, reverse=True)
    return pulses[:5], list(reversed(pulses[-5:]))


def _gap_candidates(top_n: int = 8) -> list[GapCandidate]:
    """Stocks with the strongest yesterday's close — likely gap-up morning
    candidates if the global tape co-operates.

    We deliberately pick from a curated 25-symbol prefix of the universe so
    this stays cheap when the function runs in a tight 60s pre-market window.
    """
    syms = universe.all_symbols()[:30]
    rows: list[GapCandidate] = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for sym, res in zip(syms, ex.map(_yesterday_change_pct, syms)):
            if res is None:
                continue
            last_close, d1, d5 = res
            # Strong momentum: yesterday > +1.5% AND 5-day > +3%
            if d1 < 1.5 or d5 < 3.0:
                continue
            rows.append(
                GapCandidate(
                    symbol=sym,
                    name=universe.get_name(sym),
                    sector=universe.get_sector(sym),
                    last_close=last_close,
                    change_pct_1d=d1,
                    change_pct_5d=d5,
                    note=f"+{d1:.1f}% yesterday, +{d5:.1f}% over 5 sessions",
                )
            )
    rows.sort(key=lambda r: r.change_pct_1d, reverse=True)
    return rows[:top_n]


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


def _build_verdict(
    global_cues: list[CuePoint],
    india_vix: Optional[float],
    india_vix_change_pct: Optional[float],
    top_sectors: list[SectorPulse],
    weak_sectors: list[SectorPulse],
) -> ReadinessVerdict:
    """Aggregate the inputs into a single FAVORABLE / NEUTRAL / RISKY call.

    Score is a transparent +/- accumulator so the dashboard can show the
    contributing items. The thresholds are intentionally conservative — the
    AI prefers NEUTRAL over forcing a directional verdict.
    """
    score = 0
    bullets: list[str] = []

    # US session is the dominant overnight cue for the Indian open.
    us_symbols = {"^GSPC", "^IXIC", "^DJI"}
    us_changes = [c.change_pct for c in global_cues if c.symbol in us_symbols and c.change_pct is not None]
    if us_changes:
        avg_us = sum(us_changes) / len(us_changes)
        if avg_us > 0.5:
            score += 25
            bullets.append(f"US markets +{avg_us:.2f}% on average — strong overnight tailwind.")
        elif avg_us > 0.15:
            score += 10
            bullets.append(f"US markets +{avg_us:.2f}% — mildly positive overnight.")
        elif avg_us < -0.5:
            score -= 25
            bullets.append(f"US markets {avg_us:.2f}% — overnight headwind for the open.")
        elif avg_us < -0.15:
            score -= 10
            bullets.append(f"US markets {avg_us:.2f}% — mildly negative overnight.")

    # Asian session reaction is a secondary cue.
    asia_symbols = {"^N225", "^HSI"}
    asia_changes = [c.change_pct for c in global_cues if c.symbol in asia_symbols and c.change_pct is not None]
    if asia_changes:
        avg_asia = sum(asia_changes) / len(asia_changes)
        if avg_asia > 0.4:
            score += 10
            bullets.append(f"Asian markets +{avg_asia:.2f}% — risk-on backdrop.")
        elif avg_asia < -0.4:
            score -= 10
            bullets.append(f"Asian markets {avg_asia:.2f}% — risk-off in Asia.")

    # Volatility regime.
    if india_vix is not None:
        if india_vix > 20:
            score -= 15
            bullets.append(f"India VIX at {india_vix:.1f} — elevated risk, intraday whipsaw likely.")
        elif india_vix > 16:
            score -= 5
            bullets.append(f"India VIX at {india_vix:.1f} — slightly elevated volatility.")
        elif india_vix < 12:
            score += 5
            bullets.append(f"India VIX at {india_vix:.1f} — calm regime.")

        if india_vix_change_pct is not None and india_vix_change_pct > 8:
            score -= 10
            bullets.append(
                f"India VIX jumped {india_vix_change_pct:+.1f}% yesterday — caution flag."
            )

    # Sector dispersion.
    if top_sectors and weak_sectors:
        spread = top_sectors[0].avg_change_pct - weak_sectors[0].avg_change_pct
        if spread > 2.5:
            bullets.append(
                f"High sector dispersion ({spread:.1f}%) — stay selective; broad index plays risky."
            )
        elif top_sectors[0].avg_change_pct > 1.0:
            score += 5
            bullets.append(
                f"{top_sectors[0].sector} leading at +{top_sectors[0].avg_change_pct:.2f}% — clean leadership."
            )

    # Crude / USD-INR shocks
    crude = next((c for c in global_cues if c.symbol == "CL=F"), None)
    if crude and crude.change_pct is not None and crude.change_pct > 3:
        score -= 8
        bullets.append(f"Crude +{crude.change_pct:.1f}% — inflation / macro headwind.")
    inr = next((c for c in global_cues if c.symbol == "INR=X"), None)
    if inr and inr.change_pct is not None and inr.change_pct > 0.5:
        score -= 5
        bullets.append(f"USD/INR up {inr.change_pct:.2f}% — rupee weakening pressures risk assets.")

    verdict = (
        "FAVORABLE"
        if score >= 25
        else "RISKY"
        if score <= -25
        else "NEUTRAL"
    )

    if not bullets:
        bullets.append("Global cues neutral — no major overnight catalysts.")

    return ReadinessVerdict(verdict=verdict, score=score, bullets=bullets)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_pre_market_brief() -> PreMarketBrief:
    """Compute the pre-market brief end-to-end (does not write to DB)."""
    t0 = time.time()
    cues = _global_cues_parallel()
    vix, vix_chg = _india_vix()
    top, weak = _sector_view()
    candidates = _gap_candidates()
    verdict = _build_verdict(cues, vix, vix_chg, top, weak)
    notes: list[str] = []
    if vix is None:
        notes.append("India VIX could not be fetched — verdict may be incomplete.")
    if not cues:
        notes.append("No global cues fetched — running on partial data.")
    notes.append(f"Computed in {round(time.time() - t0, 1)}s.")

    return PreMarketBrief(
        generated_at=datetime.utcnow().isoformat(),
        global_cues=cues,
        india_vix=vix,
        india_vix_change_pct=vix_chg,
        top_sectors=top,
        weak_sectors=weak,
        gap_candidates=candidates,
        readiness=verdict,
        notes=notes,
    )


def run_pre_market_cycle() -> Dict[str, Any]:
    """Generate + persist the brief. Returns the dict that endpoints serve."""
    brief = generate_pre_market_brief()
    payload = brief.to_dict()
    summary = (
        f"Pre-market verdict: {brief.readiness.verdict} (score {brief.readiness.score:+d}). "
        f"{len(brief.gap_candidates)} gap candidates."
    )
    try:
        with db_session() as db:
            db.add(
                AILearningLog(
                    event="pre_market_brief",
                    summary=summary,
                    details=payload,
                )
            )
    except Exception as exc:  # pragma: no cover
        logger.warning(f"pre_market_engine could not write log: {exc}")
    logger.info(f"pre_market_brief generated — {summary}")
    return payload


def latest_brief() -> Optional[Dict[str, Any]]:
    """Most-recent ``pre_market_brief`` log entry (or None)."""
    try:
        with db_session() as db:
            row = (
                db.query(AILearningLog)
                .filter(AILearningLog.event == "pre_market_brief")
                .order_by(AILearningLog.created_at.desc())
                .first()
            )
            if row is None:
                return None
            payload = row.details or {}
            payload["log_id"] = row.id
            payload["summary"] = row.summary
            payload["created_at"] = (
                row.created_at.isoformat() if row.created_at else None
            )
            return payload
    except Exception as exc:
        logger.warning(f"pre_market_engine.latest_brief failed: {exc}")
        return None
