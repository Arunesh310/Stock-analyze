"""Persisted AI signal model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class StoredSignal(Base):
    __tablename__ = "stored_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(10), index=True)  # BUY/SELL/HOLD
    confidence: Mapped[float] = mapped_column(Float)
    entry_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    stoploss: Mapped[float | None] = mapped_column(Float, nullable=True)
    target1: Mapped[float | None] = mapped_column(Float, nullable=True)
    target2: Mapped[float | None] = mapped_column(Float, nullable=True)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default="swing")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
