"""Pydantic schemas for the Prediction Validation + Learning engine.

These are *response* contracts only — the engine itself works on ORM rows.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PredictionOut(BaseModel):
    id: int
    symbol: str
    sector: Optional[str] = None
    action: str
    mode: str
    confidence: float
    probability: float
    score: float
    entry_ref: float
    entry_low: Optional[float] = None
    entry_high: Optional[float] = None
    stoploss: Optional[float] = None
    target1: Optional[float] = None
    target2: Optional[float] = None
    rr: Optional[float] = None
    atr_at_entry: Optional[float] = None
    market_regime: Optional[str] = None
    news_sentiment: Optional[float] = None
    sector_strength: Optional[float] = None
    detected_patterns: List[str] = []
    reasoning: str = ""
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class OutcomeOut(BaseModel):
    prediction_id: int
    outcome: str
    direction_correct: Optional[bool] = None
    entry_triggered: bool
    target1_hit: bool
    target2_hit: bool
    stoploss_hit: bool
    max_favorable_pct: Optional[float] = None
    max_adverse_pct: Optional[float] = None
    final_price: Optional[float] = None
    realized_pct: Optional[float] = None
    holding_bars: Optional[int] = None
    holding_days: Optional[float] = None
    bars_to_target1: Optional[int] = None
    bars_to_stoploss: Optional[int] = None
    notes: Optional[str] = None
    validated_at: datetime


class SimulatedReturnOut(BaseModel):
    prediction_id: int
    symbol: str
    action: str
    capital_invested: float
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    realized_pnl: float
    realized_pct: float
    unrealized_pnl: float
    max_gain_pnl: float
    max_loss_pnl: float
    holding_days: Optional[float] = None
    closed_at: Optional[datetime] = None
    updated_at: datetime


class PredictionFullOut(BaseModel):
    prediction: PredictionOut
    outcome: Optional[OutcomeOut] = None
    simulated: Optional[SimulatedReturnOut] = None


class ConfidenceBucketOut(BaseModel):
    bucket_low: int
    bucket_high: int
    mode: str
    sample_size: int
    wins: int
    losses: int
    win_rate: float
    avg_return_pct: float
    calibration_gap: float


class SetupQualityOut(BaseModel):
    setup_name: str
    mode: str
    sample_size: int
    wins: int
    losses: int
    win_rate: float
    avg_return_pct: float
    quality_score: float
    weight_multiplier: float


class SectorPerformanceOut(BaseModel):
    sector: str
    mode: str
    sample_size: int
    wins: int
    losses: int
    win_rate: float
    avg_return_pct: float


class IndicatorPerformanceOut(BaseModel):
    indicator: str
    regime: str
    mode: str
    sample_size: int
    wins: int
    losses: int
    win_rate: float
    edge_score: float
    weight: float


class LearningEventOut(BaseModel):
    id: int
    event: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    impact_score: Optional[float] = None
    created_at: datetime


class MarketRegimeOut(BaseModel):
    id: int
    regime: str
    nifty_trend: Optional[str] = None
    breadth_score: Optional[float] = None
    volatility_index: Optional[float] = None
    nifty_return_20d: Optional[float] = None
    advance_decline_ratio: Optional[float] = None
    avg_news_sentiment: Optional[float] = None
    description: Optional[str] = None
    created_at: datetime


class PerformanceSummary(BaseModel):
    total_predictions: int
    open_predictions: int
    closed_predictions: int
    wins: int
    losses: int
    win_rate: float
    avg_return_pct: float
    avg_holding_days: float
    total_simulated_pnl: float
    total_simulated_capital: float
    cumulative_return_pct: float
    best_sector: Optional[str] = None
    worst_sector: Optional[str] = None
    best_setup: Optional[str] = None
    worst_setup: Optional[str] = None
    best_regime: Optional[str] = None
    avg_rr_achieved: float
    confidence_calibration_gap: float
    samples_since: Optional[datetime] = None


class CumulativeProfitPoint(BaseModel):
    date: str
    cumulative_pnl: float
    cumulative_pct: float
    closed_trades: int


class AccuracyTrendPoint(BaseModel):
    bucket: str  # YYYY-MM or YYYY-Www
    sample_size: int
    win_rate: float
    avg_return_pct: float


class HeatmapCell(BaseModel):
    row: str
    col: str
    value: float
    sample_size: int


class ValidationRunResult(BaseModel):
    scanned: int
    closed: int
    still_open: int
    new_wins: int
    new_losses: int
    learning_events: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


SimulationMode = Literal["intraday", "swing", "positional"]
