"""Adaptive scoring weights used by ``signal_engine.build_signal``.

This module owns a small **TTL-cached** lookup of the most recent
``IndicatorPerformance`` and ``SignalQualityScore`` rows, exposed as plain
floats so the signal engine doesn't take a DB hit on every symbol.

The signal engine multiplies its raw trend / momentum / pattern component
scores by these weights, so:

- indicators / setups with a *proven* edge in the current regime are
  weighted up (capped at +50%),
- consistently failing indicators / setups are weighted down (floored at
  -50%).

Weights default to 1.0 when no data is available yet — i.e. the system
starts fully in line with the original deterministic rules, then bends
toward whatever has worked for *your* trades over time.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Dict, Optional

from loguru import logger

from ..database import db_session
from ..models.prediction_engine import (
    IndicatorPerformance,
    SignalQualityScore,
)


_TTL_SECONDS = 300  # weights refresh at most once every 5 minutes
_lock = Lock()
_cache: Dict[str, tuple[float, Dict[str, float]]] = {}


def _cache_get(key: str) -> Optional[Dict[str, float]]:
    with _lock:
        if key in _cache:
            ts, val = _cache[key]
            if time.time() - ts < _TTL_SECONDS:
                return val
            _cache.pop(key, None)
    return None


def _cache_set(key: str, val: Dict[str, float]) -> None:
    with _lock:
        _cache[key] = (time.time(), val)


def get_indicator_weights(mode: str, regime: str | None = None) -> Dict[str, float]:
    """Return ``{indicator: weight}`` for the given mode/regime.

    Falls back to ``any`` regime when a regime-specific weight is missing.
    Always returns at least the default keys (rsi/macd/ema_stack/...).
    """
    key = f"ind::{mode}::{regime or 'any'}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    weights: Dict[str, float] = {
        "rsi": 1.0,
        "macd": 1.0,
        "ema_stack": 1.0,
        "bollinger": 1.0,
        "adx": 1.0,
    }
    try:
        with db_session() as db:
            rows = db.query(IndicatorPerformance).filter(
                IndicatorPerformance.mode == mode
            ).all()
            for r in rows:
                if r.sample_size < 4:
                    continue
                if r.regime == (regime or "any"):
                    weights[r.indicator] = float(r.weight)
                elif r.regime == "any" and r.indicator not in weights:
                    weights[r.indicator] = float(r.weight)
    except Exception as exc:
        logger.warning(f"get_indicator_weights: {exc}")
    _cache_set(key, weights)
    return weights


def get_pattern_weights(mode: str) -> Dict[str, float]:
    """Return ``{pattern_name: weight}`` derived from setup quality scores."""
    key = f"pat::{mode}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    weights: Dict[str, float] = {}
    try:
        with db_session() as db:
            rows = (
                db.query(SignalQualityScore)
                .filter(SignalQualityScore.mode == mode)
                .all()
            )
            for r in rows:
                if r.sample_size < 4:
                    continue
                weights[r.setup_name] = float(r.weight_multiplier)
    except Exception as exc:
        logger.warning(f"get_pattern_weights: {exc}")
    _cache_set(key, weights)
    return weights


def reset_cache() -> None:
    with _lock:
        _cache.clear()


def composite_indicator_multiplier(mode: str, regime: str | None, active: list[str]) -> float:
    """Convenience: given a list of *active* indicators, return a multiplier
    in [0.5, 1.5] using the cached weights."""
    if not active:
        return 1.0
    w = get_indicator_weights(mode, regime)
    vals = [w.get(a, 1.0) for a in active]
    if not vals:
        return 1.0
    avg = sum(vals) / len(vals)
    return max(0.5, min(1.5, avg))


def pattern_score_multiplier(mode: str, patterns: list[str]) -> float:
    if not patterns:
        return 1.0
    w = get_pattern_weights(mode)
    vals = [w[p] for p in patterns if p in w]
    if not vals:
        return 1.0
    avg = sum(vals) / len(vals)
    return max(0.5, min(1.5, avg))
