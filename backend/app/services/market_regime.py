"""Market regime classification engine.

Classifies the current Indian market regime by combining:

- Nifty 50 trend (EMA50 / EMA200 stack + 20-day return)
- breadth (advancers vs decliners over the curated universe)
- volatility (India VIX, falling back to realised volatility)
- news sentiment (free-RSS aggregate)
- advance/decline ratio

The regime label is purely *advisory*: it is used to:
- snapshot context onto every prediction (`PredictionHistory.market_regime`),
- bucket indicator performance per regime,
- show a dedicated "Market Regime" dashboard.

Nothing here is investment advice.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from ..database import db_session
from ..models.prediction_engine import MarketRegime
from . import correlation_engine, market_data, news_engine, universe


REGIMES = {
    "bullish_trend",
    "bearish_trend",
    "sideways",
    "high_volatility",
    "risk_on",
    "risk_off",
}


@dataclass
class RegimeSnapshot:
    regime: str
    nifty_trend: str
    breadth_score: float
    volatility_index: Optional[float]
    nifty_return_20d: float
    advance_decline_ratio: float
    avg_news_sentiment: float
    description: str

    def as_dict(self) -> dict:
        return {
            "regime": self.regime,
            "nifty_trend": self.nifty_trend,
            "breadth_score": self.breadth_score,
            "volatility_index": self.volatility_index,
            "nifty_return_20d": self.nifty_return_20d,
            "advance_decline_ratio": self.advance_decline_ratio,
            "avg_news_sentiment": self.avg_news_sentiment,
            "description": self.description,
        }


def _nifty_trend(period: str = "6mo") -> tuple[str, float]:
    df = market_data.get_history("^NSEI", period=period, interval="1d")
    if df.empty or len(df) < 60:
        return "unknown", 0.0
    close = df["Close"]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1] if len(close) >= 200 else ema50
    last = float(close.iloc[-1])
    ret20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0.0
    if last > ema50 > ema200:
        trend = "uptrend"
    elif last < ema50 < ema200:
        trend = "downtrend"
    else:
        trend = "sideways"
    return trend, round(ret20, 2)


def _vix_level() -> Optional[float]:
    try:
        q = market_data.get_quote("^INDIAVIX")
        return float(q.price)
    except Exception:
        return None


def _breadth() -> dict:
    syms = universe.all_symbols()[:40]
    return correlation_engine.market_breadth(syms)


def _news_sentiment_avg() -> float:
    try:
        agg = news_engine.aggregate_market_sentiment()
        return float(agg.get("avg_sentiment", 0.0))
    except Exception:
        return 0.0


def classify_regime() -> RegimeSnapshot:
    """Compute the current regime snapshot. Does NOT persist by itself."""
    trend, ret20 = _nifty_trend()
    vix = _vix_level()
    breadth = _breadth()
    advancers = breadth.get("advancers", 0)
    decliners = breadth.get("decliners", 0)
    total = max(advancers + decliners, 1)
    ad_ratio = round(advancers / total, 3)
    breadth_score = round((advancers - decliners) / total * 100, 2)
    sentiment = _news_sentiment_avg()

    # Decision tree
    if vix is not None and vix >= 22 and abs(ret20) > 4:
        regime = "high_volatility"
    elif trend == "uptrend" and breadth_score > 10 and sentiment >= -0.05:
        regime = "bullish_trend"
    elif trend == "downtrend" and breadth_score < -10:
        regime = "bearish_trend"
    elif sentiment <= -0.15 and breadth_score < 0:
        regime = "risk_off"
    elif sentiment >= 0.15 and breadth_score > 0 and trend != "downtrend":
        regime = "risk_on"
    else:
        regime = "sideways"

    description = (
        f"Nifty {trend} ({ret20:+.1f}% 20D), "
        f"breadth {breadth_score:+.1f}, "
        f"VIX {vix if vix is not None else 'n/a'}, "
        f"news sentiment {sentiment:+.2f}"
    )

    return RegimeSnapshot(
        regime=regime,
        nifty_trend=trend,
        breadth_score=breadth_score,
        volatility_index=vix,
        nifty_return_20d=ret20,
        advance_decline_ratio=ad_ratio,
        avg_news_sentiment=sentiment,
        description=description,
    )


def get_current_regime() -> RegimeSnapshot:
    """Cached: re-uses the most recent persisted regime if <30 min old."""
    try:
        with db_session() as db:
            latest = (
                db.query(MarketRegime)
                .order_by(MarketRegime.created_at.desc())
                .first()
            )
            if latest and (datetime.utcnow() - latest.created_at) < timedelta(minutes=30):
                return RegimeSnapshot(
                    regime=latest.regime,
                    nifty_trend=latest.nifty_trend or "unknown",
                    breadth_score=latest.breadth_score or 0.0,
                    volatility_index=latest.volatility_index,
                    nifty_return_20d=latest.nifty_return_20d or 0.0,
                    advance_decline_ratio=latest.advance_decline_ratio or 0.0,
                    avg_news_sentiment=latest.avg_news_sentiment or 0.0,
                    description=latest.description or "",
                )
    except Exception as exc:
        logger.warning(f"get_current_regime cache lookup failed: {exc}")
    return persist_regime()


def persist_regime(db: Optional[Session] = None) -> RegimeSnapshot:
    """Compute, persist, and return the current regime snapshot."""
    snap = classify_regime()
    row = MarketRegime(
        regime=snap.regime,
        nifty_trend=snap.nifty_trend,
        breadth_score=snap.breadth_score,
        volatility_index=snap.volatility_index,
        nifty_return_20d=snap.nifty_return_20d,
        advance_decline_ratio=snap.advance_decline_ratio,
        avg_news_sentiment=snap.avg_news_sentiment,
        description=snap.description,
    )
    if db is not None:
        db.add(row)
    else:
        with db_session() as inner:
            inner.add(row)
    return snap


def recent_regimes(limit: int = 50) -> list[MarketRegime]:
    with db_session() as db:
        return (
            db.query(MarketRegime)
            .order_by(MarketRegime.created_at.desc())
            .limit(limit)
            .all()
        )
