export type Quote = {
  symbol: string;
  name?: string;
  price: number;
  change: number;
  change_pct: number;
  open?: number;
  high?: number;
  low?: number;
  prev_close?: number;
  volume?: number;
  timestamp: string;
};

export type OhlcRow = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Indicators = {
  rsi?: number;
  macd?: number;
  macd_signal?: number;
  macd_hist?: number;
  ema20?: number;
  ema50?: number;
  ema200?: number;
  sma50?: number;
  sma200?: number;
  vwap?: number;
  atr?: number;
  bb_upper?: number;
  bb_lower?: number;
  bb_mid?: number;
  adx?: number;
  obv?: number;
  support?: number;
  resistance?: number;
  volatility_pct?: number;
};

export type Signal = {
  symbol: string;
  action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  entry_low?: number;
  entry_high?: number;
  stoploss?: number;
  target1?: number;
  target2?: number;
  rr?: number;
  mode: "intraday" | "swing" | "positional";
  reasoning: string;
  score: number;
  probability: number;
  detected_patterns: string[];
  timestamp: string;
};

export type DataQuality = {
  score: number;
  issues: string[];
  is_stale: boolean;
  is_synthetic: boolean;
  source: string;
  last_bar_at?: string | null;
};

export type AnalysisResponse = {
  quote: Quote;
  indicators: Indicators;
  signal: Signal;
  sector?: string;
  relative_strength?: number;
  notes: string[];
  data_quality?: DataQuality | null;
};

export type SearchHit = {
  symbol: string;
  name: string;
  sector: string;
  industry?: string;
  exchange: string;
  market_cap?: string;
  nse?: string;
  bse?: string;
  price?: number;
  change?: number;
  change_pct?: number;
  match_confidence: number;
  match_source: string;
};

export type ResolveResult = {
  input: string;
  symbol?: string | null;
  name?: string | null;
  sector?: string | null;
  confidence: number;
  source: string;
  listed?: boolean;
  message?: string | null;
  suggestions?: string[];
};

export type PortfolioMetrics = {
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_return_pct: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  profit_factor: number | null;
  expectancy_pct: number;
  expectancy_inr: number;
  max_drawdown_inr: number;
  max_drawdown_pct: number;
  sharpe: number;
  cagr_pct: number;
  total_pnl: number;
  total_capital_deployed: number;
  first_trade_at: string | null;
  last_trade_at: string | null;
};

export type MarketStatus = {
  state: "preopen" | "regular" | "afterhours" | "closed";
  is_open: boolean;
  is_trading_day: boolean;
  now_ist: string;
  next_open_at?: string | null;
  next_close_at?: string | null;
  label: string;
  seconds_until_next?: number | null;
};

export type QuoteWithQuality = {
  quote: Quote;
  quality: DataQuality;
};

export type NewsItem = {
  title: string;
  summary?: string;
  link: string;
  source: string;
  published?: string;
  sentiment: number;
  impact_score: number;
  impacted_symbols: string[];
  impacted_sectors: string[];
};

export type SectorStrength = {
  sector: string;
  strength: number;
  leaders: string[];
  laggards: string[];
};

export type AlertOut = {
  id: number;
  symbol: string;
  kind: string;
  severity: "info" | "warn" | "critical";
  title: string;
  message: string;
  price?: number;
  created_at: string;
};

export type WatchlistOut = {
  id: number;
  name: string;
  symbols: string[];
};

export type DashboardData = {
  indices: Quote[];
  gainers: Quote[];
  losers: Quote[];
  most_active: Quote[];
  sectors: SectorStrength[];
  breadth: { advancers: number; decliners: number; unchanged: number };
  fii_dii: {
    fii_proxy_cr: number;
    dii_proxy_cr: number;
    nifty_change_pct: number;
    news_sentiment: number;
    samples: number;
  };
  disclaimer: string;
};

export type BacktestResponse = {
  symbol: string;
  strategy: string;
  trades: number;
  win_rate: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  avg_rr: number;
  equity_curve: number[];
};

export type ChatResponse = {
  answer: string;
  used_symbols: string[];
  used_news_count: number;
  used_memories: number;
};

// ---------------------------------------------------------------------------
// Prediction-validation + learning + profitability engine
// ---------------------------------------------------------------------------

export type PredictionOut = {
  id: number;
  symbol: string;
  sector?: string;
  action: "BUY" | "SELL" | "HOLD";
  mode: "intraday" | "swing" | "positional";
  confidence: number;
  probability: number;
  score: number;
  entry_ref: number;
  entry_low?: number;
  entry_high?: number;
  stoploss?: number;
  target1?: number;
  target2?: number;
  rr?: number;
  atr_at_entry?: number;
  market_regime?: string;
  news_sentiment?: number;
  sector_strength?: number;
  detected_patterns: string[];
  reasoning: string;
  status:
    | "OPEN"
    | "TARGET1_HIT"
    | "TARGET2_HIT"
    | "STOPLOSS_HIT"
    | "EXPIRED"
    | "INVALIDATED";
  created_at: string;
  expires_at?: string;
};

