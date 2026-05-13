"""Seed the local trading-knowledge base used by the AI engine.

Run::

    python -m app.scripts.seed_knowledge

Re-runnable: documents are upserted by ``id`` so repeated runs are idempotent.
Everything below is *educational reference material* — NOT financial advice.
"""
from __future__ import annotations

from loguru import logger

from ..logger import setup_logging
from ..services.knowledge_base import get_knowledge_base


CONCEPTS: list[dict] = [
    # --- Trend following ---
    {
        "id": "tf_basics",
        "text": (
            "Trend following: buy strength, sell weakness. The classical rule "
            "set is 'higher highs + higher lows = uptrend' and the inverse "
            "for downtrends. Position sizing is the edge; trying to predict "
            "tops/bottoms is not. Wait for confirmation (e.g. price above "
            "20EMA stacked above 50EMA above 200EMA) before initiating, and "
            "trail stops behind structure (swing lows / 20EMA / Chandelier "
            "exit) instead of fixed targets."
        ),
        "meta": {"category": "trend_following"},
    },
    {
        "id": "tf_indian_market",
        "text": (
            "Indian market trend tells: Nifty50 above its 200-day SMA defines "
            "the strategic regime. India VIX below 14 typically marks low-fear "
            "trending environments; above 18 suggests range/whippy conditions. "
            "Pair Nifty trend with sector rotation (e.g. defence/PSU/railways "
            "leadership in 2023-24) for higher-probability long setups."
        ),
        "meta": {"category": "trend_following", "market": "india"},
    },
    # --- Momentum ---
    {
        "id": "momentum_core",
        "text": (
            "Momentum: assets that performed well in the recent past tend to "
            "continue outperforming over the next 1-12 months. Practical "
            "filters: 12-month return minus 1-month (to skip short-term mean "
            "reversion), relative strength vs benchmark, breakouts from "
            "consolidations on rising volume. Beware of momentum crashes "
            "during fast bear-rallies."
        ),
        "meta": {"category": "momentum"},
    },
    {
        "id": "momentum_rsi",
        "text": (
            "RSI in trends is a momentum gauge, not just a reversal trigger. "
            "In strong uptrends RSI can stay above 70 for weeks; treating it "
            "as 'overbought' costs winners. Better use: RSI > 60 in uptrend "
            "= persistence; RSI < 40 in downtrend = persistence. RSI "
            "divergence with price is a slow, low-precision warning, never a "
            "stand-alone entry."
        ),
        "meta": {"category": "momentum"},
    },
    # --- Mean reversion ---
    {
        "id": "mean_reversion",
        "text": (
            "Mean reversion: prices oscillate around a moving average. Works "
            "best in range-bound, low-trend regimes (Nifty between 20EMA and "
            "50EMA with flat slope). Typical edges: Bollinger Band fades, "
            "deviations of 2+ ATR from a 20-day mean, opening-range gap "
            "fills. Always combine with a stop just beyond the deviation "
            "extreme — mean-reversion losers are 'fat-tailed'."
        ),
        "meta": {"category": "mean_reversion"},
    },
    # --- Wyckoff ---
    {
        "id": "wyckoff_overview",
        "text": (
            "Wyckoff method: markets move in 4 phases — Accumulation, "
            "Markup, Distribution, Markdown — driven by the 'Composite "
            "Operator' (i.e. institutions). Key Wyckoff events in "
            "accumulation: Preliminary Support (PS), Selling Climax (SC), "
            "Automatic Rally (AR), Secondary Test (ST), Spring/Shakeout, "
            "Sign of Strength (SOS), Last Point of Support (LPS) — entries "
            "are after a successful Spring + SOS, NOT at the SC."
        ),
        "meta": {"category": "wyckoff"},
    },
    {
        "id": "wyckoff_distribution",
        "text": (
            "Wyckoff distribution phase signals: Buying Climax (BC), "
            "Automatic Reaction (AR), Secondary Test (ST), Upthrust (UT), "
            "Upthrust After Distribution (UTAD), Sign of Weakness (SOW), "
            "Last Point of Supply (LPSY). Shorting is taken on LPSY after "
            "SOW confirms the breakdown, NOT at the BC."
        ),
        "meta": {"category": "wyckoff"},
    },
    # --- Dow Theory ---
    {
        "id": "dow_theory",
        "text": (
            "Dow Theory tenets: (1) market discounts everything, (2) market "
            "has three trends — primary, secondary, minor, (3) primary trends "
            "have three phases — accumulation, public participation, "
            "distribution, (4) indices must confirm each other, (5) volume "
            "must confirm price, (6) trends persist until clear reversal. "
            "Indian analogue: Nifty50 + Bank Nifty + broader Nifty500 should "
            "agree on the primary direction for highest conviction."
        ),
        "meta": {"category": "dow_theory"},
    },
    # --- Volume Spread Analysis ---
    {
        "id": "vsa_core",
        "text": (
            "Volume Spread Analysis (VSA): combines candle spread (range), "
            "close position within range, and volume to infer effort-vs-"
            "result. Bullish VSA: high volume narrow-range down bar closing "
            "near the high = 'stopping volume', professional buying. Bearish "
            "VSA: high volume wide-range up bar closing near low = 'no demand "
            "on rally / selling into strength'. Always interpret in context "
            "of the prior trend and structure."
        ),
        "meta": {"category": "vsa"},
    },
    {
        "id": "vsa_no_demand_no_supply",
        "text": (
            "VSA 'no demand': up bar on narrow range and low volume — "
            "professionals not participating, rally likely fails. 'No supply': "
            "down bar on narrow range and low volume in an uptrend pullback — "
            "sellers exhausted, ideal long re-entry."
        ),
        "meta": {"category": "vsa"},
    },
    # --- Smart Money Concepts ---
    {
        "id": "smc_overview",
        "text": (
            "Smart Money Concepts (SMC): a modern price-action framework. "
            "Core ideas: market structure (BOS/CHOCH), liquidity pools above "
            "highs and below lows, order blocks (last opposite candle before "
            "an impulsive move), fair value gaps / imbalances. Bullish entry "
            "model: liquidity sweep below a recent low -> displacement up -> "
            "retracement into an order block / FVG -> entry with stop below "
            "the sweep low."
        ),
        "meta": {"category": "smc"},
    },
    {
        "id": "smc_choch_bos",
        "text": (
            "Change of Character (CHOCH) and Break of Structure (BOS): "
            "CHOCH = first break of an internal structure level signalling a "
            "potential trend change. BOS = continuation break in the "
            "direction of the new trend. Cleanest setups stack CHOCH on a "
            "higher timeframe with BOS on a lower timeframe inside the "
            "premium/discount equilibrium."
        ),
        "meta": {"category": "smc"},
    },
    # --- Market structure ---
    {
        "id": "market_structure",
        "text": (
            "Market structure: succession of swing highs and lows. Uptrend = "
            "HH/HL, downtrend = LH/LL, range = horizontal HH+LH. Trend changes "
            "are confirmed by (a) a swing-level break in the opposite "
            "direction + (b) failure of the next pullback to retest the "
            "previous structure. Trading 'with structure' on the higher "
            "timeframe gives the highest hit-rate."
        ),
        "meta": {"category": "structure"},
    },
    # --- Price action ---
    {
        "id": "price_action",
        "text": (
            "Price action: the candle is a footprint of all activity in a "
            "period. Key formations: pin bars (long wick rejection at S/R), "
            "engulfing (full reversal of the prior body), inside bars "
            "(compression / continuation), narrow-range-7 (volatility "
            "contraction → expansion soon). Always read candles in context "
            "(trend, location, volume) — pattern alone is not a system."
        ),
        "meta": {"category": "price_action"},
    },
    # --- Risk management ---
    {
        "id": "risk_management_core",
        "text": (
            "Risk management: position size = (capital * risk%) / (entry - "
            "stop). Risk per trade 0.5%-2% of equity. Portfolio heat (sum of "
            "open risk) under 6%. Use ATR-based stops (1.5-2 ATR) instead of "
            "fixed % so volatility-adjusted. Stop is decided BEFORE entry; "
            "targets are management. Risk:reward ≥ 1:2 over a sample of 30+ "
            "trades is what produces real expectancy."
        ),
        "meta": {"category": "risk"},
    },
    {
        "id": "risk_expectancy",
        "text": (
            "Expectancy = (win_rate * avg_win) - (loss_rate * avg_loss). A "
            "system with 45% win-rate and 1:2 R:R has positive expectancy "
            "of 0.35R per trade. Sample size matters: do not change rules on "
            "fewer than 30 closed trades. Drawdowns of 2-3x average loss in "
            "a row are statistically normal."
        ),
        "meta": {"category": "risk"},
    },
    # --- Market psychology ---
    {
        "id": "psychology_cycle",
        "text": (
            "Market psychology cycle (Wall Street cheat sheet): disbelief → "
            "hope → optimism → belief → thrill → euphoria → complacency → "
            "anxiety → denial → panic → capitulation → despondency → "
            "depression → hope. Tops form on euphoria & wide retail "
            "participation; bottoms form on capitulation & disgust. The crowd "
            "is right during the trend, wrong at the extremes."
        ),
        "meta": {"category": "psychology"},
    },
    {
        "id": "psychology_biases",
        "text": (
            "Common trader biases: loss aversion (holding losers, cutting "
            "winners), recency bias (overweighting last few trades), "
            "anchoring (to entry price), gambler's fallacy (mean reversion "
            "after a streak), confirmation bias (seeking news that fits the "
            "position), FOMO (chasing late breakouts). Antidote: written "
            "rules, journaling, fixed risk per trade, and detachment from "
            "individual outcomes."
        ),
        "meta": {"category": "psychology"},
    },
    # --- Sector rotation ---
    {
        "id": "sector_rotation",
        "text": (
            "Sector rotation through the business cycle: early recovery → "
            "financials, real estate, consumer discretionary, industrials. "
            "Mid-cycle → technology, materials. Late-cycle → energy, "
            "commodities, healthcare. Recession → consumer staples, utilities, "
            "healthcare. Tracking RSI/momentum across sectors highlights the "
            "current 'leading' sectors so you can concentrate longs there."
        ),
        "meta": {"category": "sector_rotation"},
    },
    {
        "id": "sector_rotation_india",
        "text": (
            "Indian sector rotation cues: rate-cut cycle benefits banks, "
            "NBFCs, autos and real-estate; capex/infra cycles benefit "
            "cement, capital goods, PSU, defence, railways; rupee weakness "
            "helps IT and pharma exporters and hurts OMCs/paints/aviation; "
            "FII outflows hit large-cap banks first; DII flows often "
            "support midcaps."
        ),
        "meta": {"category": "sector_rotation", "market": "india"},
    },
    # --- Institutional accumulation / distribution ---
    {
        "id": "institutional_accumulation",
        "text": (
            "Institutional accumulation footprint: prolonged sideways range "
            "after a downtrend, declining volatility, repeated tests of a "
            "support with smaller selling, rising up-volume on rallies and "
            "shrinking down-volume on dips, hidden buying on news shocks. "
            "Breakout from such a base on expansion volume = high-quality "
            "entry."
        ),
        "meta": {"category": "institutional_flow"},
    },
    {
        "id": "institutional_distribution",
        "text": (
            "Institutional distribution footprint: parabolic late-stage "
            "move, wide-range up bars on heavy volume that close mid-range, "
            "rising VIX while index makes marginal new highs, breadth "
            "divergence (fewer stocks confirming), insider selling reports. "
            "First major lower-low after weeks of distribution typically "
            "starts the markdown phase."
        ),
        "meta": {"category": "institutional_flow"},
    },
    # --- Breakouts & volatility ---
    {
        "id": "breakout_quality",
        "text": (
            "High-quality breakouts: prior consolidation > 10 bars, range "
            "compressed (Bollinger Band squeeze, ADX < 20), breakout candle "
            "spread > 1.5x ATR with close in the top 1/3 of its range, volume "
            "> 1.5x 20-day average, and at least one *retest* that holds the "
            "broken level. Failed breakouts on the FIRST bar should be cut "
            "immediately."
        ),
        "meta": {"category": "breakout"},
    },
    {
        "id": "volatility_regimes",
        "text": (
            "Volatility regimes: ATR / price ratio < 1.5% = quiet (favours "
            "breakouts), 1.5-3% = normal trend conditions, > 4% = high "
            "volatility (favours mean-reversion and reduced size). India VIX "
            "above 22 historically coincides with elevated whipsaw risk; "
            "tighten filters and shorten time-frames."
        ),
        "meta": {"category": "volatility"},
    },
    # --- Indian market specifics ---
    {
        "id": "india_fii_dii",
        "text": (
            "FII/DII flow dynamics in India: persistent FII selling combined "
            "with DII buying typically marks a base; the reverse marks a "
            "topping process. Large-cap Nifty50 is FII-sensitive, while "
            "midcap/smallcap indices follow DII + retail flows. Monthly net "
            "F&O participation and cash market provisional flows are the key "
            "free indicators."
        ),
        "meta": {"category": "indian_market"},
    },
    {
        "id": "india_corporate_actions",
        "text": (
            "Corporate-action playbook (India): pre-results runs into "
            "earnings often fade post-result; bonus / split announcements "
            "drive short-term price gaps but rarely change long trend; "
            "buybacks via tender at premium provide a short-term floor; "
            "dividend yields (>5%) plus rising book value attract DII flows."
        ),
        "meta": {"category": "indian_market"},
    },
    # --- Risk-of-ruin & survival ---
    {
        "id": "risk_of_ruin",
        "text": (
            "Risk of ruin grows non-linearly with risk per trade: at 2% risk "
            "and 50% win-rate, 20 losses in a row (~0.000001 probability) "
            "still hurts. At 10% risk, just 7 losses can be terminal. "
            "Survival > optimisation. Always size so the next 5 losses "
            "barely change your equity curve."
        ),
        "meta": {"category": "risk"},
    },
    # --- Probabilistic thinking ---
    {
        "id": "probabilistic_thinking",
        "text": (
            "Think in probabilities, not certainties. Each trade is one draw "
            "from a distribution. A signal with 60% historical win-rate will "
            "still lose 40% of the time. The only way to extract the edge is "
            "to take many independent draws at consistent size. Outcome of a "
            "single trade carries no information about the system."
        ),
        "meta": {"category": "psychology"},
    },
]


def main() -> None:
    setup_logging()
    store = get_knowledge_base()
    if not store.enabled:
        logger.error("ChromaDB not available — cannot seed knowledge base.")
        return
    for c in CONCEPTS:
        store.add(c["id"], c["text"], c["meta"])
    logger.info(
        f"Seeded {len(CONCEPTS)} knowledge documents. Total in store: {store.count()}"
    )


if __name__ == "__main__":
    main()
