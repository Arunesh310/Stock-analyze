import type {
  AnalysisResponse,
  AlertOut,
  AccuracyTrendPoint,
  AIRollup,
  BacktestResponse,
  ChatResponse,
  ConfidenceBucket,
  DashboardData,
  DataQuality,
  EquityCurvePoint,
  FeedbackCategoryCount,
  HeatmapCell,
  ImprovementScore,
  IndicatorPerformanceRow,
  LearningChange,
  LearningFeedbackRow,
  LearningLog,
  MarketRegimeSnapshot,
  MarketStatus,
  NewsItem,
  OhlcRow,
  PerformanceSummary,
  PortfolioMetrics,
  PlannerRequest,
  PlannerResponse,
  PredictionFull,
  Quote,
  QuoteWithQuality,
  RegimePerformance,
  RegimeStrategyCell,
  ResolveResult,
  RollingWindows,
  SearchHit,
  SectorPerformance,
  SectorStrength,
  SetupQuality,
  Signal,
  SignalConversion,
  SignalOutcomeRow,
  StrategyPerformance,
  SyncStatus,
  ValidationRunResult,
  WatchlistOut,
} from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export const apiBase = API_URL;
// Empty string disables WS entirely (production / serverless backends).
export const wsUrl =
  process.env.NEXT_PUBLIC_WS_URL ??
  (typeof window !== "undefined" && window.location.protocol === "https:"
    ? ""
    : "ws://localhost:8000/ws/live");

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${res.statusText}: ${text || path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Stocks
  search: (q: string, opts: { limit?: number; with_prices?: boolean } = {}) => {
    const usp = new URLSearchParams({ q });
    if (opts.limit) usp.set("limit", String(opts.limit));
    if (opts.with_prices) usp.set("with_prices", "true");
    return http<SearchHit[]>(`/api/stocks/search?${usp.toString()}`);
  },
  resolve: (q: string) =>
    http<ResolveResult>(`/api/stocks/resolve?q=${encodeURIComponent(q)}`),
  trending: (limit = 12) =>
    http<SearchHit[]>(`/api/stocks/trending?limit=${limit}`),
  universe: () =>
    http<{
      symbol: string;
      name: string;
      sector: string;
      industry?: string;
      market_cap?: string;
      exchange?: string;
    }[]>(`/api/stocks/universe`),
  quote: (symbol: string) => http<Quote>(`/api/stocks/${encodeURIComponent(symbol)}`),
  quoteWithQuality: (symbol: string) =>
    http<QuoteWithQuality>(`/api/stocks/${encodeURIComponent(symbol)}/quote-quality`),
  quality: (symbol: string) =>
    http<DataQuality>(`/api/stocks/${encodeURIComponent(symbol)}/quality`),
  batchQuotes: (symbols: string[]) =>
    http<Quote[]>(`/api/stocks/quotes/batch?symbols=${symbols.join(",")}`),
  ohlc: (symbol: string, period = "1y", interval = "1d") =>
    http<OhlcRow[]>(
      `/api/stocks/${encodeURIComponent(symbol)}/ohlc?period=${period}&interval=${interval}`
    ),
  marketStatus: () => http<MarketStatus>(`/api/market-status`),

  // Analyze
  analyze: (symbol: string, mode: "intraday" | "swing" | "positional" = "swing") =>
    http<AnalysisResponse>(
      `/api/analyze/${encodeURIComponent(symbol)}?mode=${mode}`
    ),

  // Signals
  signals: (
    params: {
      mode?: string;
      min_conf?: number;
      min_grade?: "AVOID" | "WEAK" | "MODERATE" | "STRONG" | "HIGH_CONVICTION";
      limit?: number;
      sector?: string;
    } = {}
  ) => {
    const usp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && usp.set(k, String(v)));
    return http<Signal[]>(`/api/signals?${usp.toString()}`);
  },
  topPicks: (mode = "swing", limit = 10) =>
    http<Signal[]>(`/api/signals/top-picks?mode=${mode}&limit=${limit}`),
  opportunities: (mode = "swing", limit = 12) =>
    http<Signal[]>(`/api/signals/opportunities?mode=${mode}&limit=${limit}`),

  // News
  news: (limit = 50, sector?: string, symbol?: string) => {
    const usp = new URLSearchParams({ limit: String(limit) });
    if (sector) usp.set("sector", sector);
    if (symbol) usp.set("symbol", symbol);
    return http<NewsItem[]>(`/api/news?${usp.toString()}`);
  },
  sentiment: () => http<any>(`/api/news/sentiment`),
  fiiDii: () => http<any>(`/api/news/fii-dii`),

  // Sectors / correlations
  sectors: () => http<string[]>(`/api/sectors`),
  sectorStrength: (period = "1mo") =>
    http<SectorStrength[]>(`/api/sectors/strength?period=${period}`),
  breadth: () => http<{ advancers: number; decliners: number; unchanged: number }>(`/api/sectors/breadth`),
  correlations: (symbol: string, limit = 10) =>
    http<{ symbol: string; against: string; pearson: number; sample: number }[]>(
      `/api/correlations/${encodeURIComponent(symbol)}?limit=${limit}`
    ),
  sympathy: (symbol: string, limit = 5) =>
    http<{ symbol: string; against: string; pearson: number; sample: number }[]>(
      `/api/correlations/${encodeURIComponent(symbol)}/sympathy?limit=${limit}`
    ),

  // Watchlist
  watchlists: () => http<WatchlistOut[]>(`/api/watchlist`),
  createWatchlist: (name: string) =>
    http<WatchlistOut>(`/api/watchlist`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  addSymbol: (id: number, symbol: string, note?: string) =>
    http<WatchlistOut>(`/api/watchlist/${id}/symbols`, {
      method: "POST",
      body: JSON.stringify({ symbol, note }),
    }),
  removeSymbol: (id: number, symbol: string) =>
    http<WatchlistOut>(`/api/watchlist/${id}/symbols/${encodeURIComponent(symbol)}`, {
      method: "DELETE",
    }),
  deleteWatchlist: (id: number) =>
    fetch(`${API_URL}/api/watchlist/${id}`, { method: "DELETE" }),

  // Backtest
  backtest: (req: {
    symbol: string;
    strategy: string;
    period?: string;
    interval?: string;
    fast?: number;
    slow?: number;
    rsi_low?: number;
    rsi_high?: number;
  }) =>
    http<BacktestResponse>(`/api/backtest`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  // Alerts
  alerts: (limit = 100) => http<AlertOut[]>(`/api/alerts?limit=${limit}`),
  scanAlerts: (symbols?: string) =>
    http<{ created: number }>(`/api/alerts/scan${symbols ? `?symbols=${symbols}` : ""}`, {
      method: "POST",
    }),

  // Chat
  chat: (question: string, symbols: string[] = [], context_news = true) =>
    http<ChatResponse>(`/api/chat`, {
      method: "POST",
      body: JSON.stringify({ question, symbols, context_news }),
    }),

  // Dashboard
  dashboard: () => http<DashboardData>(`/api/dashboard`),

  // Risk
  risk: (req: {
    capital: number;
    entry: number;
    stoploss: number;
    target?: number;
    risk_per_trade_pct?: number;
    max_portfolio_heat_pct?: number;
  }) =>
    http<any>(`/api/risk/calculate`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  // ---- Prediction-validation + learning + profitability engine ----
  performance: {
    summary: (params: { mode?: string; since_days?: number } = {}) => {
      const usp = new URLSearchParams();
      Object.entries(params).forEach(
        ([k, v]) => v !== undefined && usp.set(k, String(v))
      );
      return http<PerformanceSummary>(
        `/api/prediction-performance/summary?${usp.toString()}`
      );
    },
    recent: (params: { limit?: number; status?: string; symbol?: string; mode?: string } = {}) => {
      const usp = new URLSearchParams();
      Object.entries(params).forEach(
        ([k, v]) => v !== undefined && usp.set(k, String(v))
      );
      return http<PredictionFull[]>(
        `/api/prediction-performance/recent?${usp.toString()}`
      );
    },
    accuracyTrend: (
      bucket: "day" | "week" | "month" = "month",
      mode?: string
    ) => {
      const usp = new URLSearchParams({ bucket });
      if (mode) usp.set("mode", mode);
      return http<AccuracyTrendPoint[]>(
        `/api/prediction-performance/accuracy-trend?${usp.toString()}`
      );
    },
    setups: (mode?: string) =>
      http<SetupQuality[]>(
        `/api/prediction-performance/setups${mode ? `?mode=${mode}` : ""}`
      ),
    sectorBreakdown: (mode?: string) =>
      http<SectorPerformance[]>(
        `/api/prediction-performance/sectors${mode ? `?mode=${mode}` : ""}`
      ),
    regimeBreakdown: (mode?: string) =>
      http<RegimePerformance[]>(
        `/api/prediction-performance/regimes${mode ? `?mode=${mode}` : ""}`
      ),
    heatmapSectorRegime: () =>
      http<HeatmapCell[]>(`/api/prediction-performance/heatmap-sector-regime`),
  },

  validate: {
    run: (limit = 200) =>
      http<ValidationRunResult>(`/api/validate-signals?limit=${limit}`, {
        method: "POST",
      }),
    expire: () =>
      http<{ expired: number }>(`/api/validate-signals/expire`, {
        method: "POST",
      }),
  },

  simulated: {
    equityCurve: (since_days = 365, mode?: string) => {
      const usp = new URLSearchParams({ since_days: String(since_days) });
      if (mode) usp.set("mode", mode);
      return http<EquityCurvePoint[]>(
        `/api/simulated-returns/equity-curve?${usp.toString()}`
      );
    },
    bySector: (mode?: string) =>
      http<SectorPerformance[]>(
        `/api/simulated-returns/by-sector${mode ? `?mode=${mode}` : ""}`
      ),
    byRegime: (mode?: string) =>
      http<RegimePerformance[]>(
        `/api/simulated-returns/by-regime${mode ? `?mode=${mode}` : ""}`
      ),
    summary: (params: { mode?: string; since_days?: number } = {}) => {
      const usp = new URLSearchParams();
      Object.entries(params).forEach(
        ([k, v]) => v !== undefined && usp.set(k, String(v))
      );
      return http<any>(`/api/simulated-returns/summary?${usp.toString()}`);
    },
    portfolioMetrics: (params: { mode?: string; since_days?: number } = {}) => {
      const usp = new URLSearchParams();
      Object.entries(params).forEach(
        ([k, v]) => v !== undefined && usp.set(k, String(v))
      );
      return http<PortfolioMetrics>(
        `/api/simulated-returns/portfolio-metrics?${usp.toString()}`
      );
    },
  },

  learning: {
    recent: (limit = 100, outcome?: "WIN" | "LOSS") =>
      http<LearningFeedbackRow[]>(
        `/api/learning-feedback/recent?limit=${limit}${outcome ? `&outcome=${outcome}` : ""}`
      ),
    topFailures: (limit = 20) =>
      http<FeedbackCategoryCount[]>(
        `/api/learning-feedback/top-failure-reasons?limit=${limit}`
      ),
    topSuccesses: (limit = 20) =>
      http<FeedbackCategoryCount[]>(
        `/api/learning-feedback/top-success-reasons?limit=${limit}`
      ),
    setups: (mode?: string) =>
      http<SetupQuality[]>(
        `/api/learning-feedback/setups${mode ? `?mode=${mode}` : ""}`
      ),
    sectors: (mode?: string) =>
      http<SectorPerformance[]>(
        `/api/learning-feedback/sectors${mode ? `?mode=${mode}` : ""}`
      ),
    indicators: (mode?: string, regime?: string) => {
      const usp = new URLSearchParams();
      if (mode) usp.set("mode", mode);
      if (regime) usp.set("regime", regime);
      return http<IndicatorPerformanceRow[]>(
        `/api/learning-feedback/indicators?${usp.toString()}`
      );
    },
    logs: (limit = 100) =>
      http<LearningLog[]>(`/api/learning-feedback/logs?limit=${limit}`),
    runCycle: () =>
      http<any>(`/api/learning-feedback/run-cycle`, { method: "POST" }),
  },

  confidence: {
    buckets: () => http<ConfidenceBucket[]>(`/api/confidence-analysis/buckets`),
    recalibrate: () =>
      http<ConfidenceBucket[]>(`/api/confidence-analysis/recalibrate`, {
        method: "POST",
      }),
  },

  regime: {
    current: () => http<MarketRegimeSnapshot>(`/api/market-regime`),
    recent: (limit = 60) =>
      http<MarketRegimeSnapshot[]>(`/api/market-regime/recent?limit=${limit}`),
    refresh: () =>
      http<MarketRegimeSnapshot>(`/api/market-regime/refresh`, {
        method: "POST",
      }),
  },

  aiPerformance: () => http<AIRollup>(`/api/ai-performance`),

  syncStatus: () => http<SyncStatus>(`/api/sync-status`),

  planner: (req: PlannerRequest) =>
    http<PlannerResponse>(`/api/capital-planner`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  evolution: {
    rolling: (mode?: string) =>
      http<RollingWindows>(`/api/ai-evolution/rolling${mode ? `?mode=${mode}` : ""}`),
    signalConversion: (mode?: string) =>
      http<SignalConversion>(
        `/api/ai-evolution/signal-conversion${mode ? `?mode=${mode}` : ""}`
      ),
    improvementScore: (mode?: string) =>
      http<ImprovementScore>(
        `/api/ai-evolution/improvement-score${mode ? `?mode=${mode}` : ""}`
      ),
    recentChanges: (limit = 30) =>
      http<LearningChange[]>(`/api/ai-evolution/recent-changes?limit=${limit}`),
    strategyPerformance: (mode?: string) =>
      http<StrategyPerformance[]>(
        `/api/ai-evolution/strategy-performance${mode ? `?mode=${mode}` : ""}`
      ),
    regimeStrategyMatrix: (mode?: string) =>
      http<RegimeStrategyCell[]>(
        `/api/ai-evolution/regime-strategy-matrix${mode ? `?mode=${mode}` : ""}`
      ),
    recentOutcomes: (limit = 50) =>
      http<SignalOutcomeRow[]>(`/api/ai-evolution/recent-outcomes?limit=${limit}`),
  },
};
