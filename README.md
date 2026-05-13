# 🇮🇳 BharatQuant — AI-Powered Indian Stock Market Analysis Platform

> An end-to-end, **100% free / local** AI trading research platform for the Indian markets (NSE / BSE).
> FastAPI + Next.js + Ollama + ChromaDB + yfinance.
>
> **Disclaimer:** This tool is for **educational and research purposes only** and is **NOT financial advice**.

---

## ✨ What it does

- 📊 **Live market dashboard** — Nifty, Bank Nifty, India VIX, USDINR, Crude, Gold, Top Gainers/Losers, Sector strength, FII/DII sentiment.
- 🤖 **AI Stock Analysis Engine** — Trend, support/resistance, RSI, MACD, VWAP, EMA, breakouts, candle patterns, momentum + **BUY/SELL/HOLD** signals with entry, stoploss, T1/T2, R:R and confidence%.
- 📰 **News + Event Engine** — Pulls Indian + global news, scores sentiment, maps consequences to Indian sectors/stocks.
- 🔗 **Relationship Engine** — Stock correlations, sector rotation, sympathy moves, market leader detection.
- 🚨 **Real-time Alerts** — Breakouts, volume spikes, RSI reversals, MACD crossovers, support bounces.
- 💬 **AI Chat Assistant** — Natural-language Q&A grounded in your local market data using Ollama.
- 🧪 **Backtesting Engine** — MA crossover, RSI reversal, breakouts, volume breakouts, sector momentum.
- 🧠 **AI Memory** — ChromaDB-backed memory of historical events (COVID crash, Adani, RBI hikes, budgets, elections) for analogue lookup.
- ⭐ **Smart Watchlists**, ⚖️ **Risk Manager** (auto position sizing), and **Intraday / Swing / Positional** modes.
- 🧠 **Prediction Validation + Learning + Profitability Engine** — every signal is persisted, its outcome objectively replayed against real OHLC, ₹10,000 of simulated capital is tracked, failure reasons are catalogued, and the engine **continuously adapts indicator / setup / sector weights** based on what has actually worked.
- 🛡️ **Validated Market-Data Architecture** — multi-source (yfinance primary + NSE public endpoints secondary + validated cache fallback), OHLC integrity checks, impossible-jump / stale-data detection, per-symbol **data-quality score** that *downgrades AI confidence* when feeds are shaky.
- 🔍 **Professional Search UX** — instant autocomplete with **fuzzy + alias + typo** matching (`relinace` → `RELIANCE.NS`, `hdfc bank` → `HDFCBANK.NS`), live price + change% in the dropdown, keyboard navigation, recent searches and trending stocks. Backed by a **~2 400-symbol** stock-master catalogue (curated metadata + bundled extension + live NSE `EQUITY_L.csv` snapshot) with sector / industry / market-cap data and explicit **"not listed" detection** for private / unlisted companies (e.g. `byju`, `oyo`, `shiprocket`).
- 🚀 **Parallel data pipeline** — quotes, signals, sector-strength and market-breadth all fetch concurrently via a thread pool. A symbol-level **negative cache** prevents endless retries against delisted tickers, and aggregate calls (`sector_strength`, `market_breadth`) are TTL-cached for 60 s so the dashboard renders in **<100 ms when warm**.
- 📈 **Portfolio risk metrics** — `/api/simulated-returns/portfolio-metrics` exposes **CAGR, Sharpe, max drawdown, profit factor, expectancy, avg win / loss %, best / worst trade** computed from the realised PnL stream.
- 🛑 **NO-TRADE filter** — the signal engine confidently flips to `HOLD` whenever data quality < 50, volatility > 80, RR < 1.0, RSI severely overbought/oversold, ADX < 15, or the data source is synthetic. The AI is rewarded for capital preservation, not signal frequency.
- 🕐 **Indian Session Engine** — IST-native market status (pre-open / regular / after-hours / closed) with NSE holiday calendar, propagated to the websocket cadence so refresh rate auto-tunes between 30 s (open) and 5 min (closed).

---

## 🔁 The self-evaluating loop

Every refresh cycle the platform:

1. Generates new signals (deterministic + LLM-flavoured reasoning).
2. Persists each signal as a `prediction_history` row with a full snapshot of indicators, regime, breadth and news sentiment.
3. Validates previously-open predictions against actual market data:
   - did the entry trigger?
   - which target / stoploss hit first?
   - what was max favourable / adverse excursion?
