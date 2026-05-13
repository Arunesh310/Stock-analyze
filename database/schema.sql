-- BharatQuant — minimal SQL schema (auto-created by SQLAlchemy on startup).
-- Kept here as a reference if you want to migrate to Postgres or run manually.

CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(120) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol VARCHAR(40) NOT NULL,
    note VARCHAR(255),
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (watchlist_id, symbol)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(40) NOT NULL,
    kind VARCHAR(40) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    price REAL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stored_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(40) NOT NULL,
    action VARCHAR(10) NOT NULL,
    confidence REAL NOT NULL,
    entry_low REAL,
    entry_high REAL,
    stoploss REAL,
    target1 REAL,
    target2 REAL,
    rr REAL,
    mode VARCHAR(20) NOT NULL DEFAULT 'swing',
    reasoning TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Prediction Validation + Learning + Profitability Engine
-- ============================================================================

CREATE TABLE IF NOT EXISTS prediction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(40) NOT NULL,
    sector VARCHAR(60),
    action VARCHAR(10) NOT NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'swing',
    confidence REAL NOT NULL,
    probability REAL DEFAULT 0.5,
    score REAL DEFAULT 0,
    entry_ref REAL NOT NULL,
    entry_low REAL,
    entry_high REAL,
    stoploss REAL,
    target1 REAL,
    target2 REAL,
    rr REAL,
    atr_at_entry REAL,
    reasoning TEXT DEFAULT '',
    detected_patterns JSON,
    indicators_snapshot JSON,
    market_regime VARCHAR(40),
    regime_snapshot JSON,
    news_sentiment REAL,
    sector_strength REAL,
    breadth_advancers INTEGER,
    breadth_decliners INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_pred_symbol_created ON prediction_history(symbol, created_at);
CREATE INDEX IF NOT EXISTS ix_pred_status ON prediction_history(status);

CREATE TABLE IF NOT EXISTS prediction_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL UNIQUE REFERENCES prediction_history(id) ON DELETE CASCADE,
    outcome VARCHAR(30) NOT NULL,
    direction_correct BOOLEAN,
    entry_triggered BOOLEAN DEFAULT 0,
    target1_hit BOOLEAN DEFAULT 0,
    target2_hit BOOLEAN DEFAULT 0,
    stoploss_hit BOOLEAN DEFAULT 0,
    max_favorable_pct REAL,
    max_adverse_pct REAL,
    final_price REAL,
    realized_pct REAL,
    holding_bars INTEGER,
    holding_days REAL,
    bars_to_target1 INTEGER,
    bars_to_stoploss INTEGER,
    notes TEXT,
    validated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulated_returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL UNIQUE REFERENCES prediction_history(id) ON DELETE CASCADE,
    capital_invested REAL DEFAULT 10000.0,
    quantity REAL DEFAULT 0,
    entry_price REAL DEFAULT 0,
    exit_price REAL,
    exit_reason VARCHAR(40),
    realized_pnl REAL DEFAULT 0,
    realized_pct REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    max_gain_pnl REAL DEFAULT 0,
    max_loss_pnl REAL DEFAULT 0,
    holding_days REAL,
    closed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS confidence_accuracy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bucket_low INTEGER NOT NULL,
    bucket_high INTEGER NOT NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'swing',
    sample_size INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0,
    avg_return_pct REAL DEFAULT 0,
    calibration_gap REAL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (bucket_low, bucket_high, mode)
);

CREATE TABLE IF NOT EXISTS learning_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL REFERENCES prediction_history(id) ON DELETE CASCADE,
    outcome VARCHAR(20) NOT NULL,
    category VARCHAR(40) NOT NULL,
    reason TEXT NOT NULL,
    market_condition VARCHAR(40),
    indicator_state JSON,
    sector_condition VARCHAR(60),
    confidence_at_signal REAL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_feedback_category ON learning_feedback(category, outcome);

CREATE TABLE IF NOT EXISTS market_regimes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regime VARCHAR(40) NOT NULL,
    nifty_trend VARCHAR(20),
    breadth_score REAL,
    volatility_index REAL,
    nifty_return_20d REAL,
    advance_decline_ratio REAL,
    avg_news_sentiment REAL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signal_quality_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setup_name VARCHAR(80) NOT NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'swing',
    sample_size INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0,
    avg_return_pct REAL DEFAULT 0,
    quality_score REAL DEFAULT 50,
    weight_multiplier REAL DEFAULT 1.0,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (setup_name, mode)
);

CREATE TABLE IF NOT EXISTS sector_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sector VARCHAR(60) NOT NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'swing',
    sample_size INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0,
    avg_return_pct REAL DEFAULT 0,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sector, mode)
);

CREATE TABLE IF NOT EXISTS indicator_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator VARCHAR(60) NOT NULL,
    regime VARCHAR(40) NOT NULL DEFAULT 'any',
    mode VARCHAR(20) NOT NULL DEFAULT 'swing',
    sample_size INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0,
    edge_score REAL DEFAULT 0,
    weight REAL DEFAULT 1.0,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (indicator, regime, mode)
);

CREATE TABLE IF NOT EXISTS ai_learning_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event VARCHAR(60) NOT NULL,
    summary TEXT NOT NULL,
    details JSON,
    impact_score REAL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
