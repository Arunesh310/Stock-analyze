"""CLI runner for scheduled compute jobs.

Designed to be invoked from GitHub Actions so the heavy lifting (yfinance
fan-out, learning cycle, ML retrain, market regime classification) runs on
the beefy 4-CPU GA runner, NOT on Render's 0.5-CPU / 512-MB free tier.

The script writes results directly to the Neon Postgres database via the
existing service code; the backend just reads from there.

Usage
-----
    python -m backend.scripts.run_job dashboard
    python -m backend.scripts.run_job overnight
    python -m backend.scripts.run_job pre_market
    python -m backend.scripts.run_job signal_scan
    python -m backend.scripts.run_job ml_retrain
    python -m backend.scripts.run_job validation
    python -m backend.scripts.run_job market_regime
    python -m backend.scripts.run_job all_market_hours  # convenience bundle

The DB connection comes from the DATABASE_URL env var, which must be set
to the Neon connection string in the GA workflow.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

# Make ``backend.app...`` imports work when run as a script. The repo layout
# is ``<repo>/backend/...`` so prepending the repo root gives us the package.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))  # <repo>/
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _safe(name: str, fn, *args, **kwargs) -> Dict[str, Any]:
    """Run a job and return a JSON-serialisable summary. Failures don't
    propagate — they're captured and returned so the GA workflow can
    still finish and run the next job."""
    started = time.time()
    try:
        result = fn(*args, **kwargs)
        duration = round(time.time() - started, 2)
        return {
            "job": name,
            "ok": True,
            "duration_seconds": duration,
            "result": _trim(result),
        }
    except Exception as exc:
        duration = round(time.time() - started, 2)
        return {
            "job": name,
            "ok": False,
            "duration_seconds": duration,
            "error": str(exc),
        }


def _trim(value: Any, depth: int = 0) -> Any:
    """Recursively shrink results to a CI-friendly JSON summary."""
    if depth > 4:
        return "..."
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "model_dump"):
        try:
            return _trim(value.model_dump(mode="json"), depth + 1)
        except Exception:
            return repr(value)
    if isinstance(value, dict):
        return {k: _trim(v, depth + 1) for k, v in list(value.items())[:30]}
    if isinstance(value, (list, tuple)):
        return [_trim(v, depth + 1) for v in list(value)[:20]]
    return repr(value)


# ---------------------------------------------------------------------------
# Job implementations — each calls the existing service code
# ---------------------------------------------------------------------------


def job_dashboard() -> Dict[str, Any]:
    from backend.app.services import dashboard_engine

    payload = dashboard_engine.run_and_persist()
    return {
        "indices": len(payload.get("indices", [])),
        "gainers": len(payload.get("gainers", [])),
        "losers": len(payload.get("losers", [])),
        "sectors": len(payload.get("sectors", [])),
    }


def job_signal_scan() -> Dict[str, Any]:
    from backend.app.services import signal_engine, universe

    counts = {}
    for mode in ("intraday", "swing", "positional"):
        try:
            sigs = signal_engine.scan_signals(
                universe.all_symbols(),
                mode=mode,
                min_conf=60,
                min_grade="MODERATE",
                track=True,
            )
            counts[mode] = len(sigs)
        except Exception as exc:
            counts[mode] = f"failed: {exc}"
    return counts


def job_validation() -> Dict[str, Any]:
    from backend.app.services import validation_engine

    res = validation_engine.validate_all_open(limit=500)
    return res.model_dump(mode="json") if hasattr(res, "model_dump") else res


def job_overnight() -> Dict[str, Any]:
    from backend.app.services import overnight_engine

    return overnight_engine.run_overnight_cycle()


def job_pre_market() -> Dict[str, Any]:
    from backend.app.services import pre_market_engine

    return pre_market_engine.run_pre_market_cycle()


def job_market_regime() -> Dict[str, Any]:
    from backend.app.services import market_regime

    snap = market_regime.persist_regime()
    return snap if isinstance(snap, dict) else _trim(snap)


def job_ml_retrain() -> Dict[str, Any]:
    from backend.app.services import ml_confidence

    return ml_confidence.retrain()


def job_news() -> Dict[str, Any]:
    from backend.app.services import news_engine

    items = news_engine.fetch_news()
    return {"items": len(items) if items else 0}


# Convenience bundle: everything we want to run during market hours every
# 5-10 minutes. Order matters — dashboard last so it includes the freshest
# regime + news.
def job_all_market_hours() -> Dict[str, Any]:
    results = []
    for name, fn in (
        ("news", job_news),
        ("market_regime", job_market_regime),
        ("validation", job_validation),
        ("dashboard", job_dashboard),
    ):
        results.append(_safe(name, fn))
    return {"bundle": results}


_JOBS = {
    "dashboard": job_dashboard,
    "signal_scan": job_signal_scan,
    "validation": job_validation,
    "overnight": job_overnight,
    "pre_market": job_pre_market,
    "market_regime": job_market_regime,
    "ml_retrain": job_ml_retrain,
    "news": job_news,
    "all_market_hours": job_all_market_hours,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job", choices=sorted(_JOBS.keys()))
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON summary (default: compact)",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    print(
        f"run_job: job={args.job} db_scheme={db_url.split(':', 1)[0] if db_url else 'unset'}",
        flush=True,
    )

    summary = _safe(args.job, _JOBS[args.job])
    print(json.dumps(summary, indent=2 if args.pretty else None, default=str), flush=True)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
