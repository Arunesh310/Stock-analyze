"""ORM models for the Prediction Validation + Learning + Profitability engine.

These tables extend (they do NOT replace) `stored_signals`. They power:

- prediction tracking with a full snapshot of indicators / regime / news at
  the moment a signal was generated,
- objective outcome validation against real price action,
- ₹-based profit simulation,
- confidence-bucket calibration,
- failure-cause learning,
- adaptive indicator / setup / sector quality scoring,
- a long-running AI learning log.

All tables are independent of the existing alerts / watchlists / stored_signals
schema and are created automatically by `init_db()` because they share the
common SQLAlchemy `Base`.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


# ---------------------------------------------------------------------------
# 1. Prediction history — every signal we ever produce
# ---------------------------------------------------------------------------


class PredictionHistory(Base):
    """A snapshot of every actionable signal at the moment it was generated.

    This is the *source of truth* for everything downstream — outcomes,
    simulated returns, confidence calibration and learning all join back
    here on ``prediction_id``.
    """

    __tablename__ = "prediction_history"
    __table_args__ = (
        Index("ix_pred_symbol_created", "symbol", "created_at"),
        Index("ix_pred_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Core signal fields
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    sector: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(10), index=True)  # BUY / SELL / HOLD
    mode: Mapped[str] = mapped_column(String(20), default="swing")
    confidence: Mapped[float] = mapped_column(Float)
    probability: Mapped[float] = mapped_column(Float, default=0.5)
    score: Mapped[float] = mapped_column(Float, default=0.0)

    # Trade plan as of signal time
    entry_ref: Mapped[float] = mapped_column(Float)  # last_close at signal time
    entry_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    stoploss: Mapped[float | None] = mapped_column(Float, nullable=True)
    target1: Mapped[float | None] = mapped_column(Float, nullable=True)
    target2: Mapped[float | None] = mapped_column(Float, nullable=True)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_at_entry: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Reasoning / patterns
    reasoning: Mapped[str] = mapped_column(Text, default="")
    detected_patterns: Mapped[list | None] = mapped_column(JSON, default=list)

    # Snapshots
    indicators_snapshot: Mapped[dict | None] = mapped_column(JSON, default=dict)
    market_regime: Mapped[str | None] = mapped_column(String(40), nullable=True)
    regime_snapshot: Mapped[dict | None] = mapped_column(JSON, default=dict)
    news_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    breadth_advancers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    breadth_decliners: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    # OPEN | TARGET1_HIT | TARGET2_HIT | STOPLOSS_HIT | EXPIRED | INVALIDATED
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Convenience back-refs
    outcome: Mapped["PredictionOutcome | None"] = relationship(
        back_populates="prediction",
        uselist=False,
        cascade="all, delete-orphan",
    )
    simulated: Mapped["SimulatedReturn | None"] = relationship(
        back_populates="prediction",
        uselist=False,
        cascade="all, delete-orphan",
    )
    feedback: Mapped[list["LearningFeedback"]] = relationship(
        back_populates="prediction",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# 2. Prediction outcomes — what actually happened
# ---------------------------------------------------------------------------


class PredictionOutcome(Base):
    """Objective outcome computed by `validation_engine` against real prices."""

    __tablename__ = "prediction_outcomes"
    __table_args__ = (
        Index("ix_outcome_hit", "target1_hit", "stoploss_hit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("prediction_history.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Outcome
    outcome: Mapped[str] = mapped_column(String(30), index=True)
    # WIN | LOSS | PARTIAL_WIN | OPEN | EXPIRED | INVALIDATED
    direction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    entry_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    target1_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    target2_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    stoploss_hit: Mapped[bool] = mapped_column(Boolean, default=False)

    # Price stats during the holding window
    max_favorable_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_adverse_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Time stats
    holding_bars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    holding_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    bars_to_target1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bars_to_stoploss: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Context
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    prediction: Mapped[PredictionHistory] = relationship(back_populates="outcome")


# ---------------------------------------------------------------------------
# 3. Simulated returns — what ₹X would have done
# ---------------------------------------------------------------------------


class SimulatedReturn(Base):
    __tablename__ = "simulated_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("prediction_history.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    capital_invested: Mapped[float] = mapped_column(Float, default=10000.0)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # TARGET1 | TARGET2 | STOPLOSS | EXPIRED | OPEN

    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pct: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    max_gain_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    max_loss_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    holding_days: Mapped[float | None] = mapped_column(Float, nullable=True)

    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True
    )

    prediction: Mapped[PredictionHistory] = relationship(back_populates="simulated")


# ---------------------------------------------------------------------------
# 4. Confidence calibration
# ---------------------------------------------------------------------------


class ConfidenceAccuracy(Base):
    """Bucketed accuracy of our confidence score (e.g. how often 80-89%
    signals actually win)."""

    __tablename__ = "confidence_accuracy"
    __table_args__ = (
        UniqueConstraint("bucket_low", "bucket_high", "mode", name="uq_conf_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket_low: Mapped[int] = mapped_column(Integer)   # inclusive
    bucket_high: Mapped[int] = mapped_column(Integer)  # exclusive
    mode: Mapped[str] = mapped_column(String(20), default="swing")
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    calibration_gap: Mapped[float] = mapped_column(Float, default=0.0)
    # +ve = overconfident, -ve = underconfident
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 5. Learning feedback
# ---------------------------------------------------------------------------


class LearningFeedback(Base):
    """Why did this prediction succeed or fail? Used by the learning engine."""

    __tablename__ = "learning_feedback"
    __table_args__ = (
        Index("ix_feedback_category", "category", "outcome"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("prediction_history.id", ondelete="CASCADE"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(20), index=True)  # WIN / LOSS / ...
    category: Mapped[str] = mapped_column(String(40), index=True)
    # e.g. weak_breadth | false_breakout | sector_reversal | volatility_spike
    reason: Mapped[str] = mapped_column(Text)
    market_condition: Mapped[str | None] = mapped_column(String(40), nullable=True)
    indicator_state: Mapped[dict | None] = mapped_column(JSON, default=dict)
    sector_condition: Mapped[str | None] = mapped_column(String(60), nullable=True)
    confidence_at_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    prediction: Mapped[PredictionHistory] = relationship(back_populates="feedback")


# ---------------------------------------------------------------------------
# 6. Market regimes
# ---------------------------------------------------------------------------


class MarketRegime(Base):
    """Periodic snapshot of the overall Indian market regime."""

    __tablename__ = "market_regimes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    regime: Mapped[str] = mapped_column(String(40), index=True)
    # bullish_trend | bearish_trend | sideways | high_volatility | risk_off | risk_on
    nifty_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    breadth_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    nifty_return_20d: Mapped[float | None] = mapped_column(Float, nullable=True)
    advance_decline_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_news_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


# ---------------------------------------------------------------------------
# 7. Signal-quality (setup-level) scoring
# ---------------------------------------------------------------------------


class SignalQualityScore(Base):
    """Quality score per (setup_name, mode) updated by the learning engine."""

    __tablename__ = "signal_quality_scores"
    __table_args__ = (
        UniqueConstraint("setup_name", "mode", name="uq_setup_mode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    setup_name: Mapped[str] = mapped_column(String(80), index=True)
    mode: Mapped[str] = mapped_column(String(20), default="swing")
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=50.0)  # 0-100
    weight_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 8. Sector performance
# ---------------------------------------------------------------------------


class SectorPerformance(Base):
    __tablename__ = "sector_performance"
    __table_args__ = (
        UniqueConstraint("sector", "mode", name="uq_sector_mode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector: Mapped[str] = mapped_column(String(60), index=True)
    mode: Mapped[str] = mapped_column(String(20), default="swing")
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 9. Indicator-level performance
# ---------------------------------------------------------------------------


class IndicatorPerformance(Base):
    """How predictive is each indicator/component in different regimes?"""

    __tablename__ = "indicator_performance"
    __table_args__ = (
        UniqueConstraint("indicator", "regime", "mode", name="uq_ind_reg_mode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator: Mapped[str] = mapped_column(String(60), index=True)
    regime: Mapped[str] = mapped_column(String(40), default="any", index=True)
    mode: Mapped[str] = mapped_column(String(20), default="swing")
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    edge_score: Mapped[float] = mapped_column(Float, default=0.0)  # -1..+1
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 10. Long-running AI learning log
# ---------------------------------------------------------------------------


class AILearningLog(Base):
    __tablename__ = "ai_learning_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(60), index=True)
    # e.g. weights_adjusted | confidence_recalibrated | regime_change
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON, default=dict)
    impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
