"""Position sizing & risk-management calculator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskPlan:
    capital: float
    risk_per_trade_pct: float
    max_loss: float
    qty: int
    notional: float
    stoploss_pct: float
    rr: Optional[float]
    portfolio_heat_pct: float


def calculate_position(
    capital: float,
    entry: float,
    stoploss: float,
    target: Optional[float] = None,
    risk_per_trade_pct: float = 1.0,
    max_portfolio_heat_pct: float = 5.0,
) -> RiskPlan:
    """Compute quantity for a trade given a fixed % risk per trade.

    Args:
        capital: Total trading capital in INR.
        entry: Planned entry price.
        stoploss: Planned stoploss price.
        target: Optional target price (for R:R calculation).
        risk_per_trade_pct: Capital at risk per trade (e.g. 1 means 1%).
        max_portfolio_heat_pct: Hard cap on combined open risk.
    """
    if entry <= 0 or stoploss <= 0 or capital <= 0:
        raise ValueError("Capital/entry/stoploss must be positive numbers")

    risk_per_share = abs(entry - stoploss)
    if risk_per_share == 0:
        raise ValueError("Stoploss cannot equal entry")

    max_loss = capital * (risk_per_trade_pct / 100.0)
    raw_qty = max_loss / risk_per_share
    qty = int(max(0, raw_qty))
    notional = qty * entry

    rr = None
    if target is not None and target != entry:
        reward = abs(target - entry)
        rr = round(reward / risk_per_share, 2)

    stoploss_pct = round((risk_per_share / entry) * 100, 2)
    portfolio_heat = round((qty * risk_per_share) / capital * 100, 2)

    if portfolio_heat > max_portfolio_heat_pct:
        scale = max_portfolio_heat_pct / max(portfolio_heat, 1e-6)
        qty = int(qty * scale)
        notional = qty * entry
        portfolio_heat = round((qty * risk_per_share) / capital * 100, 2)

    return RiskPlan(
        capital=capital,
        risk_per_trade_pct=risk_per_trade_pct,
        max_loss=round(max_loss, 2),
        qty=qty,
        notional=round(notional, 2),
        stoploss_pct=stoploss_pct,
        rr=rr,
        portfolio_heat_pct=portfolio_heat,
    )
