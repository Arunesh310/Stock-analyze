"""Technical indicator computation using `ta` library + small helpers.

Falls back to manual numpy/pandas implementations if `ta` import fails.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import MACD, ADXIndicator, EMAIndicator, SMAIndicator
    from ta.volatility import AverageTrueRange, BollingerBands
    from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
    _HAS_TA = True
except Exception:  # pragma: no cover
    _HAS_TA = False

from ..schemas.common import Indicators


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def support_resistance(df: pd.DataFrame, window: int = 20) -> tuple[float, float]:
    """Simple swing-based S/R: rolling min/max of recent window."""
    if df.empty:
        return 0.0, 0.0
    recent = df.tail(max(window * 3, 60))
    support = float(recent["Low"].rolling(window).min().dropna().iloc[-1])
    resistance = float(recent["High"].rolling(window).max().dropna().iloc[-1])
    return support, resistance


def compute_indicators(df: pd.DataFrame) -> Indicators:
    """Compute a comprehensive set of indicators on an OHLCV dataframe."""
    if df is None or df.empty or len(df) < 30:
        return Indicators()

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    vol = df["Volume"].astype(float) if "Volume" in df else pd.Series([0] * len(df))

    if _HAS_TA:
        rsi = RSIIndicator(close=close, window=14).rsi()
        macd_obj = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
        macd_line = macd_obj.macd()
        macd_signal = macd_obj.macd_signal()
        macd_hist = macd_obj.macd_diff()
        ema20 = EMAIndicator(close=close, window=20).ema_indicator()
        ema50 = EMAIndicator(close=close, window=50).ema_indicator()
        ema200 = EMAIndicator(close=close, window=200).ema_indicator()
        sma50 = SMAIndicator(close=close, window=50).sma_indicator()
        sma200 = SMAIndicator(close=close, window=200).sma_indicator()
        bb = BollingerBands(close=close, window=20, window_dev=2)
        bb_upper, bb_lower, bb_mid = bb.bollinger_hband(), bb.bollinger_lband(), bb.bollinger_mavg()
        atr = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
        adx = ADXIndicator(high=high, low=low, close=close, window=14).adx()
        try:
            vwap_series = VolumeWeightedAveragePrice(
                high=high, low=low, close=close, volume=vol, window=14
            ).volume_weighted_average_price()
        except Exception:
            vwap_series = pd.Series([np.nan] * len(close), index=close.index)
        try:
            obv = OnBalanceVolumeIndicator(close=close, volume=vol).on_balance_volume()
        except Exception:
            obv = pd.Series([np.nan] * len(close), index=close.index)
    else:  # pragma: no cover
        rsi = _rsi(close)
        ema12 = _ema(close, 12)
        ema26 = _ema(close, 26)
        macd_line = ema12 - ema26
        macd_signal = _ema(macd_line, 9)
        macd_hist = macd_line - macd_signal
        ema20 = _ema(close, 20)
        ema50 = _ema(close, 50)
        ema200 = _ema(close, 200)
        sma50 = _sma(close, 50)
        sma200 = _sma(close, 200)
        std = close.rolling(20).std()
        bb_mid = _sma(close, 20)
        bb_upper, bb_lower = bb_mid + 2 * std, bb_mid - 2 * std
        tr = pd.concat(
            [(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
        ).max(axis=1)
        atr = tr.rolling(14).mean()
        adx = pd.Series([np.nan] * len(close))
        vwap_series = (close * vol).rolling(14).sum() / vol.rolling(14).sum()
        obv = (np.sign(close.diff()).fillna(0) * vol).cumsum()

    support, resistance = support_resistance(df)
    returns = close.pct_change().dropna()
    vol_pct = float(returns.std() * np.sqrt(252) * 100) if not returns.empty else None

    def _last(series: pd.Series) -> Optional[float]:
        if series is None or series.empty:
            return None
        v = series.dropna()
        if v.empty:
            return None
        x = v.iloc[-1]
        try:
            return float(x)
        except Exception:
            return None

    return Indicators(
        rsi=_last(rsi),
        macd=_last(macd_line),
        macd_signal=_last(macd_signal),
        macd_hist=_last(macd_hist),
        ema20=_last(ema20),
        ema50=_last(ema50),
        ema200=_last(ema200),
        sma50=_last(sma50),
        sma200=_last(sma200),
        vwap=_last(vwap_series),
        atr=_last(atr),
        bb_upper=_last(bb_upper),
        bb_lower=_last(bb_lower),
        bb_mid=_last(bb_mid),
        adx=_last(adx),
        obv=_last(obv),
        support=round(support, 2) if support else None,
        resistance=round(resistance, 2) if resistance else None,
        volatility_pct=round(vol_pct, 2) if vol_pct else None,
    )
