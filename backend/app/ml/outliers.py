"""Outlier / delay-detection logic.

A case is considered *delayed* when its current age exceeds the model's
predicted duration by a configurable factor (the *delay ratio*):

    delay_ratio = current_age_days / predicted_duration_days

Severity levels
---------------
* **moderate** — delay_ratio ≥ 1.5  (case is 50 % overdue)
* **severe**   — delay_ratio ≥ 2.0  (case is twice as old as predicted)
* **extreme**  — delay_ratio ≥ 3.0  (case is triply overdue)

The thresholds are configurable via :class:`~app.ml.config.MLSettings`.

:func:`flag_delayed_cases`
    Scans all non-disposed active cases, runs batch prediction, and upserts
    rows in the ``case_predictions`` table.  Returns a list of summary dicts
    for cases that exceeded the moderate threshold.

All DB model imports are deferred so this module can be imported without
an active database connection (e.g. during unit tests).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy.orm import Session

from app.ml.config import get_ml_settings

if TYPE_CHECKING:
    from app.ml.predict import CaseDurationPredictor

logger = logging.getLogger(__name__)

_settings = get_ml_settings()

# Threshold mapping used for default severity classification.
_SEVERITY_MAP: dict[str, float] = {
    "extreme": _settings.ml_delay_threshold_extreme,
    "severe": _settings.ml_delay_threshold_severe,
    "moderate": _settings.ml_delay_threshold_moderate,
}


# ---------------------------------------------------------------------------
# Pure computation helpers (no DB, easily unit-tested)
# ---------------------------------------------------------------------------


def compute_delay_ratio(
    current_age_days: float, predicted_duration_days: float
) -> float:
    """Ratio of current case age to the model's predicted duration.

    * ``< 1.0``  — case is progressing faster than predicted.
    * ``= 1.0``  — case is exactly on schedule.
    * ``> 1.0``  — case is overdue.

    Returns ``0.0`` when *predicted_duration_days* is zero to avoid
    division-by-zero.
    """
    if predicted_duration_days <= 0.0:
        return 0.0
    return round(current_age_days / predicted_duration_days, 4)


def classify_delay_severity(delay_ratio: float) -> Optional[str]:
    """Map a delay ratio to a severity label, or ``None`` if not delayed.

    Thresholds are read from :class:`~app.ml.config.MLSettings` once at
    module import time.  They can be overridden via environment variables.
    """
    for label in ("extreme", "severe", "moderate"):
        if delay_ratio >= _SEVERITY_MAP[label]:
            return label
    return None


# ---------------------------------------------------------------------------
# Batch flagging (DB-integrated)
# ---------------------------------------------------------------------------


def flag_delayed_cases(
    db: Session,
    predictor: Optional["CaseDurationPredictor"] = None,
    threshold: Optional[float] = None,
) -> list[dict]:
    """Predict delay status for every non-disposed active case.

    For each case the function:

    1. Extracts ML features.
    2. Calls the predictor to get expected duration.
    3. Computes :func:`compute_delay_ratio` and :func:`classify_delay_severity`.
    4. Upserts a row in ``case_predictions``.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.
    predictor:
        Optional :class:`~app.ml.predict.CaseDurationPredictor` instance.
        If ``None``, the module singleton is used.
    threshold:
        Minimum delay ratio to include a case in the returned list.
        Defaults to the *moderate* threshold from settings.

    Returns
    -------
    list[dict]
        Summary dicts for each case that exceeded *threshold*.
    """
    from app.ml.dataset import build_inference_row
    from app.ml.predict import PREDICTION_UNAVAILABLE, get_predictor
    from app.models.entities import Case, CasePrediction

    if predictor is None:
        predictor = get_predictor()
    if threshold is None:
        threshold = _settings.ml_delay_threshold_moderate

    active_cases = (
        db.query(Case)
        .filter(
            Case.status != "disposed",
            Case.filing_date.isnot(None),
            Case.is_deleted.is_(False),
        )
        .all()
    )

    flagged: list[dict] = []
    today = date.today()

    for case in active_cases:
        row = build_inference_row(case, db)
        if row is None:
            continue

        result = predictor.predict(row)
        if result is PREDICTION_UNAVAILABLE or result.model_version == "unavailable":
            continue

        current_age = float((today - case.filing_date).days)
        delay_ratio = compute_delay_ratio(current_age, result.predicted_days)
        severity = classify_delay_severity(delay_ratio)

        # Upsert CasePrediction record
        existing: Optional[Any] = (
            db.query(CasePrediction)
            .filter(CasePrediction.case_id == case.id)
            .first()
        )
        pred_kwargs = {
            "case_id": case.id,
            "predicted_duration_days": result.predicted_days,
            "lower_bound_days": result.lower_bound,
            "upper_bound_days": result.upper_bound,
            "confidence_score": result.confidence,
            "delay_ratio": delay_ratio,
            "ml_delay_flag": severity is not None,
            "ml_delay_severity": severity,
            "ml_model_version": result.model_version,
            "feature_importance": {"top_features": result.top_features},
        }
        if existing:
            for attr, value in pred_kwargs.items():
                setattr(existing, attr, value)
        else:
            db.add(CasePrediction(**pred_kwargs))

        if delay_ratio >= threshold and severity is not None:
            flagged.append(
                {
                    "case_id": case.id,
                    "case_number": case.case_number,
                    "delay_ratio": delay_ratio,
                    "severity": severity,
                    "predicted_days": result.predicted_days,
                    "current_age_days": int(current_age),
                    "model_version": result.model_version,
                }
            )

    db.commit()
    logger.info(
        "ML delay scan: flagged %d / %d active cases as delayed",
        len(flagged),
        len(active_cases),
    )
    return flagged
