"""Alert generation: scan a symbol list and emit DB-persisted alerts."""
from __future__ import annotations

from datetime import datetime
from typing import List

from loguru import logger
from sqlalchemy.orm import Session

from ..models.alerts import Alert
from .indicators import compute_indicators
from .market_data import get_history
from .patterns import detected_patterns


def _emit(db: Session, symbol: str, kind: str, severity: str,
          title: str, message: str, price: float | None) -> Alert:
    a = Alert(symbol=symbol, kind=kind, severity=severity,
              title=title, message=message, price=price,
              created_at=datetime.utcnow())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def scan_for_alerts(db: Session, symbols: List[str]) -> List[Alert]:
    """Run alert checks on all symbols. Idempotency is intentionally relaxed
    (callers typically clear/refresh before re-scanning).
    """
    out: List[Alert] = []
    for symbol in symbols:
        try:
            df = get_history(symbol, period="3mo", interval="1d")
            if df.empty or len(df) < 30:
                continue
            ind = compute_indicators(df)
            patterns = detected_patterns(df)
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])

            # Volume spike
            if "Volume" in df:
                vol_now = float(df["Volume"].iloc[-1])
                vol_avg = float(df["Volume"].rolling(20).mean().iloc[-1] or 0)
                if vol_avg and vol_now > 2 * vol_avg:
                    out.append(_emit(db, symbol, "volume_spike", "warn",
                                     f"Volume spike on {symbol}",
                                     f"Today's volume {vol_now/1e5:.1f}L is "
                                     f"{vol_now/vol_avg:.1f}x the 20-day avg.",
                                     last))

            # 20-day breakout / breakdown
            if "20-day breakout" in patterns:
                out.append(_emit(db, symbol, "breakout", "info",
                                 f"Breakout: {symbol} above 20-day high",
                                 f"Closed at {last:.2f}, breaking the recent range.",
                                 last))
            if "20-day breakdown" in patterns:
                out.append(_emit(db, symbol, "breakdown", "warn",
                                 f"Breakdown: {symbol} below 20-day low",
                                 f"Closed at {last:.2f}, breaking down.",
                                 last))

            # RSI reversal (cross 30 or cross 70)
            if ind.rsi is not None:
                prev_ind_df = df.iloc[-2:]
                if len(prev_ind_df) == 2:
                    if ind.rsi > 30 and prev < last and ind.rsi < 40:
                        out.append(_emit(db, symbol, "rsi_reversal", "info",
                                         f"RSI bullish reversal on {symbol}",
                                         f"RSI {ind.rsi:.1f} climbing out of oversold.",
                                         last))
                    if ind.rsi < 70 and prev > last and ind.rsi > 60:
                        out.append(_emit(db, symbol, "rsi_reversal", "warn",
                                         f"RSI bearish reversal on {symbol}",
                                         f"RSI {ind.rsi:.1f} rolling over from overbought.",
                                         last))

            # MACD crossover
            if ind.macd is not None and ind.macd_signal is not None:
                if ind.macd_hist is not None:
                    # use the histogram sign change
                    macd_prev = float(ind.macd) - float(ind.macd_hist)
                    sig_prev = macd_prev - 0  # placeholder, just want sign change
                    if ind.macd > ind.macd_signal and ind.macd_hist > 0 > sig_prev - ind.macd_hist:
                        out.append(_emit(db, symbol, "macd_cross", "info",
                                         f"MACD bullish crossover on {symbol}",
                                         f"MACD {ind.macd:.2f} > Signal {ind.macd_signal:.2f}",
                                         last))

            # Support bounce
            if ind.support and abs(last - ind.support) / last < 0.01 and last > prev:
                out.append(_emit(db, symbol, "support_bounce", "info",
                                 f"Support bounce on {symbol}",
                                 f"Price {last:.2f} bouncing near support {ind.support:.2f}.",
                                 last))

            # Resistance breakout
            if ind.resistance and last > ind.resistance and prev <= ind.resistance:
                out.append(_emit(db, symbol, "resistance_break", "info",
                                 f"Resistance break on {symbol}",
                                 f"Cleared {ind.resistance:.2f}, closed at {last:.2f}.",
                                 last))
        except Exception as exc:
            logger.warning(f"Alert scan failed for {symbol}: {exc}")
            continue
    return out
