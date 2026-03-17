"""ML prediction REST endpoint.

GET /api/v1/ml/case/{case_id}/prediction
-----------------------------------------
Returns the ML-predicted duration and delay analysis for a single case.

Response when ML is available::

    {
        "ml_available": true,
        "case_id": 42,
        "case_number": "WP/1234/2021",
        "predicted_duration_days": 847.3,
        "lower_bound_days": 540.0,
        "upper_bound_days": 1210.0,
        "confidence_score": 0.612,
        "model_version": "v20260317_0200",
        "current_age_days": 1240,
        "delay_ratio": 1.46,
        "ml_delay_flag": false,
        "ml_delay_severity": null,
        "feature_importance": [
            {"feature": "court_level", "importance": 0.312},
            ...
        ],
        "source": "live"
    }

Response when ML is unavailable (model not trained)::

    {
        "ml_available": false,
        "reason": "Model not trained yet — run the training task first"
    }

Design
------
* The endpoint always attempts a **live** prediction using the in-memory
  singleton predictor.
* If that fails, it falls back to the last row in ``case_predictions`` (if any).
* If both fail, it returns ``ml_available: false`` with an explanatory message.
* A 404 is raised only when the ``case_id`` does not exist in the database.

Rate limiting and caching follow the same conventions as all other routes.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/case/{case_id}/prediction")
def get_case_prediction(
    case_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Return ML duration prediction and delay analysis for a case.

    Degrades gracefully: returns ``{"ml_available": false}`` when the model
    is not yet trained rather than raising a 5xx error.
    """
    from app.ml.config import get_ml_settings
    from app.ml.features import FeatureExtractor
    from app.ml.outliers import classify_delay_severity, compute_delay_ratio
    from app.ml.predict import PREDICTION_UNAVAILABLE, get_predictor
    from app.models.entities import Case, CasePrediction

    ml_cfg = get_ml_settings()
    if not ml_cfg.ml_enabled:
        return {"ml_available": False, "reason": "ML module is disabled (ML_ENABLED=false)"}

    case = db.get(Case, case_id)
    if case is None or case.is_deleted:
        raise HTTPException(status_code=404, detail="Case not found")

    # ── Attempt live prediction ──────────────────────────────────────────────
    live_result: Optional[dict] = None
    try:
        extractor = FeatureExtractor()
        features = extractor.extract(case, db)
        predictor = get_predictor()
        result = predictor.predict(features.to_dict())

        if result is not PREDICTION_UNAVAILABLE and result.model_version != "unavailable":
            current_age = _current_age(case)
            delay_ratio = compute_delay_ratio(float(current_age), result.predicted_days)
            severity = classify_delay_severity(delay_ratio)
            live_result = {
                "ml_available": True,
                "case_id": case_id,
                "case_number": case.case_number,
                "predicted_duration_days": result.predicted_days,
                "lower_bound_days": result.lower_bound,
                "upper_bound_days": result.upper_bound,
                "confidence_score": result.confidence,
                "model_version": result.model_version,
                "current_age_days": current_age,
                "delay_ratio": delay_ratio,
                "ml_delay_flag": severity is not None,
                "ml_delay_severity": severity,
                "feature_importance": result.top_features,
                "source": "live",
            }
    except Exception:
        pass  # Fall through to cached result or unavailable response

    if live_result is not None:
        return live_result

    # ── Fall back to cached DB row ───────────────────────────────────────────
    cached: Optional[Any] = (
        db.query(CasePrediction).filter(CasePrediction.case_id == case_id).first()
    )
    if cached:
        return _prediction_from_db(cached, case, db)

    return {
        "ml_available": False,
        "reason": (
            "Model not trained yet — run the 'retrain_duration_model' Celery task first"
        ),
    }


@router.get("/status")
def ml_status() -> dict:
    """Return ML module status and loaded model version (if any)."""
    from app.ml.config import get_ml_settings
    from app.ml.predict import get_predictor

    ml_cfg = get_ml_settings()
    if not ml_cfg.ml_enabled:
        return {"ml_enabled": False}

    predictor = get_predictor()
    if not predictor._loaded:
        predictor.load()

    return {
        "ml_enabled": True,
        "model_loaded": predictor._loaded,
        "model_version": predictor._metadata.get("version", "not loaded"),
        "best_model": predictor._metadata.get("best_model", "unknown"),
        "metrics": predictor._metadata.get("metrics", {}),
        "train_size": predictor._metadata.get("train_size"),
        "val_size": predictor._metadata.get("val_size"),
        "feature_importance_top5": predictor._metadata.get(
            "feature_importance", []
        )[:5],
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _current_age(case: Any) -> int:
    """Return the number of days since the case was filed."""
    if case.filing_date:
        return max(0, (date.today() - case.filing_date).days)
    return 0


def _prediction_from_db(pred: Any, case: Any, db: Session) -> dict:
    """Serialise a ``CasePrediction`` ORM row to the API response shape."""
    from app.ml.outliers import classify_delay_severity, compute_delay_ratio

    current_age = _current_age(case)
    # Re-compute delay ratio against current age (it may have grown since last run)
    delay_ratio = compute_delay_ratio(
        float(current_age), pred.predicted_duration_days
    )
    severity = classify_delay_severity(delay_ratio)

    return {
        "ml_available": True,
        "case_id": pred.case_id,
        "case_number": case.case_number,
        "predicted_duration_days": pred.predicted_duration_days,
        "lower_bound_days": pred.lower_bound_days,
        "upper_bound_days": pred.upper_bound_days,
        "confidence_score": pred.confidence_score,
        "model_version": pred.ml_model_version,
        "current_age_days": current_age,
        "delay_ratio": delay_ratio,
        "ml_delay_flag": severity is not None,
        "ml_delay_severity": severity,
        "feature_importance": (pred.feature_importance or {}).get("top_features", []),
        "source": "cached",
    }
