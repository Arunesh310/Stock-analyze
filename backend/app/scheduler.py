"""APScheduler-backed background jobs (lightweight in-process scheduler).

Heavy compute (signal scan, dashboard refresh, overnight cycle, pre-market
brief, ML retrain, market regime, news, validation) is intentionally NOT
run in this process. Those jobs live on GitHub Actions
(``.github/workflows/compute.yml``) which calls
``backend.scripts.run_job`` on a beefy CI runner and writes results
directly to Neon Postgres. The backend then just reads from there.

This module keeps only cheap house-keeping jobs that have to live in the
API process because they touch in-memory caches:

- ``indicators_5m`` — resets the adaptive-scoring weights cache so the
  next request uses the freshest learning output pulled from DB.
- ``expire_1h``     — marks predictions whose horizon has passed.

The remaining ``job_*`` helpers below are still exported so other routers
can invoke them on demand, but they're no longer scheduled here.
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


def job_overnight_cycle() -> None:
    """Heavy post-close pipeline — validate + learn + recalibrate + regime."""
    from .services import overnight_engine

    overnight_engine.run_overnight_cycle()


def job_pre_market_brief() -> None:
    """Morning brief: global cues, sector pulse, gap candidates, verdict."""
    from .services import pre_market_engine

    pre_market_engine.run_pre_market_cycle()


def job_ml_retrain() -> None:
    """Refresh the XGBoost confidence model from the latest validated trades."""
    from .services import ml_confidence

    ml_confidence.retrain()


# ---------------------------------------------------------------------------
# Public scheduler control
# ---------------------------------------------------------------------------


def start_scheduler() -> None:
    """Start the background scheduler. Idempotent.

    Heavy jobs (signal scan, dashboard refresh, overnight cycle, pre-market
    brief, ML retrain) have been MOVED to GitHub Actions so the Render free
    tier (512 MB / 0.5 CPU) does not fall over under load. The scheduler
    here now only runs cheap house-keeping jobs that need to react fast to
    in-process state.
    """
    global _scheduler
    if _scheduler is not None:
        return
    sched = BackgroundScheduler(timezone="Asia/Kolkata", daemon=True)

    # Cheap: just resets in-process caches so the next scan uses the latest
    # adaptive weights pulled from DB. ~20 ms.
    sched.add_job(
        lambda: _safe("indicators_5m", job_refresh_indicators_weights),
        "interval", minutes=5, id="indicators_5m", coalesce=True, max_instances=1,
    )
    # Cheap: marks expired predictions in DB. Single update query.
    sched.add_job(
        lambda: _safe("expire_1h", job_expire_stale),
        "interval", hours=1, id="expire_1h", coalesce=True, max_instances=1,
    )

    sched.start()
    _scheduler = sched
    logger.info(
        "BharatQuant scheduler started (lightweight — heavy jobs are on CI)."
    )


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