4. Updates a `SimulatedReturn` row (assume ₹10,000 per signal) — realised, unrealised and peak P&L.
5. Catalogues *why* each closed trade succeeded or failed (false breakout, weak breadth, regime mismatch, volatility spike, …).
6. Re-aggregates **setup / sector / indicator / regime** performance and adjusts the `weight_multiplier` used by future signal scores.
7. Recalibrates confidence buckets so that 80%-confidence signals statistically perform better than 50%-confidence signals — or it knows it isn't yet.

Schedules (configurable via APScheduler in `app/scheduler.py`):

| Job                          | Interval |
|------------------------------|----------|
| Stock price refresh          | 1 min   |
| Indicator-weights cache reset| 5 min   |
| Signal validation + learning | 15 min  |
| Regime snapshot              | 30 min  |
| Stale prediction expiry      | 1 hr    |
| News refresh                 | 2 hr    |
| Confidence recalibration     | 6 hr    |

> ⚠️ Predictions are probabilistic, not guarantees. The system explicitly never claims certainty and is meant to *survive first and improve gradually* on Indian-market data.

---

## 🏗 Architecture

```
┌────────────────────┐        REST + WebSocket        ┌──────────────────────┐
│  Next.js Frontend  │  ───────────────────────────▶ │  FastAPI Backend     │
│  (TS + shadcn +    │                                │  (services + routers)│
│  Recharts + TVLC)  │ ◀───────────────────────────  │                      │
└────────────────────┘                                └──────────┬───────────┘
                                                                 │
                          ┌──────────────┬───────────────────────┼─────────────────────┐
                          ▼              ▼                       ▼                     ▼
                   yfinance / NSE   Ollama (LLM +           ChromaDB              SQLite/Postgres
                   public endpoints  embeddings)        (event memory)       (watchlists, alerts)
```

```
Stock analyze/
├── backend/        # FastAPI app (services, routers, WS)
├── frontend/       # Next.js app (dashboard, charts, chat)
├── database/       # SQL schema / migrations
├── models/         # Saved ML / scaler files
├── scripts/        # bootstrap, seed, ollama setup
├── data/           # dummy data, news cache, csvs
├── logs/
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick start

### 0) Prerequisites
- Python **3.11+**
- Node.js **20+** and npm/pnpm
- [Ollama](https://ollama.com/download) installed locally

### 1) Pull the local LLM (free, offline)

```bash
ollama pull llama3
ollama pull nomic-embed-text
ollama serve   # starts the API on http://localhost:11434
```

> You can swap `llama3` for `mistral`, `phi3`, `qwen2.5`, etc. — set `OLLAMA_MODEL` in `.env`.

### 2) Backend

```bash
cd backend
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Optional: seed the historical event memory (ChromaDB)
python -m app.scripts.seed_memory

# Optional: seed the trading-knowledge base (trend/momentum/Wyckoff/SMC/...).
python -m app.scripts.seed_knowledge

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### 3) Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

UI: http://localhost:3000

### 4) (Optional) Docker

```bash
docker compose up --build
```

---

## 🔌 Backend API

