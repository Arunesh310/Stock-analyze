"""Full per-symbol AI analysis."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..schemas.common import AnalysisResponse, DataQualityOut
from ..services import market_data, prediction_tracker, signal_engine, symbol_normalizer
from ..services.ai_engine import explain_signal
from ..services.universe import get_sector

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


@router.get("/{symbol}", response_model=AnalysisResponse)
def analyze(
    symbol: str,
    mode: str = Query("swing", pattern="^(intraday|swing|positional)$"),
    use_llm: bool = True,
) -> AnalysisResponse:
    symbol = symbol_normalizer.canonical(symbol)
    try:
        quote = market_data.get_quote(symbol)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    sig, ind, patterns = signal_engine.build_signal(symbol, mode=mode)
    rs = signal_engine.relative_strength(symbol, "^NSEI")
    quality = market_data.get_quality(symbol)

    # Track actionable analysis as a prediction so the validation engine
    # can grade it later.
    if sig.action in ("BUY", "SELL"):
        try:
            prediction_tracker.record_signal(sig, ind)
        except Exception:
            pass

    if use_llm:
        try:
            sig.reasoning = explain_signal(
                symbol=symbol,
                indicators_dict=ind.model_dump(),
                signal_dict=sig.model_dump(),
                patterns=patterns,
                extra_context=(
                    f"Quote: price={quote.price}, change%={quote.change_pct}, "
                    f"sector={get_sector(symbol)}, relative_strength_vs_nifty={rs}"
                ),
            )
        except Exception:
            pass

    notes = []
    if rs is not None:
        notes.append(
            f"Relative strength vs Nifty (20D): {rs:+.2f} pp "
            f"({'outperforming' if rs > 0 else 'underperforming'})"
        )
    if quality.is_synthetic:
        notes.append(
            "Data is synthetic — live sources unavailable. Treat with extreme caution."
        )
    elif quality.is_stale:
        notes.append("Latest market data appears stale; refresh recommended.")
    elif quality.score < 80 and quality.issues:
        notes.append(
            f"Data quality {quality.score:.0f}/100 — {'; '.join(quality.issues[:2])}"
        )
    notes.append(
        "This tool is for educational and research purposes only "
        "and not financial advice."
    )

    return AnalysisResponse(
        quote=quote,
        indicators=ind,
        signal=sig,
        sector=get_sector(symbol),
        relative_strength=rs,
        notes=notes,
        data_quality=DataQualityOut(**quality.as_dict()),
    )
