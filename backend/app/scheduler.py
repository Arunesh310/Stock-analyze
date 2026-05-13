"""APScheduler-backed background jobs for the prediction engine.

Schedule (per project requirements):

- **stock prices**         : every 1 minute  — light cache refresh
- **indicators**           : every 5 minutes — refresh adaptive weights cache
- **signal validation**    : every 15 minutes — validate open predictions
- **news**                 : every 2 hours — refresh news cache
- **learning cycle**       : after every validation cycle
- **market regime snapshot**: every 30 minutes
- **confidence recalibration**: every 6 hours

All jobs are wrapped in try/except so a single failing run never kills the
scheduler. The scheduler is started inside the FastAPI lifespan context.
"""
from __future__ import annotations

from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger


_scheduler: Optional[BackgroundScheduler] = None


# ---------------------------------------------------------------------------
# Job wrappers
# ---------------------------------------------------------------------------


def _safe(name: str, fn, *args, **kwargs) -> None:
    try:
        result = fn(*args, **kwargs)
        logger.info(f"scheduler[{name}] ok — {result!r}")
    except Exception as exc:
        logger.warning(f"scheduler[{name}] failed: {exc}")


def job_refresh_prices() -> None:
    """Touch the price cache for the curated universe so quotes stay fresh."""
    from .services import market_data, universe

    syms = ["^NSEI", "^NSEBANK", "^INDIAVIX", "INR=X"] + universe.all_symbols()[:25]
    market_data.get_quotes(syms)


def job_refresh_indicators_weights() -> None:
    """Reset the adaptive-scoring weights cache so the next signal scan uses
    the freshest learning output."""
    from .services import scoring_engine

    scoring_engine.reset_cache()


def job_validate_signals() -> None:
    from .services import validation_engine

    validation_engine.validate_all_open(limit=200)


def job_learning_cycle() -> None:
    from .services import learning_engine

    learning_engine.run_learning_cycle()


def job_recalibrate_confidence() -> None:
    from .services import confidence_engine

    confidence_engine.recalibrate()


def job_refresh_news() -> None:
    from .services import news_engine

    news_engine.fetch_news()


def job_snapshot_regime() -> None:
    from .services import market_regime

    market_regime.persist_regime()


def job_expire_stale() -> None:
    from .services import validation_engine

    validation_engine.expire_stale_predictions()


def job_validation_then_learning() -> None:
    job_validate_signals()
    job_learning_cycle()
    job_refresh_indicators_weights()


# ---------------------------------------------------------------------------
# Public scheduler control
# ---------------------------------------------------------------------------


def start_scheduler() -> None:
    """Start the background scheduler. Idempotent."""
    global _scheduler
    if _scheduler is not None:
        return
    sched = BackgroundScheduler(timezone="Asia/Kolkata", daemon=True)

    sched.add_job(
        lambda: _safe("prices_1m", job_refresh_prices),
        "interval", minutes=1, id="prices_1m", coalesce=True, max_instances=1,
    )
    sched.add_job(
        lambda: _safe("indicators_5m", job_refresh_indicators_weights),
        "interval", minutes=5, id="indicators_5m", coalesce=True, max_instances=1,
    )
    sched.add_job(
        lambda: _safe("validate_15m", job_validation_then_learning),
        "interval", minutes=15, id="validate_15m", coalesce=True, max_instances=1,
    )
    sched.add_job(
        lambda: _safe("news_2h", job_refresh_news),
        "interval", hours=2, id="news_2h", coalesce=True, max_instances=1,
    )
    sched.add_job(
        lambda: _safe("regime_30m", job_snapshot_regime),
        "interval", minutes=30, id="regime_30m", coalesce=True, max_instances=1,
    )
    sched.add_job(
        lambda: _safe("confidence_6h", job_recalibrate_confidence),
        "interval", hours=6, id="confidence_6h", coalesce=True, max_instances=1,
    )
    sched.add_job(
        lambda: _safe("expire_1h", job_expire_stale),
        "interval", hours=1, id="expire_1h", coalesce=True, max_instances=1,
    )

    sched.start()
    _scheduler = sched
    logger.info("BharatQuant scheduler started.")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    except Exception:  # pragma: no cover
        pass
    _scheduler = None
    logger.info("BharatQuant scheduler stopped.")