| Method | Path                                       | Description                                           |
|-------:|--------------------------------------------|-------------------------------------------------------|
| GET    | `/api/stocks/search?q=&with_prices=`       | Fuzzy / alias autocomplete with optional price enrichment |
| GET    | `/api/stocks/resolve?q=`                   | Normalise free-text input to a canonical symbol         |
| GET    | `/api/stocks/trending?limit=`              | Largest movers from the curated universe                |
| GET    | `/api/stocks/universe`                     | Curated NSE catalogue with sector / industry / market-cap |
| GET    | `/api/stocks/sectors`                      | All sectors                                             |
| GET    | `/api/stocks/{symbol}`                     | Validated live quote                                    |
| GET    | `/api/stocks/{symbol}/quote-quality`       | Quote + data-quality summary                            |
| GET    | `/api/stocks/{symbol}/quality`             | Just the data-quality summary                           |
| GET    | `/api/stocks/{symbol}/ohlc`                | Validated OHLC history                                  |
| GET    | `/api/market-status`                       | Indian market session state in IST                      |
| GET    | `/api/analyze/{symbol}`                    | Full AI analysis: indicators + LLM reasoning + signal  |
| GET    | `/api/signals`                             | Active BUY/SELL/HOLD signals across watchlist          |
| GET    | `/api/news`                                | Aggregated news + sentiment + impacted sectors        |
| GET    | `/api/sectors`                             | Sector strength + rotation                             |
| GET    | `/api/correlations/{symbol}`               | Pearson correlations vs index/peers                  |
| GET/POST| `/api/watchlist`                          | Manage watchlists                                      |
| POST   | `/api/backtest`                            | Run a strategy backtest                                |
| POST   | `/api/chat`                                | Ask the AI assistant                                   |
| GET    | `/api/alerts`                              | Recent alerts                                          |
| WS     | `/ws/live`                                 | Real-time tick & alert stream                          |
| GET    | `/api/prediction-performance/summary`      | Overall AI performance summary                         |
| GET    | `/api/prediction-performance/recent`       | Recent predictions with outcomes + simulated P&L       |
| GET    | `/api/prediction-performance/accuracy-trend`| Win-rate / avg-return over time                       |
| GET    | `/api/prediction-performance/setups`       | Setup quality scores                                   |
| GET    | `/api/prediction-performance/sectors`      | Sector-level performance breakdown                     |
| GET    | `/api/prediction-performance/regimes`      | Regime-level performance breakdown                     |
| GET    | `/api/prediction-performance/heatmap-sector-regime` | 2D win-rate heatmap                          |
| POST   | `/api/validate-signals`                    | Manually trigger validation cycle                      |
| GET    | `/api/simulated-returns/equity-curve`      | Cumulative simulated P&L curve                         |
| GET    | `/api/simulated-returns/by-sector`         | Simulated P&L by sector                                |
| GET    | `/api/simulated-returns/by-regime`         | Simulated P&L by regime                                |
| GET    | `/api/learning-feedback/recent`            | Recent win/loss reasons                                |
| GET    | `/api/learning-feedback/top-failure-reasons`| Top categories of losses                              |
| GET    | `/api/learning-feedback/indicators`        | Per-indicator/regime edge scores                       |
| GET    | `/api/learning-feedback/logs`              | AI learning event log                                  |
| GET    | `/api/confidence-analysis/buckets`         | Confidence calibration buckets                         |
| POST   | `/api/confidence-analysis/recalibrate`     | Rebuild confidence buckets                             |
| GET    | `/api/market-regime`                       | Current market regime                                  |
| GET    | `/api/market-regime/recent`                | Historical regime snapshots                            |
| GET    | `/api/ai-performance`                      | Single-call rollup for the home widget                 |

---

## 🧰 Tech stack

**Frontend:** Next.js 14 · TypeScript · TailwindCSS · shadcn/ui · Recharts · TradingView Lightweight Charts
**Backend:** FastAPI · pandas · numpy · scikit-learn · `ta` + `pandas-ta` · yfinance · feedparser · httpx
**AI:** Ollama (`llama3` / `mistral`) + `nomic-embed-text` embeddings
**DB:** SQLite (default) or PostgreSQL · ChromaDB (vector)
**Realtime:** WebSockets

---

## 📊 Dashboards (frontend)

In addition to the existing pages the upgrade ships 5 new dashboards under
the **AI Brain** section in the sidebar:

| Page | What it shows |
|------|---------------|
| **AI Accuracy** (`/performance`) | KPI strip, accuracy trend, sector & setup quality, sector × regime heatmap, recent predictions table |
| **Simulated Profit** (`/profit`) | Cumulative simulated P&L, per-sector P&L bars, per-regime P&L |
| **Learning Feedback** (`/learning`) | Failure & success reason categories, indicator edge per regime, setup quality scores, learning log |
| **Market Regime** (`/regime`) | Current regime snapshot (Nifty trend, breadth, VIX, sentiment), regime history chart, per-regime performance |
| **Confidence Reliability** (`/confidence`) | Confidence-bucket calibration (expected vs realised win-rate) and recalibration controls |

---

## 🗄 Database tables

Auto-created by SQLAlchemy on startup; SQL reference in `database/schema.sql`:

- `prediction_history` · `prediction_outcomes` · `simulated_returns`
- `confidence_accuracy` · `learning_feedback` · `market_regimes`
- `signal_quality_scores` · `sector_performance` · `indicator_performance`
- `ai_learning_logs`

---

## ⚠️ Disclaimer

> This software is provided **for educational and research purposes only**.
> Nothing here is investment, financial, legal, tax or trading advice.
> Markets are risky. The AI engine is probabilistic — it does NOT guarantee
> profits, does NOT claim certainty, and does NOT pretend to know future
> prices. It simply tracks how well its own past predictions actually
> performed against real data and adapts gradually. Do your own research
> and consult a SEBI-registered advisor.
