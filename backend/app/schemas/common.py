"""Common Pydantic schemas used across the API."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Quote(BaseModel):
    symbol: str
    name: Optional[str] = None
    price: float
    change: float
    change_pct: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DataQualityOut(BaseModel):
    score: float
    issues: List[str] = []
    is_stale: bool = False
    is_synthetic: bool = False
    source: str = "yfinance"
    last_bar_at: Optional[datetime] = None


class QuoteWithQuality(BaseModel):
    quote: Quote
    quality: DataQualityOut


class SearchHit(BaseModel):
    symbol: str
    name: str
    sector: str
    industry: Optional[str] = None
    exchange: str = "NSE"
    market_cap: Optional[str] = None
    nse: Optional[str] = None
    bse: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    match_confidence: float = 1.0
    match_source: str = "exact"


class ResolveOut(BaseModel):
    input: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    sector: Optional[str] = None
    confidence: float = 0.0
    source: str = "fallback"
    listed: bool = True
    message: Optional[str] = None
    suggestions: List[str] = []


class MarketStatusOut(BaseModel):
    state: str
    is_open: bool
    is_trading_day: bool
    now_ist: datetime
    next_open_at: Optional[datetime] = None
    next_close_at: Optional[datetime] = None
    label: str
    seconds_until_next: Optional[int] = None


class OhlcRow(BaseModel):
    time: int  # unix seconds
    open: float
    high: float
    low: float
    close: float
    volume: float


class Indicators(BaseModel):
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema200: Optional[float] = None
    sma50: Optional[float] = None
    sma200: Optional[float] = None
    vwap: Optional[float] = None
    atr: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_mid: Optional[float] = None
    adx: Optional[float] = None
    obv: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    volatility_pct: Optional[float] = None


class Signal(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0, le=100)
    entry_low: Optional[float] = None
    entry_high: Optional[float] = None
    stoploss: Optional[float] = None
    target1: Optional[float] = None
    target2: Optional[float] = None
    rr: Optional[float] = None
    mode: Literal["intraday", "swing", "positional"] = "swing"
    reasoning: str = ""
    score: float = 0
    probability: float = 0
    detected_patterns: List[str] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # Quality-control fields (filled by quality_engine)
    quality_score: float = 0  # 0..100 composite
    quality_grade: Literal[
        "AVOID", "WEAK", "MODERATE", "STRONG", "HIGH_CONVICTION", "NO_TRADE"
    ] = "MODERATE"
    quality_breakdown: dict = Field(default_factory=dict)
    no_trade_reasons: List[str] = []
    # ML-augmented confidence (filled by ml_confidence when the model is ready)
    ml_confidence: Optional[float] = None
    ml_p_win: Optional[float] = None
    rule_confidence: Optional[float] = None


class AnalysisResponse(BaseModel):
    quote: Quote
    indicators: Indicators
    signal: Signal
    sector: Optional[str] = None
    relative_strength: Optional[float] = None
    notes: List[str] = []
    data_quality: Optional[DataQualityOut] = None


class NewsItem(BaseModel):
    title: str
    summary: Optional[str] = None
    link: str
    source: str
    published: Optional[datetime] = None
    sentiment: float = 0  # -1..1
    impact_score: float = 0  # 0..1
    impacted_symbols: List[str] = []
    impacted_sectors: List[str] = []


class SectorStrength(BaseModel):
    sector: str
    strength: float  # -100..100
    leaders: List[str] = []
    laggards: List[str] = []


class WatchlistCreate(BaseModel):
    name: str


class WatchlistAddSymbol(BaseModel):
    symbol: str
    note: Optional[str] = None


class WatchlistOut(BaseModel):
    id: int
    name: str
    symbols: List[str]


class BacktestRequest(BaseModel):
    symbol: str
    strategy: Literal[
        "sma_crossover", "rsi_reversal", "breakout", "volume_breakout",
    ] = "sma_crossover"
    period: str = "1y"
    interval: str = "1d"
    fast: int = 20
    slow: int = 50
    rsi_low: int = 30
    rsi_high: int = 70


class BacktestResponse(BaseModel):
    symbol: str
    strategy: str
    trades: int
    win_rate: float
    total_return_pct: float
    max_drawdown_pct: float
    avg_rr: float
    equity_curve: List[float]


class ChatRequest(BaseModel):
    question: str
    symbols: List[str] = []
    context_news: bool = True


class ChatResponse(BaseModel):
    answer: str
    used_symbols: List[str] = []
    used_news_count: int = 0
    used_memories: int = 0


class AlertOut(BaseModel):
    id: int
    symbol: str
    kind: str
    severity: str
    title: str
    message: str
    price: Optional[float] = None
    created_at: datetime


class CorrelationOut(BaseModel):
    symbol: str
    against: str
    pearson: float
    sample: int
