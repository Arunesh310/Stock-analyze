"""ML Confidence Engine — XGBoost classifier on prediction outcomes.

What this does
--------------
For every signal we ever produced we already store a rich snapshot in
``PredictionHistory`` (indicators, regime, breadth, sector strength, news
sentiment, ATR, RR, …) and the *actual outcome* in ``PredictionOutcome``.

This module trains an XGBoost binary classifier (win / loss) on that
snapshot + outcome data and uses it at inference time to produce a
probability of success for new signals. That probability is blended with
the existing rule-based confidence so the engine has a learned probabilistic
view in addition to its hand-crafted scoring.

Why XGBoost and not a deep net
------------------------------
Tabular financial data is short and noisy. Gradient-boosted decision trees
beat deep nets consistently on this kind of data, train in seconds on a CPU,
score in microseconds, handle missing values natively, and surface feature
importance — which is exactly what we need to keep the system explainable.

Why we still keep the rule-based score
--------------------------------------
ML can over-fit on small samples. The rule-based score is a stable prior.
We blend 60/40 (ML/rules) when the model is healthy and fall back entirely
to rules when there isn't enough data or the model isn't loaded.

Honesty: walk-forward CV
------------------------
Out-of-sample accuracy is computed with expanding-window time-series CV
(train on first k folds, test on fold k+1, never peek forward) and reported
in ``status()``. This is the number you should trust — not the in-sample
training accuracy.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from loguru import logger

from ..database import db_session
from ..models.prediction_engine import (
    AILearningLog,
    PredictionHistory,
    PredictionOutcome,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Where we persist the trained model. On Render free tier this dir is
# ephemeral, but the training data lives on Neon so a retrain rebuilds it.
_MODEL_DIR = Path(os.environ.get("ML_MODEL_DIR", "data/ml_models"))
_MODEL_DIR.mkdir(parents=True, exist_ok=True)
_MODEL_FILE = _MODEL_DIR / "xgb_confidence.joblib"

# Below this many validated trades we silently fall back to rule-based
# confidence — too little data to learn anything trustworthy.
_MIN_TRAIN_SAMPLES = 30

# How much weight the ML probability gets when blending with rule confidence.
_ML_BLEND_WEIGHT = 0.6

# Stable encoding orders so the feature matrix is consistent across retrains.
_REGIMES = [
    "bullish_trend", "bearish_trend", "sideways",
    "high_volatility", "risk_off", "risk_on", "unknown",
]
_MODES = ["intraday", "swing", "positional"]
_ACTIONS = ["BUY", "SELL"]


# ---------------------------------------------------------------------------
# Feature extraction — MUST be identical for training and inference
# ---------------------------------------------------------------------------


def _safe_float(v: Any, default: float = float("nan")) -> float:
    try:
        if v is None:
            return default
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _build_features(
    *,
    action: str,
    mode: str,
    confidence_rule: float,
    score: float,
    entry_ref: Optional[float],
    stoploss: Optional[float],
    target1: Optional[float],
    rr: Optional[float],
    atr: Optional[float],
    market_regime: Optional[str],
    news_sentiment: Optional[float],
    sector_strength: Optional[float],
    breadth_advancers: Optional[int],
    breadth_decliners: Optional[int],
    indicators: Dict[str, Any],
    patterns: List[str],
) -> Dict[str, float]:
    """Return a deterministic feature dict. NaNs are kept — XGBoost handles them."""
    f: Dict[str, float] = {}

    f["rule_confidence"] = _safe_float(confidence_rule)
    f["rule_score"] = _safe_float(score)
    f["rr"] = _safe_float(rr)

    entry = _safe_float(entry_ref)
    sl = _safe_float(stoploss)
    t1 = _safe_float(target1)
    atr_v = _safe_float(atr)
    if not np.isnan(entry) and entry > 0:
        f["sl_pct"] = abs(entry - sl) / entry if not np.isnan(sl) else float("nan")
        f["t1_pct"] = abs(t1 - entry) / entry if not np.isnan(t1) else float("nan")
        f["atr_pct"] = atr_v / entry if not np.isnan(atr_v) else float("nan")
    else:
        f["sl_pct"] = float("nan")
        f["t1_pct"] = float("nan")
        f["atr_pct"] = float("nan")

    f["news_sentiment"] = _safe_float(news_sentiment, 0.0)
    f["sector_strength"] = _safe_float(sector_strength, 0.0)
    adv = _safe_float(breadth_advancers, 0.0)
    dec = _safe_float(breadth_decliners, 0.0)
    total = adv + dec
    f["breadth_ratio"] = adv / total if total > 0 else 0.5

    inds = indicators or {}
    f["rsi"] = _safe_float(inds.get("rsi"))
    f["macd"] = _safe_float(inds.get("macd"))
    f["macd_signal"] = _safe_float(inds.get("macd_signal"))
    f["macd_hist"] = _safe_float(inds.get("macd_hist"))
    f["adx"] = _safe_float(inds.get("adx"))

    if not np.isnan(f["macd"]) and not np.isnan(f["macd_signal"]):
        f["macd_bull"] = 1.0 if f["macd"] > f["macd_signal"] else 0.0
    else:
        f["macd_bull"] = float("nan")

    e20 = _safe_float(inds.get("ema20"))
    e50 = _safe_float(inds.get("ema50"))
    e200 = _safe_float(inds.get("ema200"))
    if not any(np.isnan(x) for x in (e20, e50, e200)):
        f["ema_bull_stack"] = 1.0 if e20 > e50 > e200 else 0.0
        f["ema_bear_stack"] = 1.0 if e20 < e50 < e200 else 0.0
    else:
        f["ema_bull_stack"] = float("nan")
        f["ema_bear_stack"] = float("nan")

    f["volatility_pct"] = _safe_float(inds.get("volatility_pct"))

    bb_u = _safe_float(inds.get("bb_upper"))
    bb_l = _safe_float(inds.get("bb_lower"))
    if not any(np.isnan(x) for x in (bb_u, bb_l, entry)) and bb_u > bb_l:
        f["bb_position"] = (entry - bb_l) / (bb_u - bb_l)
    else:
        f["bb_position"] = float("nan")

    f["pattern_count"] = float(len(patterns or []))

    regime_key = (market_regime or "unknown").lower()
    for reg in _REGIMES:
        f[f"regime__{reg}"] = 1.0 if regime_key == reg else 0.0
    for m in _MODES:
        f[f"mode__{m}"] = 1.0 if mode == m else 0.0
    for a in _ACTIONS:
        f[f"action__{a}"] = 1.0 if action == a else 0.0

    return f


def _features_from_prediction(pred: PredictionHistory) -> Dict[str, float]:
    return _build_features(
        action=pred.action,
        mode=pred.mode,
        confidence_rule=pred.confidence,
        score=pred.score,
        entry_ref=pred.entry_ref,
        stoploss=pred.stoploss,
        target1=pred.target1,
        rr=pred.rr,
        atr=pred.atr_at_entry,
        market_regime=pred.market_regime,
        news_sentiment=pred.news_sentiment,
        sector_strength=pred.sector_strength,
        breadth_advancers=pred.breadth_advancers,
        breadth_decliners=pred.breadth_decliners,
        indicators=pred.indicators_snapshot or {},
        patterns=pred.detected_patterns or [],
    )


# ---------------------------------------------------------------------------
# Model state — singleton, lazy-loaded
# ---------------------------------------------------------------------------


@dataclass
class _ModelState:
    model: Any = None
    feature_names: List[str] = field(default_factory=list)
    trained_at: Optional[datetime] = None
    train_samples: int = 0
    cv_auc: Optional[float] = None
    cv_accuracy: Optional[float] = None
    cv_log_loss: Optional[float] = None
    cv_folds: int = 0
    feature_importance: Dict[str, float] = field(default_factory=dict)
    win_rate_in_sample: Optional[float] = None
    last_error: Optional[str] = None


_state = _ModelState()
_state_lock = threading.Lock()


def _save_state() -> None:
    if _state.model is None:
        return
    payload = {
        "model": _state.model,
        "feature_names": _state.feature_names,
        "trained_at": _state.trained_at.isoformat() if _state.trained_at else None,
        "train_samples": _state.train_samples,
        "cv_auc": _state.cv_auc,
        "cv_accuracy": _state.cv_accuracy,
        "cv_log_loss": _state.cv_log_loss,
        "cv_folds": _state.cv_folds,
        "feature_importance": _state.feature_importance,
        "win_rate_in_sample": _state.win_rate_in_sample,
    }
    try:
        joblib.dump(payload, _MODEL_FILE)
    except Exception as exc:
        logger.warning(f"ml_confidence: failed to persist model: {exc}")


def _load_state() -> bool:
    if not _MODEL_FILE.exists():
        return False
    try:
        payload = joblib.load(_MODEL_FILE)
        _state.model = payload.get("model")
        _state.feature_names = payload.get("feature_names", [])
        ta = payload.get("trained_at")
        _state.trained_at = datetime.fromisoformat(ta) if ta else None
        _state.train_samples = payload.get("train_samples", 0)
        _state.cv_auc = payload.get("cv_auc")
        _state.cv_accuracy = payload.get("cv_accuracy")
        _state.cv_log_loss = payload.get("cv_log_loss")
        _state.cv_folds = payload.get("cv_folds", 0)
        _state.feature_importance = payload.get("feature_importance", {})
        _state.win_rate_in_sample = payload.get("win_rate_in_sample")
        logger.info(
            f"ml_confidence: loaded model trained at {_state.trained_at} on "
            f"{_state.train_samples} samples (CV AUC {_state.cv_auc})"
        )
        return True
    except Exception as exc:
        logger.warning(f"ml_confidence: failed to load model: {exc}")
        return False


# Best-effort load on import — completely silent on failure.
try:
    _load_state()
except Exception:
    pass


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------


def _new_clf():
    """Conservative XGBoost defaults — small data, regularised."""
    from xgboost import XGBClassifier

    return XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=2,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        verbosity=0,
        random_state=42,
        tree_method="hist",
    )


def _collect_training_data() -> Tuple[np.ndarray, np.ndarray, List[datetime], List[str]]:
    """Load all validated predictions from the DB, sorted by signal time."""
    with db_session() as db:
        rows = (
            db.query(PredictionHistory, PredictionOutcome)
            .join(
                PredictionOutcome,
                PredictionOutcome.prediction_id == PredictionHistory.id,
            )
            .filter(
                PredictionOutcome.outcome.in_(
                    ["WIN", "LOSS", "PARTIAL_WIN", "EXPIRED", "INVALIDATED"]
                )
            )
            .filter(PredictionHistory.action.in_(["BUY", "SELL"]))
            .order_by(PredictionHistory.created_at.asc())
            .all()
        )
    if not rows:
        return np.empty((0, 0)), np.empty((0,)), [], []

    feature_dicts: List[Dict[str, float]] = []
    targets: List[int] = []
    timestamps: List[datetime] = []
    for pred, outcome in rows:
        feature_dicts.append(_features_from_prediction(pred))
        is_win = (outcome.outcome in ("WIN", "PARTIAL_WIN")) and (
            (outcome.realized_pct or 0) > 0
        )
        targets.append(1 if is_win else 0)
        timestamps.append(pred.created_at)

    feature_names = sorted(feature_dicts[0].keys())
    X = np.array(
        [[fd.get(name, float("nan")) for name in feature_names] for fd in feature_dicts],
        dtype=np.float32,
    )
    y = np.array(targets, dtype=np.int32)
    return X, y, timestamps, feature_names


def _walk_forward_cv(
    X: np.ndarray, y: np.ndarray, folds: int = 5
) -> Dict[str, Optional[float]]:
    """Expanding-window time-series CV: never peek forward.

    Fold k trains on the first ``k * fold_size`` rows and tests on the next
    ``fold_size`` rows. We report the mean of AUC/accuracy/log-loss over all
    folds where both classes were present in the test split.
    """
    from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

    n = len(X)
    if n < 20:
        return {"cv_auc": None, "cv_accuracy": None, "cv_log_loss": None, "folds_used": 0}

    fold_size = max(5, n // (folds + 1))
    aucs: List[float] = []
    accs: List[float] = []
    losses: List[float] = []

    for i in range(1, folds + 1):
        end_train = fold_size * i
        end_test = min(n, fold_size * (i + 1))
        if end_test <= end_train + 2:
            continue
        X_tr, y_tr = X[:end_train], y[:end_train]
        X_te, y_te = X[end_train:end_test], y[end_train:end_test]
        if len(set(y_tr.tolist())) < 2 or len(y_te) < 2:
            continue
        try:
            clf = _new_clf()
            clf.fit(X_tr, y_tr)
            p = clf.predict_proba(X_te)[:, 1]
            if len(set(y_te.tolist())) > 1:
                aucs.append(float(roc_auc_score(y_te, p)))
            accs.append(float(accuracy_score(y_te, (p > 0.5).astype(int))))
            losses.append(
                float(log_loss(y_te, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1]))
            )
        except Exception as exc:
            logger.debug(f"ml_confidence: fold {i} skipped — {exc}")
            continue

    return {
        "cv_auc": float(np.mean(aucs)) if aucs else None,
        "cv_accuracy": float(np.mean(accs)) if accs else None,
        "cv_log_loss": float(np.mean(losses)) if losses else None,
        "folds_used": len(aucs),
    }


def retrain() -> Dict[str, Any]:
    """Refresh training data, run walk-forward CV, fit final model on all
    data, persist to disk and log to AILearningLog.

    Safe to call from a request handler or the scheduler — single-threaded
    via ``_state_lock``.
    """
    with _state_lock:
        X, y, _ts, feature_names = _collect_training_data()
        n = len(X)
        if n < _MIN_TRAIN_SAMPLES:
            msg = (
                f"Not enough validated trades — have {n}, need {_MIN_TRAIN_SAMPLES}."
            )
            logger.info(f"ml_confidence: {msg}")
            _state.last_error = msg
            return {
                "ok": False,
                "trained": False,
                "samples": n,
                "min_required": _MIN_TRAIN_SAMPLES,
                "message": msg,
            }
        if len(set(y.tolist())) < 2:
            msg = "Need at least one WIN and one LOSS in the dataset."
            _state.last_error = msg
            return {"ok": False, "trained": False, "samples": n, "message": msg}

        cv = _walk_forward_cv(X, y)

        clf = _new_clf()
        clf.fit(X, y)
        importance = dict(
            zip(feature_names, [float(v) for v in clf.feature_importances_])
        )

        _state.model = clf
        _state.feature_names = feature_names
        _state.trained_at = datetime.utcnow()
        _state.train_samples = n
        _state.cv_auc = cv.get("cv_auc")
        _state.cv_accuracy = cv.get("cv_accuracy")
        _state.cv_log_loss = cv.get("cv_log_loss")
        _state.cv_folds = cv.get("folds_used") or 0
        _state.feature_importance = importance
        _state.win_rate_in_sample = float(y.mean()) if n else None
        _state.last_error = None
        _save_state()

        summary = (
            f"Retrained ML confidence on {n} samples · "
            f"CV AUC {(_state.cv_auc or 0):.3f} · "
            f"accuracy {(_state.cv_accuracy or 0):.1%} "
            f"({_state.cv_folds} folds)"
        )
        try:
            with db_session() as db:
                db.add(
                    AILearningLog(
                        event="ml_retrain",
                        summary=summary,
                        details={
                            "samples": n,
                            "cv_auc": _state.cv_auc,
                            "cv_accuracy": _state.cv_accuracy,
                            "cv_log_loss": _state.cv_log_loss,
                            "cv_folds": _state.cv_folds,
                            "win_rate_in_sample": _state.win_rate_in_sample,
                            "top_features": sorted(
                                importance.items(), key=lambda kv: kv[1], reverse=True
                            )[:10],
                        },
                    )
                )
        except Exception as exc:
            logger.warning(f"ml_confidence: could not write AILearningLog: {exc}")
        logger.info(f"ml_confidence: {summary}")

        return {
            "ok": True,
            "trained": True,
            "samples": n,
            "cv_auc": _state.cv_auc,
            "cv_accuracy": _state.cv_accuracy,
            "cv_log_loss": _state.cv_log_loss,
            "cv_folds": _state.cv_folds,
            "win_rate_in_sample": _state.win_rate_in_sample,
            "trained_at": _state.trained_at.isoformat(),
            "top_features": sorted(
                importance.items(), key=lambda kv: kv[1], reverse=True
            )[:10],
        }


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------


def is_ready() -> bool:
    return _state.model is not None and bool(_state.feature_names)


def score_signal(
    *,
    action: str,
    mode: str,
    confidence_rule: float,
    score: float,
    entry_ref: Optional[float],
    stoploss: Optional[float],
    target1: Optional[float],
    rr: Optional[float],
    atr: Optional[float],
    market_regime: Optional[str],
    news_sentiment: Optional[float],
    sector_strength: Optional[float],
    breadth_advancers: Optional[int],
    breadth_decliners: Optional[int],
    indicators: Dict[str, Any],
    patterns: List[str],
) -> Optional[Dict[str, float]]:
    """Score a single live signal.

    Returns ``None`` when the model isn't ready — callers must treat this as
    the signal that they should use the rule-based confidence alone.

    On success returns ``{"p_win", "ml_confidence", "blended_confidence"}``.
    """
    if not is_ready():
        return None
    try:
        feats = _build_features(
            action=action,
            mode=mode,
            confidence_rule=confidence_rule,
            score=score,
            entry_ref=entry_ref,
            stoploss=stoploss,
            target1=target1,
            rr=rr,
            atr=atr,
            market_regime=market_regime,
            news_sentiment=news_sentiment,
            sector_strength=sector_strength,
            breadth_advancers=breadth_advancers,
            breadth_decliners=breadth_decliners,
            indicators=indicators,
            patterns=patterns,
        )
        row = np.array(
            [[feats.get(name, float("nan")) for name in _state.feature_names]],
            dtype=np.float32,
        )
        p_win = float(_state.model.predict_proba(row)[0, 1])
        ml_conf = round(p_win * 100.0, 2)
        blended = round(
            (1 - _ML_BLEND_WEIGHT) * confidence_rule + _ML_BLEND_WEIGHT * ml_conf, 2
        )
        return {
            "p_win": p_win,
            "ml_confidence": ml_conf,
            "blended_confidence": blended,
        }
    except Exception as exc:
        logger.warning(f"ml_confidence.score_signal failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Status (for /api/ml/status + dashboard)
# ---------------------------------------------------------------------------


def status() -> Dict[str, Any]:
    return {
        "ready": is_ready(),
        "trained_at": _state.trained_at.isoformat() if _state.trained_at else None,
        "train_samples": _state.train_samples,
        "min_required_samples": _MIN_TRAIN_SAMPLES,
        "ml_blend_weight": _ML_BLEND_WEIGHT,
        "cv_auc": _state.cv_auc,
        "cv_accuracy": _state.cv_accuracy,
        "cv_log_loss": _state.cv_log_loss,
        "cv_folds": _state.cv_folds,
        "win_rate_in_sample": _state.win_rate_in_sample,
        "top_features": sorted(
            _state.feature_importance.items(), key=lambda kv: kv[1], reverse=True
        )[:15],
        "last_error": _state.last_error,
    }
