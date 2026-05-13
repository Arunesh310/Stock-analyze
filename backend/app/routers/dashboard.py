"""Aggregated dashboard endpoint — single call drives the home page.

Read path: serve the latest snapshot persisted by GitHub Actions (compute
runs there, not on Render). If no snapshot exists yet (e.g. brand-new
deploy and the GA workflow hasn't run yet), fall back to a single
direct compute and cache it for 60s.

This makes the home page resilient on Render free tier: it never has to
do the heavy yfinance fan-out on the request path during normal operation.
"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, HTTPException
from loguru import logger

from ..services import dashboard_engine

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


_CACHE_TTL_SECONDS = 60
_cache_lock = threading.Lock()
_cache_payload: dict | None = None
_cache_set_at: float = 0.0


def _live_compute_with_cache() -> dict:
    """Fallback path — only used when there is no snapshot in the DB yet."""
    global _cache_payload, _cache_set_at

    now = time.time()
    if _cache_payload is not None and (now - _cache_set_at) < _CACHE_TTL_SECONDS:
        return _cache_payload

    with _cache_lock:
        if _cache_payload is not None and (time.time() - _cache_set_at) < _CACHE_TTL_SECONDS:
            return _cache_payload
        try:
            payload = dashboard_engine.compute_payload()
            _cache_payload = payload
            _cache_set_at = time.time()
            return payload
        except Exception as exc:
            logger.warning(f"dashboard live-compute failed: {exc}")
            if _cache_payload is not None:
                return _cache_payload
            raise HTTPException(
                status_code=503,
                detail=(
                    "Dashboard snapshot is not available yet and a live compute "
                    "failed. The scheduled GitHub Actions job will populate it "
                    "shortly."
                ),
            )


@router.get("")
def dashboard() -> dict:
    """Serve the latest dashboard snapshot from Neon (computed by CI).

    Falls back to direct compute only when no snapshot exists.
    """
    snap = dashboard_engine.latest_snapshot()
    if snap is not None:
        return snap
    return _live_compute_with_cache()


@router.get("/snapshot-meta")
def snapshot_meta() -> dict:
    """Lightweight introspection for the sync panel — exists?, age, stale?"""
    return dashboard_engine.snapshot_meta()


@router.post("/refresh")
def dashboard_refresh() -> dict:
    """Force a synchronous recompute + persist. Usually called by the CI
    workflow on cron; safe to hit manually from the UI for debugging."""
    return dashboard_engine.run_and_persist()
