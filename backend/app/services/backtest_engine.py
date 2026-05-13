"""Simple, vectorised strategy backtester.

Strategies supported:
- sma_crossover: long when fast SMA > slow SMA
- rsi_reversal: long when RSI crosses above `rsi_low`, exit when above `rsi_high`
- breakout: long when close > rolling 20-day high (Donchian)
- volume_breakout: long when close > 20-day high AND volume > 2x avg

Returns trade stats and equity curve. Long-only for simplicity.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd

from .indicators import _rsi, _sma
from .market_data import get_history


def _trade_stats(equity: pd.Series, trades: List[Tuple[float, float]]) -> dict:
    if equity.empty:
        return {"trades": 0, "win_rate": 0, "total_return_pct": 0,
                "max_drawdown_pct": 0, "avg_rr": 0, "equity_curve": []}
    wins = [t for t in trades if t[1] > t[0]]
    losses = [t for t in trades if t[1] <= t[0]]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
    total_return = float((equity.iloc[-1] / equity.iloc[0] - 1) * 100)
    rolling_max = equity.cummax()
    dd = (equity - rolling_max) / rolling_max
    max_dd = float(dd.min() * 100) if not dd.empty else 0.0
    if wins and losses:
        avg_win = np.mean([(b / a - 1) for a, b in wins])
        avg_loss = abs(np.mean([(b / a - 1) for a, b in losses]))
        avg_rr = float(avg_win / avg_loss) if avg_loss else 0.0
    else:
        avg_rr = 0.0
    return {
        "trades": len(trades),
        "win_rate": round(win_rate, 2),
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "avg_rr": round(avg_rr, 2),
        "equity_curve": [round(v, 4) for v in equity.tolist()],
    }


def _signals_to_trades(close: pd.Series, signal: pd.Series) -> Tuple[pd.Series, List[Tuple[float, float]]]:
    """Convert a 0/1 long signal series to entries/exits and an equity curve."""
    pos = signal.shift(1).fillna(0).astype(int)
    rets = close.pct_change().fillna(0) * pos
    equity = (1 + rets).cumprod()

    trades: List[Tuple[float, float]] = []
    entry_price = None
    for i in range(1, len(signal)):
        if signal.iloc[i] == 1 and signal.iloc[i - 1] == 0:
            entry_price = float(close.iloc[i])
        elif signal.iloc[i] == 0 and signal.iloc[i - 1] == 1 and entry_price is not None:
            trades.append((entry_price, float(close.iloc[i])))
            entry_price = None
    if entry_price is not None:
        trades.append((entry_price, float(close.iloc[-1])))
    return equity, trades


def backtest(
    symbol: str,
    strategy: str = "sma_crossover",
    period: str = "1y",
    interval: str = "1d",
    fast: int = 20,
    slow: int = 50,
    rsi_low: int = 30,
    rsi_high: int = 70,
) -> dict:
    df = get_history(symbol, period=period, interval=interval)
    if df.empty or len(df) < max(fast, slow, 20) + 5:
        return {"trades": 0, "win_rate": 0, "total_return_pct": 0,
                "max_drawdown_pct": 0, "avg_rr": 0, "equity_curve": []}

    close = df["Close"].astype(float)
    vol = df["Volume"].astype(float) if "Volume" in df else pd.Series([0] * len(df))

    if strategy == "sma_crossover":
        f = _sma(close, fast)
        s = _sma(close, slow)
        sig = (f > s).astype(int)
    elif strategy == "rsi_reversal":
        rsi = _rsi(close)
        sig = pd.Series(0, index=close.index)
        in_pos = 0
        for i in range(len(close)):
            if not np.isnan(rsi.iloc[i]):
                if not in_pos and rsi.iloc[i] < rsi_low:
                    in_pos = 1
                elif in_pos and rsi.iloc[i] > rsi_high:
                    in_pos = 0
            sig.iloc[i] = in_pos
    elif strategy == "breakout":
        roll_high = close.rolling(fast).max().shift(1)
        sig = (close > roll_high).astype(int)
    elif strategy == "volume_breakout":
        roll_high = close.rolling(fast).max().shift(1)
        avg_v = vol.rolling(fast).mean().shift(1)
        sig = ((close > roll_high) & (vol > 2 * avg_v)).astype(int)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    equity, trades = _signals_to_trades(close, sig)
    return _trade_stats(equity, trades)