export type OutcomeOut = {
  prediction_id: number;
  outcome:
    | "WIN"
    | "PARTIAL_WIN"
    | "LOSS"
    | "EXPIRED"
    | "INVALIDATED"
    | "OPEN";
  direction_correct?: boolean;
  entry_triggered: boolean;
  target1_hit: boolean;
  target2_hit: boolean;
  stoploss_hit: boolean;
  max_favorable_pct?: number;
  max_adverse_pct?: number;
  final_price?: number;
  realized_pct?: number;
  holding_bars?: number;
  holding_days?: number;
  bars_to_target1?: number;
  bars_to_stoploss?: number;
  notes?: string;
  validated_at: string;
};

export type SimulatedReturnOut = {
  prediction_id: number;
  symbol: string;
  action: "BUY" | "SELL" | "HOLD";
  capital_invested: number;
  quantity: number;
  entry_price: number;
  exit_price?: number;
  exit_reason?: string;
  realized_pnl: number;
  realized_pct: number;
  unrealized_pnl: number;
  max_gain_pnl: number;
  max_loss_pnl: number;
  holding_days?: number;
  closed_at?: string;
  updated_at: string;
};

export type PredictionFull = {
  prediction: PredictionOut;
  outcome?: OutcomeOut | null;
  simulated?: SimulatedReturnOut | null;
};

export type PerformanceSummary = {
  total_predictions: number;
  open_predictions: number;
  closed_predictions: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_return_pct: number;
  avg_holding_days: number;
  total_simulated_pnl: number;
  total_simulated_capital: number;
  cumulative_return_pct: number;
  best_sector?: string;
  worst_sector?: string;
  best_setup?: string;
  worst_setup?: string;
  best_regime?: string;
  avg_rr_achieved: number;
  confidence_calibration_gap: number;
  samples_since?: string;
};

export type EquityCurvePoint = {
  date: string;
  closed_trades: number;
  daily_pnl: number;
  cumulative_pnl: number;
  cumulative_pct: number;
};

export type AccuracyTrendPoint = {
  bucket: string;
  sample_size: number;
  win_rate: number;
  avg_return_pct: number;
};

export type ConfidenceBucket = {
  bucket_low: number;
  bucket_high: number;
  mode: string;
  sample_size: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_return_pct: number;
  calibration_gap: number;
};

export type SetupQuality = {
  setup_name: string;
  mode: string;
  sample_size: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_return_pct: number;
  quality_score: number;
  weight_multiplier: number;
};

export type SectorPerformance = {
  sector: string;
  mode?: string;
  trades?: number;
  sample_size?: number;
  wins: number;
  losses: number;
  win_rate: number;
  pnl?: number;
  return_pct?: number;
  avg_return_pct?: number;
};

export type RegimePerformance = {
  regime: string;
  trades: number;
  win_rate: number;
  pnl: number;
  return_pct: number;
};

export type IndicatorPerformanceRow = {
  indicator: string;
  regime: string;
  mode: string;
  sample_size: number;
  wins: number;
  losses: number;
  win_rate: number;
  edge_score: number;
  weight: number;
};

export type LearningFeedbackRow = {
  id: number;
  prediction_id: number;
  outcome: "WIN" | "LOSS";
  category: string;
  reason: string;
  market_condition?: string;
  sector_condition?: string;
  confidence_at_signal?: number;
  created_at: string;
};

export type FeedbackCategoryCount = {
  category: string;
  count: number;
  example: string;
};

export type LearningLog = {
  id: number;
  event: string;
  summary: string;
  details: Record<string, any>;
  impact_score?: number;
  created_at: string;
};

export type MarketRegimeSnapshot = {
  regime: string;
  nifty_trend?: string;
  breadth_score?: number;
  volatility_index?: number;
  nifty_return_20d?: number;
  advance_decline_ratio?: number;
  avg_news_sentiment?: number;
  description?: string;
  created_at?: string;
};

export type ValidationRunResult = {
  scanned: number;
  closed: number;
  still_open: number;
  new_wins: number;
  new_losses: number;
  learning_events: number;
  timestamp: string;
};

export type AIRollup = {
  as_of: string;
  summary: {
    total_predictions: number;
    open_predictions: number;
    closed_predictions: number;
    wins: number;
    losses: number;
    win_rate: number;
    total_simulated_pnl: number;
    total_simulated_capital: number;
    cumulative_return_pct: number;
  };
  regime: MarketRegimeSnapshot;
  last_equity_point?: EquityCurvePoint;
  calibration_gap: number;
  recent_learning: LearningLog[];
  disclaimer: string;
};

export type HeatmapCell = {
  row: string;
  col: string;
  value: number;
  sample_size: number;
};
